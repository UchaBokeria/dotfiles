"""Regression tests for hunt-round fixes (2026-09-24).

Each test pins a bug found live or by adversarial reading, so it cannot
silently regress. Named by finding ID from .remember/tmp/live-test-notes.md.
"""

import json

from archpilot import ipc, persist
from archpilot.context import relevance
from archpilot.daemon import split_directives
from archpilot.markup import wrap_plain
from archpilot.ui import theme as ui_theme


def test_u23_prompts_keep_newlines_without_directives():
    text = "line one\n  indented two\n```\ncode\n```"
    out, model, mode = split_directives(text)
    assert out == text and model is None and mode is None
    out2, wanted = relevance.split_directives(text)
    assert out2 == text and wanted == set()


def test_u23_directives_still_strip():
    out, model, mode = split_directives(":sonnet hello")
    assert (out, model, mode) == ("hello", "sonnet", None)
    out2, wanted = relevance.split_directives(":term hello")
    assert (out2, wanted) == ("hello", {"terminal"})


def test_h4_wrap_plain_never_hangs():
    assert wrap_plain("hello world", 0) == "hello world"
    assert wrap_plain("hello world", -3) == "hello world"


def test_u33_alpha_accepts_shorthand():
    assert ui_theme._alpha("#ABC", 100) == "rgba(170,187,204,1.00)"


def test_d2_read_lines_skips_non_objects():
    import asyncio

    async def feed():
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"op": "x"}\n')
        reader.feed_data(b'[1,2]\n')
        reader.feed_data(b'42\n')
        reader.feed_data(b'not json\n')
        reader.feed_eof()
        return [msg async for msg in ipc.read_lines(reader)]

    out = asyncio.run(feed())
    assert out == [{"op": "x"}]


def test_h8_persist_is_atomic_and_validated(tmp_path, monkeypatch):
    import archpilot.paths as paths

    monkeypatch.setattr(paths, "state_dir", lambda: tmp_path)
    assert persist.load() is None
    (tmp_path / "last-session.json").write_text("[1,2]")
    assert persist.load() is None
    (tmp_path / "last-session.json").write_text(
        json.dumps({"id": "", "cwd": "", "mode": "evil", "model": "x"}))
    assert persist.load() is None


def test_u46_tabs_round_trip(tmp_path, monkeypatch):
    import archpilot.paths as paths
    from archpilot.session import SessionManager

    monkeypatch.setattr(paths, "state_dir", lambda: tmp_path)
    from pathlib import Path

    mgr = SessionManager({})
    a = mgr.new(mode="ask", model="haiku", cwd=Path("/tmp"))
    b = mgr.new(mode="action", model="sonnet", cwd=Path("/tmp"))
    # Validation needs transcripts: fake them where the slug points.
    for session in (a, b):
        transcript = session.transcript
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("{}\n")
    persist.save(b, mgr)
    back = persist.load_all()
    assert [s.id for s in back] == [b.id, a.id]


def test_ipc_decode_may_return_non_dict():
    assert ipc.decode(b"[1]") == [1]
    assert ipc.decode('{"a": 1}') == {"a": 1}
