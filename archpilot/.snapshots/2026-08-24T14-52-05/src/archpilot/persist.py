"""Remember the current conversation across daemon restarts.

Claude Code already persists the transcript; what was missing was the pointer to
it. Without this, `systemctl --user restart archpilotd` - or a reboot - silently
drops you into a blank session while the previous conversation sits on disk,
reachable only through the session browser.

Only the pointer is stored. The conversation itself stays where Claude Code puts
it, and is re-attached with `--resume`.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import paths
from .session import Session


def save(session: Session | None) -> None:
    path = paths.last_session_file()
    if session is None:
        path.unlink(missing_ok=True)
        return
    payload = {
        "id": session.id,
        "cwd": str(session.cwd),
        "mode": session.mode,
        "model": session.model,
        "effort": session.effort,
    }
    try:
        path.write_text(json.dumps(payload))
    except OSError:
        pass


def load() -> Session | None:
    """Rebuild the last session, or None if there is nothing usable to restore."""
    try:
        payload = json.loads(paths.last_session_file().read_text())
    except (OSError, ValueError):
        return None

    required = ("id", "cwd", "mode", "model")
    if not all(isinstance(payload.get(k), str) for k in required):
        return None

    session = Session(
        id=payload["id"],
        cwd=Path(payload["cwd"]),
        mode=payload["mode"],
        model=payload["model"],
        effort=payload.get("effort", "high"),
        restored=True,
    )
    # A pointer to a transcript that no longer exists is worse than no pointer:
    # --resume would fail on the next prompt.
    if not session.transcript.exists():
        return None
    return session
