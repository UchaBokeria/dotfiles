"""Targets with no import mechanism, where the generator owns the whole file.

mako, cava, kitty, nvim and tmux all read a flat key/value file and none of them
can include another one. Splitting a hand-written half from a generated half is
therefore impossible, so the generator writes them outright. Nothing is lost:
these files carry no layout, only values.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header


def mako(tokens: Tokens) -> str:
    """mako/config - notification banners.

    Glass here comes from two halves that only work together: an alpha-carrying
    `background-color` (this file) and `layerrule = blur on, match:namespace
    notifications` (hypr/configs/windowrules.conf). Alpha alone shows the raw
    wallpaper; the layerrule alone has nothing translucent to blur.

    Urgency is carried by the border rather than the fill, so a critical
    notification stays as readable as a normal one instead of being tinted.
    """
    t = tokens
    return header("#", "", tokens=tokens) + f"""
font={t.font_ui.split(',')[0].strip('"')} 11
width=380
height=150
margin=14
padding=14
border-size=1
border-radius=18
default-timeout=6000
ignore-timeout=0
layer=overlay
anchor=top-right
max-icon-size=48
icon-location=left
markup=1
actions=1
history=1
max-visible=5

background-color={t.glass.hex8}
text-color={t.fg.hex6}
border-color={t.rim.hex8}
progress-color=over {t.accent_lo.hex8}

[grouped]
background-color={t.glass_hi.hex8}

[urgency=low]
text-color={t.muted.hex8}
border-color={t.edge.hex8}
default-timeout=4000

[urgency=normal]
border-color={t.rim.hex8}

[urgency=critical]
border-color={t.bad.hex6}
border-size=2
default-timeout=0

# A notification carrying an action has to outlive the default timeout, or the
# button disappears before you can reach it. blackwall-watch tags those with
# this category.
[category=blackwall-action]
default-timeout=0
border-color={t.accent_edge.hex8}

[mode=do-not-disturb]
invisible=1
"""


def cava(tokens: Tokens) -> str:
    """cava/config - the audio visualiser.

    A gradient from accent to link rather than a flat colour: the bars are the
    one place in the rice with enough vertical run for a gradient to read as
    anything but noise.
    """
    t = tokens
    ramp = [
        t.accent.mix(t.bg, 0.45),
        t.accent,
        t.accent.mix(t.link, 0.5),
        t.link,
        t.link.lighten(0.35),
    ]
    gradient = "\n".join(
        f"gradient_color_{i + 1} = '{c.hex6}'" for i, c in enumerate(ramp)
    )
    return header("#", "", tokens=tokens) + f"""
[general]
bars = 24
framerate = 60
autosens = 1

[input]
method = pipewire

[output]
alacritty_sync = 0

[color]
background = '{t.bg.hex6}'
foreground = '{t.accent.hex6}'
gradient = 1
gradient_count = {len(ramp)}
{gradient}

[smoothing]
monstercat = 0
noise_reduction = 55
"""


def kitty(tokens: Tokens) -> str:
    """kitty/colors.conf - the full sixteen, not the five wallust exported.

    The previous template emitted background, foreground and three colours, so
    the other thirteen came from `lovelace_colors.conf` and never followed the
    wallpaper. Anything ANSI-coloured in a terminal - ls, git diff, the fish
    prompt - was therefore off-palette by construction.

    Every colour here is opaque. kitty rejects `#RRGGBBAA` outright - it raises
    `Invalid color name` and refuses to start - so tokens that carry alpha are
    pre-composited against the background with `mix` instead.
    """
    t = tokens
    p = t.palette
    ansi = "\n".join(
        f"color{i:<3} {p[i].hex6}" for i in range(16)
    )
    return header("#", "", tokens=tokens) + f"""
background {t.bg.hex6}
foreground {t.fg.hex6}

cursor            {p.cursor.hex6}
cursor_text_color {t.bg.hex6}

selection_background {t.accent.hex6}
selection_foreground {t.on_accent.hex6}

url_color {t.link.hex6}

active_border_color   {t.accent.hex6}
inactive_border_color {t.edge.over(t.bg).hex6}
bell_border_color     {t.warn.hex6}

active_tab_background   {t.accent.hex6}
active_tab_foreground   {t.on_accent.hex6}
active_tab_font_style   bold
inactive_tab_background {t.bg.mix(t.fg, 0.08).hex6}
inactive_tab_foreground {t.muted.over(t.bg).hex6}
tab_bar_background      {t.bg.hex6}

mark1_foreground {t.bg.hex6}
mark1_background {t.accent.hex6}

{ansi}
"""


def nvim(tokens: Tokens) -> str:
    """nvim/lua/custom/blackwall_palette.lua - a table, not a colourscheme.

    Emitting a table rather than a full colourscheme keeps this out of the way
    of the ten schemes already in lua/custom/plugins/theme.lua: the switcher
    keeps working, and the blackwall scheme is one more entry in it that
    happens to follow the wallpaper.
    """
    t = tokens
    p = t.palette
    ansi = "\n".join(f"    [{i}] = '{p[i].hex6}'," for i in range(16))
    return header("--", "", tokens=tokens) + f"""
---@class BlackwallPalette
return {{
  bg        = '{t.bg.hex6}',
  fg        = '{t.fg.hex6}',
  accent    = '{t.accent.hex6}',
  on_accent = '{t.on_accent.hex6}',
  link      = '{t.link.hex6}',
  muted     = '{t.muted.over(t.bg).hex6}',
  faint     = '{t.faint.over(t.bg).hex6}',
  cursor    = '{p.cursor.hex6}',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '{t.bg.mix(t.fg, 0.07).hex6}',
  raised_hi = '{t.bg.mix(t.fg, 0.11).hex6}',
  sunken    = '{t.bg.darken(0.35).hex6}',
  edge      = '{t.bg.mix(t.fg, 0.16).hex6}',
  selection = '{t.bg.mix(t.accent, 0.28).hex6}',

  warn      = '{t.warn.hex6}',
  bad       = '{t.bad.hex6}',
  good      = '{t.good.hex6}',

  ansi = {{
{ansi}
  }},
}}
"""


def tmux(tokens: Tokens) -> str:
    """The blackwall block spliced into tmux/tmux.conf.local.

    tmux draws inside the terminal cell grid, so there is no glass here; what
    it can do is stop being the loudest thing on screen.

    This rice runs oh-my-tmux, which is read by *two* parsers: tmux itself for
    the commands, and a shell inside tmux.conf that expands the
    `tmux_conf_theme_*` variables to build the status line. That rules out both
    obvious integrations. Setting `status-style` directly loses, because the
    theme is applied afterwards and overwrites it. Putting the variables in a
    separate file and `source-file`-ing it also loses, twice over: tmux config
    variables do not cross a source-file boundary, and the shell half never
    sees a tmux command at all. The values have to be physically present in
    tmux.conf.local, which is why this one target is spliced in rather than
    written to a file of its own.
    """
    t = tokens
    bg = t.bg
    muted = t.muted.over(bg)
    faint = t.faint.over(bg)

    # oh-my-tmux's slot meanings, in its own numbering. Everything else in its
    # theme - pane borders, clock, mode, indicators - is derived from these.
    slots = (
        (1, bg, "background"),
        (2, bg.mix(t.fg, 0.09), "raised surface"),
        (3, muted, "secondary text"),
        (4, t.accent, "accent"),
        (5, t.warn, "warn"),
        (6, bg, "text on the accent"),
        (7, t.fg, "primary text"),
        (8, bg, "background"),
        (9, t.warn, "warn"),
        (10, t.link, "link"),
        (11, t.good, "good"),
        (12, faint, "faint text"),
        (13, t.fg, "primary text"),
        (14, bg, "background"),
        (15, bg, "background"),
        (16, t.bad, "bad"),
        (17, t.fg, "primary text"),
    )
    lines = [
        f'tmux_conf_theme_colour_{i}={c.hex6!r}'.replace("'", '"')
        + " " * (3 - len(str(i)))
        + f"  # {what}"
        for i, c, what in slots
    ]

    # The same palette again, as tmux *user options*. The shell variables above
    # only exist while oh-my-tmux is reading this file; user options live in
    # the server and resolve inside `#[fg=...]` at render time, which is what
    # lets the status-line variants in tmux/status/ be plain sourced files
    # instead of more shell-expanded assignments.
    named = (
        ("bg", bg), ("fg", t.fg), ("accent", t.accent),
        ("on_accent", t.on_accent), ("link", t.link),
        ("muted", muted), ("faint", faint),
        ("raised", bg.mix(t.fg, 0.09)), ("edge", bg.mix(t.fg, 0.16)),
        ("warn", t.warn), ("bad", t.bad), ("good", t.good),
    )
    lines.append("")
    lines += [f'set -g @bw_{name} "{c.hex6}"' for name, c in named]
    return "\n".join(lines) + "\n"
