"""Read the wallpaper palette that wallust produced.

wallust owns colour *extraction*; this package owns colour *derivation*. The
boundary between them is a single JSON file that wallust writes from a template
(`wallust/templates/palette.json`), so there is one agreed handoff rather than
each consumer parsing whatever generated file it happens to like.

Three fallbacks sit behind that, because the rice has to render on a machine
where setwall has never run:

  1. the handoff file, if wallust has written it,
  2. wallust's own cache, which holds the same JSON under a wallpaper-derived
     directory name,
  3. `eww/colors.scss`, which has only bg/fg/accent but has been the de-facto
     source for archpilot and is always present,
  4. a built-in palette, so a fresh checkout still themes.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .color import Colour

ROOT = Path(__file__).resolve().parent.parent.parent
HANDOFF = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "blackwall" / "palette.json"
WALLUST_CACHE = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "wallust"
EWW_COLORS = ROOT / "eww" / "colors.scss"

#: Last resort. The rice's own colours, so a checkout with no wallpaper set
#: still renders as blackwall rather than as unstyled grey.
BUILTIN = {
    "background": "#15121B",
    "foreground": "#FBFAFC",
    "cursor": "#D0D6DB",
    "color0": "#3D3A43",
    "color1": "#6397E2",
    "color2": "#A5B2BA",
    "color3": "#F4C8EB",
    "color4": "#BAEDFE",
    "color5": "#CFF3D7",
    "color6": "#F3F0F7",
    "color7": "#F1EFF3",
    "color8": "#A8A7AA",
    "color9": "#6397E2",
    "color10": "#A5B2BA",
    "color11": "#F4C8EB",
    "color12": "#BAEDFE",
    "color13": "#CFF3D7",
    "color14": "#F3F0F7",
    "color15": "#F1EFF3",
}

_SCSS_VAR = re.compile(r"^\s*\$(\w+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;?\s*$", re.M)


@dataclass(frozen=True)
class Palette:
    """The sixteen ANSI colours plus background, foreground and cursor."""

    background: Colour
    foreground: Colour
    cursor: Colour
    ansi: tuple[Colour, ...]
    source: str = "builtin"

    @property
    def bg(self) -> Colour:
        return self.background

    @property
    def fg(self) -> Colour:
        return self.foreground

    @property
    def accent(self) -> Colour:
        """color1 - what every existing template in this rice already uses."""
        return self.ansi[1]

    @property
    def accent2(self) -> Colour:
        return self.ansi[2]

    def __getitem__(self, index: int) -> Colour:
        return self.ansi[index]


def _from_mapping(data: dict, source: str) -> Palette:
    merged = {**BUILTIN, **{k: v for k, v in data.items() if v}}
    return Palette(
        background=Colour.parse(merged["background"]),
        foreground=Colour.parse(merged["foreground"]),
        cursor=Colour.parse(merged.get("cursor", merged["foreground"])),
        ansi=tuple(Colour.parse(merged[f"color{i}"]) for i in range(16)),
        source=source,
    )


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "background" in data else None


def _from_wallust_cache() -> tuple[dict, str] | None:
    """Find the freshest palette wallust cached.

    The cache is `~/.cache/wallust/<hash>_<ver>/<Backend>_<Space>_<Thresh>[_Palette]`.
    Only the small JSON files are palettes - the sibling `Full` file is a raw
    pixel dump that runs to hundreds of megabytes, so anything large is skipped
    without reading it.
    """
    if not WALLUST_CACHE.is_dir():
        return None
    candidates = []
    for path in WALLUST_CACHE.glob("*/*"):
        try:
            if not path.is_file() or path.stat().st_size > 8192:
                continue
        except OSError:
            continue
        candidates.append(path)
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        data = _read_json(path)
        if data:
            return data, f"wallust cache ({path.parent.name}/{path.name})"
    return None


def _from_eww_scss() -> tuple[dict, str] | None:
    """bg/fg/accent only - the rest fills in from BUILTIN."""
    try:
        text = EWW_COLORS.read_text()
    except OSError:
        return None
    found = dict(_SCSS_VAR.findall(text))
    if not {"bg", "fg", "accent"} <= found.keys():
        return None
    return (
        {
            "background": found["bg"],
            "foreground": found["fg"],
            "color1": found["accent"],
            "color9": found["accent"],
        },
        "eww/colors.scss",
    )


def load(explicit: Path | None = None) -> Palette:
    """Best available palette, with where it came from recorded on it."""
    if explicit is not None:
        data = _read_json(explicit)
        if data is None:
            raise SystemExit(f"not a wallust palette: {explicit}")
        return _from_mapping(data, str(explicit))

    data = _read_json(HANDOFF)
    if data:
        return _from_mapping(data, "wallust handoff")

    cached = _from_wallust_cache()
    if cached:
        return _from_mapping(*cached)

    scss = _from_eww_scss()
    if scss:
        return _from_mapping(*scss)

    return _from_mapping(BUILTIN, "builtin")
