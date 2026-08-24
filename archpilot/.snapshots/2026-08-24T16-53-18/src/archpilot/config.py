"""Config loading. Stdlib-only TOML with a defaults merge."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "ui": {
        # How the widget behaves around a turn.
        #   toggle  - stays up and grows; if you hide it, it stays hidden and
        #             mako announces the result
        #   expand  - same, but the widget reopens itself when the answer lands
        #   dismiss - hides on submit; mako announces the result
        # An error reopens the widget in every mode.
        "on_submit": "toggle",
        "notify_on_complete": True,
    },
    "model": {
        # Manual selection: this default, overridable inline with ":opus " / ":sonnet ".
        # haiku is the default because most prompts here are quick questions and
        # it is markedly cheaper against the subscription rate limit; the chip
        # cycles up when a turn needs more.
        "default": "haiku",
    },
    "mode": {
        "default": "ask",  # ask | action
    },
    "effort": {
        # Reasoning depth. Lower is cheaper and faster; on a subscription that
        # is rate-limit budget, so it is a keystroke away (alt+tab).
        "default": "medium",  # low | medium | high | xhigh | max
    },
    "session": {
        # Opt-in: when the focused window is a terminal, start the session in
        # that terminal's cwd instead of the archpilot base dir.
        "follow_terminal_cwd": False,
    },
    "context": {
        "window": True,
        "terminal": True,
        "sessions": True,
        # System stats are noisy, so they are gathered on demand rather than
        # prepended to every single turn.
        "system": False,
    },
    "safety": {
        # The hook's OWN deadline. Must stay well under the harness `timeout`
        # in settings/action.json, because a harness-killed hook FAILS OPEN.
        "approval_deadline_s": 240,
        "auto_commit": True,
    },
    "mcp": {
        # MCP servers to load, by name from ~/.claude.json. Empty means none:
        # ~20 servers' tool schemas on every turn is pure rate-limit waste.
        # Add e.g. ["claude-in-chrome"] to use the browser tools here.
        "servers": [],
    },
    "rofi": {
        # Empty means "generate one from the rice colours" (see rofi_theme.py).
        # The launcher themes here cannot be used: they @import a
        # shared/colors.rasi that does not exist on this machine, so rofi falls
        # back to unstyled. Point this at a .rasi to override.
        "theme": "",
        # Also (re)generate shared/colors.rasi for the rice's own launcher
        # themes. That file is wallust's job and is missing here, which leaves
        # every rofi launcher unstyled. Regenerated on daemon start so it
        # tracks the wallpaper. Set false to leave your rofi config alone.
        "sync_launcher_colors": True,
    },
    "screenshot": {
        # {path} is substituted with the destination file.
        "cmd": 'grim -g "$(slurp -d)" {path}',
    },
}


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass(frozen=True)
class Config:
    data: dict[str, Any] = field(default_factory=lambda: DEFAULTS)

    def get(self, section: str, key: str) -> Any:
        return self.data[section][key]

    @property
    def on_submit(self) -> str:
        return self.get("ui", "on_submit")

    @property
    def default_model(self) -> str:
        return self.get("model", "default")

    @property
    def default_mode(self) -> str:
        return self.get("mode", "default")

    @property
    def default_effort(self) -> str:
        return self.get("effort", "default")

    @property
    def mcp_servers(self) -> tuple:
        return tuple(self.get("mcp", "servers") or ())

    @property
    def rofi_theme(self) -> str:
        return str(self.get("rofi", "theme") or "")

    @property
    def sync_launcher_colors(self) -> bool:
        return bool(self.get("rofi", "sync_launcher_colors"))

    @property
    def approval_deadline_s(self) -> int:
        return int(self.get("safety", "approval_deadline_s"))


def load() -> Config:
    """Load config, falling back to defaults. A malformed file is not fatal."""
    path = paths.CONFIG_FILE
    if not path.exists():
        return Config(DEFAULTS)
    try:
        with path.open("rb") as handle:
            user = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return Config(DEFAULTS)
    return Config(_merge(DEFAULTS, user))
