import json
import os
import time

import pytest

from archpilot.context import sessions


def write_transcript(root, project, session_id, entries, age_s=0):
    d = root / project
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{session_id}.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    if age_s:
        stamp = time.time() - age_s
        os.utime(p, (stamp, stamp))
    return p


def entry(**kw):
    base = {"type": "assistant", "cwd": "/home/u/dev", "gitBranch": "main", "slug": "my-task"}
    base.update(kw)
    return base


def todo_entry(done, total):
    todos = [{"status": "completed" if i < done else "pending", "content": f"t{i}"}
             for i in range(total)]
    return {"type": "assistant", "slug": "my-task",
            "message": {"content": [{"type": "tool_use", "name": "TodoWrite",
                                     "input": {"todos": todos}}]}}


def test_reads_slug_cwd_and_branch(tmp_path):
    p = write_transcript(tmp_path, "-home-u-dev", "abc", [entry()])
    info = sessions.read(p)
    assert info.slug == "my-task" and info.git_branch == "main"
    assert info.title == "my-task"


def test_title_falls_back_to_id_when_slug_missing(tmp_path):
    p = write_transcript(tmp_path, "-p", "abcdef1234567890", [entry(slug="")])
    assert sessions.read(p).title == "abcdef12"


@pytest.mark.parametrize("age,expected", [(5, "working"), (300, "quiet"), (4000, "finished")])
def test_state_is_derived_from_recency(tmp_path, age, expected):
    p = write_transcript(tmp_path, "-p", "abc", [entry()], age_s=age)
    assert sessions.read(p).state == expected


def test_todo_progress_uses_the_latest_todowrite(tmp_path):
    p = write_transcript(tmp_path, "-p", "abc", [todo_entry(1, 7), todo_entry(4, 7)])
    info = sessions.read(p)
    assert (info.todos_done, info.todos_total) == (4, 7)
    assert info.progress == "4/7 tasks"


def test_no_todos_means_no_progress_string(tmp_path):
    p = write_transcript(tmp_path, "-p", "abc", [entry()])
    assert sessions.read(p).progress == ""


def test_large_transcript_is_tail_read_not_fully_parsed(tmp_path):
    """Transcripts reach megabytes; the indexer must stay cheap."""
    filler = [entry(slug="old") for _ in range(4000)]
    p = write_transcript(tmp_path, "-p", "abc", filler + [entry(slug="newest")])
    assert p.stat().st_size > sessions.TAIL_BYTES
    assert sessions.read(p).slug == "newest"


def test_corrupt_lines_are_skipped(tmp_path):
    d = tmp_path / "-p"
    d.mkdir(parents=True)
    p = d / "abc.jsonl"
    p.write_text('{"broken\n' + json.dumps(entry()) + "\n")
    assert sessions.read(p).slug == "my-task"


def test_empty_transcript_yields_nothing(tmp_path):
    d = tmp_path / "-p"
    d.mkdir(parents=True)
    p = d / "abc.jsonl"
    p.write_text("")
    assert sessions.read(p) is None


def test_index_orders_by_recency(tmp_path):
    write_transcript(tmp_path, "-p", "old", [entry(slug="old")], age_s=5000)
    write_transcript(tmp_path, "-p", "new", [entry(slug="new")], age_s=1)
    assert [s.slug for s in sessions.index(root=tmp_path)] == ["new", "old"]


def test_summarize_excludes_finished_sessions(tmp_path):
    write_transcript(tmp_path, "-p", "done", [entry(slug="done")], age_s=99999)
    write_transcript(tmp_path, "-p", "live", [entry(slug="live")], age_s=2)
    text = sessions.summarize(root=tmp_path)
    assert "live" in text and "done" not in text


def test_summarize_with_no_sessions_is_explicit(tmp_path):
    assert "No Claude Code sessions" in sessions.summarize(root=tmp_path)


def test_missing_root_is_not_fatal(tmp_path):
    assert sessions.index(root=tmp_path / "nope") == []
