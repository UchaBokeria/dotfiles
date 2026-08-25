"""Hyprland's own colours.

Hyprland cannot read the token files - it has its own config language - but it
does have variables, so the generator writes a file of them and hyprland.conf
sources it. Without this the window border would be the only thing in the rice
that does not follow the wallpaper, which is exactly how it got left on
Hyprland's stock cyan-to-green demo gradient.

Hyprland spells colours `rgba(RRGGBBAA)` - no hash, no commas, alpha packed
into the same literal - so none of the `Colour` spellings fit and this module
has its own.
"""

from __future__ import annotations

from ..color import Colour
from ..tokens import Tokens
from . import header


def _rgba(colour: Colour) -> str:
    """Hyprland's literal: `rgba(6397e2cc)`."""
    return f"rgba({colour.hex8.lstrip('#').lower()})"


def _rgb(colour: Colour) -> str:
    return f"rgb({colour.hex6.lstrip('#').lower()})"


def hypr(tokens: Tokens) -> str:
    t = tokens
    # The active border runs accent -> link so it reads as one lit edge rather
    # than a flat outline, which is the same move as the specular top on every
    # glass surface. 45deg puts the light top-left, matching the 158deg fill.
    active_a = t.accent.alpha(85)
    active_b = t.accent.mix(t.link, 0.85).alpha(85)

    # The rice's motion curve, in Hyprland's spelling. Hyprland writes a bezier
    # as four bare numbers, so the `cubic-bezier(...)` wrapper is stripped
    # rather than a second curve being invented here. A window sliding across
    # the scrolling layout then settles exactly like a panel opening.
    ease_points = t.ease.removeprefix("cubic-bezier(").removesuffix(")")

    return header("#", "", tokens=tokens) + f"""
# The motion curve every surface uses, for `bezier = name, $bw_ease`.
$bw_ease   = {ease_points}

# Palette, for anything in hyprland.conf that needs a colour.
$bw_bg     = {_rgb(t.bg)}
$bw_fg     = {_rgb(t.fg)}
$bw_accent = {_rgb(t.accent)}
$bw_link   = {_rgb(t.link)}
$bw_warn   = {_rgb(t.warn)}
$bw_bad    = {_rgb(t.bad)}

# Window borders. The inactive edge is a bare hairline of the foreground -
# present enough to separate two tiled windows, quiet enough that a screen full
# of them does not read as a grid of outlines.
$bw_border_active   = {_rgba(active_a)} {_rgba(active_b)} 45deg
$bw_border_inactive = {_rgba(t.fg.alpha(9))}

# Shadows. Neutral black rather than tinted: a coloured shadow reads as a glow,
# and a glow is the thing that makes a rice look like a rice.
$bw_shadow          = {_rgba(t.bg.darken(0.75).alpha(62))}
$bw_shadow_inactive = {_rgba(t.bg.darken(0.75).alpha(38))}

# Group bars (SUPER+G).
$bw_group_active   = {_rgba(t.accent.alpha(90))}
$bw_group_inactive = {_rgba(t.fg.alpha(14))}
$bw_group_locked   = {_rgba(t.warn.alpha(90))}
"""
