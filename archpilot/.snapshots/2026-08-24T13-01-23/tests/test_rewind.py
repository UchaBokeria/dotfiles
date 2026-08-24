"""Rewind, end to end through the daemon's own method.

Two things went wrong before, and neither shows up in a unit test of
`rewind_to` alone:
  - it called manager.new(), which APPENDS, so a second tab appeared beside the
    untouched conversation and rewinding looked like it had done nothing;
  - it kept the rewound message in the transcript, where Claude Code takes it
    out and puts the text back in the input, unsent.
"""

from __future__ import annotations

import asyncio

import pytest

from archpilot import daemon as daemon_module
from archpilot import ipc
from archpilot.daemon import Daemon
from archpilot.session import SessionManager


@pytest.fixture
def harness(monkeypatch):
    """A Daemon with just enough wired up to run rewind()."""
    monkeypatch.setattr(daemon_module.persist, "save", lambda *a, **k: None)
    d = Daemon.__new__(Daemon)
    d.manager = SessionManager({})
    d.draft = ""
    d.sent: list = []

    async def broadcast(msg):
        d.sent.append(msg)

    async def push_state():
        return None

    d.broadcast = broadcast
    d.push_state = push_state

    session = d.manager.new(mode="ask", model="haiku")
    for word in ("alpha", "beta", "gamma"):
        session.prompt = f"say {word}"
        session.finish_turn(word)
    return d


def test_rewind_does_not_open_a_second_tab(harness):
    assert len(harness.manager.tabs()) == 1
    asyncio.run(harness.rewind(1))
    assert len(harness.manager.tabs()) == 1


def test_rewind_removes_that_message_and_the_ones_after_it(harness):
    asyncio.run(harness.rewind(1))
    assert [t["prompt"] for t in harness.manager.current.turns] == ["say alpha"]


def test_the_rewound_text_is_handed_back_for_the_input(harness):
    asyncio.run(harness.rewind(1))
    restore = [m for m in harness.sent if m.get("ev") == ipc.EV_RESTORE_INPUT]
    assert restore and restore[0]["text"] == "say beta"
    assert harness.draft == "say beta"


def test_the_surviving_history_is_replayed_into_the_fresh_session(harness):
    asyncio.run(harness.rewind(1))
    replay = harness.manager.current.pending_replay
    assert "say alpha" in replay
    assert "say beta" not in replay, "the rewound turn must not be replayed"


def test_rewinding_the_first_message_leaves_nothing_to_replay(harness):
    """A preamble reading "earlier in this conversation" followed by nothing
    would be a lie to the model."""
    asyncio.run(harness.rewind(0))
    assert harness.manager.current.turns == []
    assert harness.manager.current.pending_replay == ""
    assert harness.draft == "say alpha"


def test_an_out_of_range_rewind_changes_nothing(harness):
    asyncio.run(harness.rewind(99))
    assert len(harness.manager.current.turns) == 3
    assert harness.sent == []
