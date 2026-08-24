"""Machine state, gathered on demand.

Deliberately not attached to every prompt: it is several hundred tokens that
answer nothing for "how do I write a for loop in fish". Triggered by keyword or
by an explicit `:sys` directive instead.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _run(*args: str, timeout: float = 3) -> str:
    if not shutil.which(args[0]):
        return ""
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def memory() -> str:
    return _run("free", "-h")


def disk() -> str:
    return _run("df", "-h", "-x", "tmpfs", "-x", "devtmpfs")


def failed_units() -> str:
    text = _run("systemctl", "--failed", "--no-legend", "--no-pager")
    return text or "none"


def pending_updates() -> str:
    # checkupdates exits 2 with no output when nothing is pending.
    text = _run("checkupdates", timeout=10)
    if not text:
        return "none (or checkupdates unavailable)"
    lines = text.splitlines()
    head = "\n".join(lines[:20])
    return head + (f"\n... and {len(lines) - 20} more" if len(lines) > 20 else "")


def pacnew_files() -> str:
    """Config files pacman left behind for manual merging after an upgrade."""
    found = _run("find", "/etc", "-maxdepth", "4", "-name", "*.pacnew", timeout=5)
    return found or "none"


def summarize() -> str:
    blocks = [
        ("Memory", memory()),
        ("Disks", disk()),
        ("Failed systemd units", failed_units()),
        ("Pending package updates", pending_updates()),
        (".pacnew files awaiting merge", pacnew_files()),
    ]
    return "\n\n".join(f"{name}:\n{value}" for name, value in blocks if value)
