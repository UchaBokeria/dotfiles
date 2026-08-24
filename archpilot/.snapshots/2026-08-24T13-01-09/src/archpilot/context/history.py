"""Past prompts, read back out of the Claude Code transcripts.

Nothing extra is stored: every prompt the user has ever sent is already in
`~/.claude/projects/*/*.jsonl`. History is a read over that, which means it
also covers conversations started from a terminal, not just from the widget.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path

from .. import paths

#: Context blocks the daemon prepends are noise in a history list.
CONTEXT_OPEN = "<archpilot-context>"
CONTEXT_CLOSE = "</archpilot-context>"

#: Transcripts record more than what a human typed - skill bodies, tool results
#: and harness scaffolding all arrive as role "user". These prefixes identify
#: the ones that are not prompts.
NOISE_PREFIXES = (
    "base directory for this skill",
    "caveat: the messages below",
    "<command-name>",
    "<system-reminder>",
    "<local-command",
    "<user-prompt-submit-hook>",
    "result of calling",
    "tool result",
    "[request interrupted",
    "api error",
    "this session is being continued",
    "your task is to create a detailed summary",
    # ArchPilot's own generated prompts. Offering to re-run one of these as if
    # the user had typed it is confusing - they never did.
    "run exactly this command and report the result",
    "these .pacnew/.pacsave files are waiting",
    "these systemd units are failed",
)


def is_noise(text: str) -> bool:
    lowered = text.lstrip().lower()
    return any(lowered.startswith(prefix) for prefix in NOISE_PREFIXES)


@dataclass(frozen=True)
class Entry:
    prompt: str
    session_id: str
    cwd: str
    timestamp: float

    #: A name the user gave this chat, when there is one. Shown instead of
    #: the prompt, because "the deploy script one" beats the sixth copy of
    #: "fix the widget".
    title: str = ""

    @property
    def when(self) -> str:
        return time.strftime("%m-%d %H:%M", time.localtime(self.timestamp))

    @property
    def label(self) -> str:
        """What the history list should show for this entry."""
        return self.title or self.prompt

    def as_dict(self) -> dict:
        return {"prompt": self.prompt, "session": self.session_id,
                "cwd": self.cwd, "when": self.when, "title": self.title,
                "label": self.label}


def strip_context(text: str) -> str:
    """Remove the injected context block so history shows what the user typed."""
    if CONTEXT_OPEN in text and CONTEXT_CLOSE in text:
        tail = text.split(CONTEXT_CLOSE, 1)[1]
        return tail.strip()
    return text.strip()


#: Only the tail of each transcript is read. Prompts appear throughout a file,
#: but "recent history" only ever needs the end of one, and whole-file parsing
#: cost ~3s across a few hundred sessions.
TAIL_BYTES = 96 * 1024

#: (path, mtime, size) -> parsed entries. Transcripts are append-only, so a file
#: whose mtime and size are unchanged cannot have new prompts in it.
_CACHE: dict = {}


def _prompts_in(path: Path) -> list[Entry]:
    try:
        stat = path.stat()
    except OSError:
        return []
    key = (str(path), stat.st_mtime, stat.st_size)
    if (cached := _CACHE.get(key)) is not None:
        return cached

    try:
        with path.open("rb") as handle:
            if stat.st_size > TAIL_BYTES:
                handle.seek(stat.st_size - TAIL_BYTES)
                handle.readline()          # discard the partial line
            raw = handle.read()
    except OSError:
        return []

    entries: list[Entry] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        # Cheap reject before the expensive json.loads - most lines are
        # assistant messages and tool results, not prompts.
        if not line or '"type":"user"' not in line.replace(" ", ""):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "user":
            continue
        content = (record.get("message") or {}).get("content")
        if isinstance(content, list):
            text = " ".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
        elif isinstance(content, str):
            text = content
        else:
            continue

        text = strip_context(text)
        if not text or text.startswith("<") or len(text) < 2 or is_noise(text):
            continue
        entries.append(Entry(
            prompt=" ".join(text.split())[:200],
            session_id=path.stem,
            cwd=str(record.get("cwd") or ""),
            timestamp=stat.st_mtime,
        ))

    _CACHE[key] = entries
    if len(_CACHE) > 600:                  # bound the cache, oldest first
        for stale in list(_CACHE)[:200]:
            _CACHE.pop(stale, None)
    return entries


def recent(limit: int = 200, root: Path | None = None,
           max_files: int = 120) -> list[Entry]:
    """Most recent prompts first, de-duplicated."""
    root = root or paths.CLAUDE_PROJECTS
    if not root.exists():
        return []
    files = sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    # Read once here rather than per entry: the file is tiny, but this runs
    # over hundreds of prompts every time the history panel opens.
    from .. import titles as titles_store
    names = titles_store.load()

    seen: set[str] = set()
    out: list[Entry] = []
    for path in files[:max_files]:
        for entry in reversed(_prompts_in(path)):
            if entry.prompt in seen:
                continue
            seen.add(entry.prompt)
            if name := names.get(entry.session_id):
                entry = replace(entry, title=name)
            out.append(entry)
            if len(out) >= limit:
                return out
    return out


def conversation(session_id: str, root: Path | None = None,
                 limit: int = 60) -> tuple[list[dict], str]:
    """Rebuild a past session's exchanges, newest last.

    Returns (turns, cwd). Turns are shaped the way Session.turns are, so the
    widget can render an old conversation with no special case. Only the tail
    is read - these files reach megabytes and the recent exchanges are what
    anyone reopening a session is looking for.
    """
    base = root or (Path.home() / ".claude" / "projects")
    matches = list(base.glob(f"*/{session_id}.jsonl"))
    if not matches:
        return ([], "")
    path = matches[0]

    try:
        stat = path.stat()
        with path.open("rb") as handle:
            if stat.st_size > TAIL_BYTES:
                handle.seek(stat.st_size - TAIL_BYTES)
                handle.readline()              # discard the partial line
            raw = handle.read()
    except OSError:
        return ([], "")

    turns: list[dict] = []
    cwd = ""
    pending: str | None = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        cwd = str(record.get("cwd") or cwd)
        kind = record.get("type")
        if kind not in ("user", "assistant"):
            continue
        content = (record.get("message") or {}).get("content")
        if isinstance(content, list):
            text = " ".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
        elif isinstance(content, str):
            text = content
        else:
            continue
        text = text.strip()
        if not text:
            continue

        if kind == "user":
            text = strip_context(text)
            # Tool results arrive as user messages too; they are not prompts.
            if not text or text.startswith("<") or is_noise(text):
                continue
            pending = text
        elif pending is not None:
            turns.append({"prompt": pending, "answer": text,
                          "actions": [], "took": 0.0})
            pending = None

    return (turns[-limit:], cwd)
