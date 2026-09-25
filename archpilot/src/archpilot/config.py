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
        #             swaync announces the result
        #   expand  - same, but the widget reopens itself when the answer lands
        #   dismiss - hides on submit; swaync announces the result
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
    "engine": {
        # Which CLI answers: claude | codex. ctrl+alt+tab or a click on the
        # engine chip switches the live conversation; this is where new ones
        # start.
        "default": "claude",
    },
    "codex": {
        # Models the chip cycles through on Codex. Empty means "whatever
        # Codex's own catalogue offers this account" (~/.codex/models_cache.json),
        # with the model from ~/.codex/config.toml first.
        "models": [],
        # The binary, when `codex` is not on the daemon's PATH.
        "binary": "codex",
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
    def default_engine(self) -> str:
        from .modes import ENGINE_CYCLE
        engine = str(self.get("engine", "default") or "")
        return engine if engine in ENGINE_CYCLE else ENGINE_CYCLE[0]

    @property
    def codex_models(self) -> tuple:
        configured = tuple(str(m) for m in (self.get("codex", "models") or ())
                           if str(m).strip())
        if configured:
            return configured
        from .engine.codex import available_models
        return available_models()

    @property
    def codex_binary(self) -> str:
        return str(self.get("codex", "binary") or "codex")

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
        """The hook's own deadline, clamped under the harness timeout.

        U1: a user setting this >= HARNESS_TIMEOUT_S (600) lets the harness
        kill the hook, which FAILS OPEN (the command runs). Clamp so the hook
        always dies by its own hand with an explicit refusal.
        """
        from . import settings as _settings

        try:
            value = int(self.get("safety", "approval_deadline_s"))
        except (TypeError, ValueError):
            value = 240
        return max(5, min(value, _settings.HARNESS_TIMEOUT_S - 60))


def load() -> Config:
    """Load config, falling back to defaults. A malformed file is not fatal."""
    path = paths.CONFIG_FILE
    if not path.exists():
        return Config(_copy(DEFAULTS))
    try:
        with path.open("rb") as handle:
            user = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return Config(_copy(DEFAULTS))
    # U12: unknown keys are kept (forward-compatible) but typos in KNOWN
    # sections are worth surfacing nowhere — the daemon logs them instead.
    # (Kept silent by design here: config loads before logging exists.)
    merged = _merge(_copy(DEFAULTS), user if isinstance(user, dict) else {})
    return Config(merged)


def _copy(base: dict[str, Any]) -> dict[str, Any]:
    """Deep-ish copy so Config.data never aliases the global DEFAULTS.

    U12: Config(DEFAULTS) handed out the global dict itself — any caller
    mutating cfg.data poisoned every future load process-wide. frozen=True
    only blocks attribute assignment, not data mutation.
    """
    import copy as _copy_mod

    return _copy_mod.deepcopy(base)


def save(config: "Config") -> bool:
    """Write the in-memory config back to config.toml. U45: setting changes
    (apply_setting/_switch_engine no-session path) used to live and die in
    memory — defaults reverted on every restart. Returns success."""
    import tomllib as _tomllib  # noqa: F401  (symmetric import for readers)

    path = paths.CONFIG_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for section, values in config.data.items():
            if not isinstance(values, dict):
                continue
            lines.append(f"[{section}]")
            for key, value in values.items():
                lines.append(f"{key} = {_toml_value(value)}")
            lines.append("")
        temp = path.with_suffix(".tmp")
        temp.write_text("\n".join(lines))
        temp.replace(path)
        return True
    except OSError:
        return False


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return '"{}"'.format(str(value).replace('"', '\\"'))
