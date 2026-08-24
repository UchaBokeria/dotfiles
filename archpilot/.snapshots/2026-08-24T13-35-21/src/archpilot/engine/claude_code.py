"""Drive one long-lived `claude -p` child over stream-json.

Holding stdin open across turns is not just convenient - it is cheaper. A fresh
`claude -p` per question re-sends the whole system prompt and tool schemas every
time; a held-open child gets prompt-cache hits on that prefix instead.

Event shapes below were observed from a real run, not assumed:
  system            - init/meta
  stream_event      - partial deltas (needs --include-partial-messages)
  assistant         - a complete assistant message
  rate_limit_event  - subscription rate-limit status (surfaced in the widget)
  (an assistant message carrying tool_use also yields a `tool` event)
  result            - the turn is over
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator


@dataclass(frozen=True)
class EngineEvent:
    kind: str           # delta | message | tool | result | rate_limit | system | error
    text: str = ""
    raw: dict | None = None


#: asyncio's StreamReader caps a single line at 64KB by default, and stream-json
#: puts an entire message on one line. A screenshot read comes back as base64 and
#: blows straight past that, raising "Separator is not found, and chunk exceed the
#: limit" and wedging the turn. Large file reads and long command output do the
#: same. 32MB comfortably covers an image tool_result.
STREAM_LIMIT = 32 * 1024 * 1024

#: How many stderr lines to keep. The cause of a failed start is always in
#: the last few; keeping more just holds memory for a session's whole life.
STDERR_TAIL = 40


def _user_message(text: str) -> bytes:
    """stream-json input frame. Verified shape."""
    payload = {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }
    return (json.dumps(payload) + "\n").encode()


class ClaudeCodeEngine:
    def __init__(self, argv: list[str], cwd: Path, extra_env: dict[str, str] | None = None):
        self._argv = argv
        self._cwd = cwd
        self._extra_env = extra_env or {}
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL)
        self._stderr_task: asyncio.Task | None = None

    @property
    def stderr_tail(self) -> str:
        """Recent stderr. Empty on a healthy run; the reason on a broken one."""
        return "\n".join(self._stderr)

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        # Strip ANTHROPIC_API_KEY so a stray export cannot silently move us off
        # the subscription path and onto metered billing.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        # PATH shim + SUDO_ASKPASS, so a command needing a password asks the
        # widget instead of hanging on a tty that does not exist.
        env.update(self._extra_env)
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._argv,
                cwd=str(self._cwd),
                env=env,
                limit=STREAM_LIMIT,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as exc:
            # Phrased so problems.classify() recognises it - a daemon that cannot
            # find `claude` should say so, not time out looking like a hang.
            raise RuntimeError(
                f"command not found: {self._argv[0]} ({exc})") from exc
        self._stderr.clear()
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        """Keep reading stderr so the child never blocks on a full pipe.

        Nothing consumed stderr before, which meant a chatty failure could fill
        the 64KB pipe buffer and wedge the child mid-turn - a hang with no
        message, the worst failure mode to debug.
        """
        assert self._proc is not None and self._proc.stderr is not None
        stderr = self._proc.stderr
        while True:
            try:
                line = await stderr.readline()
            except (ValueError, asyncio.LimitOverrunError):
                continue          # oversized line; drop it, keep draining
            except asyncio.CancelledError:
                raise
            if not line:
                return
            if text := line.decode("utf-8", "replace").rstrip():
                self._stderr.append(text)

    async def send(self, text: str) -> None:
        if not self.running or self._proc is None or self._proc.stdin is None:
            raise RuntimeError("engine is not running")
        self._proc.stdin.write(_user_message(text))
        await self._proc.stdin.drain()

    async def events(self) -> AsyncIterator[EngineEvent]:
        """Yield events until the child exits. One `result` ends a turn."""
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("engine is not running")

        while True:
            try:
                line = await self._proc.stdout.readline()
            except ValueError:
                # Line longer than STREAM_LIMIT. Skip it rather than abort the
                # turn - losing one event beats wedging the session forever.
                yield EngineEvent("error", "dropped an oversized stream line")
                continue
            if not line:
                # stdout closed. If the child died, say why - an unexplained
                # empty answer is the symptom users report as "it just broke".
                await asyncio.sleep(0)          # let the stderr drain catch up
                code = self._proc.returncode
                if code not in (0, None):
                    yield EngineEvent(
                        "error",
                        self.stderr_tail or f"claude exited with status {code}",
                        {"returncode": code})
                return
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            kind = event.get("type")
            if kind == "stream_event":
                delta = (event.get("event") or {}).get("delta") or {}
                if text := delta.get("text"):
                    yield EngineEvent("delta", text, event)
            elif kind == "assistant":
                blocks = (event.get("message") or {}).get("content", [])
                text = "".join(block.get("text", "") for block in blocks
                               if block.get("type") == "text")
                # A message that calls a tool is what the widget needs to name
                # what is happening; without it the wait is just three dots.
                if any(b.get("type") == "tool_use" for b in blocks):
                    yield EngineEvent("tool", "", event)
                if text:
                    yield EngineEvent("message", text, event)
            elif kind == "rate_limit_event":
                yield EngineEvent("rate_limit", "", event)
            elif kind == "result":
                yield EngineEvent("result", event.get("result") or "", event)
            elif kind == "system":
                yield EngineEvent("system", "", event)

    async def cancel(self) -> None:
        """Stop a turn NOW.

        stop() closes stdin and waits for the child to finish, which is right
        for shutdown but wrong for cancelling: a turn already streaming does
        not care that stdin closed, so "stop" appeared to do nothing for five
        seconds and then killed it anyway. Signal first, ask questions later.
        """
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=0.7)
        except (asyncio.TimeoutError, ProcessLookupError):
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.kill()
        await self.stop()

    async def stop(self) -> None:
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            self._stderr_task = None
        if self._proc is None:
            return
        if self._proc.stdin is not None and not self._proc.stdin.is_closing():
            self._proc.stdin.close()
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            with_suppress = getattr(self._proc, "kill", lambda: None)
            with_suppress()
        self._proc = None
