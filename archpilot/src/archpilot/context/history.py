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


def _codex_files(root: Path, max_files: int) -> list[Path]:
    """Rollout files from Codex's session store, newest first."""
    from ..engine.codex import codex_home

    sessions = codex_home() / "sessions"
    if not sessions.is_dir():
        return []
    try:
        files = sorted(sessions.rglob("rollout-*.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    return files[:max_files]


def recent(limit: int = 200, root: Path | None = None,
           max_files: int = 120) -> list[Entry]:
    """Most recent prompts first, de-duplicated.

    U29: Codex threads used to be invisible here — history only read
    ~/.claude. Rollouts are merged in, newest-first across both stores.
    """
    root = root or paths.CLAUDE_PROJECTS
    files: list[Path] = []
    if root.exists():
        try:
            files = sorted(root.glob("*/*.jsonl"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            files = []
    # An explicit root is a test/scope boundary: only merge the live Codex
    # store when reading the default location.
    codex = _codex_files(root, max_files) if root == paths.CLAUDE_PROJECTS else []
    try:
        merged = sorted(files[:max_files] + codex,
                        key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        merged = files[:max_files] + codex

    # Read once here rather than per entry: the file is tiny, but this runs
    # over hundreds of prompts every time the history panel opens.
    from .. import titles as titles_store
    names = titles_store.load()

    seen: set[str] = set()
    out: list[Entry] = []
    for path in merged[:max_files]:
        prompts = (_codex_prompts_in(path) if path.name.startswith("rollout-")
                   else _prompts_in(path))
        for entry in reversed(prompts):
            if entry.prompt in seen:
                continue
            seen.add(entry.prompt)
            if name := names.get(entry.session_id):
                entry = replace(entry, title=name)
            out.append(entry)
            if len(out) >= limit:
                return out
    return out


def _codex_text(content) -> str:
    """Plain text out of a rollout message's content blocks."""
    if isinstance(content, list):
        return " ".join(
            str(block.get("text", "")) for block in content
            if isinstance(block, dict)
            and block.get("type") in ("input_text", "output_text")
            and block.get("text"))
    return str(content) if isinstance(content, str) else ""


def _codex_entries(path: Path) -> tuple[str, list[tuple[str, str]], str]:
    """(thread_id, [(role, text)...], cwd) from a rollout file's tail."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > TAIL_BYTES:
                handle.seek(size - TAIL_BYTES)
                handle.readline()
            raw = handle.read()
    except OSError:
        return ("", [], "")
    thread, cwd = "", ""
    messages: list[tuple[str, str]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        kind = record.get("type")
        payload = record.get("payload") or {}
        if kind == "session_meta":
            thread = str(payload.get("id") or payload.get("session_id") or thread)
            cwd = str(payload.get("cwd") or cwd)
        elif kind == "response_item" and isinstance(payload, dict):
            role = payload.get("role")
            if role == "developer":
                continue  # instructions, permissions, environment — not chat
            text = _codex_text(payload.get("content")).strip()
            if role in ("user", "assistant") and text:
                messages.append((role, text))
        elif kind == "turn_context" and isinstance(payload, dict):
            cwd = str(payload.get("cwd") or cwd)
    if not thread:
        # Thread id is also the rollout filename's trailing segment.
        stem = path.stem
        if stem.startswith("rollout-") and "-" in stem:
            thread = stem.rsplit("-", 1)[-1]
    return (thread, messages, cwd)


def _codex_prompts_in(path: Path) -> list[Entry]:
    """History entries from one Codex rollout (cached like Claude's)."""
    try:
        stat = path.stat()
    except OSError:
        return []
    key = ("codex", str(path), stat.st_mtime, stat.st_size)
    if (cached := _CACHE.get(key)) is not None:
        return cached
    thread, messages, cwd = _codex_entries(path)
    entries = [
        Entry(prompt=" ".join(text.split())[:200], session_id=f"codex:{thread}",
              cwd=cwd, timestamp=stat.st_mtime)
        for role, text in messages if role == "user"
        and (cleaned := strip_context(text))
        and not cleaned.startswith("<") and not is_noise(cleaned)
    ]
    _CACHE[key] = entries
    if len(_CACHE) > 600:
        for stale in list(_CACHE)[:200]:
            _CACHE.pop(stale, None)
    return entries


def _codex_conversation(session_id: str,
                        limit: int = 60) -> tuple[list[dict], str]:
    """Rebuild exchanges from a Codex rollout. Returns (turns, cwd)."""
    thread = (session_id.split("codex:", 1)[-1] if session_id.startswith("codex:")
              else session_id)
    from ..engine.codex import codex_home

    sessions = codex_home() / "sessions"
    matches = list(sessions.rglob(f"rollout-*-{thread}.jsonl")) if thread else []
    if not matches:
        return ([], "")
    _thread, messages, cwd = _codex_entries(matches[0])
    turns: list[dict] = []
    pending: str | None = None
    for role, text in messages:
        if role == "user":
            text = strip_context(text)
            if not text or text.startswith("<") or is_noise(text):
                continue
            pending = text
        elif pending is not None:
            turns.append({"prompt": pending, "answer": text,
                          "actions": [], "took": 0.0,
                          "engine": "codex"})
            pending = None
    return (turns[-limit:], cwd)


def conversation(session_id: str, root: Path | None = None,
                 limit: int = 60) -> tuple[list[dict], str]:
    """Rebuild a past session's exchanges, newest last.

    Returns (turns, cwd). Turns are shaped the way Session.turns are, so the
    widget can render an old conversation with no special case. Only the tail
    is read - these files reach megabytes and the recent exchanges are what
    anyone reopening a session is looking for.

    U29: `codex:<thread>` ids (and bare thread ids matching a rollout)
    rebuild from the Codex session store instead of Claude's transcripts.
    """
    if session_id.startswith("codex:"):
        return _codex_conversation(session_id, limit)
    if "-" in session_id and "/" not in session_id:
        # A bare Codex thread id (no path chars, uuid-shaped) — try rollouts
        # before falling through to the Claude glob.
        turns, cwd = _codex_conversation(session_id, limit)
        if turns or cwd:
            return (turns, cwd)
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
