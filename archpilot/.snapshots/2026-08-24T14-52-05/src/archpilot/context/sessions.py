"""Index the Claude Code sessions on this machine.

Backs two things: the session browser, and answering "is that session done?"
from evidence rather than guesswork.

Transcripts are newline-delimited JSON and reach several megabytes, so entries
are read by seeking to the tail rather than parsing whole files.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .. import paths

TAIL_BYTES = 64 * 1024

#: Below this, the session is mid-turn. Above the idle threshold, it has almost
#: certainly finished. Between the two, it is ambiguous and we say so.
ACTIVE_S = 60
IDLE_S = 600


@dataclass(frozen=True)
class SessionInfo:
    id: str
    path: Path
    slug: str
    cwd: str
    git_branch: str
    mtime: float
    last_kind: str
    todos_done: int
    todos_total: int

    @property
    def age_s(self) -> float:
        return max(0.0, time.time() - self.mtime)

    @property
    def state(self) -> str:
        if self.age_s < ACTIVE_S:
            return "working"
        if self.age_s > IDLE_S:
            return "finished"
        return "quiet"

    @property
    def title(self) -> str:
        # The CLI already stores a human-readable slug, so there is nothing to
        # generate - just fall back to the id when it is missing.
        return self.slug or self.id[:8]

    @property
    def progress(self) -> str:
        if not self.todos_total:
            return ""
        return f"{self.todos_done}/{self.todos_total} tasks"

    def describe(self) -> str:
        bits = [f"{self.title} [{self.state}]"]
        if self.progress:
            bits.append(self.progress)
        bits.append(f"last activity {_ago(self.age_s)}")
        if self.git_branch:
            bits.append(f"branch {self.git_branch}")
        return " - ".join(bits)


def _ago(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s ago"
    if seconds < 5400:
        return f"{int(seconds // 60)}m ago"
    return f"{int(seconds // 3600)}h ago"


def _tail_entries(path: Path) -> list[dict]:
    """Parse the JSON objects in the last TAIL_BYTES of a transcript."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > TAIL_BYTES:
                handle.seek(size - TAIL_BYTES)
                handle.readline()  # discard the partial line we landed in
            raw = handle.read()
    except OSError:
        return []

    entries = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _todo_progress(entries: list[dict]) -> tuple[int, int]:
    """Latest TodoWrite state, which is the most honest progress signal there is."""
    for entry in reversed(entries):
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") == "TodoWrite":
                todos = (block.get("input") or {}).get("todos") or []
                if todos:
                    done = sum(1 for t in todos if t.get("status") == "completed")
                    return done, len(todos)
    return 0, 0


def read(path: Path) -> SessionInfo | None:
    entries = _tail_entries(path)
    if not entries:
        return None
    last = entries[-1]
    done, total = _todo_progress(entries)
    return SessionInfo(
        id=path.stem,
        path=path,
        slug=str(last.get("slug") or ""),
        cwd=str(last.get("cwd") or ""),
        git_branch=str(last.get("gitBranch") or ""),
        mtime=path.stat().st_mtime,
        last_kind=str(last.get("type") or ""),
        todos_done=done,
        todos_total=total,
    )


def index(limit: int = 40, root: Path | None = None) -> list[SessionInfo]:
    """Most recently touched sessions first."""
    root = root or paths.CLAUDE_PROJECTS
    if not root.exists():
        return []
    files = sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    found = [info for path in files[:limit] if (info := read(path)) is not None]
    return found


def summarize(limit: int = 6, root: Path | None = None) -> str:
    """A compact digest to prepend when the user asks about other sessions."""
    live = [s for s in index(root=root) if s.state != "finished"][:limit]
    if not live:
        return "No Claude Code sessions have been active recently."
    lines = [f"- {s.describe()}" for s in live]
    return "Recent Claude Code sessions on this machine:\n" + "\n".join(lines)
