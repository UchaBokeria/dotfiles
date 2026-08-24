import json

import pytest

from archpilot import paths, persist
from archpilot.session import Session


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "last_session_file", lambda: tmp_path / "last-session.json")
    return tmp_path / "last-session.json"


def session_with_transcript(tmp_path, monkeypatch, session_id="11111111-2222-3333-4444-555555555555"):
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "claude_project_dir", lambda cwd: project)
    (project / f"{session_id}.jsonl").write_text("{}\n")
    return Session(id=session_id, cwd=tmp_path, mode="ask", model="opus")


def test_round_trip_restores_the_pointer(state, tmp_path, monkeypatch):
    original = session_with_transcript(tmp_path, monkeypatch)
    persist.save(original)

    restored = persist.load()
    assert restored is not None
    assert restored.id == original.id
    assert restored.mode == "ask" and restored.model == "opus"
    assert restored.restored is True, "must re-attach with --resume, not claim a new id"


def test_nothing_saved_yet(state):
    assert persist.load() is None


def test_corrupt_state_file_is_not_fatal(state):
    state.write_text("{not json")
    assert persist.load() is None


def test_incomplete_state_file_is_rejected(state):
    state.write_text(json.dumps({"id": "abc"}))
    assert persist.load() is None


def test_pointer_to_a_missing_transcript_is_discarded(state, tmp_path, monkeypatch):
    """--resume would fail on the next prompt, so a dangling pointer is worse
    than none at all."""
    session = session_with_transcript(tmp_path, monkeypatch)
    persist.save(session)
    session.transcript.unlink()
    assert persist.load() is None


def test_saving_none_clears_the_pointer(state, tmp_path, monkeypatch):
    persist.save(session_with_transcript(tmp_path, monkeypatch))
    assert state.exists()
    persist.save(None)
    assert not state.exists()
