"""Terminal scrollback and working directory.

This is the injector that removes the most friction: "why did that fail?" needs
no screenshot and no copy-paste, because the scrollback is already on the
machine. kitty is already configured for it on this host:

    allow_remote_control yes
    listen_on unix:@mykitty
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import window as window_ctx

#: kitty appends its instance pid to the configured `listen_on` address, so the
#: bare name refuses connections. Building it from the focused window's pid also
#: guarantees we read the terminal the user is actually looking at rather than
#: whichever kitty happens to answer first.
KITTY_SOCKET_BASE = "unix:@mykitty"
KITTY_CLASSES = {"kitty", "xterm-kitty"}
MAX_LINES = 120


def _descendant_shell_cwd(pid: int) -> Path | None:
    """Resolve the cwd of the foreground process under a terminal pid.

    Reading /proc directly beats asking the shell, because it works no matter
    which shell is running and needs no cooperation from it.
    """
    candidates = [pid]
    seen = set()
    while candidates:
        current = candidates.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            cwd = Path(f"/proc/{current}/cwd").resolve()
        except (OSError, RuntimeError):
            cwd = None
        children_file = Path(f"/proc/{current}/task/{current}/children")
        try:
            children = [int(p) for p in children_file.read_text().split()]
        except (OSError, ValueError):
            children = []
        if not children and cwd is not None:
            return cwd
        candidates.extend(children)
    return None


def socket_for(pid: int) -> str:
    return f"{KITTY_SOCKET_BASE}-{pid}"


def scrollback(pid: int | None = None, max_lines: int = MAX_LINES) -> str:
    """Recent text from the focused kitty window, oldest line first."""
    focused = window_ctx.active() if pid is None else None
    if pid is None:
        if focused is None:
            return ""
        pid = focused.pid
    try:
        out = subprocess.run(
            ["kitty", "@", "--to", socket_for(pid), "get-text", "--extent", "screen"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if out.returncode != 0 or out.stdout.startswith("Error:"):
        return ""
    lines = [line.rstrip() for line in out.stdout.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines[-max_lines:])


def cwd_of_focused() -> Path | None:
    focused = window_ctx.active()
    if focused is None or focused.cls not in KITTY_CLASSES or not focused.pid:
        return None
    return _descendant_shell_cwd(focused.pid)


def summarize() -> str:
    focused = window_ctx.active()
    if focused is None or focused.cls not in KITTY_CLASSES:
        return ""

    parts = []
    if (cwd := cwd_of_focused()) is not None:
        parts.append(f"Terminal working directory: {cwd}")
    if text := scrollback(focused.pid):
        parts.append("Visible terminal output:\n```\n" + text + "\n```")
    return "\n".join(parts)


def is_focused_terminal() -> bool:
    focused = window_ctx.active()
    return focused is not None and focused.cls in KITTY_CLASSES
