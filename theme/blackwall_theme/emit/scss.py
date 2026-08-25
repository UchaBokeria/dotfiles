"""eww's SCSS tokens.

eww compiles SCSS before handing the result to GTK, so unlike plain GTK CSS it
can carry lengths, shadows and font stacks as variables too. That makes this
the one target where the whole token set survives intact, so the eww widgets
never spell a radius or a shadow themselves.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header

_COLOURS = (
    "bg", "fg", "accent",
    "glass_hi", "glass", "glass_lo",
    "thin_hi", "thin", "thin_lo", "scrim",
    "rim", "rim_top", "rim_bottom", "edge",
    "raised_hi", "raised_lo", "sunken", "sunken_deep", "hover",
    "muted", "faint", "on_accent",
    "accent_hi", "accent_lo", "accent_edge", "accent_deep",
    "link", "link_edge",
    "warn", "warn_hi", "warn_edge", "bad", "bad_hi", "bad_edge", "good",
)

_LENGTHS = (
    "r_window", "r_lg", "r_md", "r_sm", "r_pill",
    "lift_soft", "lift", "lift_high", "drop",
    "font_ui", "font_mono", "font_icon",
    "t_xs", "t_sm", "t_md", "t_lg", "t_xl",
    "ease", "quick", "normal", "slow",
)


def eww(tokens: Tokens) -> str:
    lines = [header(tokens=tokens)]

    lines.append("\n// ---- colours ----")
    width = max(len(n) for n in _COLOURS)
    for name in _COLOURS:
        lines.append(f"${name:<{width}}: {getattr(tokens, name).css};")

    lines.append("\n// ---- geometry, depth, type, motion ----")
    width = max(len(n) for n in _LENGTHS)
    for name in _LENGTHS:
        value = getattr(tokens, name)
        # Font stacks already carry their own quotes; wrapping again would
        # produce a nested-quote literal that SCSS passes straight to GTK.
        lines.append(f"${name:<{width}}: {value};")

    lines.append(
        "\n// ---- composites ----\n"
        "// The standard glass fill and rim, so no widget re-spells them.\n"
        f"$glass_fill: {tokens.gradient()};\n"
        f"$thin_fill: {tokens.gradient(thin=True)};\n"
        f"$ring: {tokens.ring().replace(chr(10) + '    ', ' ')};\n"
        f"$ring_lift: {tokens.ring(tokens.lift).replace(chr(10) + '    ', ' ')};\n"
        f"$ring_high: "
        f"{tokens.ring(tokens.lift_high).replace(chr(10) + '    ', ' ')};\n"
        f"$ring_drop: {tokens.ring(tokens.drop).replace(chr(10) + '    ', ' ')};"
    )

    # eww's SCSS build treats every top-level file as a module; the widgets
    # `@import` this one, so it must end with a newline or the next import
    # statement is glued onto the last declaration.
    return "\n".join(lines) + "\n"
