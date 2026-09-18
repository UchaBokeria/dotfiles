"""Remember the current conversation across daemon restarts.

Claude Code already persists the transcript; what was missing was the pointer to
it. Without this, `systemctl --user restart archpilotd` - or a reboot - silently
drops you into a blank session while the previous conversation sits on disk,
reachable only through the session browser.

Only the pointer is stored. The conversation itself stays where Claude Code puts
it, and is re-attached with `--resume` - or, on Codex, where Codex puts it, and
is re-attached with `codex exec resume <thread>`.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import modes, paths
from .engine import codex as codex_engine
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
        "engine": session.engine_name,
        "codex_thread": session.codex_thread,
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
    engine = payload.get("engine")
    session.engine_name = engine if engine in modes.ENGINE_CYCLE else modes.CLAUDE
    session.codex_thread = str(payload.get("codex_thread") or "")

    # A pointer to a transcript that no longer exists is worse than no pointer:
    # --resume would fail on the next prompt.
    if session.engine_name == modes.CODEX:
        if not codex_engine.thread_exists(session.codex_thread):
            return None
    elif not session.transcript.exists():
        return None
    return session
