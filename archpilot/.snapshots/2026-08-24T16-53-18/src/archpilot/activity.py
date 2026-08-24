"""Turning a tool call into a line a person can read.

Three dots tell you something is happening but not whether it is stuck. Claude
Code's own interface names the tool it is running, and that difference is the
whole reason you stop wondering whether to press stop.

Phrasings are deliberately plain and present-tense: "running mkinitcpio", not
"Bash(command=...)". The point is to be glanceable, not complete.
"""

from __future__ import annotations

import os
import re

#: Keep it short enough to sit on one line beside the dots.
MAX = 46


def _trim(text: str, limit: int = MAX) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "\N{HORIZONTAL ELLIPSIS}"


def _base(path: str) -> str:
    return os.path.basename(str(path).rstrip("/")) or str(path)


def describe(name: str, params: dict | None = None) -> str:
    """A present-tense phrase for one tool call."""
    params = params or {}
    name = str(name or "")

    if name == "Bash":
        command = str(params.get("command") or "").strip()
        # The first word is the program, which is the useful half of a long
        # pipeline - "running rg" beats 90 characters of flags.
        program = command.split()[0] if command else ""
        if program in ("sudo", "doas") and len(command.split()) > 1:
            program = f"{program} {command.split()[1]}"
        return _trim(f"running {program}" if program else "running a command")

    if name in ("Read", "NotebookRead"):
        return _trim(f"reading {_base(params.get('file_path', ''))}")
    if name in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        return _trim(f"editing {_base(params.get('file_path', ''))}")
    if name == "Glob":
        return _trim(f"looking for {params.get('pattern', 'files')}")
    if name == "Grep":
        return _trim(f"searching for {params.get('pattern', '')}")
    if name in ("WebFetch", "WebSearch"):
        return _trim(f"searching the web for {params.get('query')}"
                     if params.get("query") else "fetching a page")
    if name == "TodoWrite":
        return "updating the plan"
    if name == "Task":
        return _trim(f"delegating: {params.get('description', 'a subtask')}")
    if name.startswith("mcp__"):
        # mcp__server__tool -> "server: tool"
        parts = name.split("__")
        if len(parts) >= 3:
            return _trim(f"{parts[1]}: {parts[2].replace('_', ' ')}")

    # Tool names are CamelCase; split them so an unrecognised one still
    # reads as words rather than "somenewtool".
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.replace("_", " "))
    return _trim(" ".join(spaced.split()).lower() or "working")


def from_blocks(blocks: list) -> str:
    """Describe the last tool call in an assistant message, or "" if none."""
    for block in reversed(blocks or []):
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return describe(block.get("name", ""), block.get("input") or {})
    return ""
