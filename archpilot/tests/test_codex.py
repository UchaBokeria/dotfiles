"""The Codex engine, and switching a conversation between Claude and Codex.

No real `codex` runs here. A stand-in script on disk prints canned JSONL and
records how it was invoked, so the argv, the stdin framing and the event
parsing are all exercised through a real subprocess. The signed-out case is
the exact failure codex produced on this machine when the engine was built.
"""

from __future__ import annotations

import asyncio
import copy
import json
import time
from pathlib import Path

import pytest

from archpilot import commands, config, modes, paths, persist, problems
from archpilot import daemon as daemon_module
from archpilot.daemon import Daemon
from archpilot.engine import codex as codex_engine
from archpilot.engine.codex import CodexEngine, describe_item
from archpilot.problems import AUTH, MISSING
from archpilot.session import Session, SessionManager, replay_text

CWD = Path("/tmp/archpilot-codex-test")
SIGNED_OUT = "Your access token could not be refreshed. Please log out and sign in again."


# -- argv ----------------------------------------------------------------------

def test_a_new_thread_is_sandboxed_by_mode():
    ask = modes.codex_argv(mode=modes.ASK, cwd=CWD)
    assert ask[:2] == ["codex", "exec"]
    assert ask[ask.index("--sandbox") + 1] == "read-only"
    assert ask[ask.index("-C") + 1] == str(CWD)

    action = modes.codex_argv(mode=modes.ACTION, cwd=CWD)
    assert action[action.index("--sandbox") + 1] == "workspace-write"


def test_nothing_ever_bypasses_the_sandbox():
    for mode in modes.MODES:
        for thread in ("", "t-1"):
            argv = modes.codex_argv(mode=mode, cwd=CWD, thread_id=thread,
                                    model="gpt-x", effort="max")
            assert not any("dangerously" in part for part in argv), argv


def test_events_stream_as_json_and_the_prompt_comes_from_stdin():
    argv = modes.codex_argv(mode=modes.ASK, cwd=CWD)
    assert "--json" in argv and "--skip-git-repo-check" in argv
    assert argv[-1] == "-"


def test_resume_carries_the_sandbox_as_a_config_override():
    """`codex exec resume` rejects --sandbox and -C, so neither may appear."""
    argv = modes.codex_argv(mode=modes.ASK, cwd=CWD, thread_id="t-1")
    assert argv[:3] == ["codex", "exec", "resume"]
    assert "--sandbox" not in argv and "-C" not in argv
    assert 'sandbox_mode="read-only"' in argv
    assert argv[-2:] == ["t-1", "-"]

    action = modes.codex_argv(mode=modes.ACTION, cwd=CWD, thread_id="t-1")
    assert 'sandbox_mode="workspace-write"' in action


def test_model_flag_only_for_a_real_model_name():
    argv = modes.codex_argv(mode=modes.ASK, cwd=CWD, model="gpt-5.5")
    assert argv[argv.index("-m") + 1] == "gpt-5.5"
    assert "-m" not in modes.codex_argv(mode=modes.ASK, cwd=CWD, model="default")
    assert "-m" not in modes.codex_argv(mode=modes.ASK, cwd=CWD)


def test_effort_is_passed_and_clamped_to_what_the_model_supports():
    full = ("low", "medium", "high", "xhigh", "max")
    argv = modes.codex_argv(mode=modes.ASK, cwd=CWD, effort="high", supported=full)
    assert 'model_reasoning_effort="high"' in argv

    assert modes.codex_effort("max", full) == "max"
    assert modes.codex_effort("max", ("low", "medium", "high", "xhigh")) == "xhigh"
    assert modes.codex_effort("max") == "xhigh", "unknown model: the common set"
    assert modes.codex_effort("xhigh", ("low", "medium")) == "medium"
    with pytest.raises(ValueError):
        modes.codex_effort("ludicrous")


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        modes.codex_argv(mode="yolo", cwd=CWD)


def test_the_claude_argv_is_unchanged():
    """Adding an engine must not move a single Claude flag."""
    prompt = "M\n\n" + modes.SYSTEM_PROMPT_SUFFIX
    tail = ["--setting-sources", "", "--strict-mcp-config", "--mcp-config",
            '{"mcpServers":{}}']
    head = ["--input-format", "stream-json", "--output-format", "stream-json",
            "--include-partial-messages", "--verbose",
            "--append-system-prompt", prompt, "--settings", "/tmp/s.json",
            "--effort", "high"]

    ask = modes.build_argv(mode="ask", session_id="S", model="opus",
                           settings_file=Path("/tmp/s.json"), effort="high", machine="M")
    assert ask == (["claude", "-p", "--model", "opus", "--session-id", "S"] + head + tail
                   + ["--permission-mode", "manual",
                      "--disallowedTools", "Write", "Edit", "NotebookEdit"])

    action = modes.build_argv(mode="action", session_id="S", model="opus",
                              settings_file=Path("/tmp/s.json"), resume=True,
                              effort="high", machine="M")
    assert action == (["claude", "-p", "--model", "opus", "--resume", "S"] + head + tail
                      + ["--permission-mode", "acceptEdits"])


# -- Codex's catalogue -----------------------------------------------------------

@pytest.fixture
def home(tmp_path):
    root = tmp_path / "codex-home"
    root.mkdir()
    levels = lambda *names: [{"effort": n, "description": n} for n in names]  # noqa: E731
    (root / "models_cache.json").write_text(json.dumps({"models": [
        {"slug": "gpt-a", "visibility": "list",
         "supported_reasoning_levels": levels("low", "medium", "high", "xhigh", "max"),
         "context_window": 200000, "effective_context_window_percent": 95},
        {"slug": "gpt-b", "visibility": "list",
         "supported_reasoning_levels": levels("low", "medium", "high", "xhigh")},
        {"slug": "internal-review", "visibility": "hide"},
    ]}))
    (root / "config.toml").write_text('model = "gpt-b"\n')
    return root


def test_available_models_come_from_codexs_own_catalogue(home):
    assert codex_engine.available_models(home) == ("gpt-b", "gpt-a"), \
        "configured default first, hidden models left out"


def test_without_a_catalogue_the_configured_model_or_default(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    assert codex_engine.available_models(bare) == ("default",), "no -m at all"

    configured = tmp_path / "configured"
    configured.mkdir()
    (configured / "config.toml").write_text('model = "gpt-z"\n')
    assert codex_engine.available_models(configured) == ("gpt-z",)


def test_supported_efforts_and_context_window(home):
    assert codex_engine.supported_efforts("gpt-b", home) == ("low", "medium", "high", "xhigh")
    assert codex_engine.supported_efforts("default", home) == ("low", "medium", "high", "xhigh")
    assert codex_engine.supported_efforts("nope", home) == ()
    assert codex_engine.context_window("gpt-a", home) == 190000


def test_thread_exists_looks_for_the_rollout(home):
    day = home / "sessions" / "2026" / "09" / "12"
    day.mkdir(parents=True)
    (day / "rollout-2026-09-12T10-00-00-t-live.jsonl").write_text("{}\n")
    assert codex_engine.thread_exists("t-live", home)
    assert not codex_engine.thread_exists("t-gone", home)
    assert not codex_engine.thread_exists("", home)


# -- describing activity -------------------------------------------------------

def test_items_read_like_the_claude_engines_activity_lines():
    assert describe_item({"type": "command_execution",
                          "command": "bash -lc 'rg --files src'"}) == "running rg"
    assert describe_item({"type": "command_execution",
                          "command": ["/bin/zsh", "-c", "ls -la"]}) == "running ls"
    assert describe_item({"type": "file_change",
                          "changes": [{"path": "/a/b/notes.md", "kind": "update"}]}) \
        == "editing notes.md"
    assert describe_item({"type": "mcp_tool_call", "server": "chrome",
                          "tool": "take_screenshot"}) == "chrome: take screenshot"
    assert describe_item({"type": "web_search", "query": "hyprland"}) \
        == "searching the web for hyprland"
    assert describe_item({"type": "todo_list"}) == "updating the plan"
    assert describe_item({"type": "reasoning"}) == "thinking"
    assert describe_item({"type": "agent_message"}) == ""


# -- event parsing, with scripted stdout ----------------------------------------

class FakeStdout:
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
    def __init__(self, items, returncode=0):
        self.stdout = FakeStdout(items)
        self.returncode = returncode

    async def wait(self):
        return self.returncode


def line(obj):
    return (json.dumps(obj) + "\n").encode()


def scripted(items, returncode=0, **kw):
    engine = CodexEngine(cwd=CWD, mode=modes.ASK, **kw)
    engine._proc = FakeProc(items, returncode)
    return engine


def drain(engine):
    async def go():
        return [e async for e in engine.events()]
    return asyncio.run(go())


def test_a_notice_item_is_not_a_failure():
    """The skills-budget warning arrives as an item of type error."""
    events = drain(scripted([
        line({"type": "item.completed",
              "item": {"id": "i0", "type": "error", "message": "Skill descriptions were shortened"}}),
        line({"type": "item.completed", "item": {"id": "i1", "type": "agent_message", "text": "ok"}}),
        line({"type": "turn.completed", "usage": {}}),
    ]))
    assert [e.kind for e in events] == ["message", "result"]
    assert events[-1].text == "ok"


def test_a_repeated_item_is_announced_once():
    todo = {"id": "t", "type": "todo_list", "items": []}
    events = drain(scripted([
        line({"type": "item.started", "item": todo}),
        line({"type": "item.updated", "item": todo}),
        line({"type": "item.completed", "item": todo}),
        line({"type": "turn.completed"}),
    ]))
    assert [e.kind for e in events] == ["tool", "result"]


def test_the_last_agent_message_is_the_answer():
    events = drain(scripted([
        line({"type": "item.completed", "item": {"id": "a", "type": "agent_message",
                                                  "text": "Let me check."}}),
        line({"type": "item.completed", "item": {"id": "b", "type": "agent_message",
                                                  "text": "It is 42."}}),
        line({"type": "turn.completed"}),
    ]))
    assert events[-1].kind == "result" and events[-1].text == "It is 42."


def test_malformed_and_oversized_lines_are_skipped():
    events = drain(scripted([
        b"{not json\n",
        ValueError("Separator is not found, and chunk exceed the limit"),
        b"\n",
        line({"type": "turn.completed"}),
    ]))
    assert [e.kind for e in events] == ["result"]


def test_a_clean_exit_without_turn_completed_still_ends_the_turn():
    events = drain(scripted([
        line({"type": "item.completed", "item": {"id": "a", "type": "agent_message",
                                                  "text": "partial"}}),
    ]))
    assert events[-1].kind == "result" and events[-1].text == "partial"


def test_an_error_line_then_a_silent_death_reports_the_error():
    events = drain(scripted([line({"type": "error", "message": SIGNED_OUT})], returncode=1))
    assert events[-1].kind == "error" and events[-1].text == SIGNED_OUT


def test_a_crash_with_no_output_names_the_status():
    events = drain(scripted([], returncode=101))
    assert events[-1].kind == "error" and "101" in events[-1].text


def test_the_thread_is_adopted_only_when_a_turn_completes():
    seen = []
    failed = scripted([line({"type": "thread.started", "thread_id": "t-bad"}),
                       line({"type": "turn.failed", "error": {"message": SIGNED_OUT}})],
                      on_thread=seen.append)
    drain(failed)
    assert failed.thread_id == "" and seen == []

    ok = scripted([line({"type": "thread.started", "thread_id": "t-good"}),
                   line({"type": "turn.completed"})], on_thread=seen.append)
    drain(ok)
    assert ok.thread_id == "t-good" and seen == ["t-good"]


def test_send_before_start_is_an_error():
    engine = CodexEngine(cwd=CWD, mode=modes.ASK)
    with pytest.raises(RuntimeError):
        asyncio.run(engine.send("hi"))


def test_a_missing_binary_is_named_and_recognised():
    engine = CodexEngine(cwd=CWD, mode=modes.ASK, binary="/nonexistent/codex")
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(engine.start())
    problem = problems.classify(str(caught.value))
    assert problem.kind == MISSING and problem.command == "which codex"


# -- through a real subprocess -----------------------------------------------------

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys, time
prompt = sys.stdin.read()
with open(os.environ["FAKE_CODEX_LOG"], "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "stdin": prompt, "cwd": os.getcwd(),
                          "openai": os.environ.get("OPENAI_API_KEY")}) + "\n")
script = os.environ.get("FAKE_CODEX_SCRIPT", "ok")
def emit(obj):
    print(json.dumps(obj), flush=True)
if script == "ok":
    emit({"type": "thread.started", "thread_id": "thread-1"})
    emit({"type": "turn.started"})
    emit({"type": "item.completed", "item": {"id": "i0", "type": "error",
          "message": "Skill descriptions were shortened to fit"}})
    emit({"type": "item.started", "item": {"id": "i1", "type": "command_execution",
          "command": "bash -lc 'rg --files'"}})
    emit({"type": "item.completed", "item": {"id": "i1", "type": "command_execution",
          "command": "bash -lc 'rg --files'", "exit_code": 0}})
    emit({"type": "item.completed", "item": {"id": "i2", "type": "agent_message",
          "text": "pong"}})
    emit({"type": "turn.completed", "usage": {"input_tokens": 1200,
          "cached_input_tokens": 1000, "output_tokens": 5}})
elif script == "signed_out":
    msg = "Your access token could not be refreshed. Please log out and sign in again."
    emit({"type": "thread.started", "thread_id": "thread-x"})
    emit({"type": "turn.started"})
    emit({"type": "error", "message": msg})
    emit({"type": "turn.failed", "error": {"message": msg}})
elif script == "crash":
    print("fatal: the thing broke", file=sys.stderr, flush=True)
    sys.exit(3)
elif script == "hang":
    emit({"type": "thread.started", "thread_id": "thread-h"})
    time.sleep(30)
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    binary = tmp_path / "bin" / "codex"
    binary.parent.mkdir()
    binary.write_text(FAKE_CODEX)
    binary.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-reach-codex")
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


def test_a_turn_through_a_real_process(fake, home):
    binary, work, calls = fake
    threads = []
    engine = CodexEngine(cwd=work, mode=modes.ASK, model="gpt-a", effort="max",
                         preamble="STANDING RULES", binary=str(binary), home=home,
                         on_thread=threads.append)
    (events,) = run_turns(engine, "ping")

    kinds = [e.kind for e in events]
    assert "error" not in kinds
    assert [e.text for e in events if e.kind == "tool"] == ["running rg"]
    assert events[-1].kind == "result" and events[-1].text == "pong"
    assert engine.thread_id == "thread-1" and threads == ["thread-1"]

    (call,) = calls()
    argv = call["argv"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[argv.index("-C") + 1] == str(work)
    assert argv[argv.index("-m") + 1] == "gpt-a"
    assert 'model_reasoning_effort="max"' in argv
    assert call["stdin"].startswith("<instructions>\nSTANDING RULES")
    assert call["stdin"].endswith("ping")
    assert call["cwd"] == str(work)
    assert call["openai"] is None, "a stray OPENAI_API_KEY must not reach codex"


def test_the_second_turn_resumes_the_thread_without_the_preamble(fake, home):
    binary, work, calls = fake
    engine = CodexEngine(cwd=work, mode=modes.ACTION, model="gpt-b", effort="max",
                         preamble="STANDING RULES", binary=str(binary), home=home)
    run_turns(engine, "first", "second")

    first, second = calls()
    assert first["argv"][:1] == ["exec"] and "resume" not in first["argv"]
    assert second["argv"][:2] == ["exec", "resume"]
    assert second["argv"][-2:] == ["thread-1", "-"]
    assert 'sandbox_mode="workspace-write"' in second["argv"]
    assert 'model_reasoning_effort="xhigh"' in second["argv"], "gpt-b stops at xhigh"
    assert second["stdin"] == "second", "instructions ride only in a thread's first message"


def test_the_result_feeds_the_context_meter(fake, home):
    binary, work, _calls = fake
    engine = CodexEngine(cwd=work, mode=modes.ASK, model="gpt-a",
                         binary=str(binary), home=home)
    (events,) = run_turns(engine, "ping")
    session = Session.create(mode="ask", model="gpt-a", engine_name="codex")
    session.record_usage(events[-1].raw)
    assert session.context_used == 1200
    assert session.context_total == 190000


def test_the_signed_out_failure_is_an_auth_problem_with_its_fix(fake, home, monkeypatch):
    binary, work, _calls = fake
    monkeypatch.setenv("FAKE_CODEX_SCRIPT", "signed_out")
    engine = CodexEngine(cwd=work, mode=modes.ASK, binary=str(binary), home=home)
    (events,) = run_turns(engine, "ping")
    assert events[-1].kind == "error" and events[-1].text == SIGNED_OUT
    assert engine.thread_id == "", "a thread whose first turn failed is not resumed"
    problem = problems.classify(events[-1].text)
    assert problem.kind == AUTH and problem.command == "codex login"


def test_a_crash_explains_itself(fake, home, monkeypatch):
    binary, work, _calls = fake
    monkeypatch.setenv("FAKE_CODEX_SCRIPT", "crash")
    engine = CodexEngine(cwd=work, mode=modes.ASK, binary=str(binary), home=home)
    (events,) = run_turns(engine, "ping")
    assert events[-1].kind == "error"
    assert "the thing broke" in events[-1].text


def test_cancel_stops_a_turn_at_once(fake, home, monkeypatch):
    binary, work, _calls = fake
    monkeypatch.setenv("FAKE_CODEX_SCRIPT", "hang")
    engine = CodexEngine(cwd=work, mode=modes.ASK, binary=str(binary), home=home)

    async def go():
        await engine.start()
        await engine.send("ping")
        proc = engine._proc
        await asyncio.sleep(0.3)
        started = time.monotonic()
        await engine.cancel()
        return proc, time.monotonic() - started

    proc, took = asyncio.run(go())
    assert proc.returncode is not None, "the child must be gone"
    assert took < 3
    assert engine.running is False


# -- problems -------------------------------------------------------------------

def test_codex_sign_in_failure_is_not_mistaken_for_claude():
    """The same failure also carries a 401, which the Claude rule would claim."""
    problem = problems.classify(SIGNED_OUT, "HTTP error: 401 Unauthorized")
    assert problem.kind == AUTH
    assert problem.command == "codex login"
    assert "Codex" in problem.title


def test_claude_problems_still_point_at_claude():
    assert problems.classify("Invalid API key · Please run /login").command == "claude /login"
    assert problems.classify("command not found: claude").command == "which claude"


# -- the `:` command line --------------------------------------------------------

def test_engine_command():
    assert commands.parse("engine codex").args == {"field": "engine", "value": "codex"}
    assert commands.parse("engine claude").kind == "set"
    assert "usage:" in commands.parse("engine").message
    assert "unknown engine" in commands.parse("engine gemini").message
    assert commands.resolve("eng") == "engine"
    assert commands.resolve("e") == "effort", "the existing alias is untouched"


def test_model_command_takes_the_active_engines_names():
    codex_models = ("gpt-a", "gpt-b")
    assert commands.parse("model gpt-b", models=codex_models).args["value"] == "gpt-b"
    assert commands.parse("model opus", models=codex_models).failed
    assert commands.parse("model opus").args["value"] == "opus", "Claude by default"


def test_the_engine_key_is_documented():
    rows = [key for _group, entries in commands.KEYBINDINGS for key, _ in entries]
    assert "ctrl+alt+tab" in rows


# -- the session ----------------------------------------------------------------

def test_codex_resume_hint_and_snapshot():
    session = Session.create(mode="ask", model="gpt-a", engine_name="codex")
    assert session.resume_hint == f"cd {session.cwd} && codex"
    session.codex_thread = "t-9"
    assert session.resume_hint == f"cd {session.cwd} && codex resume t-9"
    assert session.snapshot()["engine"] == "codex"
    assert Session.create(mode="ask", model="opus").snapshot()["engine"] == "claude"


def test_each_turn_records_which_engine_answered():
    session = Session.create(mode="ask", model="opus")
    session.prompt = "one"
    session.finish_turn("a")
    session.engine_name = "codex"
    session.prompt = "two"
    session.finish_turn("b")
    assert [t["engine"] for t in session.turns] == ["claude", "codex"]


def test_replay_text_is_bounded_and_honest():
    turns = [{"prompt": f"p{i}", "answer": "x" * 50} for i in range(10)]
    text = replay_text(turns, limit=3, clip=10)
    assert "p9" in text and "p7" in text and "p6" not in text
    assert "x" * 11 not in text
    assert replay_text([]) == ""


def test_persisting_a_codex_conversation(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "last_session_file", lambda: tmp_path / "last.json")
    monkeypatch.setattr(codex_engine, "thread_exists", lambda thread, home=None: thread == "t-1")
    session = Session.create(mode="action", model="gpt-a", effort="max", engine_name="codex")
    session.codex_thread = "t-1"
    persist.save(session)

    back = persist.load()
    assert back is not None
    assert (back.engine_name, back.codex_thread, back.model) == ("codex", "t-1", "gpt-a")

    session.codex_thread = "t-gone"
    persist.save(session)
    assert persist.load() is None, "a pointer to a vanished thread is worse than none"


def test_an_old_pointer_without_an_engine_is_claude(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(paths, "last_session_file", lambda: tmp_path / "last.json")
    monkeypatch.setattr(paths, "claude_project_dir", lambda cwd: project)
    (project / "abc.jsonl").write_text("{}\n")
    (tmp_path / "last.json").write_text(json.dumps(
        {"id": "abc", "cwd": str(tmp_path), "mode": "ask", "model": "opus"}))
    back = persist.load()
    assert back is not None and back.engine_name == "claude"


# -- switching engines in the daemon ----------------------------------------------

class FakeEngine:
    def __init__(self):
        self.stopped = False
        self.running = True

    async def stop(self):
        self.stopped = True


@pytest.fixture
def harness(monkeypatch, tmp_path):
    """A Daemon with just enough wired up to run apply_setting()."""
    saved = []
    monkeypatch.setattr(daemon_module.persist, "save", lambda s: saved.append(s))
    monkeypatch.setattr(paths, "claude_project_dir", lambda cwd: tmp_path / "claude")
    monkeypatch.setattr(codex_engine, "thread_exists", lambda thread, home=None: bool(thread))
    d = Daemon.__new__(Daemon)
    d.cfg = config.Config(config._merge(copy.deepcopy(config.DEFAULTS),
                                        {"codex": {"models": ["gpt-a", "gpt-b"]}}))
    d.manager = SessionManager({})
    d.draft = ""
    d.attachments = []
    d.saved = saved

    async def push_state():
        return None

    d.push_state = push_state
    return d


def with_turns(session, *pairs):
    for engine, prompt in pairs:
        session.engine_name = engine
        session.prompt = prompt
        session.finish_turn(f"answer to {prompt}")
    return session


def test_switching_to_codex_keeps_the_tab_and_resets_the_model(harness):
    session = with_turns(harness.manager.new(mode="ask", model="haiku"),
                         ("claude", "first"), ("claude", "second"))
    running = FakeEngine()
    session.engine = running

    assert asyncio.run(harness.apply_setting("engine", None, True)) == "codex"
    assert session.engine_name == "codex"
    assert session.model == "gpt-a", "haiku means nothing to Codex"
    assert running.stopped and session.engine is None
    assert len(harness.manager.tabs()) == 1 and harness.manager.current is session
    assert [t["prompt"] for t in session.turns] == ["first", "second"]
    assert "first" in session.pending_replay and "second" in session.pending_replay
    assert harness.cfg.default_engine == "codex", "a new chat starts where you left off"
    assert harness.saved[-1] is session


def test_switching_back_replays_only_what_claude_missed(harness, tmp_path):
    session = with_turns(harness.manager.new(mode="ask", model="haiku"),
                         ("claude", "asked claude"), ("codex", "asked codex"))
    session.engine_name = "codex"
    session.model = "gpt-a"
    session.transcript.parent.mkdir(parents=True, exist_ok=True)
    session.transcript.write_text("{}\n")

    assert asyncio.run(harness.apply_setting("engine", "claude", False)) == "claude"
    assert session.model == "haiku"
    assert session.restored is True, "Claude resumes its own transcript"
    assert "asked codex" in session.pending_replay
    assert "asked claude" not in session.pending_replay, "Claude already has that one"


def test_a_chat_that_began_on_codex_starts_claude_fresh(harness):
    session = harness.manager.new(mode="ask", model="gpt-a", engine_name="codex")
    with_turns(session, ("codex", "only codex saw this"))
    session.engine_name = "codex"

    asyncio.run(harness.apply_setting("engine", "claude", False))
    assert session.restored is False, "no transcript, so no --resume"
    assert "only codex saw this" in session.pending_replay


def test_codex_resumes_its_thread_and_gets_only_what_it_missed(harness):
    session = harness.manager.new(mode="ask", model="haiku")
    with_turns(session, ("codex", "old codex turn"), ("claude", "newer claude turn"))
    session.engine_name = "claude"
    session.codex_thread = "t-1"

    asyncio.run(harness.apply_setting("engine", "codex", False))
    assert session.codex_thread == "t-1"
    assert "newer claude turn" in session.pending_replay
    assert "old codex turn" not in session.pending_replay


def test_an_unknown_engine_is_refused(harness):
    harness.manager.new(mode="ask", model="haiku")
    assert asyncio.run(harness.apply_setting("engine", "gemini", False)) is None
    assert harness.manager.current.engine_name == "claude"


def test_switching_with_no_conversation_changes_where_the_next_one_starts(harness):
    assert harness.manager.current is None
    assert asyncio.run(harness.apply_setting("engine", None, True)) == "codex"
    assert harness.cfg.default_engine == "codex"
    assert harness._default_model("codex") == "gpt-a"
    assert harness.cfg.default_model == "haiku", "Claude's default is untouched"


def test_the_model_cycle_is_per_engine(harness):
    session = harness.manager.new(mode="ask", model="gpt-a", engine_name="codex")
    assert asyncio.run(harness.apply_setting("model", None, True)) == "gpt-b"
    assert asyncio.run(harness.apply_setting("model", "opus", False)) is None
    assert session.model == "gpt-b"


def test_a_codex_model_never_becomes_claudes_default(harness):
    harness.cfg.data["engine"]["default"] = "codex"
    assert asyncio.run(harness.apply_setting("model", "gpt-b", False)) == "gpt-b"
    assert harness.cfg.default_model == "haiku"
    assert harness._default_model("codex") == "gpt-b"


def test_claude_model_switching_is_unchanged(harness):
    session = harness.manager.new(mode="ask", model="haiku")
    session.engine = FakeEngine()
    assert asyncio.run(harness.apply_setting("model", None, True)) == "sonnet"
    assert session.restored is True and session.engine is None
    assert session.engine_name == "claude"


def test_a_claude_model_directive_on_codex_moves_the_prompt_to_claude(harness):
    codex = harness.manager.new(mode="ask", model="gpt-a", engine_name="codex")
    ran = []

    async def run_turn(session, text, explicit=None):
        ran.append((session, text))

    harness.run_turn = run_turn

    async def go():
        await harness._on_prompt({"text": "plain question"})
        await harness._on_prompt({"text": ":opus harder question"})
        await asyncio.sleep(0)

    asyncio.run(go())
    (first, _), (second, text) = ran
    assert first is codex, "a plain prompt stays on the codex conversation"
    assert second.engine_name == "claude" and second.model == "opus"
    assert text == "harder question"
