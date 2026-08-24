import subprocess
from pathlib import Path

import pytest

from archpilot.git import commit_changes, dirty_paths


def run(*args, cwd):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    run("init", "-q", "-b", "main", cwd=tmp_path)
    run("config", "user.email", "t@example.com", cwd=tmp_path)
    run("config", "user.name", "t", cwd=tmp_path)
    (tmp_path / "tracked.txt").write_text("original\n")
    run("add", "-A", cwd=tmp_path)
    run("commit", "-q", "-m", "init", cwd=tmp_path)
    return tmp_path


def log(repo):
    return subprocess.run(["git", "-C", str(repo), "log", "--format=%s"],
                          capture_output=True, text=True, check=True).stdout.split("\n")


def test_nothing_changed_means_no_commit(repo):
    assert commit_changes(dirty_paths(repo), "noop", repo=repo) is None


def test_commits_a_new_change(repo):
    before = dirty_paths(repo)
    (repo / "tracked.txt").write_text("edited\n")
    sha = commit_changes(before, "edit the file", repo=repo)
    assert sha
    assert log(repo)[0] == "archpilot: edit the file"


def test_preexisting_work_in_progress_is_left_alone(repo):
    """The repo usually has unrelated edits; undo must not revert the user's work."""
    (repo / "tracked.txt").write_text("user's own uncommitted work\n")
    before = dirty_paths(repo)

    (repo / "new.txt").write_text("archpilot made this\n")
    sha = commit_changes(before, "add new file", repo=repo)
    assert sha

    # The user's edit is still uncommitted, and not part of the commit.
    assert (repo / "tracked.txt").read_text() == "user's own uncommitted work\n"
    files = subprocess.run(["git", "-C", str(repo), "show", "--name-only", "--format=", sha],
                           capture_output=True, text=True, check=True).stdout.split()
    assert files == ["new.txt"]


def test_commit_message_is_bounded(repo):
    before = dirty_paths(repo)
    (repo / "tracked.txt").write_text("x\n")
    sha = commit_changes(before, "y" * 300, repo=repo)
    assert sha
    assert len(log(repo)[0]) <= len("archpilot: ") + 72


def test_files_inside_an_untracked_directory_are_seen(repo):
    """git collapses untracked dirs by default, which made auto-commit a no-op
    for anything created inside an already-untracked tree."""
    (repo / "newdir").mkdir()
    (repo / "newdir" / "a.txt").write_text("a\n")
    before = dirty_paths(repo)
    assert "newdir/a.txt" in before

    (repo / "newdir" / "b.txt").write_text("b\n")
    sha = commit_changes(before, "add b", repo=repo)
    assert sha, "a file added inside an untracked directory must be committed"

    files = subprocess.run(["git", "-C", str(repo), "show", "--name-only", "--format=", sha],
                           capture_output=True, text=True, check=True).stdout.split()
    assert files == ["newdir/b.txt"], "and only that file"
