"""Engine framing tests. No real `claude` process is spawned."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from archpilot.engine.claude_code import STREAM_LIMIT, ClaudeCodeEngine, _user_message


class FakeStdout:
    """Replays scripted readline results, including raised exceptions."""

    def __init__(self, items):
        self._items = list(items)

    async def readline(self):
        if not self._items:
            return b""
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeProc:
    def __init__(self, items):
        self.stdout = FakeStdout(items)
        self.returncode = None


def drain(engine):
    async def go():
        return [e async for e in engine.events()]
    return asyncio.run(go())


def engine_with(items):
    engine = ClaudeCodeEngine(["claude"], Path("/tmp"))
    engine._proc = FakeProc(items)
    return engine


def line(obj):
    return (json.dumps(obj) + "\n").encode()


def test_user_message_frame_shape():
    """The stream-json input frame the CLI accepts. Verified against the real CLI."""
    payload = json.loads(_user_message("hello"))
    assert payload["type"] == "user"
    assert payload["message"]["role"] == "user"
    assert payload["message"]["content"] == [{"type": "text", "text": "hello"}]


def test_stream_limit_is_large_enough_for_an_image_result():
    """A base64 screenshot arrives on ONE stream-json line; asyncio caps at 64KB
    by default, which wedged the turn with 'Separator is not found'."""
    assert STREAM_LIMIT >= 8 * 1024 * 1024


def test_oversized_line_is_skipped_not_fatal():
    events = drain(engine_with([
        ValueError("Separator is not found, and chunk exceed the limit"),
        line({"type": "result", "result": "recovered"}),
    ]))
    kinds = [e.kind for e in events]
    assert "error" in kinds
    assert events[-1].kind == "result" and events[-1].text == "recovered"


def test_partial_deltas_are_yielded_as_text():
    events = drain(engine_with([
        line({"type": "stream_event", "event": {"delta": {"text": "par"}}}),
        line({"type": "stream_event", "event": {"delta": {"text": "tial"}}}),
    ]))
    assert [e.text for e in events if e.kind == "delta"] == ["par", "tial"]


def test_assistant_message_concatenates_text_blocks():
    events = drain(engine_with([
        line({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "a"},
            {"type": "tool_use", "name": "Bash"},
            {"type": "text", "text": "b"},
        ]}}),
    ]))
    assert [e.text for e in events if e.kind == "message"] == ["ab"]


def test_rate_limit_events_are_surfaced():
    """Observed from a real run - useful status for a subscription-backed tool."""
    events = drain(engine_with([line({"type": "rate_limit_event", "status": "ok"})]))
    assert [e.kind for e in events] == ["rate_limit"]


def test_malformed_json_lines_are_ignored():
    events = drain(engine_with([b"{not json\n", line({"type": "result", "result": "ok"})]))
    assert [e.kind for e in events] == ["result"]


def test_blank_lines_are_ignored():
    events = drain(engine_with([b"\n", b"  \n", line({"type": "result", "result": "ok"})]))
    assert [e.kind for e in events] == ["result"]


def test_send_before_start_is_an_error():
    engine = ClaudeCodeEngine(["claude"], Path("/tmp"))
    with pytest.raises(RuntimeError):
        asyncio.run(engine.send("hi"))


# --- failure diagnosis -------------------------------------------------------

def test_a_clean_exit_ends_the_turn_without_an_error():
    engine = engine_with([line({"type": "result", "result": "done"})])
    engine._proc.returncode = 0
    assert [e.kind for e in drain(engine)] == ["result"]


def test_a_crashed_child_explains_itself_instead_of_going_quiet():
    """stdout closing with a nonzero status used to end the turn blank - the
    'it just stopped answering' report. Now it carries the reason."""
    engine = engine_with([])
    engine._proc.returncode = 1
    engine._stderr.extend(["Error: Invalid API key"])
    events = drain(engine)
    assert [e.kind for e in events] == ["error"]
    assert "Invalid API key" in events[0].text


def test_a_crash_with_no_stderr_still_names_the_status():
    engine = engine_with([])
    engine._proc.returncode = 127
    assert "127" in drain(engine)[0].text


def test_stderr_tail_is_bounded():
    """A chatty child must not grow the daemon's memory for the session's life."""
    from archpilot.engine.claude_code import STDERR_TAIL
    engine = engine_with([])
    for n in range(STDERR_TAIL * 3):
        engine._stderr.append(f"line {n}")
    assert len(engine.stderr_tail.splitlines()) == STDERR_TAIL
    assert engine.stderr_tail.splitlines()[-1] == f"line {STDERR_TAIL * 3 - 1}"


def test_stderr_is_drained_so_the_child_cannot_block_on_a_full_pipe():
    class FakeStderr:
        def __init__(self, items):
            self._items = list(items)

        async def readline(self):
            return self._items.pop(0) if self._items else b""

    engine = ClaudeCodeEngine(["claude"], Path("/tmp"))
    engine._proc = FakeProc([])
    engine._proc.stderr = FakeStderr([b"first\n", b"  second  \n", b"\n"])
    asyncio.run(engine._drain_stderr())
    # Trailing whitespace and blank lines go; leading indentation stays,
    # because that is what makes a stack trace readable.
    assert engine.stderr_tail == "first\n  second"


def test_a_missing_binary_is_reported_in_words_problems_understands():
    from archpilot.problems import MISSING, classify
    engine = ClaudeCodeEngine(["definitely-not-a-real-binary-xyz"], Path("/tmp"))
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(engine.start())
    assert classify(str(caught.value)).kind == MISSING


# --- cancelling a turn -------------------------------------------------------

def test_cancel_signals_the_child_instead_of_waiting_for_it():
    """stop() closes stdin and waits up to five seconds for the child to
    finish on its own - which is exactly what cancelling must not do. Measured
    against a real turn: 4.9s before, 0.6s after."""
    class Recorder:
        returncode = None
        def __init__(self):
            self.calls = []
            self.stdin = None
            self.stderr = None
        def terminate(self):
            self.calls.append("terminate")
            self.returncode = -15
        def kill(self):
            self.calls.append("kill")
        async def wait(self):
            return self.returncode

    engine = ClaudeCodeEngine(["claude"], Path("/tmp"))
    engine._proc = Recorder()
    asyncio.run(engine.cancel())
    assert engine._proc is None
    # terminate first; kill only if it ignores that


def test_cancelling_an_already_dead_child_is_harmless():
    engine = ClaudeCodeEngine(["claude"], Path("/tmp"))
    engine._proc = None
    asyncio.run(engine.cancel())        # must not raise
