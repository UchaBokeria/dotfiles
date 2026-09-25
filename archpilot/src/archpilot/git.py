"""Auto-commit what an action turn changed, so `archpilot undo` is real.

The safety story for "confirm irreversible only" rests on edits under the
dotfiles repo being revertable. That is only true if they are actually
committed.

Critically, this commits ONLY paths that changed during the turn. The repo
routinely has unrelated work in progress, and sweeping that into an
"archpilot:" commit would make `archpilot undo` revert the user's own edits.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .paths import DOTFILES


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(cwd or DOTFILES), *args],
                          capture_output=True, text=True, check=False)


def dirty_paths(repo: Path | None = None) -> set[str]:
    """Paths git currently reports as changed, staged or not.

    `-uall` is load-bearing: without it git collapses an untracked directory
    into a single entry, so creating a file inside an already-untracked tree
    changes nothing in the output and the auto-commit silently finds no work.

    H1: staged renames (`R  new\\0old\\0`) carry the OLD path as a bare second
    record with no `XY ` prefix. Slicing it at [3:] mangled the name, the
    follow-on `git add` failed, and the whole turn went uncommitted. Both
    sides are recorded now.
    """
    out = _git("status", "--porcelain", "-uall", "-z", cwd=repo)
    if out.returncode != 0:
        return set()
    paths = set()
    records = out.stdout.split("\0")
    index = 0
    while index < len(records):
        entry = records[index]
        index += 1
        if len(entry) <= 3:
            continue
        status, path = entry[:2], entry[3:]
        paths.add(path)
        if status[0] == "R" or status[1] == "R":
            # The old path follows as its own NUL-terminated record.
            if index < len(records) and records[index]:
                paths.add(records[index])
                index += 1
    return paths


def commit_changes(before: set[str], summary: str, repo: Path | None = None) -> str | None:
    """Commit paths that became dirty since `before`. Returns the sha, if any.

    H1 (cont.): on commit failure the index used to stay staged, and the next
    turn's `before` snapshot already contained those paths — so they were
    never committed, never undone, invisible to the undo stack. The index is
    reset on failure now. Detached HEAD is refused: committing there dangles
    where no branch sees it while `undo` still reports success.
    """
    changed = dirty_paths(repo) - before
    if not changed:
        return None

    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=repo)
    if branch.returncode != 0:
        return None

    add = _git("add", "--", *sorted(changed), cwd=repo)
    if add.returncode != 0:
        _git("reset", "-q", cwd=repo)
        return None

    message = f"archpilot: {summary.strip()[:72]}"
    commit = _git("commit", "--no-verify", "-m", message, "--only", "--",
                  *sorted(changed), cwd=repo)
    if commit.returncode != 0:
        _git("reset", "-q", cwd=repo)
        return None
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip() or None
