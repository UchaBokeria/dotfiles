"""Per-surface emitters.

Each emitter turns the resolved `Tokens` into one file, in whatever syntax that
surface speaks. Two shapes exist, and which one a surface gets is decided by
the format rather than by taste:

  * **tokens only** - the surface's real stylesheet stays hand-written and
    `@import`s a generated file of values. Used wherever the format has an
    import mechanism: waybar, eww, wlogout, rofi, GTK.
  * **whole file** - the generator owns the file outright. Used where there is
    no import mechanism at all and the file is pure key/value anyway, so there
    is nothing to hand-tune: mako, cava, kitty, nvim, tmux.

A generated file always opens with `header()` so it is obvious in a diff that
editing it is pointless.
"""

from __future__ import annotations

from ..tokens import Tokens

BANNER = "blackwall design tokens - generated, do not edit"
SOURCE = "theme/blackwall_theme/tokens.py"


def header(comment: str = "/*", close: str = "*/", *, tokens: Tokens) -> str:
    """A do-not-edit banner in the target's own comment syntax.

    `comment` is either a block opener (with `close`) or a line-comment marker
    (pass close="").
    """
    lines = [
        BANNER,
        f"edit {SOURCE} and run `blackwall-theme` instead",
        f"palette: {tokens.palette.source}",
    ]
    if close:
        body = "\n   ".join(lines)
        return f"{comment} {body} {close}\n"
    return "".join(f"{comment} {line}\n" for line in lines)
