"""Clipboard and primary selection.

Deliberately opt-in, unlike the window and terminal injectors. A clipboard
routinely holds passwords, tokens and private text; quietly attaching it to
every prompt that happens to say "this" would leak them into a transcript that
lives on disk. So it is reached only through an explicit `:clip` / `:sel`
directive, or the select-and-ask keybind.
"""

from __future__ import annotations

import subprocess

MAX_CHARS = 4000


def _paste(primary: bool) -> str:
    argv = ["wl-paste", "--no-newline"]
    if primary:
        argv.append("--primary")
    try:
        out = subprocess.run(argv, capture_output=True, text=True,
                             timeout=2, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout


def clipboard() -> str:
    return _paste(primary=False)


def selection() -> str:
    """The primary selection: whatever is highlighted right now."""
    return _paste(primary=True)


def _block(label: str, text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n... (truncated, {len(text)} chars total)"
    return f"{label}:\n```\n{text}\n```"


def summarize(want_clipboard: bool, want_selection: bool) -> str:
    parts = []
    if want_selection:
        parts.append(_block("Selected text", selection()))
    if want_clipboard:
        parts.append(_block("Clipboard contents", clipboard()))
    return "\n\n".join(p for p in parts if p)
