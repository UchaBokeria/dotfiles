"""Filesystem locations ArchPilot uses. Single source of truth."""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()

#: The dotfiles repo. Edits under here are git-tracked, therefore revertable,
#: which is what makes "confirm irreversible only" a defensible default.
DOTFILES = HOME / ".config" / ".dotfiles" / "blackwall"

#: Default cwd for ArchPilot sessions. Chosen so every conversation is
#: resumable from one predictable place with `claude --resume <uuid>`.
BASE_DIR = DOTFILES / "archpilot"

#: Where the Claude Code CLI keeps its session transcripts.
CLAUDE_PROJECTS = HOME / ".claude" / "projects"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "archpilot"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def runtime_dir() -> Path:
    """Per-user runtime dir, falling back to /tmp when XDG_RUNTIME_DIR is unset."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    path = Path(base) if base else Path(f"/tmp/archpilot-{os.getuid()}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir() -> Path:
    """Persistent state. Unlike the runtime dir, this survives a reboot."""
    base = os.environ.get("XDG_STATE_HOME", HOME / ".local" / "state")
    path = Path(base) / "archpilot"
    path.mkdir(parents=True, exist_ok=True)
    return path


def last_session_file() -> Path:
    return state_dir() / "last-session.json"


def shim_dir() -> Path:
    """Directory prepended to the claude child's PATH.

    Holds a `sudo` wrapper that adds -A, so sudo asks our askpass helper
    instead of a tty that does not exist. A shim is used rather than rewriting
    the command in the hook because a rewritten command makes the transcript
    lie about what ran - and the model notices and flags it as tampering.
    """
    path = runtime_dir() / "archpilot-bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def socket_path() -> Path:
    return runtime_dir() / "archpilot.sock"


def shot_dir() -> Path:
    path = runtime_dir() / "archpilot-shots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def claude_project_dir(cwd: Path) -> Path:
    """Mirror the CLI's cwd -> project-dir slug so we can find transcripts.

    The CLI slugifies an absolute path by replacing every "/" with "-", which
    leaves a leading "-" and doubles up on the "." in ".dotfiles" -> "--".
    Verified against the real directory names under ~/.claude/projects.
    """
    return CLAUDE_PROJECTS / str(cwd.resolve()).replace("/", "-").replace(".", "-")
