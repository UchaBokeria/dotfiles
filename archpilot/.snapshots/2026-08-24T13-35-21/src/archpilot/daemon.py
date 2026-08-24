"""The ArchPilot daemon.

Owns the sessions, the child `claude` processes, and the approval broker that
hooks/pretooluse.py blocks on. Speaks newline-JSON over a unix socket so the
frontend stays swappable - eww is a client, not a dependency.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import time
import subprocess
import sys
import uuid
from pathlib import Path

from . import (activity, auth, compositor, config, ipc, modes, paths, persist,
               policy,
               problems, rofi_theme, settings, shim, titles)
from .markup import wrap_plain
from . import git
from .context import clipboard as clipboard_ctx
from .context import history as history_ctx
from .context import relevance
from .context import sessions as session_index
from .context import system as system_ctx
from .context import terminal as terminal_ctx
from .context import window as window_ctx
from .session import AWAITING, ERROR, IDLE, THINKING, Session, SessionManager

#: Coalesce streaming deltas so eww is not woken hundreds of times a second.
DELTA_THROTTLE_S = 0.08

#: Credentials change on the scale of days. Re-reading the file more
#: often than this just puts disk IO under every streamed delta.
AUTH_RECHECK_S = 60.0

MODEL_PREFIXES = {":opus": "opus", ":sonnet": "sonnet", ":fable": "fable", ":haiku": "haiku"}


def split_directives(text: str) -> tuple[str, str | None, str | None]:
    """Pull leading `:model` / `:mode` directives off a prompt.

    Manual model selection was the chosen policy, so this is the switch: typing
    ":sonnet how much ram is used" overrides the configured default for one turn.
    """
    model = mode = None
    words = text.split()
    while words:
        head = words[0].lower()
        if head in MODEL_PREFIXES:
            model = MODEL_PREFIXES[head]
        elif head in (":ask", ":action"):
            mode = head[1:]
        else:
            break
        words = words[1:]
    return " ".join(words), model, mode


class Daemon:
    def __init__(self) -> None:
        self.cfg = config.load()
        self.settings = settings.render()
        # Keep the pickers - and the rice's own launchers - in step with the
        # current wallust palette.
        rofi_theme.render()
        if self.cfg.sync_launcher_colors:
            rofi_theme.sync_launcher_colors()

        askpass = Path(__file__).resolve().parent.parent.parent / "hooks" / "askpass.py"
        self.manager = SessionManager(self.settings, shim.env_for(askpass),
                                      mcp_servers=self.cfg.mcp_servers)
        # Re-attach to whatever conversation was live before the last restart.
        if (restored := persist.load()) is not None:
            self.manager.adopt(restored)
        self.subscribers: set[asyncio.StreamWriter] = set()
        self.pending: dict[str, asyncio.Future[str]] = {}
        self.pending_meta: dict[str, dict] = {}
        self._turn_lock = asyncio.Lock()
        #: Files staged by `archpilot shot`, consumed by the next prompt.
        self.attachments: list[str] = []
        #: Unsent input, so closing and reopening the window does not lose what
        #: you were half-way through typing. Cleared only by starting a new chat.
        self.draft = ""
        #: Pending password request, if the widget is being asked right now.
        self._password: asyncio.Future[str] | None = None
        self._password_prompt = ""
        #: Armed only while an approved elevated command is in flight. Without
        #: this, the model could invoke the askpass helper itself (SUDO_ASKPASS
        #: is in its environment) and make the user type a password for a
        #: command nobody approved.
        self._sudo_armed = False
        self._auth_problem = None
        self._auth_checked_at = -AUTH_RECHECK_S
        self._armed_command = ""

    # -- fan-out ---------------------------------------------------------
    async def broadcast(self, event: dict) -> None:
        dead = []
        payload = ipc.encode(event)
        for writer in self.subscribers:
            try:
                writer.write(payload)
                await writer.drain()
            except (ConnectionError, RuntimeError):
                dead.append(writer)
        for writer in dead:
            self.subscribers.discard(writer)

    def snapshot(self) -> dict:
        session = self.manager.current
        if session is None:
            # Built from a real Session rather than a hand-written dict: the two
            # key sets must never drift, or the widget silently renders a stale
            # value for whatever the fallback forgot.
            session = Session.create(mode=self.cfg.default_mode,
                                     model=self.cfg.default_model,
                                     effort=self.cfg.default_effort)
            base = session.snapshot()
            base["session"] = ""
            base["resume"] = ""
        else:
            base = session.snapshot()
        pending = next(iter(self.pending_meta.values()), None)
        # Wrapped here for the same reason answers are: eww 0.5.0 labels
        # ignore :wrap, and an ellipsised command is one you cannot vet.
        base["pending"] = wrap_plain(pending["command"], 80) if pending else ""
        base["pending_id"] = pending["id"] if pending else ""
        base["pending_reason"] = pending["reason"] if pending else ""
        base["password_prompt"] = self._password_prompt
        base["needs_password"] = bool(self._password_prompt)
        base["draft"] = self.draft
        base["tabs"] = [
            {"id": s.id, "title": (s.turns[0]["prompt"][:22] if s.turns else "new chat"),
             "busy": s.status == THINKING}
            for s in self.manager.tabs()
        ]
        base["tab_active"] = self.manager.active_index()
        base["attachments"] = list(self.attachments)
        base["has_attachments"] = bool(self.attachments)
        # A turn's own failure wins: it is more specific and more recent than a
        # pre-flight guess. Otherwise, warn before the user types rather than
        # letting them discover it by getting nothing back.
        if not base.get("problem"):
            if standing := self._standing_problem():
                base["problem"] = standing.as_dict()
                base["has_problem"] = True
        return base

    def _standing_problem(self):
        """A reason the next turn would fail, checked at most once a minute.

        Reading and parsing the credentials file on every state push would put
        file IO in the path of every streamed delta, so the answer is cached -
        it changes on the scale of days, not deltas.
        """
        now = time.monotonic()
        if now - self._auth_checked_at < AUTH_RECHECK_S:
            return self._auth_problem
        self._auth_checked_at = now
        self._auth_problem = auth.check()
        return self._auth_problem

    async def push_state(self) -> None:
        await self.broadcast({"ev": ipc.EV_STATE, **self.snapshot()})

    # -- turns -----------------------------------------------------------
    async def run_turn(self, session: Session, text: str,
                       explicit: set[str] | None = None) -> None:
        async with self._turn_lock:
            await self.manager.ensure_started(session)
            assert session.engine is not None

            session.prompt = text
            session.answer = ""
            session.actions = []
            session.error = ""
            session.status = THINKING
            session.started_at = time.time()
            session.scroll_offset = 0  # a new prompt always follows the answer
            await self.push_state()

            # Snapshot what is already dirty so the auto-commit can be scoped to
            # what THIS turn changes. The repo usually has unrelated work in
            # progress, and sweeping it up would make `archpilot undo` revert it.
            dirty_before = (
                git.dirty_paths()
                if session.mode == modes.ACTION and self.cfg.get("safety", "auto_commit")
                else None
            )

            outgoing = self._with_context(text, explicit)
            if session.pending_replay:
                outgoing = session.pending_replay + "\n\n" + outgoing
                session.pending_replay = ""
            await session.engine.send(outgoing)

            session.problem = None
            session.error = ""
            session.activity = ""
            chunks: list[str] = []
            last_push = 0.0
            loop = asyncio.get_running_loop()
            try:
                async for event in session.engine.events():
                    if event.kind == "delta":
                        chunks.append(event.text)
                        session.answer = "".join(chunks)
                        now = loop.time()
                        if now - last_push >= DELTA_THROTTLE_S:
                            last_push = now
                            await self.push_state()
                    elif event.kind == "tool":
                        blocks = ((event.raw or {}).get("message") or {}).get("content", [])
                        if described := activity.from_blocks(blocks):
                            session.activity = described
                            await self.push_state()
                    elif event.kind == "message" and event.text:
                        chunks = [event.text]
                        session.activity = ""       # it is writing, not working
                    elif event.kind == "rate_limit":
                        session.record_limits(event.raw or {})
                    elif event.kind == "error":
                        # The child died mid-turn. Name the reason.
                        session.problem = (problems.classify(event.text)
                                           or problems.Problem(
                                               problems.CRASH, "Claude Code stopped",
                                               event.text, "", True))
                        session.error = event.text
                        break
                    elif event.kind == "result":
                        session.record_usage(event.raw or {})
                        stderr = (session.engine.stderr_tail
                                  if session.engine is not None else "")
                        session.problem = problems.from_result(event.raw or {}, stderr)
                        session.finish_turn(event.text or "".join(chunks))
                        break
            except (OSError, RuntimeError, ValueError) as exc:
                session.status = ERROR
                session.error = f"{type(exc).__name__}: {exc}"
                session.problem = problems.classify(str(exc))
            finally:
                # Never leave a session stuck on "thinking": the widget would
                # show a spinner forever with no way back short of a restart.
                session.activity = ""
                if session.status == THINKING:
                    session.finish_turn("".join(chunks))
                if session.problem is not None:
                    session.status = ERROR

            # The approved command has finished; no further password prompts
            # may be raised until something else is approved.
            self._sudo_armed = False
            self._armed_command = ""

            if dirty_before is not None:
                summary = session.prompt.splitlines()[0] if session.prompt else "changes"
                if sha := git.commit_changes(dirty_before, summary):
                    session.answer += f"\n\n(committed {sha[:8]} - archpilot undo reverts it)"

            await self.push_state()
            await self.broadcast({
                "ev": ipc.EV_TURN_END,
                "text": session.answer,
                "actions": [a.command for a in session.actions],
                "problem": session.problem.as_dict() if session.problem else None,
            })
            self._surface_result(session)
            self._maybe_notify(session)

    def _surface_result(self, session: Session) -> None:
        """Bring the answer to the user, according to on_submit.

        The three modes have to actually differ, or the setting is decoration:
          expand  - pull the widget back up so the answer appears on screen
          toggle  - respect that it was hidden; mako announces it instead
          dismiss - stays hidden by design; mako announces it
        An error always surfaces, whatever the mode, because a silent failure
        is the one outcome the user cannot act on.
        """
        mode = self.cfg.on_submit
        if mode == "expand" or session.status == ERROR:
            _ui_open()

    def _with_context(self, text: str, explicit: set[str] | None = None) -> str:
        """Prepend ambient context the user should not have to retype.

        This is the difference between an assistant and a chatbot in a box: the
        machine already knows which window is focused, what just failed in the
        terminal, and what other Claude sessions are doing.

        Each source is gated twice - by config, and by whether the prompt
        actually calls for it - because scrollback and system stats are hundreds
        of tokens that answer nothing for a generic question.
        """
        wanted = relevance.wanted_for(text, explicit)
        parts: list[str] = []

        if self.cfg.get("context", "window"):
            if summary := window_ctx.summarize():
                parts.append(summary)

        if "terminal" in wanted and self.cfg.get("context", "terminal"):
            if summary := terminal_ctx.summarize():
                parts.append(summary)

        if "sessions" in wanted and self.cfg.get("context", "sessions"):
            if summary := session_index.summarize():
                parts.append(summary)

        if wanted & {"clipboard", "selection"}:
            if summary := clipboard_ctx.summarize("clipboard" in wanted,
                                                  "selection" in wanted):
                parts.append(summary)

        if "system" in wanted and self.cfg.get("context", "system"):
            if summary := system_ctx.summarize():
                parts.append("System state:\n" + summary)

        if not parts:
            return text
        return (
            "<archpilot-context>\n" + "\n\n".join(parts) + "\n</archpilot-context>\n\n"
            + text
        )

    @staticmethod
    def _rate_limit_label(raw: dict) -> str:
        payload = raw.get("rate_limit") or raw
        for key in ("status", "state", "message"):
            if value := payload.get(key):
                return str(value)
        return ""

    def _maybe_notify(self, session: Session) -> None:
        """Notify only when the answer is not already on screen.

        Popping a notification over a widget the user is reading is noise, so
        this fires in dismiss mode or whenever the widget is hidden - which is
        exactly the toggle-mode case where they hid it and walked away.
        """
        if not self.cfg.get("ui", "notify_on_complete"):
            return
        # A notification per answer trains you to dismiss them unread, and then
        # the one that mattered gets dismissed too. Only turns that need a
        # decision - a proposed command, or an error - are worth interrupting for.
        interesting = bool(session.actions) or session.status == ERROR
        visible = widget_is_open()
        if not interesting:
            return
        if self.cfg.on_submit != "dismiss" and visible:
            return
        summary = (session.actions[0].command if session.actions
                   else (session.error or "done")).splitlines()[0][:90]
        with contextlib.suppress(OSError):
            urgency = "critical" if session.status == ERROR else "normal"
            subprocess.Popen(
                ["notify-send", "-a", "archpilot", "-u", urgency,
                 f"ArchPilot ({session.mode})", summary],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    # -- approvals -------------------------------------------------------
    async def ask_permission(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        """Block the hook until a human answers, then reply on its connection.

        The hook enforces its own (shorter) deadline, so if this wait is the one
        that expires, the hook has already given up and refused. Either way the
        command does not run without approval.
        """
        request_id = msg.get("tool_use_id") or str(uuid.uuid4())
        command = (msg.get("tool_input") or {}).get("command") or msg.get("tool_name", "?")
        meta = {"id": request_id, "command": command, "reason": msg.get("reason", "")}
        self._armed_command = command

        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        self.pending_meta[request_id] = meta

        if session := self.manager.current:
            session.status = AWAITING
        # Always surface the widget for an approval: in dismiss mode it was just
        # hidden, and a blocked command with nowhere to answer would sit there
        # until the hook's deadline expired and refused it.
        _ui_open()
        await self.broadcast({"ev": ipc.EV_APPROVAL_REQUEST, **meta})
        await self.push_state()
        self._notify_approval(meta)

        try:
            decision = await asyncio.wait_for(future, timeout=self.cfg.approval_deadline_s + 5)
        except asyncio.TimeoutError:
            decision = "deny"
        finally:
            self.pending.pop(request_id, None)
            self.pending_meta.pop(request_id, None)
            if session := self.manager.current:
                session.status = THINKING

        with contextlib.suppress(ConnectionError, RuntimeError):
            writer.write(ipc.encode({"decision": decision}))
            await writer.drain()
        await self.push_state()

    def _notify_approval(self, meta: dict) -> None:
        """Ask for approval in the notification itself.

        `notify-send -A` implies --wait and prints the chosen action, so the
        decision can be made without returning to the window. It blocks until
        answered, hence the executor.
        """
        if not self.cfg.get("ui", "notify_on_complete"):
            return

        loop = asyncio.get_running_loop()
        request_id = meta["id"]

        def ask() -> str:
            try:
                out = subprocess.run(
                    ["notify-send", "-a", "archpilot", "-u", "critical",
                     "-A", "allow=Run it", "-A", "deny=Skip",
                     "ArchPilot needs approval",
                     meta["command"].splitlines()[0][:90]],
                    capture_output=True, text=True, timeout=240, check=False)
            except (OSError, subprocess.SubprocessError):
                return ""
            return out.stdout.strip()

        def done(choice: str) -> None:
            if choice in ("allow", "deny"):
                self.resolve(request_id, choice)

        future = loop.run_in_executor(None, ask)
        future.add_done_callback(
            lambda f: loop.call_soon_threadsafe(done, f.result() if not f.cancelled() else ""))

    async def ask_password(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        """Ask the user for a sudo password on behalf of the askpass helper.

        Refused unless armed by an approved elevated command. The password is
        held in a Future, handed to exactly one caller, and never stored,
        logged, or written to disk - sudo's own timestamp cache handles repeats,
        so there is nothing for archpilot to remember.
        """
        if not self._sudo_armed:
            with contextlib.suppress(ConnectionError, RuntimeError):
                writer.write(ipc.encode({
                    "password": "",
                    "reason": "no approved elevated command is in flight",
                }))
                await writer.drain()
            return

        # Arming lasts for the approved command's execution, not one prompt:
        # sudo retries up to three times, and a typo should not mean starting
        # the whole turn over. It is cleared when the turn ends.
        self._password_prompt = str(msg.get("prompt") or "Password:")[:120]
        self._password = asyncio.get_running_loop().create_future()

        _ui_open()
        await self.broadcast({"ev": ipc.EV_PASSWORD_REQUEST, "prompt": self._password_prompt})
        await self.push_state()

        try:
            password = await asyncio.wait_for(self._password, timeout=150)
        except asyncio.TimeoutError:
            password = ""
        finally:
            self._password = None
            self._password_prompt = ""

        with contextlib.suppress(ConnectionError, RuntimeError):
            writer.write(ipc.encode({"password": password,
                                     "reason": "" if password else "declined or timed out"}))
            await writer.drain()
        # Drop the reference immediately; nothing else may read it.
        del password
        await self.push_state()

    def submit_password(self, value: str) -> bool:
        if self._password is None or self._password.done():
            return False
        self._password.set_result(value)
        return True

    def resolve(self, request_id: str | None, decision: str) -> bool:
        """Answer a pending approval. An empty id answers the only one waiting."""
        if not request_id:
            request_id = next(iter(self.pending), None)
        future = self.pending.get(request_id) if request_id else None
        if future is None or future.done():
            return False
        allowed = decision == "allow"
        if allowed and self._armed_command and policy.uses_elevation(self._armed_command):
            # One approved elevated command earns exactly one password prompt.
            self._sudo_armed = True
        future.set_result("allow" if allowed else "deny")
        return True

    # -- connection handling ---------------------------------------------
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        subscribed = False
        try:
            async for msg in ipc.read_lines(reader):
                op = msg.get("op")

                if op == ipc.OP_SUBSCRIBE:
                    subscribed = True
                    self.subscribers.add(writer)
                    writer.write(ipc.encode({"ev": ipc.EV_STATE, **self.snapshot()}))
                    await writer.drain()

                elif op == ipc.OP_STATE:
                    writer.write(ipc.encode(self.snapshot()))
                    await writer.drain()
                    break

                elif op == ipc.OP_PROMPT:
                    await self._on_prompt(msg)

                elif op == ipc.OP_ASK_PERMISSION:
                    await self.ask_permission(msg, writer)
                    break

                elif op == ipc.OP_ASK_PASSWORD:
                    await self.ask_password(msg, writer)
                    break

                elif op == ipc.OP_PASSWORD:
                    ok = self.submit_password(msg.get("value") or "")
                    writer.write(ipc.encode({"ok": ok}))
                    await writer.drain()

                elif op == ipc.OP_APPROVE:
                    ok = self.resolve(msg.get("id"), msg.get("decision", "deny"))
                    writer.write(ipc.encode({"ok": ok}))
                    await writer.drain()

                elif op == ipc.OP_SESSIONS:
                    listing = [
                        {"id": s.id, "title": s.title, "state": s.state,
                         "progress": s.progress, "cwd": s.cwd, "branch": s.git_branch,
                         "resume": f"cd {s.cwd} && claude --resume {s.id}"}
                        for s in session_index.index()
                    ]
                    writer.write(ipc.encode({"sessions": listing}))
                    await writer.drain()
                    break

                elif op == ipc.OP_PICKER:
                    # Fire and forget: the caller is usually a widget button,
                    # and the less it does the fewer ways it can fail.
                    asyncio.create_task(self.run_picker(msg.get("kind", "history")))
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_TAB:
                    await self.handle_tab(msg)
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_DRAFT:
                    self.draft = str(msg.get("text") or "")
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_REWIND:
                    await self.rewind(int(msg.get("index", 0)))
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_SCROLL:
                    if (session := self.manager.current) is not None:
                        live = session.answer if session.status == THINKING else ""
                        session.scroll(int(msg.get("delta", 0)), live)
                        await self.push_state()
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_WIDGET:
                    # Asked for by commands that eww itself spawned. They must
                    # not call `eww` directly: eww waits for the command it
                    # launched, so a callback into eww deadlocks and the click
                    # appears to do nothing at all. The daemon is not eww's
                    # child, so it can drive the widget safely.
                    if msg.get("action") == "hide":
                        _ui_close()
                    else:
                        _ui_open()
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_NEW:
                    await self.start_new()
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_SET and msg.get("field") == "mcp":
                    await self.toggle_mcp(str(msg.get("value") or ""),
                                          bool(msg.get("enable", True)))
                    writer.write(ipc.encode({"ok": True}))
                    await writer.drain()

                elif op == ipc.OP_SET:
                    value = await self.apply_setting(
                        msg.get("field", ""), msg.get("value"), bool(msg.get("cycle")))
                    writer.write(ipc.encode({"ok": value is not None, "value": value}))
                    await writer.drain()

                elif op == ipc.OP_RUN_ACTION:
                    await self._on_run_action(msg)

                elif op == ipc.OP_ATTACH:
                    self.attachments.extend(msg.get("paths") or [])
                    await self.push_state()
                    _ui_open()

                elif op == ipc.OP_RENAME:
                    titles.rename(str(msg.get("session_id") or ""),
                                  str(msg.get("title") or ""))
                    await self.push_state()

                elif op == ipc.OP_OPEN_SESSION:
                    await self.open_session(str(msg.get("session_id") or ""),
                                            str(msg.get("cwd") or ""))

                elif op == ipc.OP_DETACH:
                    target = str(msg.get("path") or "")
                    self.attachments = [a for a in self.attachments if a != target]
                    await self.push_state()

                elif op == ipc.OP_TOGGLE:
                    _ui_toggle()

                elif op == ipc.OP_CANCEL:
                    if (session := self.manager.get(msg.get("session"))) and session.engine:
                        # cancel(), not stop(): stop() waits for the child to
                        # finish on its own, which is exactly what we are
                        # trying not to do.
                        await session.engine.cancel()
                        session.engine = None
                        session.status = IDLE
                        await self.push_state()

                else:
                    writer.write(ipc.encode({"ev": ipc.EV_ERROR, "message": f"unknown op {op!r}"}))
                    await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            if subscribed:
                self.subscribers.discard(writer)
            with contextlib.suppress(Exception):
                writer.close()

    async def _on_prompt(self, msg: dict) -> None:
        text, model, mode = split_directives(msg.get("text", "").strip())
        text, explicit = relevance.split_directives(text)
        if not text:
            return
        self.draft = ""          # it has been sent; nothing left to restore

        mode = msg.get("mode") or mode or (
            self.manager.current.mode if self.manager.current else self.cfg.default_mode
        )
        model = msg.get("model") or model or (
            self.manager.current.model if self.manager.current else self.cfg.default_model
        )

        session = None if msg.get("new") else self.manager.get(msg.get("session"))
        if session is None or session.mode != mode or session.model != model:
            cwd = Path(msg["cwd"]) if msg.get("cwd") else None
            effort = (self.manager.current.effort if self.manager.current
                      else self.cfg.default_effort)
            session = self.manager.new(mode=mode, model=model, effort=effort, cwd=cwd)
        self.manager.current = session
        # Persist the pointer so a daemon restart or reboot re-attaches to this
        # conversation instead of silently dropping into a blank one.
        persist.save(session)

        attachments = list(self.attachments) + list(msg.get("attachments") or [])
        self.attachments.clear()
        if attachments:
            listed = "\n".join(f"- {a}" for a in attachments)
            text = f"{text}\n\nAttached files (read them):\n{listed}"

        # on_submit: dismiss hides the widget immediately and lets mako announce
        # the result; expand and toggle both leave it up to stream the answer in.
        if self.cfg.on_submit == "dismiss":
            _ui_close()

        asyncio.create_task(self.run_turn(session, text, explicit))

    async def run_picker(self, kind: str) -> None:
        """Run a rofi picker from the daemon, not from a widget button.

        Every previous attempt drove rofi from the process the button spawned,
        and that process is a child of eww: closing the window could reap it,
        and calling back into eww to close the window could deadlock. Neither
        can happen here - the daemon is nobody's child. The button now only
        writes one line to a socket.
        """

        if kind == "sessions":
            entries = session_index.index()
            rows = [f"{s.title}\t{s.state}\t{s.progress or '-'}\t{s.cwd}\t{s.id}"
                    for s in entries]
            prompt = "session"
        else:
            entries = history_ctx.recent(limit=200)
            rows = [f"{e.when}\t{e.session_id[:8]}\t{e.prompt}" for e in entries]
            prompt = "history"

        if not rows:
            self._notify_plain("archpilot", f"no {kind} yet")
            return

        _ui_close()
        _submap("reset")
        try:
            choice = await self._rofi(rows, prompt)
        finally:
            _ui_open()

        if not choice:
            return
        if kind == "sessions":
            fields = choice.split("\t")
            if len(fields) >= 5:
                self._open_terminal(fields[3].strip(), fields[-1].strip())
        else:
            await self._on_prompt({"text": choice.split("\t", 2)[-1]})

    async def _rofi(self, rows: list[str], prompt: str) -> str:
        from . import rofi_theme

        configured = self.cfg.rofi_theme
        theme = Path(configured).expanduser() if configured else rofi_theme.render()
        argv = ["rofi", "-dmenu", "-i", "-p", prompt, "-format", "s"]
        if theme.exists():
            argv += ["-theme", str(theme)]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            out, _ = await proc.communicate("\n".join(rows).encode())
        except (OSError, ValueError):
            return ""
        return out.decode(errors="replace").strip()

    def _open_terminal(self, cwd: str, session_id: str) -> None:
        with contextlib.suppress(OSError):
            subprocess.Popen(["kitty", "--directory", cwd, "--",
                              "claude", "--resume", session_id],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)

    def _notify_plain(self, title: str, body: str) -> None:
        with contextlib.suppress(OSError):
            subprocess.Popen(["notify-send", "-a", "archpilot", title, body],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    async def rewind(self, index: int) -> None:
        """Undo a message: take it out of the chat and back into the input.

        Claude Code cannot resume a session at a chosen point, so this starts a
        fresh one and replays the EARLIER exchanges into it as context. The
        rewound prompt is handed back to the widget so it lands in the input
        unsent, ready to edit and send again.

        The fresh session takes the old one's tab rather than being appended -
        adding a tab is what made rewinding look like it had done nothing to
        the conversation you were looking at.
        """
        session = self.manager.current
        if session is None:
            return
        kept, undone = session.rewind_to(index)
        if not undone:
            return

        if session.engine is not None:
            await session.engine.stop()
            session.engine = None

        fresh = Session.create(mode=session.mode, model=session.model,
                               effort=session.effort, cwd=session.cwd)
        self.manager.replace_current(fresh)
        fresh.turns = list(kept)
        if kept:
            replay = "\n\n".join(
                f"User: {turn['prompt']}\nYou: {turn['answer']}" for turn in kept)
            fresh.pending_replay = (
                "Earlier in this conversation:\n\n" + replay
                + "\n\nContinue from there. Do not repeat any of it back."
            )
        # Rewinding to the very first message leaves nothing to replay, and a
        # preamble saying "earlier in this conversation" followed by nothing
        # would be a lie to the model.

        self.draft = undone
        persist.save(fresh)
        await self.push_state()
        await self.broadcast({"ev": ipc.EV_RESTORE_INPUT, "text": undone})

    async def start_new(self) -> None:
        """Forget the current conversation without touching its transcript.

        The old session stays on disk and remains resumable from the session
        browser or a terminal - this only clears what the widget is pointed at.
        """
        if (session := self.manager.current) is not None and session.engine is not None:
            await session.engine.stop()
            session.engine = None
        self.manager.current = None
        self.attachments.clear()
        self.draft = ""          # a new chat is the one thing that discards it
        persist.save(None)
        await self.push_state()

    async def open_session(self, session_id: str, cwd: str = "") -> None:
        """Reopen a past conversation as a live, resumable session.

        Selecting a history result used to paste its text into whatever chat
        you were already in, which is not opening it at all - the answers were
        left behind. This rebuilds the exchanges from the transcript and
        attaches to the SAME Claude Code session id, so `--resume` picks the
        real conversation up where it stopped.
        """
        if not session_id:
            return
        turns, recorded_cwd = history_ctx.conversation(session_id)

        if existing := self.manager.get(session_id):
            # Already open in a tab - just focus it. But a session restored
            # from disk can be an empty shell with only its id, so fill in the
            # history if it has none, or reopening shows a blank chat.
            if not existing.turns:
                existing.turns = turns
                existing.restored = True
            self.manager.current = existing
            await self.push_state()
            _ui_open()
            return
        session = Session.create(
            mode=self.cfg.default_mode, model=self.cfg.default_model,
            effort=self.cfg.default_effort,
            cwd=Path(cwd or recorded_cwd) if (cwd or recorded_cwd) else None)
        # Claim the transcript's own id, and resume rather than start fresh.
        session.id = session_id
        session.restored = True
        session.turns = turns

        current = self.manager.current
        if current is not None and not current.turns and current.status == IDLE:
            # An untouched blank tab is not worth keeping around.
            self.manager.replace_current(session)
        else:
            self.manager.sessions[session.id] = session
            if session.id not in self.manager.order:
                self.manager.order.append(session.id)
            self.manager.current = session

        persist.save(session)
        await self.push_state()
        _ui_open()

    async def handle_tab(self, msg: dict) -> None:
        """Open conversations side by side.

        Each tab is a separate Claude Code session with its own transcript, so
        they stay independently resumable - this is a view over sessions, not a
        new concept.
        """
        action = msg.get("action")
        if action == "new":
            self.manager.new(mode=self.cfg.default_mode, model=self.cfg.default_model,
                             effort=self.cfg.default_effort)
        elif action == "next":
            self.manager.cycle_tab(1)
        elif action == "prev":
            self.manager.cycle_tab(-1)
        elif action == "select":
            self.manager.select(int(msg.get("index", 0)))
        elif action == "close":
            index = msg.get("index")
            await self.manager.close_tab(int(index) if index is not None else None)
        persist.save(self.manager.current)
        await self.push_state()

    async def toggle_mcp(self, server: str, enable: bool) -> None:
        """Enable or disable an MCP server for sessions started from now on.

        Not retroactive: the server list is a launch flag on the child process,
        so the running session keeps whatever it started with.
        """
        current = list(self.manager._mcp_servers)
        if enable and server not in current:
            current.append(server)
        elif not enable and server in current:
            current.remove(server)
        self.manager._mcp_servers = tuple(current)
        await self.push_state()

    async def apply_setting(self, field: str, value: str | None, cycling: bool) -> str | None:
        """Change mode / model / effort, keeping the conversation.

        All three are per-process flags on the `claude` child, so they cannot be
        changed in place. The engine is stopped and the session marked for
        resume, so the next prompt re-attaches to the same conversation with the
        new flags rather than starting over.
        """
        session = self.manager.current
        current = {
            "mode": session.mode if session else self.cfg.default_mode,
            "model": session.model if session else self.cfg.default_model,
            "effort": session.effort if session else self.cfg.default_effort,
        }
        if field not in current:
            return None

        cycles = {
            "mode": modes.MODES,
            "model": modes.MODEL_CYCLE,
            "effort": modes.EFFORT_CYCLE,
        }
        if cycling:
            value = modes.cycle(cycles[field], current[field])
        if value not in cycles[field]:
            return None
        if value == current[field]:
            return value

        if session is None:
            # Nothing live yet - the next session picks this up.
            self.cfg.data[field if field != "model" else "model"]["default"] = value
            await self.push_state()
            return value

        setattr(session, field, value)
        if session.engine is not None:
            await session.engine.stop()
            session.engine = None
            # Re-attach rather than start fresh: the conversation is the point.
            session.restored = True

        persist.save(session)
        await self.push_state()
        return value

    async def _on_run_action(self, msg: dict) -> None:
        """Run a suggested action by position.

        Referring to actions by index rather than by text keeps the eww button
        free of shell quoting entirely, and means the command the user clicked
        is the command the model actually proposed - not a re-parse of it.

        The command still goes through the engine, so the PreToolUse gate vets
        it exactly as it would any other command. The button is a shortcut, not
        a bypass.
        """
        session = self.manager.current
        if session is None:
            return
        try:
            action = session.actions[int(msg.get("index", 0))]
        except (ValueError, IndexError, TypeError):
            return
        prompt = (
            "Run exactly this command and report the result. Do not modify it.\n\n"
            f"{action.command}"
        )
        # Switch the EXISTING session into action mode rather than starting a
        # new one. Creating a session here wiped the visible conversation every
        # time a proposed command was run.
        if session.mode != "action":
            await self.apply_setting("mode", "action", False)
        session.mark_action_done(action.command)
        await self.push_state()
        asyncio.create_task(self.run_turn(session, prompt))

    async def serve(self) -> None:
        sock = paths.socket_path()
        if sock.exists():
            sock.unlink()
        server = await asyncio.start_unix_server(self.handle, path=str(sock))
        sock.chmod(0o600)

        loop = asyncio.get_running_loop()
        stop = loop.create_future()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, lambda: stop.done() or stop.set_result(None))

        print(f"archpilotd listening on {sock}", file=sys.stderr, flush=True)
        await stop

        # Deliberately NOT `async with server:`. Its __aexit__ awaits
        # wait_closed(), which since Python 3.12 blocks until every client
        # handler returns - and the widget's `subscribe` connection is designed
        # never to return. The daemon therefore ignored SIGTERM and systemd
        # SIGKILLed it 90 seconds later, on every restart and every reboot.
        server.close()
        for writer in list(self.subscribers):
            with contextlib.suppress(Exception):
                writer.close()
        self.subscribers.clear()
        with contextlib.suppress(asyncio.TimeoutError, Exception):
            await asyncio.wait_for(server.wait_closed(), timeout=2)

        await self.manager.shutdown()
        with contextlib.suppress(OSError):
            sock.unlink()


UI_CLASS = "dev.archpilot.ui"

LAUNCHER = Path(__file__).resolve().parent.parent.parent / "bin" / "archpilot-ui"


def gtk_window_is_open() -> bool:
    try:
        return any(c.get("class") == UI_CLASS
                   for c in json.loads(compositor.query("clients", "-j") or "[]"))
    except ValueError:
        return False


def widget_is_open() -> bool:
    """Whether the window is on screen.

    Decides whether a turn needs a notification: if the answer is already in
    front of the user, a mako popup is noise.
    """
    return gtk_window_is_open()


def _hypr(*args: str) -> None:
    """Dispatch through the discovery layer.

    The daemon may be running before hyprland exists (it starts with the user
    session now, not with a graphical target that is never reached here), so
    this has to tolerate there being no compositor yet.
    """
    compositor.dispatch(*args)


def _ui_open() -> None:
    """Bring the GTK window up, launching it if it is not running.

    The eww widget used to be opened from here. That is exactly what made a
    proposed command spawn a second, unclosable window before asking for
    permission - the daemon was driving a frontend the user had already left.
    There is one frontend now.
    """
    if gtk_window_is_open():
        _hypr("focuswindow", f"class:{UI_CLASS}")
        return
    with contextlib.suppress(OSError):
        subprocess.Popen([str(LAUNCHER)], env={**os.environ, **compositor.env()},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


def _ui_close() -> None:
    _hypr("closewindow", f"class:{UI_CLASS}")
    _hypr("submap", "reset")


def _ui_toggle() -> None:
    if gtk_window_is_open():
        _ui_close()
    else:
        _ui_open()


def main() -> None:
    try:
        asyncio.run(Daemon().serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
