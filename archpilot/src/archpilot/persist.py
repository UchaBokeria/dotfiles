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


def save(session: Session | None, manager=None) -> None:
    """Persist the session pointer (H8: atomically now).

    U46: when given the SessionManager, ALL open tabs are saved (order +
    current), not just the current session — restart used to drop every
    background tab.
    """
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
    if manager is not None:
        try:
            tabs = [{"id": s.id, "cwd": str(s.cwd), "mode": s.mode,
                     "model": s.model, "effort": s.effort,
                     "engine": s.engine_name, "codex_thread": s.codex_thread}
                    for s in manager.tabs()]
            payload["tabs"] = tabs
            payload["current"] = session.id
        except Exception:
            pass
    try:
        # H8: tmp+replace — a crash mid-write used to leave half-JSON and the
        # pointer was lost (load → None → blank session).
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload))
        temp.replace(path)
    except OSError:
        pass


def _build(payload: dict) -> Session | None:
    """One session from one payload dict, validated. None if unusable."""
    required = ("id", "cwd", "mode", "model")
    if not all(isinstance(payload.get(k), str) and payload.get(k) for k in required):
        return None
    if payload.get("mode") not in modes.MODES:
        return None
    try:
        cwd = Path(payload["cwd"])
    except (TypeError, ValueError):
        return None

    session = Session(
        id=payload["id"],
        cwd=cwd,
        mode=payload["mode"],
        model=payload["model"],
        effort=payload.get("effort") or "medium",
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


def load() -> Session | None:
    """Rebuild the last session, or None if there is nothing usable to restore.

    U46: multi-tab files restore the CURRENT tab here; the daemon re-adopts
    the rest via load_all(). H8: non-dict JSON and empty-string ids are
    rejected (they used to crash .get or restore into ".").
    """
    try:
        payload = json.loads(paths.last_session_file().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    tabs = payload.get("tabs")
    if isinstance(tabs, list) and tabs:
        current = payload.get("current")
        ordered = sorted(tabs, key=lambda t: 0 if t.get("id") == current else 1)
        for entry in ordered:
            if isinstance(entry, dict) and (session := _build(entry)) is not None:
                return session
        return None
    return _build(payload)


def load_all() -> list[Session]:
    """Every restorable tab, current first. Used by the daemon at startup."""
    try:
        payload = json.loads(paths.last_session_file().read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    tabs = payload.get("tabs")
    if not isinstance(tabs, list) or not tabs:
        single = _build(payload)
        return [single] if single is not None else []
    current = payload.get("current")
    ordered = sorted(tabs, key=lambda t: 0 if t.get("id") == current else 1)
    out = []
    for entry in ordered:
        if isinstance(entry, dict) and (session := _build(entry)) is not None:
            out.append(session)
    return out
