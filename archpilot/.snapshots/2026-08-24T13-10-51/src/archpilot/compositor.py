"""Talking to Hyprland without depending on inherited environment.

The daemon is a systemd user service. Hyprland is not systemd-managed here, so
`graphical-session.target` is never reached and nothing guarantees the service
inherits HYPRLAND_INSTANCE_SIGNATURE or WAYLAND_DISPLAY - after a reboot the
daemon can be running with neither.

Both are discoverable: hyprland puts one socket directory per instance under
$XDG_RUNTIME_DIR/hypr, and the wayland socket sits in the runtime dir too.
Looking them up at call time means the daemon works whether it was started
before hyprland, after it, or across a compositor restart.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


def instance_signature() -> str:
    """The newest live hyprland instance, or "" if none is running."""
    if signature := os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        if (runtime_dir() / "hypr" / signature).exists():
            return signature
    root = runtime_dir() / "hypr"
    if not root.is_dir():
        return ""
    candidates = [d for d in root.iterdir() if d.is_dir() and (d / ".socket.sock").exists()]
    if not candidates:
        return ""
    newest = max(candidates, key=lambda d: d.stat().st_mtime)
    return newest.name


def wayland_display() -> str:
    if display := os.environ.get("WAYLAND_DISPLAY"):
        return display
    for candidate in sorted(runtime_dir().glob("wayland-*")):
        if candidate.is_socket():
            return candidate.name
    return "wayland-0"


def env() -> dict:
    """Environment additions that make hyprctl and GTK clients work."""
    extra = {"WAYLAND_DISPLAY": wayland_display(),
             "XDG_RUNTIME_DIR": str(runtime_dir())}
    if signature := instance_signature():
        extra["HYPRLAND_INSTANCE_SIGNATURE"] = signature
    return extra


def available() -> bool:
    return bool(instance_signature())


def dispatch(*args: str) -> None:
    """Fire a hyprctl dispatch, tolerating hyprland not being up yet."""
    if not available():
        return
    merged = {**os.environ, **env()}
    try:
        subprocess.Popen(["hyprctl", "dispatch", *args], env=merged,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def query(*args: str, timeout: float = 2.0) -> str:
    if not available():
        return ""
    merged = {**os.environ, **env()}
    try:
        out = subprocess.run(["hyprctl", *args], capture_output=True, text=True,
                             timeout=timeout, check=False, env=merged)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout
