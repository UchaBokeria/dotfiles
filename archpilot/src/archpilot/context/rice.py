"""A compact description of this machine, for the system prompt.

Kept deliberately small. It rides in `--append-system-prompt`, which sits in the
prompt-cached prefix, so it is paid for once per session rather than per turn -
but a long block still crowds the real instructions and dilutes them. The bar
for a line here is: the model would otherwise guess wrong, and guessing wrong
costs a tool call.

Versions are read live rather than hardcoded so this cannot go stale.
"""

from __future__ import annotations

import platform
import shutil
import subprocess

from .. import paths


def _version(binary: str, *args: str) -> str:
    if not shutil.which(binary):
        return ""
    try:
        out = subprocess.run([binary, *args], capture_output=True, text=True,
                             timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    text = (out.stdout or out.stderr).strip().splitlines()
    if not text:
        return ""
    import re
    found = re.search(r"\d+\.\d+(\.\d+)?", text[0])
    return found.group(0) if found else ""


def _present(*names: str) -> list[str]:
    return [n for n in names if shutil.which(n)]


def describe() -> str:
    hypr = _version("hyprctl", "version")
    eww = _version("eww", "--version")
    tools = _present("wallust", "swaync", "waybar", "rofi", "kitty", "hyprlock",
                     "hypridle", "thunar", "nvim", "tmux", "fish")

    return f"""\
<machine>
Arch Linux, kernel {platform.release()}, Wayland/Hyprland {hypr or "?"}. Shell: fish.
Rice lives in {paths.DOTFILES} (git repo, "blackwall"), symlinked into ~/.config.
  hypr/lua/  the live config (hyprland.lua loads it; keybinds/rules/glass/env/settings/animations).
    Lua: `hyprctl dispatch` takes an hl.dsp.… expression, never legacy .conf syntax.
    The old hypr/hyprland.conf + configs/ tree is a login fallback only.
  eww/  eww {eww or "?"} panels: control centre, network, audio, calendar, clocks, notifications.
  waybar/  bar (variants via waybar/variant) + modules/*.json + style.css
  rofi/  launchers under rofi/blackwall/ sharing the generated rofi/shared/blackwall.rasi
  swaync/  notification daemon (mako is masked)   fish/  kitty/  nvim/  tmux/
  wallpapers/  scripts/  theme/blackwall_theme/ (token generator: NEVER hardcode colours/radii)
Theme tokens come from theme/blackwall-theme (tokens.py is the source of truth);
generated token files are outputs, never edited by hand.
Present: {", ".join(tools)}.
Prefer hyprctl/systemctl --user/pacman. Edits under the rice are git-tracked and
auto-committed, so they are revertable; edits elsewhere are not.
</machine>"""
