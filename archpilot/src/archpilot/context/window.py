"""What the user is looking at, via hyprctl."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ActiveWindow:
    cls: str
    title: str
    workspace: str
    pid: int

    def describe(self) -> str:
        where = f" on workspace {self.workspace}" if self.workspace else ""
        return f'Focused window: {self.cls} - "{self.title}"{where}.'


def _hyprctl(*args: str) -> dict | list | None:
    from .. import compositor

    raw = compositor.query("-j", *args)
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def active() -> ActiveWindow | None:
    data = _hyprctl("activewindow")
    if not isinstance(data, dict) or not data.get("class"):
        return None
    workspace = (data.get("workspace") or {}).get("name") or ""
    return ActiveWindow(
        cls=str(data.get("class") or ""),
        title=str(data.get("title") or ""),
        workspace=str(workspace),
        pid=int(data.get("pid") or 0),
    )


def summarize() -> str:
    window = active()
    return window.describe() if window else ""
