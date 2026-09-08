"""whatsapp/theme.toml - the palette for the wa terminal client.

A TUI draws inside the terminal cell grid, so none of the glass tokens apply:
there is no compositor to blur behind us and no alpha to carry. What the
terminal does have is a background the emulator has already composited, which
is why every colour here is flattened with `.over(bg)` or taken as `.hex6`.
Handing a `#RRGGBBAA` to a TUI would render the alpha as a literal, or drop it
silently and show the colour at full strength - the same trap kitty and tmux
fall into, documented on `plain.py`.

The two bubble fills are decided here rather than in Go so that the chat's look
follows the wallpaper along with everything else, and so no colour literal has
to appear in the source.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header


def wa(tokens: Tokens) -> str:
    t = tokens
    p = t.palette
    ansi = "\n".join(f'  "{p[i].hex6}",' for i in range(16))
    return header("#", "", tokens=tokens) + f"""
bg        = "{t.bg.hex6}"
fg        = "{t.fg.hex6}"
accent    = "{t.accent.hex6}"
on_accent = "{t.on_accent.hex6}"
link      = "{t.link.hex6}"
muted     = "{t.muted.over(t.bg).hex6}"
faint     = "{t.faint.over(t.bg).hex6}"
cursor    = "{p.cursor.hex6}"

# Surfaces. Opaque for the reason in this module's docstring.
raised    = "{t.bg.mix(t.fg, 0.07).hex6}"
raised_hi = "{t.bg.mix(t.fg, 0.11).hex6}"
sunken    = "{t.bg.darken(0.35).hex6}"
edge      = "{t.bg.mix(t.fg, 0.16).hex6}"
selection = "{t.bg.mix(t.accent, 0.28).hex6}"

# Message bubbles. Yours carries the accent so the conversation reads at a
# glance; theirs is a neutral raised surface, one step off the background.
bubble_mine   = "{t.bg.mix(t.accent, 0.22).hex6}"
bubble_theirs = "{t.bg.mix(t.fg, 0.07).hex6}"

warn = "{t.warn.hex6}"
bad  = "{t.bad.hex6}"
good = "{t.good.hex6}"

ansi = [
{ansi}
]
"""
