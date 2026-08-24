"""User-given names for past chats.

Claude Code's own `slug` is derived from the first prompt, which is fine until
you have six sessions that all began "fix the widget". A name you chose
yourself is the only reliable way to find one again, so it is stored here -
alongside ArchPilot's state, never inside Claude Code's transcripts, which are
its files to manage.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import paths

#: Long enough to be descriptive, short enough to render in a list row.
MAX_TITLE = 80


def _file(root: Path | None = None) -> Path:
    return (root or paths.state_dir()) / "titles.json"


def load(root: Path | None = None) -> dict:
    try:
        data = json.loads(_file(root).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(session_id: str, root: Path | None = None) -> str:
    return str(load(root).get(session_id) or "")


def clean(title: str) -> str:
    """The stored form of a typed name.

    Shared with the widget so a row can show the saved name immediately,
    without waiting for the write and re-read to come back.
    """
    return " ".join(str(title or "").split())[:MAX_TITLE]


def rename(session_id: str, title: str, root: Path | None = None) -> str:
    """Name a chat. An empty title removes the name rather than storing "".

    Returns the stored title, so the caller does not have to re-apply the same
    trimming rules to know what was saved.
    """
    if not session_id:
        return ""
    titles = load(root)
    cleaned = clean(title)
    if cleaned:
        titles[session_id] = cleaned
    else:
        titles.pop(session_id, None)

    path = _file(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written whole then moved, so an interrupted write cannot leave a
        # half-file that loses every other name.
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(titles, indent=1, sort_keys=True))
        temp.replace(path)
    except OSError:
        return ""
    return cleaned
