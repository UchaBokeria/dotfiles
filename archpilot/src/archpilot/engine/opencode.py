"""Drive the opencode CLI, one `opencode run` process per turn.

Same shape as Codex: every turn is its own process, continuity comes from
the session id opencode announces on the first event. `start()` only means
"attached"; nothing runs between turns.

Event shapes (opencode 1.18.32, `--format json`), recorded from live runs
2026-09-24, not assumed:
  step_start     {part.type: step-start}            - a step begins
  text           {part.type: text, part.text}       - answer text
  tool           {part.type: tool, tool, callID,    - a tool call
                  state.status/input/output}
  step_finish    {part.type: step-finish,           - step over; reason
                  reason: stop|tool-calls,           `tool-calls` between
                  part.tokens {total,input,output,   steps, `stop` at end
                  reasoning,cache}, cost}
  error          {error.name/data}                  - failure (EXIT stays 0!)

Resume: `opencode run -s <sessionID>` re-enters the session (verified: same
sessionID comes back). Bad session id prints `Error: Session not found` on
stderr, EXIT=0 — parse output, not the exit code.

Safety: opencode tools do NOT pass through ArchPilot's PreToolUse hook, and
there is no --sandbox equivalent. NEVER pass --auto (the bypass-flag
equivalent). Ask mode runs the read-only `plan` agent; action mode runs the
default agent and relies on opencode's own permission config — see
SAFETY.md note in modes.opencode_argv. Fail closed whatever is chosen.

Billing: opencode on Meta keys is METERED (MODEL_API_KEY* fish universals).
That deliberately departs from the never-metered rule — nothing is stripped
here, by decision, not by accident.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
from collections import deque
from pathlib import Path
from typing import AsyncIterator, Callable

from .. import activity, modes
from .claude_code import STDERR_TAIL, STREAM_LIMIT, EngineEvent


def session_exists(session_id: str, binary: str = "opencode",
                   cwd: Path | None = None) -> bool:
    """True when a resume probe finds the session.

    opencode stores sessions server-side; there is no rollout file to stat.
    A cheap probe (`run -s <id>` with an empty prompt is NOT cheap — it runs
    a turn), so callers should use this sparingly (startup validation only).
    Currently: trust non-empty ids; the turn itself reports "not found".
    """
    return bool(session_id)


class OpencodeEngine:
    """One opencode session, driven a turn at a time.

    Same surface as ClaudeCodeEngine/CodexEngine — start, send, events,
    cancel, stop, running, stderr_tail — so the daemon never knows which it
    holds.
    """

    def __init__(self, *, cwd: Path, mode: str, model: str = "",
                 effort: str | None = None, session_id: str = "",
                 preamble: str = "", binary: str = "opencode",
                 extra_env: dict[str, str] | None = None,
                 on_session: Callable[[str], None] | None = None):
        self._cwd = cwd
        self._mode = mode
        self._model = model
        self._effort = effort
        self._session_id = session_id
        self._preamble = preamble
        self._binary = binary
        self._extra_env = extra_env or {}
        self._on_session = on_session
        self._attached = False
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL)
        self._stderr_task: asyncio.Task | None = None

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def stderr_tail(self) -> str:
        return "\n".join(self._stderr)

    @property
    def running(self) -> bool:
        """Attached and not stopped — no long-lived child between turns."""
        return self._attached

    def argv(self) -> list[str]:
        return modes.opencode_argv(
            mode=self._mode, cwd=self._cwd, model=self._model,
            effort=self._effort, session_id=self._session_id,
            binary=self._binary)

    def _env(self) -> dict[str, str]:
        # Billing decision: metered Meta keys are left in place deliberately.
        # Stripping them would break the engine; see module docstring.
        env = dict(os.environ)
        env.update(self._extra_env)
        return env

    async def start(self) -> None:
        if not shutil.which(self._binary, path=self._env().get("PATH")):
            raise RuntimeError(f"command not found: {self._binary}")
        self._attached = True

    async def send(self, text: str) -> None:
        if not self._attached:
            raise RuntimeError("engine is not running")
        await self._reap()

        prompt = text
        if not self._session_id and self._preamble:
            # No --append-system-prompt: instructions ride the first message
            # of a session, once. Resumed sessions carry them in history.
            prompt = f"<instructions>\n{self._preamble}\n</instructions>\n\n{text}"

        argv = [*self.argv(), prompt]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self._cwd),
                env=self._env(),
                limit=STREAM_LIMIT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise RuntimeError(f"command not found: {self._binary} ({exc})") from exc
        self._proc = proc
        self._stderr.clear()
        self._stderr_task = asyncio.create_task(self._drain_stderr(proc))

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
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

        chunks: list[str] = []
        announced: set = set()
        while True:
            try:
                raw_line = await proc.stdout.readline()
            except (ValueError, asyncio.LimitOverrunError):
                continue
            if not raw_line:
                code = await self._exit_code(proc)
                await self._settle_stderr()
                tail = self.stderr_tail
                if "Session not found" in tail:
                    yield EngineEvent("error", "opencode session not found", {})
                    return
                if code not in (0, None):
                    yield EngineEvent(
                        "error",
                        tail or f"opencode exited with status {code}",
                        {"returncode": code})
                    return
                # Clean exit with no step_finish: what it said is the answer.
                yield EngineEvent("result", "".join(chunks), {})
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
            part = event.get("part") or {}
            if kind == "step_start":
                if sid := event.get("sessionID"):
                    self._adopt(str(sid))
                yield EngineEvent("system", "", event)
            elif kind == "text":
                if text := part.get("text"):
                    chunks.append(str(text))
                    yield EngineEvent("delta", str(text), event)
            elif kind == "tool" or part.get("type") == "tool":
                key = part.get("callID") or json.dumps(part, sort_keys=True)
                if key in announced:
                    continue
                announced.add(key)
                if described := self._describe_tool(part):
                    yield EngineEvent("tool", described, event)
            elif kind == "step_finish":
                reason = part.get("reason") or ""
                if reason == "tool-calls":
                    continue  # more steps coming; not the end of the turn
                self._adopt(str(event.get("sessionID") or self._session_id))
                yield EngineEvent("result", "".join(chunks),
                                  self._result_raw(event))
                return
            elif kind == "error":
                err = event.get("error") or {}
                message = str(err.get("data", {}).get("message")
                              if isinstance(err.get("data"), dict)
                              else err.get("message") or "opencode reported an error")
                yield EngineEvent("error", message, event)
                return

    @staticmethod
    def _describe_tool(part: dict) -> str:
        """A present-tense line for one opencode tool call."""
        tool = str(part.get("tool") or "")
        state = part.get("state") or {}
        action = state.get("input") or {}
        if tool in ("bash", "execute", "shell"):
            return activity.describe("Bash", {"command": action.get("command")})
        if tool in ("read", "write", "edit"):
            verb = {"read": "Read", "write": "Write"}.get(tool, "Edit")
            return activity.describe(
                verb, {"file_path": action.get("filePath") or action.get("path")})
        if tool in ("grep", "glob", "search"):
            return activity.describe("Grep", {"pattern": action.get("pattern")})
        if tool.startswith("mcp__"):
            return activity.describe(tool)
        return activity.describe(tool or "tool")

    def _adopt(self, session_id: str) -> None:
        """Resume this session from now on (adopted from first event)."""
        if session_id and session_id != self._session_id:
            self._session_id = session_id
            if self._on_session is not None:
                self._on_session(session_id)

    def _result_raw(self, event: dict) -> dict:
        """Shape the result the way Session.record_usage reads Claude's.

        opencode reports no contextWindow — the ctx meter falls back to
        tokens-so-far with no total (context_total stays 0, label hidden).
        """
        part = event.get("part") or {}
        tokens = part.get("tokens") or {}
        raw: dict = {"usage": {
            "input_tokens": _int(tokens.get("input")),
            "cache_read_input_tokens": _int((tokens.get("cache") or {}).get("read")),
            "output_tokens": _int(tokens.get("output")),
        }, "opencode": event}
        return raw

    async def _settle_stderr(self) -> None:
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
        self._attached = False
        await self._reap(grace=0)


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
