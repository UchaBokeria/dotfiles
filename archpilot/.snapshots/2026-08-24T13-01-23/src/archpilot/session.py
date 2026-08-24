"""One ArchPilot conversation, backed by one Claude Code session.

The session id is generated here and handed to `claude --session-id`, which is
what makes the conversation resumable from a terminal:

    cd <cwd> && claude --resume <id>

Verified working end to end - a session created by the daemon carries its full
history into an interactive terminal resume.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import modes, paths
from .context import rice
from .actions import Action, parse, strip
from .engine import ClaudeCodeEngine
from .markup import to_pango, wrap_pango

IDLE = "idle"
THINKING = "thinking"
AWAITING = "awaiting_approval"
ERROR = "error"


@dataclass
class Session:
    id: str
    cwd: Path
    mode: str
    model: str
    effort: str = "high"
    engine: ClaudeCodeEngine | None = None
    status: str = IDLE
    prompt: str = ""
    answer: str = ""
    actions: list[Action] = field(default_factory=list)
    #: Completed turns, oldest first. The widget renders them newest-first so a
    #: new answer is visible without scrolling; scrolling down goes back in time.
    turns: list = field(default_factory=list)
    #: Lines scrolled back from the newest output. 0 means "following".
    scroll_offset: int = 0
    rate_limit: str = ""
    #: Tokens occupied in the context window, and the window size.
    context_used: int = 0
    context_total: int = 0
    #: Rate-limit windows keyed by type ("five_hour", "weekly"), each holding
    #: the unix timestamp the window resets at. Claude Code reports the reset
    #: time in stream-json but NOT the percentage consumed - that figure lives
    #: only inside its own statusline, so it is not shown here rather than
    #: guessed at.
    limits: dict = field(default_factory=dict)
    limit_status: str = ""
    #: When the current turn started, for the "took 4.2s" line under an answer.
    started_at: float = 0.0
    #: Context to prepend on the next prompt after a rewind, once.
    pending_replay: str = ""
    error: str = ""
    #: A recognised failure (auth, rate limit, network...) with a plain
    #: sentence and the command that fixes it. `error` is the raw text;
    #: this is what the widget can actually act on.
    problem: object | None = None
    #: True when restored from a previous daemon run, so the engine must
    #: attach with --resume instead of claiming a fresh --session-id.
    restored: bool = False

    @classmethod
    def create(cls, *, mode: str, model: str, effort: str = "high",
               cwd: Path | None = None) -> "Session":
        return cls(
            id=str(uuid.uuid4()),
            cwd=cwd or paths.BASE_DIR,
            mode=mode,
            model=model,
            effort=effort,
        )

    @property
    def transcript(self) -> Path:
        return paths.claude_project_dir(self.cwd) / f"{self.id}.jsonl"

    @property
    def resume_hint(self) -> str:
        """Exactly what to type in a terminal to continue this conversation."""
        return f"cd {self.cwd} && claude --resume {self.id}"

    def record_limits(self, raw: dict) -> None:
        info = raw.get("rate_limit_info") or {}
        kind = info.get("rateLimitType")
        if kind and info.get("resetsAt"):
            self.limits[str(kind)] = int(info["resetsAt"])
        if status := info.get("status"):
            self.limit_status = str(status)

    @staticmethod
    def _until(stamp: int) -> str:
        remaining = stamp - time.time()
        if remaining <= 0:
            return "now"
        # Round to the nearest minute rather than truncating: a window that
        # resets in exactly 2h15m should not read 2h14m because a fraction of
        # a second elapsed between the event and the render.
        hours, minutes = divmod(round(remaining / 60), 60)
        if hours >= 24:
            return f"{hours // 24}d{hours % 24}h"
        return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"

    @staticmethod
    def _at(stamp: int) -> str:
        """When the window resets, as a wall clock time.

        "resets 23:00" is easier to plan around than "2h14m left" - you compare
        it against the clock you are already looking at instead of doing
        arithmetic. Windows more than a day out get a weekday too.
        """
        remaining = stamp - time.time()
        if remaining <= 0:
            # The window already rolled over; a time in the past would read as
            # a limit that is still pending.
            return "now"
        when = time.localtime(stamp)
        if remaining > 20 * 3600:
            return time.strftime("%a %H:%M", when)
        return time.strftime("%H:%M", when)

    #: Window lengths, for turning "resets at 20:00" into "38% left". Claude
    #: Code does not report quota consumed, only when the window rolls over, so
    #: this is elapsed time - which is what you can actually act on.
    WINDOW_SECONDS = {"five_hour": 5 * 3600, "weekly": 7 * 24 * 3600,
                      "weekly_opus": 7 * 24 * 3600}

    def limit_pct(self, kind: str) -> int:
        stamp = self.limits.get(kind)
        span = self.WINDOW_SECONDS.get(kind)
        if not stamp or not span:
            return 0
        return max(0, min(100, round((stamp - time.time()) * 100 / span)))

    @property
    def limit_labels(self) -> dict:
        names = {"five_hour": "5h", "weekly": "wk", "weekly_opus": "wk-opus"}
        return {names.get(k, k): self._at(v) for k, v in sorted(self.limits.items())}

    @staticmethod
    def _tokens(count: int) -> str:
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1000:
            return f"{count // 1000}k"
        return str(count)

    @property
    def context_used_label(self) -> str:
        return self._tokens(self.context_used) if self.context_total else ""

    @property
    def context_total_label(self) -> str:
        return self._tokens(self.context_total) if self.context_total else ""

    @property
    def context_left_label(self) -> str:
        if not self.context_total:
            return ""
        return self._tokens(max(0, self.context_total - self.context_used))

    def record_usage(self, result: dict) -> None:
        """Read context occupancy out of a turn's result event.

        Cache reads count toward the window just like fresh input does, so the
        occupied figure is input + cache-creation + cache-read. Worth showing on
        a subscription: a session quietly approaching its window is the thing
        that makes later turns expensive.
        """
        usage = result.get("usage") or {}
        used = sum(int(usage.get(key) or 0) for key in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        if used:
            self.context_used = used

        for entry in (result.get("modelUsage") or {}).values():
            if window := entry.get("contextWindow"):
                self.context_total = int(window)
                break

    @property
    def context_pct(self) -> int:
        if not self.context_total:
            return 0
        return min(100, round(self.context_used * 100 / self.context_total))

    @property
    def context_label(self) -> str:
        if not self.context_total:
            return ""
        return f"ctx {self.context_pct}%"

    #: Enough history to be useful without making the markup enormous.
    MAX_TURNS = 20

    def finish_turn(self, text: str) -> None:
        """Split a completed answer into display text and suggested actions."""
        self.actions = parse(text)
        self.answer = strip(text)
        self.status = IDLE
        if self.answer or self.actions:
            self.turns.append({
                "prompt": self.prompt,
                "answer": self.answer,
                "took": round(time.time() - self.started_at, 1) if self.started_at else 0.0,
                # Actions belong to the turn that proposed them. Once one has
                # been run its button goes away but the command stays visible
                # as text, so the conversation still records what happened.
                "actions": [{"command": a.command, "done": False} for a in self.actions],
            })
            self.scroll_offset = 0  # follow the newest output
            del self.turns[: -self.MAX_TURNS]

    #: How many wrapped lines fit in the transcript area of the fixed window.
    VIEWPORT_LINES = 14

    def rewind_to(self, index: int) -> tuple[list[dict], str]:
        """Undo the turn at `index`: drop it and everything after it.

        Returns the surviving history and the prompt that was rewound, so the
        caller can hand that text back to the input - the message ends up
        looking like it was never sent, which is what a rewind means to anyone
        who has used Claude Code.

        A true rewind of the model's own context is not something Claude Code
        exposes - a session resumes whole or not at all. So this trims the
        conversation locally and the caller replays what is left into a fresh
        session, which is a real rewind in the only sense available: what the
        model is asked to continue from actually changes.
        """
        if not 0 <= index < len(self.turns):
            return ([], "")
        undone = self.turns[index].get("prompt", "")
        kept = self.turns[:index]
        self.turns = kept
        self.scroll_offset = 0
        return (kept, undone)

    def mark_action_done(self, command: str) -> None:
        """Retire a proposed action once it has been run."""
        for turn in reversed(self.turns):
            for action in turn.get("actions", []):
                if action["command"] == command and not action["done"]:
                    action["done"] = True
                    return

    def turn_views(self) -> list[dict]:
        """Per-message payload for the frontend.

        One entry per exchange rather than a single blob, so each message can
        carry its own copy button and its own action buttons.
        """
        views = []
        for turn in self.turns:
            views.append({
                "prompt": turn["prompt"],
                "answer": turn["answer"],
                "answer_markup": wrap_pango(to_pango(turn["answer"]), self.WRAP_COLS),
                "actions": turn.get("actions", []),
                "took": turn.get("took", 0.0),
            })
        if self.status == THINKING and self.answer:
            views.append({
                "prompt": self.prompt,
                "answer": self.answer,
                "answer_markup": wrap_pango(to_pango(self.answer), self.WRAP_COLS),
                "actions": [],
                "streaming": True,
            })
        elif self.status == THINKING:
            views.append({"prompt": self.prompt, "answer": "", "answer_markup": "",
                          "actions": [], "streaming": True})
        return views

    def transcript_lines(self, live: str = "") -> list[str]:
        """The whole conversation as wrapped markup lines, oldest first.

        `live` is the answer currently streaming in, which is not a completed
        turn yet but must still be visible as it arrives.
        """
        lines: list[str] = []
        for turn in self.turns:
            prompt = wrap_pango(to_pango(turn["prompt"]), self.WRAP_COLS)
            answer = wrap_pango(to_pango(turn["answer"]), self.WRAP_COLS)
            lines.append(f'<span alpha="50%">\u276f {prompt}</span>')
            lines.extend(answer.splitlines())
            lines.append("")
        if live:
            lines.append(f'<span alpha="50%">\u276f {wrap_pango(to_pango(self.prompt), self.WRAP_COLS)}</span>')
            lines.extend(wrap_pango(to_pango(live), self.WRAP_COLS).splitlines())
        while lines and not lines[-1]:
            lines.pop()
        return lines

    def render_transcript(self, live: str = "") -> str:
        """One screenful of the conversation, oldest first, anchored to the end.

        eww's scroll widget exposes no scroll position and cannot be driven
        programmatically, so a real chat log would show its oldest message and
        never follow along. Instead the daemon renders a viewport: the last
        VIEWPORT_LINES lines by default, offset upward by `scroll_offset`. New
        output resets the offset, which is what makes it follow the answer.
        """
        lines = self.transcript_lines(live)
        if not lines:
            return ""
        end = len(lines) - self.scroll_offset
        end = max(min(end, len(lines)), 1)
        start = max(0, end - self.VIEWPORT_LINES)
        return "\n".join(lines[start:end])

    def max_scroll(self, live: str = "") -> int:
        return max(0, len(self.transcript_lines(live)) - self.VIEWPORT_LINES)

    def scroll(self, delta: int, live: str = "") -> None:
        """Positive scrolls back in time; 0 pins to the newest output."""
        self.scroll_offset = max(0, min(self.max_scroll(live), self.scroll_offset + delta))

    #: Rough metrics for the 13px answer font inside a 720px scroll. Used only
    #: to size the widget, so being a few pixels off is harmless.
    WRAP_COLS = 84
    LINE_PX = 21
    MIN_ANSWER_PX = 44
    MAX_ANSWER_PX = 460

    def rendered(self) -> str:
        """The answer as wrapped Pango markup, ready for the eww label."""
        return wrap_pango(to_pango(self.answer), self.WRAP_COLS)

    def answer_height(self, rendered: str | None = None) -> int:
        """Pixel height the answer needs, so the widget grows to fit it.

        Exact rather than estimated: the text is hard-wrapped here (eww's label
        ignores :wrap in this build), so the line count is known, not guessed.
        """
        if not self.answer:
            return self.MIN_ANSWER_PX
        rendered = self.rendered() if rendered is None else rendered
        lines = len(rendered.splitlines()) or 1
        return max(self.MIN_ANSWER_PX,
                   min(self.MAX_ANSWER_PX, lines * self.LINE_PX + 12))

    def snapshot(self) -> dict:
        """The widget's whole view of the world, as one JSON object.

        eww reads this via `deflisten`, so it must stay flat and cheap to
        render - dot access like {ap.mode} rather than nested lookups.
        """
        rendered = self.rendered()
        flat = {}
        # Flattened action slots. eww's JSON array indexing is version-sensitive,
        # and a widget that silently renders nothing is worse than three fields.
        for i in range(3):
            action = self.actions[i] if i < len(self.actions) else None
            flat[f"action{i}"] = action.label if action else ""
            flat[f"show_action{i}"] = action is not None

        return {
            "session": self.id,
            "mode": self.mode,
            "model": self.model,
            "effort": self.effort,
            "status": self.status,
            "cwd": str(self.cwd),
            "prompt": self.prompt,
            "answer": self.answer,
            "answer_markup": rendered,
            "actions": [{"label": a.label, "command": a.command} for a in self.actions],
            "has_actions": bool(self.actions),
            "rate_limit": self.rate_limit,
            "context_pct": self.context_pct,
            "context_label": self.context_label,
            "context_warn": self.context_pct >= 75,
            "context_left": self.context_left_label,
            "context_used": self.context_used_label,
            "context_total": self.context_total_label,
            "context_frac": round(self.context_pct / 100, 3),
            # Two renderings on purpose: eww cannot scroll, so it gets a
            # daemon-rendered viewport; GTK can, so it gets the whole thing and
            # scrolls it itself.
            "transcript": self.render_transcript(self.answer if self.status == THINKING else ""),
            "transcript_full": "\n".join(
                self.transcript_lines(self.answer if self.status == THINKING else "")),
            "has_transcript": bool(self.turns) or bool(self.answer),
            "scrolled_back": self.scroll_offset > 0,
            "limit_5h": self.limit_labels.get("5h", ""),
            "limit_week": self.limit_labels.get("wk", ""),
            "limit_status": self.limit_status,
            "limit_5h_pct": self.limit_pct("five_hour"),
            # "1h50m left" reads better than a reset clock time for a window
            # that is only five hours wide.
            "limit_5h_left": (self._until(self.limits["five_hour"])
                              if self.limits.get("five_hour") else ""),
            "limit_week_left": (self._until(self.limits["weekly"])
                                if self.limits.get("weekly") else ""),
            "limit_week_pct": self.limit_pct("weekly"),
            "turns": self.turn_views(),
            "limit_warn": self.limit_status not in ("", "allowed"),
            "error": self.error,
            "problem": self.problem.as_dict() if self.problem else None,
            "has_problem": self.problem is not None,
            "action_count": len(self.actions),
            "answer_height": self.answer_height(rendered),
            "resume": self.resume_hint,
            **flat,
        }


class SessionManager:
    """Owns live sessions and their child processes."""

    def __init__(self, settings_files: dict[str, Path],
                 extra_env: dict[str, str] | None = None,
                 mcp_servers: tuple = ()):
        self._settings = settings_files
        self._extra_env = extra_env or {}
        self._mcp_servers = mcp_servers
        self.sessions: dict[str, Session] = {}
        #: Tab order, which dict insertion order alone would not survive a close.
        self.order: list[str] = []
        self.current: Session | None = None

    def adopt(self, session: Session) -> Session:
        """Register a session restored from disk as the current one."""
        self.sessions[session.id] = session
        if session.id not in self.order:
            self.order.append(session.id)
        self.current = session
        return session

    def new(self, *, mode: str, model: str, effort: str = "high",
            cwd: Path | None = None) -> Session:
        session = Session.create(mode=mode, model=model, effort=effort, cwd=cwd)
        self.sessions[session.id] = session
        self.order.append(session.id)
        self.current = session
        return session

    def replace_current(self, session: "Session") -> "Session":
        """Put `session` where the current one sits, and drop the old one.

        Rewinding used to call new(), which appends - so instead of the
        conversation going back, a second tab appeared next to the untouched
        original. Taking the same slot is what makes it read as a rewind.
        The old transcript stays on disk and is still resumable by id.
        """
        outgoing = self.current
        self.sessions[session.id] = session
        if outgoing is not None and outgoing.id in self.order:
            self.order[self.order.index(outgoing.id)] = session.id
            self.sessions.pop(outgoing.id, None)
        elif session.id not in self.order:
            self.order.append(session.id)
        self.current = session
        return session

    # -- tabs -------------------------------------------------------------
    def tabs(self) -> list:
        """Open conversations, oldest first. Each is a real Claude Code session,
        so every tab stays resumable from a terminal."""
        return [self.sessions[sid] for sid in self.order if sid in self.sessions]

    def active_index(self) -> int:
        if self.current is None:
            return -1
        try:
            return self.tabs().index(self.current)
        except ValueError:
            return -1

    def select(self, index: int) -> Session | None:
        open_tabs = self.tabs()
        if not open_tabs:
            return None
        self.current = open_tabs[max(0, min(index, len(open_tabs) - 1))]
        return self.current

    def cycle_tab(self, delta: int) -> Session | None:
        open_tabs = self.tabs()
        if not open_tabs:
            return None
        return self.select((self.active_index() + delta) % len(open_tabs))

    async def close_tab(self, index: int | None = None) -> Session | None:
        """Close a tab by position, or the current one when no index is given.

        The x on a tab has to be able to close THAT tab, not whichever one
        happens to be focused.
        """
        session = self.current
        if index is not None:
            tabs = self.tabs()
            if not 0 <= index < len(tabs):
                return self.current
            session = tabs[index]
        if session is None:
            return None
        if session.engine is not None:
            await session.engine.stop()
        self.sessions.pop(session.id, None)
        if session.id in self.order:
            self.order.remove(session.id)
        remaining = self.tabs()
        if self.current is session or self.current is None:
            self.current = remaining[-1] if remaining else None
        return self.current

    def get(self, session_id: str | None) -> Session | None:
        if session_id is None:
            return self.current
        return self.sessions.get(session_id)

    async def ensure_started(self, session: Session, *, resume: bool = False) -> None:
        if session.engine is not None and session.engine.running:
            return
        resume = resume or session.restored
        argv = modes.build_argv(
            mode=session.mode,
            session_id=session.id,
            model=session.model,
            effort=session.effort,
            settings_file=self._settings[session.mode],
            resume=resume,
            machine=rice.describe(),
            mcp_servers=self._mcp_servers,
        )
        session.engine = ClaudeCodeEngine(argv, session.cwd, self._extra_env)
        await session.engine.start()
        # Only the first attach needs --resume; the child then holds the session.
        session.restored = False

    async def shutdown(self) -> None:
        for session in self.sessions.values():
            if session.engine is not None:
                await session.engine.stop()
