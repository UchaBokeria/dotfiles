"""rofi's shared theme.

rofi's rasi format has real variables that hold any value type, so this file
carries the whole token set - colours, radii, padding and fonts. The three
launcher layouts then contain nothing but layout.

rofi cannot blur behind itself; that is the compositor's job, via
`layerrule = blur on, match:namespace rofi`. What rofi contributes is the
translucent fill for the blur to show through, which is why `transparency:
"real"` and an alpha-carrying background are both required - either one alone
gives a solid panel.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header

_COLOURS = (
    ("bw-bg", "bg"),
    ("bw-fg", "fg"),
    ("bw-accent", "accent"),
    ("bw-glass-hi", "glass_hi"),
    ("bw-glass", "glass"),
    ("bw-glass-lo", "glass_lo"),
    ("bw-scrim", "scrim"),
    ("bw-rim", "rim"),
    ("bw-rim-top", "rim_top"),
    ("bw-edge", "edge"),
    ("bw-raised-hi", "raised_hi"),
    ("bw-raised-lo", "raised_lo"),
    ("bw-sunken", "sunken"),
    ("bw-hover", "hover"),
    ("bw-muted", "muted"),
    ("bw-faint", "faint"),
    ("bw-on-accent", "on_accent"),
    ("bw-accent-hi", "accent_hi"),
    ("bw-accent-lo", "accent_lo"),
    ("bw-accent-edge", "accent_edge"),
    ("bw-link", "link"),
    ("bw-warn", "warn"),
    ("bw-bad", "bad"),
)

_LENGTHS = (
    ("bw-r-lg", "r_lg"),
    ("bw-r-md", "r_md"),
    ("bw-r-sm", "r_sm"),
    ("bw-r-pill", "r_pill"),
)


def rofi(tokens: Tokens) -> str:
    t = tokens
    lines = [header(tokens=tokens), "* {"]

    width = max(len(n) for n, _ in (*_COLOURS, *_LENGTHS)) + 1
    lines.append("    /* colours */")
    for name, attr in _COLOURS:
        # rofi understands #RRGGBBAA directly and renders it more predictably
        # than its own rgba() spelling, which some builds round differently.
        lines.append(f"    {name + ':':<{width}} {getattr(t, attr).hex8};")

    lines.append("\n    /* geometry */")
    for name, attr in _LENGTHS:
        lines.append(f"    {name + ':':<{width}} {getattr(t, attr)};")

    lines.append(f"""
    /* The names the adi1090x layouts already reference, mapped onto the
       tokens above so those files need no colour edits of their own. */
    background:          @bw-glass;
    background-alt:      @bw-raised-hi;
    foreground:          @bw-fg;
    selected:            @bw-accent;
    active:              @bw-link;
    urgent:              @bw-bad;

    background-color:    transparent;
    text-color:          @bw-fg;
    font:                "Inter 11";
}}

/*****----- the shared glass shell -----*****/
/* Layouts import this file and then override only geometry. Anything that
   decides how the surface *looks* belongs here and nowhere else. */

window {{
    /* "real" so the corners are round rather than composited against black -
       but the surface itself is opaque.
       
       It was @bw-glass, 68% alpha over the compositor's blur, which is the
       same frosted treatment every panel gets. It is blurred correctly; the
       problem is what it is for. A launcher is a list of words read at speed,
       often over a busy wallpaper, and a third of the wallpaper coming
       through costs legibility that the panels - which hold shapes and
       numbers, not dense text - can afford to spend. Solid here, glass
       everywhere else. */
    transparency:     "real";
    background-color: @bw-bg;
    border:           0px;
    border-radius:    {t.r_lg};
    border-color:     @bw-rim;
    padding:          18px;
    cursor:           "default";
}}

mainbox {{
    background-color: transparent;
    spacing:          12px;
    padding:          0px;
}}

inputbar {{
    background-color: @bw-sunken;
    text-color:       @bw-fg;
    border-radius:    {t.r_md};
    padding:          10px 13px;
    spacing:          10px;
    children:         [ "prompt", "entry" ];
}}

prompt {{
    background-color: transparent;
    text-color:       @bw-accent;
}}

entry {{
    background-color: transparent;
    text-color:       @bw-fg;
    cursor:           text;
    placeholder:      "search";
    placeholder-color: @bw-faint;
}}

listview {{
    background-color: transparent;
    text-color:       @bw-fg;
    spacing:          4px;
    cycle:            true;
    /* Centred, so the wheel slides the list under a fixed selection instead of
       stepping the highlight down one row at a time. rofi has no way to move
       the view without moving the selection - the listview always keeps the
       selection visible - so this is the closest it gets to scrolling. */
    scroll-method:    1;
    dynamic:          true;
    scrollbar:        true;
    cursor:           "default";
}}

scrollbar {{
    handle-width:     5px;
    handle-color:     @bw-faint;
    background-color: transparent;
    border-radius:    {t.r_pill};
}}

element {{
    background-color: transparent;
    text-color:       @bw-fg;
    border-radius:    {t.r_md};
    padding:          9px 11px;
    spacing:          10px;
    cursor:           pointer;
}}

element normal.normal    {{ background-color: transparent;    text-color: @bw-fg;       }}
element alternate.normal {{ background-color: transparent;    text-color: @bw-fg;       }}
element normal.active    {{ background-color: @bw-accent-lo;  text-color: @bw-link;     }}
element alternate.active {{ background-color: @bw-accent-lo;  text-color: @bw-link;     }}
element normal.urgent    {{ background-color: @bw-bad;        text-color: @bw-bg;       }}
element alternate.urgent {{ background-color: @bw-bad;        text-color: @bw-bg;       }}
element selected.normal  {{ background-color: @bw-accent;     text-color: @bw-on-accent; }}
element selected.active  {{ background-color: @bw-accent;     text-color: @bw-on-accent; }}
element selected.urgent  {{ background-color: @bw-bad;        text-color: @bw-bg;       }}

element-icon {{
    background-color: transparent;
    text-color:       inherit;
    size:             22px;
    cursor:           inherit;
}}

element-text {{
    background-color: transparent;
    text-color:       inherit;
    highlight:        inherit;
    cursor:           inherit;
    vertical-align:   0.5;
    horizontal-align: 0.0;
}}

message {{
    background-color: transparent;
    padding:          0px;
}}

textbox {{
    background-color: @bw-raised-lo;
    text-color:       @bw-muted;
    border-radius:    {t.r_md};
    padding:          10px 12px;
    vertical-align:   0.5;
    markup:           true;
}}

error-message {{
    background-color: @bw-glass;
    text-color:       @bw-fg;
    border-radius:    {t.r_md};
    padding:          12px;
}}

mode-switcher {{
    background-color: transparent;
    spacing:          8px;
}}

button {{
    background-color: @bw-raised-lo;
    text-color:       @bw-muted;
    border-radius:    {t.r_md};
    padding:          8px 16px;
    cursor:           pointer;
}}

button selected {{
    background-color: @bw-accent;
    text-color:       @bw-on-accent;
}}
""")
    return "\n".join(lines)
