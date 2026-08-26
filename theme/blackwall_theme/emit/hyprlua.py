"""Hyprland's palette, as a Lua module.

Hyprland 0.57 drops the `.conf` format for Lua. The colours have to cross that
boundary the same way they do everywhere else - generated from the tokens, not
retyped - so this emits a table the config `require`s:

    local bw = require("colors")
    hl.config({ general = { col = { active_border = bw.border_active } } })

Hyprland spells a colour `rgba(RRGGBBAA)` in both formats, so the literals are
unchanged from the .conf emitter; only the wrapper differs.
"""

from __future__ import annotations

from ..color import Colour
from ..tokens import Tokens
from . import header


def _rgba(colour: Colour) -> str:
    return f"rgba({colour.hex8.lstrip('#').lower()})"


def _rgb(colour: Colour) -> str:
    return f"rgb({colour.hex6.lstrip('#').lower()})"


def hyprlua(tokens: Tokens) -> str:
    t = tokens
    active_a = t.accent.alpha(85)
    active_b = t.accent.mix(t.link, 0.85).alpha(85)
    ease = t.ease.removeprefix("cubic-bezier(").removesuffix(")")
    points = [p.strip() for p in ease.split(",")]

    return header("--", "", tokens=tokens) + f"""
return {{
  bg     = "{_rgb(t.bg)}",
  fg     = "{_rgb(t.fg)}",
  accent = "{_rgb(t.accent)}",
  link   = "{_rgb(t.link)}",
  warn   = "{_rgb(t.warn)}",
  bad    = "{_rgb(t.bad)}",

  -- The active border runs accent -> link so it reads as one lit edge rather
  -- than a flat outline. 45deg puts the light top-left, matching the glass.
  border_active = {{ colors = {{ "{_rgba(active_a)}", "{_rgba(active_b)}" }}, angle = 45 }},
  border_inactive = "{_rgba(t.fg.alpha(9))}",

  shadow          = "{_rgba(t.bg.darken(0.55).alpha(62))}",
  shadow_inactive = "{_rgba(t.bg.darken(0.55).alpha(38))}",

  group_active   = "{_rgba(t.accent.alpha(90))}",
  group_inactive = "{_rgba(t.fg.alpha(14))}",
  group_locked   = "{_rgba(t.warn.alpha(90))}",

  -- The motion curve every surface shares, as bezier control points.
  ease = {{ {{ {points[0]}, {points[1]} }}, {{ {points[2]}, {points[3]} }} }},
}}
"""
