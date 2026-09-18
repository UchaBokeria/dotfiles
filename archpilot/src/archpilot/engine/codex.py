"""Drive the Codex CLI, one `codex exec` process per turn.

Claude Code holds one child open across turns and is fed stream-json on stdin.
`codex exec` has no such mode: every turn is its own process, and continuity
comes from the thread id it announces first - the next turn runs
`codex exec resume <thread>` and Codex reloads the conversation from its own
rollout file. So `start()` here only means "attached". There is nothing to
spawn until there is something to say, and nothing running between turns is
the healthy state, not a dead engine.

Event shapes (codex-cli 0.154, `--json`). The first five were observed from a
real run on this machine; the item types are the documented set:
  thread.started   {thread_id}            - the id to resume with
  turn.started
  item.completed   {item: {type: error}}  - a NON-fatal notice (skills budget)
  error            {message}              - usually followed by turn.failed
  turn.failed      {error: {message}}
  item.started / item.updated / item.completed, item.type one of
      agent_message (text) · reasoning · command_execution (command) ·
      file_change (changes) · mcp_tool_call (server, tool) ·
      web_search (query) · todo_list
  turn.completed   {usage}                - the turn is over

Nothing here ever passes --dangerously-bypass-approvals-and-sandbox. On this
engine the sandbox is what makes ask mode safe; see modes.CODEX_SANDBOX.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import os
import shlex
import shutil
import tomllib
from collections import deque
from pathlib import Path
from typing import AsyncIterator, Callable

from .. import activity, modes
from .claude_code import STDERR_TAIL, STREAM_LIMIT, EngineEvent

#: Stripped from the child's environment so a stray export cannot move a
#: ChatGPT-subscription sign-in onto metered API billing - the same guard the
#: Claude engine applies to ANTHROPIC_API_KEY.
METERED_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY")

#: Item types that are the model doing something rather than saying something.
TOOL_ITEMS = ("command_execution", "file_change", "mcp_tool_call", "web_search",
              "todo_list", "reasoning")

_SHELLS = ("bash", "sh", "zsh", "fish", "dash")


def codex_home() -> Path:
    """Where Codex keeps its config, sign-in, model catalogue and rollouts."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


# -- Codex's own catalogue ----------------------------------------------------

def _catalogue(home: Path) -> list[dict]:
    try:
        data = json.loads((home / "models_cache.json").read_text())
    except (OSError, ValueError):
        return []
    models = data.get("models") if isinstance(data, dict) else data
    return [m for m in models or [] if isinstance(m, dict) and m.get("slug")]


def configured_model(home: Path | None = None) -> str:
    """The `model` in ~/.codex/config.toml, or "" if none is set."""
    try:
        with ((home or codex_home()) / "config.toml").open("rb") as handle:
            return str(tomllib.load(handle).get("model") or "")
    except (OSError, tomllib.TOMLDecodeError):
        return ""


@functools.lru_cache(maxsize=8)
def _available(home: str) -> tuple[str, ...]:
    path = Path(home)
    listed = [m["slug"] for m in _catalogue(path) if m.get("visibility", "list") == "list"]
    default = configured_model(path)
    if default:
        listed = [default] + [slug for slug in listed if slug != default]
    return tuple(listed) or ("default",)


def available_models(home: Path | None = None) -> tuple[str, ...]:
    """Models the signed-in account offers, the configured default first.

    Read from Codex's own catalogue (models_cache.json) so the chip cycles
    through exactly what `codex` itself would offer, rather than a list that
    goes stale here. "default" means "pass no -m and let codex decide". Cached
    for the daemon's life: the catalogue changes on the scale of releases, and
    this is asked on every state push.
    """
    return _available(str(home or codex_home()))


def _entry(model: str, home: Path) -> dict:
    slug = model if model and model != "default" else configured_model(home)
    return next((m for m in _catalogue(home) if m.get("slug") == slug), {})


def supported_efforts(model: str, home: Path | None = None) -> tuple[str, ...]:
    """Reasoning levels this model accepts, or () when the catalogue is silent."""
    levels = _entry(model, home or codex_home()).get("supported_reasoning_levels") or []
    out = []
    for level in levels:
        name = level.get("effort") if isinstance(level, dict) else level
        if isinstance(name, str):
            out.append(name)
    return tuple(out)


def context_window(model: str, home: Path | None = None) -> int:
    """Usable context for the model, as Codex itself budgets it."""
    entry = _entry(model, home or codex_home())
    window = int(entry.get("context_window") or 0)
    percent = int(entry.get("effective_context_window_percent") or 100)
    return window * percent // 100


def thread_exists(thread_id: str, home: Path | None = None) -> bool:
    """True when Codex still has the rollout a resume would reload."""
    if not thread_id:
        return False
    sessions = (home or codex_home()) / "sessions"
    return any(sessions.rglob(f"rollout-*-{thread_id}.jsonl"))


# -- turning items into activity lines ----------------------------------------

def _unwrap_shell(command) -> str:
    """`bash -lc 'rg foo'` -> `rg foo`.

    Codex runs most commands through a login shell, and "running bash" names
    the wrapper instead of the work.
    """
    if isinstance(command, list):
        parts = [str(part) for part in command]
    else:
        try:
            parts = shlex.split(str(command or ""))
        except ValueError:
            return str(command or "")
    if (len(parts) >= 3 and os.path.basename(parts[0]) in _SHELLS
            and parts[1].startswith("-") and "c" in parts[1]):
        return parts[2]
    return " ".join(parts)


def describe_item(item: dict) -> str:
    """A present-tense line for one Codex item, in the Claude engine's voice."""
    kind = item.get("type")
    if kind == "command_execution":
        return activity.describe("Bash", {"command": _unwrap_shell(item.get("command"))})
    if kind == "file_change":
        changes = item.get("changes") or []
        path = next((c.get("path") for c in changes
                     if isinstance(c, dict) and c.get("path")), "")
        return activity.describe("Edit", {"file_path": path}) if path else "editing files"
    if kind == "mcp_tool_call":
        return activity.describe(
            f"mcp__{item.get('server') or 'mcp'}__{item.get('tool') or 'tool'}")
    if kind == "web_search":
        return activity.describe("WebSearch", {"query": item.get("query")})
    if kind == "todo_list":
        return "updating the plan"
    if kind == "reasoning":
        return "thinking"
    return ""


class CodexEngine:
    """One Codex thread, driven a turn at a time.

    Same surface as ClaudeCodeEngine - start, send, events, cancel, stop,
    running, stderr_tail - so the daemon does not need to know which it holds.
    """

    def __init__(self, *, cwd: Path, mode: str, model: str = "",
                 effort: str | None = None, thread_id: str = "",
                 preamble: str = "", binary: str = "codex",
                 extra_env: dict[str, str] | None = None,
                 on_thread: Callable[[str], None] | None = None,
                 home: Path | None = None):
        self._cwd = cwd
        self._mode = mode
        self._model = model
        self._effort = effort
        self._thread_id = thread_id
        self._preamble = preamble
        self._binary = binary
        self._extra_env = extra_env or {}
        self._on_thread = on_thread
        self._home = home
        self._attached = False
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL)
        self._stderr_task: asyncio.Task | None = None

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def stderr_tail(self) -> str:
        return "\n".join(self._stderr)

    @property
    def running(self) -> bool:
        """Attached and not stopped - there is no long-lived child to ask."""
        return self._attached

    def argv(self) -> list[str]:
        home = self._home or codex_home()
        return modes.codex_argv(
            mode=self._mode, cwd=self._cwd, model=self._model, effort=self._effort,
            thread_id=self._thread_id, binary=self._binary,
            supported=supported_efforts(self._model, home))

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k not in METERED_ENV}
        env.update(self._extra_env)
        return env

    async def start(self) -> None:
        # Phrased so problems.classify() recognises it: a daemon that cannot
        # find `codex` should say so, not fail on the first prompt instead.
        if not shutil.which(self._binary, path=self._env().get("PATH")):
            raise RuntimeError(f"command not found: {self._binary}")
        self._attached = True

    async def send(self, text: str) -> None:
        if not self._attached:
            raise RuntimeError("engine is not running")
        await self._reap()

        prompt = text
        if not self._thread_id and self._preamble:
            # `codex exec` has no --append-system-prompt, so the standing
            # instructions ride in the first message of a thread, once. A
            # resumed thread already carries them in its history.
            prompt = f"<instructions>\n{self._preamble}\n</instructions>\n\n{text}"

        try:
            proc = await asyncio.create_subprocess_exec(
                *self.argv(),
                cwd=str(self._cwd),
                env=self._env(),
                limit=STREAM_LIMIT,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise RuntimeError(f"command not found: {self._binary} ({exc})") from exc
        self._proc = proc
        self._stderr.clear()
        self._stderr_task = asyncio.create_task(self._drain_stderr(proc))

        assert proc.stdin is not None
        proc.stdin.write(prompt.encode())
        # A child that dies at once (signed out, bad flag) closes its end
        # before we finish writing; events() reports why, so do not raise here.
        with contextlib.suppress(ConnectionError):
            await proc.stdin.drain()
        proc.stdin.close()

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
        """Keep reading stderr so the child never blocks on a full pipe."""
        if proc.stderr is None:
            return
        while True:
            try:
                line = await proc.stderr.readline()
            except (ValueError, asyncio.LimitOverrunError):
                continue
            if not line:
                return
            if text := line.decode("utf-8", "replace").rstrip():
                self._stderr.append(text)

    async def events(self) -> AsyncIterator[EngineEvent]:
        """Yield this turn's events. `result` or `error` ends the turn."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise RuntimeError("engine is not running")

        last_message = ""
        thread = ""
        failure = ""
        announced: set = set()
        while True:
            try:
                raw_line = await proc.stdout.readline()
            except ValueError:
                # Longer than STREAM_LIMIT. Losing one event beats wedging the
                # turn; unlike Claude's stream this is never the answer itself.
                continue
            if not raw_line:
                code = await self._exit_code(proc)
                await self._settle_stderr()
                if failure or code not in (0, None):
                    yield EngineEvent(
                        "error",
                        failure or self.stderr_tail or f"codex exited with status {code}",
                        {"returncode": code})
                else:
                    # A clean exit without turn.completed: what it did say is
                    # the answer, rather than an invented failure.
                    yield EngineEvent("result", last_message, {})
                return
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            kind = event.get("type")
            if kind == "thread.started":
                thread = str(event.get("thread_id") or "")
                yield EngineEvent("system", "", event)
            elif kind in ("item.started", "item.updated", "item.completed"):
                item = event.get("item") or {}
                item_type = item.get("type")
                if item_type == "agent_message":
                    if text := str(item.get("text") or ""):
                        last_message = text
                        yield EngineEvent("message", text, event)
                elif item_type in TOOL_ITEMS:
                    key = item.get("id") or json.dumps(item, sort_keys=True)
                    if key in announced:
                        continue
                    announced.add(key)
                    if described := describe_item(item):
                        yield EngineEvent("tool", described, event)
                # item.type == "error" is a notice, not a failure: the real
                # failures arrive as `error` + `turn.failed` below.
            elif kind == "turn.completed":
                self._adopt(thread)
                yield EngineEvent("result", last_message, self._result_raw(event))
                return
            elif kind == "turn.failed":
                message = (str((event.get("error") or {}).get("message") or "")
                           or failure or "Codex reported a failed turn.")
                yield EngineEvent("error", message, event)
                return
            elif kind == "error":
                failure = str(event.get("message") or "")

    def _adopt(self, thread: str) -> None:
        """Resume this thread from now on.

        Only once a turn has COMPLETED: a thread whose first turn failed never
        saw the standing instructions answered, so the next prompt starts a new
        one and sends them again rather than resuming a broken start.
        """
        if thread and thread != self._thread_id:
            self._thread_id = thread
            if self._on_thread is not None:
                self._on_thread(thread)

    def _result_raw(self, event: dict) -> dict:
        """Shape the result the way Session.record_usage reads Claude's."""
        usage = event.get("usage") or {}
        raw: dict = {"usage": {"input_tokens": int(usage.get("input_tokens") or 0)},
                     "codex": event}
        if window := context_window(self._model, self._home or codex_home()):
            raw["modelUsage"] = {self._model or "default": {"contextWindow": window}}
        return raw

    async def _settle_stderr(self) -> None:
        """Let the stderr reader catch the last lines of a child that just
        exited - the reason for a crash is always in them."""
        task = self._stderr_task
        if task is not None and not task.done():
            await asyncio.wait({task}, timeout=0.5)

    @staticmethod
    async def _exit_code(proc) -> int | None:
        await asyncio.sleep(0)
        if proc.returncode is not None:
            return proc.returncode
        try:
            return await asyncio.wait_for(proc.wait(), timeout=2)
        except (asyncio.TimeoutError, ProcessLookupError):
            return proc.returncode

    async def _reap(self, grace: float = 2.0) -> None:
        """Make sure no earlier turn's process outlives its turn.

        The daemon stops reading at `result` and Codex exits a moment later on
        its own, so this normally just collects it. Only a turn abandoned
        mid-flight is forced.
        """
        proc, self._proc = self._proc, None
        task, self._stderr_task = self._stderr_task, None
        if proc is not None and proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=grace)
            except (asyncio.TimeoutError, ProcessLookupError):
                with contextlib.suppress(ProcessLookupError, OSError):
                    proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except (asyncio.TimeoutError, ProcessLookupError):
                    with contextlib.suppress(ProcessLookupError, OSError):
                        proc.kill()
        if task is not None:
            task.cancel()

    async def cancel(self) -> None:
        """Stop a turn NOW - signal first, the same as the Claude engine."""
        proc = self._proc
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=0.7)
            except (asyncio.TimeoutError, ProcessLookupError):
                with contextlib.suppress(ProcessLookupError, OSError):
                    proc.kill()
        await self.stop()

    async def stop(self) -> None:
        # Stopping means the turn is being abandoned (switch, rewind, close),
        # so there is no grace period to wait out.
        self._attached = False
        await self._reap(grace=0)
