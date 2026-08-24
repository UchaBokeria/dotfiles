"""Opening a past chat from history must really open it.

The old behaviour pasted the matched prompt into whatever conversation you were
already in and left the answers behind - which is not opening it at all.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from archpilot import daemon as daemon_module
from archpilot.context import history
from archpilot.daemon import Daemon
from archpilot.session import IDLE, SessionManager


def write_transcript(root, session_id: str, exchanges, cwd="/tmp/project"):
    project = root / "project-slug"
    project.mkdir(parents=True, exist_ok=True)
    path = project / f"{session_id}.jsonl"
    lines = []
    for prompt, answer in exchanges:
        lines.append(json.dumps({
            "type": "user", "cwd": cwd,
            "message": {"content": [{"type": "text", "text": prompt}]}}))
        lines.append(json.dumps({
            "type": "assistant", "cwd": cwd,
            "message": {"content": [{"type": "text", "text": answer}]}}))
    path.write_text("\n".join(lines))
    return path


def test_conversation_rebuilds_exchanges_in_order(tmp_path):
    write_transcript(tmp_path, "abc123",
                     [("first question", "first answer"),
                      ("second question", "second answer")])
    turns, cwd = history.conversation("abc123", root=tmp_path)
    assert [t["prompt"] for t in turns] == ["first question", "second question"]
    assert [t["answer"] for t in turns] == ["first answer", "second answer"]
    assert cwd == "/tmp/project"


def test_an_unanswered_last_prompt_is_not_a_turn(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    (project / "solo.jsonl").write_text(json.dumps(
        {"type": "user", "message": {"content": [{"type": "text", "text": "hello"}]}}))
    turns, _ = history.conversation("solo", root=tmp_path)
    assert turns == []


def test_an_unknown_session_is_not_an_error(tmp_path):
    assert history.conversation("nope", root=tmp_path) == ([], "")


@pytest.fixture
def harness(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon_module.persist, "save", lambda *a, **k: None)
    monkeypatch.setattr(daemon_module, "_ui_open", lambda *a, **k: None)
    write_transcript(tmp_path, "past01", [("what failed?", "bluetooth did")])
    # daemon_module.history_ctx IS this module, so grab the real function
    # before patching or the replacement calls itself forever.
    real = history.conversation
    monkeypatch.setattr(history, "conversation",
                        lambda sid, **kw: real(sid, root=tmp_path))

    d = Daemon.__new__(Daemon)
    d.manager = SessionManager({})
    d.cfg = daemon_module.config.load()

    async def push_state():
        return None

    d.push_state = push_state
    return d


def test_opening_a_past_chat_loads_its_exchanges(harness):
    harness.manager.new(mode="ask", model="haiku")
    asyncio.run(harness.open_session("past01"))
    current = harness.manager.current
    assert current.id == "past01", "must attach to the SAME claude session id"
    assert current.restored is True, "so the engine resumes instead of starting fresh"
    assert [t["prompt"] for t in current.turns] == ["what failed?"]


def test_an_untouched_blank_tab_is_reused_rather_than_stacked(harness):
    harness.manager.new(mode="ask", model="haiku")
    asyncio.run(harness.open_session("past01"))
    assert len(harness.manager.tabs()) == 1


def test_a_conversation_in_progress_gets_its_own_tab(harness):
    busy = harness.manager.new(mode="ask", model="haiku")
    busy.prompt = "mid conversation"
    busy.finish_turn("an answer")
    asyncio.run(harness.open_session("past01"))
    assert len(harness.manager.tabs()) == 2
    assert harness.manager.current.id == "past01"


def test_reopening_an_empty_restored_session_still_fills_in_history(harness):
    """A session restored from disk can be an id and nothing else. Focusing it
    without loading the transcript showed a blank chat - the bug that made this
    look broken even after the feature existed."""
    from archpilot.session import Session
    shell = Session.create(mode="ask", model="haiku")
    shell.id = "past01"
    harness.manager.sessions["past01"] = shell
    harness.manager.order.append("past01")
    harness.manager.current = shell

    asyncio.run(harness.open_session("past01"))
    assert [t["prompt"] for t in harness.manager.current.turns] == ["what failed?"]


def test_opening_nothing_is_ignored(harness):
    harness.manager.new(mode="ask", model="haiku")
    asyncio.run(harness.open_session(""))
    assert harness.manager.current.turns == []
