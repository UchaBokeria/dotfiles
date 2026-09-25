"""The opencode engine: argv, event parsing, session adoption, failures.

No real `opencode` runs here. A stand-in script prints the JSONL shapes the
real CLI emitted during the 2026-09-24 probe (opencode 1.18.32) and records
how it was invoked. The bad-model and bad-session shapes are the exact
failures observed live (both with EXIT=0 — detect via events, not codes).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from archpilot import modes
from archpilot.engine.opencode import OpencodeEngine
from archpilot.problems import MODEL, MISSING, classify
from archpilot.session import Session

CWD = Path("/tmp/archpilot-opencode-test")

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys
prompt = sys.argv[-1]
with open(os.environ["FAKE_OPENCODE_LOG"], "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:-1], "message": prompt,
                          "cwd": os.getcwd()}) + "\n")
script = os.environ.get("FAKE_OPENCODE_SCRIPT", "ok")
SID = "ses_f2f50dff0ffeL6vTHWjN1wzguB"
def emit(obj):
    print(json.dumps(obj), flush=True)
if script == "ok":
    emit({"type": "step_start", "timestamp": 1, "sessionID": SID,
          "part": {"type": "step-start"}})
    emit({"type": "text", "timestamp": 2, "sessionID": SID,
          "part": {"type": "text", "text": "Listing engine files."}})
    emit({"type": "tool", "timestamp": 3, "sessionID": SID,
          "part": {"type": "tool", "tool": "read", "callID": "call-1",
                   "state": {"status": "completed",
                             "input": {"filePath": "engine/"}}}})
    emit({"type": "step_finish", "timestamp": 4, "sessionID": SID,
          "part": {"type": "step-finish", "reason": "tool-calls"}})
    emit({"type": "step_start", "timestamp": 5, "sessionID": SID,
          "part": {"type": "step-start"}})
    emit({"type": "text", "timestamp": 6, "sessionID": SID,
          "part": {"type": "text", "text": "done"}})
    emit({"type": "step_finish", "timestamp": 7, "sessionID": SID,
          "part": {"type": "step-finish", "reason": "stop",
                   "tokens": {"total": 100, "input": 90, "output": 10,
                              "reasoning": 5, "cache": {"write": 0, "read": 3}}}})
elif script == "bad_model":
    emit({"type": "error", "timestamp": 1, "sessionID": "ses_x",
          "error": {"name": "UnknownError",
                    "data": {"message": "Unexpected server error."}}})
elif script == "bad_session":
    print("Error: Session not found", file=sys.stderr, flush=True)
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    binary = tmp_path / "bin" / "opencode"
    binary.parent.mkdir()
    binary.write_text(FAKE_OPENCODE)
    binary.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_OPENCODE_LOG", str(log))
    work = tmp_path / "work"
    work.mkdir()

    def calls():
        return [json.loads(row) for row in log.read_text().splitlines()] if log.exists() else []

    return binary, work, calls


def run_turns(engine, *prompts):
    async def go():
        await engine.start()
        results = []
        for prompt in prompts:
            await engine.send(prompt)
            results.append([e async for e in engine.events()])
        await engine.stop()
        return results
    return asyncio.run(go())


# -- argv ----------------------------------------------------------------------

def test_new_session_uses_json_format_and_agent():
    # Probed 2026-09-25: `-` stdin form hangs with --dir; bare run rejects
    # --dir/--variant. Message goes positional, cwd via process cwd.
    argv = modes.opencode_argv(mode=modes.ASK, cwd=CWD)
    assert argv[:2] == ["opencode", "run"]
    assert "--format" in argv and argv[argv.index("--format") + 1] == "json"
    assert "--dir" not in argv and "-" not in argv
    assert argv[argv.index("--agent") + 1] == "plan"


def test_action_uses_build_agent_and_never_auto():
    argv = modes.opencode_argv(mode=modes.ACTION, cwd=CWD)
    assert argv[argv.index("--agent") + 1] == "build"
    assert "--auto" not in argv


def test_resume_passes_session_id():
    argv = modes.opencode_argv(mode=modes.ASK, cwd=CWD, session_id="ses_abc")
    assert "-s" in argv and argv[argv.index("-s") + 1] == "ses_abc"


def test_model_passes_through_and_variant_is_dropped():
    # --variant is listed in `run --help` but rejected at runtime
    # ("Unrecognized flag", probed 2026-09-25) — never emit it.
    argv = modes.opencode_argv(mode=modes.ASK, cwd=CWD, model="m/x",
                               effort="max")
    assert argv[argv.index("-m") + 1] == "m/x"
    assert "--variant" not in argv


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        modes.opencode_argv(mode="evil", cwd=CWD)


# -- turns ---------------------------------------------------------------------

def test_a_turn_through_a_real_process(fake):
    binary, work, calls = fake
    adopted = []
    engine = OpencodeEngine(cwd=work, mode=modes.ASK, model="m/x",
                            preamble="STANDING RULES", binary=str(binary),
                            on_session=adopted.append)
    (events,) = run_turns(engine, "ping")

    kinds = [e.kind for e in events]
    assert "tool" in kinds and events[-1].kind == "result"
    assert events[-1].text == "Listing engine files.done"
    assert adopted == ["ses_f2f50dff0ffeL6vTHWjN1wzguB"]

    (call,) = calls()
    assert call["argv"][:2] == ["run", "--format"]
    assert "<instructions>" in call["message"] and "STANDING RULES" in call["message"]

    session = Session.create(mode="ask", model="m/x", engine_name="opencode")
    session.record_usage(events[-1].raw)
    # input 90 + cache.read 3; no contextWindow from opencode, so no total.
    assert session.context_used == 93
    assert session.context_total == 0  # opencode reports no contextWindow


def test_resume_sends_session_id_and_no_preamble(fake):
    binary, work, calls = fake
    engine = OpencodeEngine(cwd=work, mode=modes.ASK,
                            session_id="ses_f2f50dff0ffeL6vTHWjN1wzguB",
                            preamble="STANDING RULES", binary=str(binary))
    run_turns(engine, "second")
    (call,) = calls()
    assert call["argv"][call["argv"].index("-s") + 1] == "ses_f2f50dff0ffeL6vTHWjN1wzguB"
    assert "<instructions>" not in call["message"]


def test_bad_model_is_an_error_event(fake, monkeypatch):
    binary, work, _calls = fake
    monkeypatch.setenv("FAKE_OPENCODE_SCRIPT", "bad_model")
    engine = OpencodeEngine(cwd=work, mode=modes.ASK, binary=str(binary))
    (events,) = run_turns(engine, "ping")
    assert events[-1].kind == "error"
    problem = classify(events[-1].text)
    assert problem is not None and problem.kind == MODEL


def test_bad_session_id_is_an_error_event(fake, monkeypatch):
    binary, work, _calls = fake
    monkeypatch.setenv("FAKE_OPENCODE_SCRIPT", "bad_session")
    engine = OpencodeEngine(cwd=work, mode=modes.ASK,
                            session_id="ses_nope", binary=str(binary))
    (events,) = run_turns(engine, "ping")
    assert events[-1].kind == "error"
    assert "not found" in events[-1].text.lower()
    problem = classify(events[-1].text)
    assert problem is not None and problem.kind == MISSING


def test_engine_is_in_the_cycle():
    assert "opencode" in modes.ENGINE_CYCLE
    assert modes.cycle(modes.ENGINE_CYCLE, "codex") == "opencode"
