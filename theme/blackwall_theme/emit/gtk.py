"""GTK CSS targets: waybar, wlogout, and the GTK3/GTK4 application themes.

GTK's CSS parser only has one kind of variable - `@define-color` - and it holds
colours and nothing else. Lengths and shadows cannot be passed through it, so
only colours are generated here; the radius scale and the depth steps live as
literals in the hand-written stylesheets.

That split is safe because it follows a real distinction: colours change with
every wallpaper, whereas the radius scale and shadow steps are design constants
that never do. `blackwall-theme check` guards the one risk it introduces, by
failing if a stylesheet uses a radius outside the scale.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header

#: (name, attribute) pairs. Order is grouped for readability in the output.
COLOURS = (
    ("Base palette", (
        ("bw_bg", "bg"),
        ("bw_fg", "fg"),
        ("bw_accent", "accent"),
    )),
    ("Glass - panels", (
        ("bw_glass_hi", "glass_hi"),
        ("bw_glass", "glass"),
        ("bw_glass_lo", "glass_lo"),
    )),
    ("Glass - the bar (thinner: perceived opacity scales with area)", (
        ("bw_thin_hi", "thin_hi"),
        ("bw_thin", "thin"),
        ("bw_thin_lo", "thin_lo"),
        ("bw_scrim", "scrim"),
    )),
    ("Rim - always an inset ring, never a border", (
        ("bw_rim", "rim"),
        ("bw_rim_top", "rim_top"),
        ("bw_rim_bottom", "rim_bottom"),
        ("bw_edge", "edge"),
    )),
    ("Surfaces within a panel", (
        ("bw_raised_hi", "raised_hi"),
        ("bw_raised_lo", "raised_lo"),
        ("bw_sunken", "sunken"),
        ("bw_sunken_deep", "sunken_deep"),
        ("bw_hover", "hover"),
    )),
    ("Text", (
        ("bw_muted", "muted"),
        ("bw_faint", "faint"),
        ("bw_on_accent", "on_accent"),
    )),
    ("Accent family", (
        ("bw_accent_hi", "accent_hi"),
        ("bw_accent_lo", "accent_lo"),
        ("bw_accent_edge", "accent_edge"),
        ("bw_accent_deep", "accent_deep"),
        ("bw_link", "link"),
        ("bw_link_edge", "link_edge"),
    )),
    ("Status - fixed, never palette-derived", (
        ("bw_warn", "warn"),
        ("bw_warn_hi", "warn_hi"),
        ("bw_warn_edge", "warn_edge"),
        ("bw_bad", "bad"),
        ("bw_bad_hi", "bad_hi"),
        ("bw_bad_edge", "bad_edge"),
        ("bw_good", "good"),
    )),
)


def _defines(tokens: Tokens) -> str:
    out = []
    for group, entries in COLOURS:
        out.append(f"\n/* {group} */")
        width = max(len(name) for name, _ in entries)
        for name, attr in entries:
            value = getattr(tokens, attr)
            out.append(f"@define-color {name:<{width}} {value.css};")
    return "\n".join(out)


def waybar(tokens: Tokens) -> str:
    """waybar/tokens.css - imported by waybar/style.css."""
    return header(tokens=tokens) + _defines(tokens) + "\n"


def wlogout(tokens: Tokens) -> str:
    """wlogout/colors/tokens.css - imported by wlogout/style.css."""
    return header(tokens=tokens) + _defines(tokens) + "\n"


def gtk3(tokens: Tokens) -> str:
    """~/.themes/wallust/gtk-3.0/colors.css - the Thunar-facing app theme.

    Content windows are solid here on purpose. The rice's glass lives in the
    chrome layer; an opaque file manager keeps its text crisp and its icons
    legible, which is how macOS splits it too.
    """
    t = tokens
    body = f"""
/* Foreground / text */
@define-color theme_fg_color        {t.fg.hex6};
@define-color theme_text_color      {t.fg.hex6};
@define-color fg_color              {t.fg.hex6};
@define-color text_color            {t.fg.hex6};

/* Backgrounds. Solid: this is a content window, not chrome. */
@define-color theme_bg_color        {t.bg.hex6};
@define-color bg_color              {t.bg.hex6};
@define-color theme_base_color      {t.bg.mix(t.fg, 0.04).hex6};
@define-color base_color            {t.bg.mix(t.fg, 0.04).hex6};
@define-color content_view_bg       {t.bg.hex6};
@define-color text_view_bg          {t.bg.hex6};
@define-color card_bg_color         {t.bg.mix(t.fg, 0.07).hex6};
@define-color popover_bg_color      {t.bg.mix(t.fg, 0.09).hex6};
@define-color headerbar_bg_color    {t.bg.mix(t.fg, 0.06).hex6};
@define-color sidebar_bg_color      {t.bg.mix(t.fg, 0.03).hex6};

/* Selection */
@define-color theme_selected_bg_color   {t.accent.hex6};
@define-color theme_selected_fg_color   {t.on_accent.hex6};
@define-color selected_bg_color         {t.accent.hex6};
@define-color selected_fg_color         {t.on_accent.hex6};
@define-color accent_bg_color           {t.accent.hex6};
@define-color accent_fg_color           {t.on_accent.hex6};
@define-color accent_color              {t.accent.hex6};

/* Unfocused */
@define-color theme_unfocused_fg_color    {t.muted.css};
@define-color theme_unfocused_text_color  {t.fg.hex6};
@define-color theme_unfocused_bg_color    {t.bg.hex6};
@define-color theme_unfocused_base_color  {t.bg.hex6};
@define-color unfocused_fg_color          {t.muted.css};
@define-color unfocused_text_color        {t.fg.hex6};
@define-color unfocused_bg_color          {t.bg.hex6};
@define-color unfocused_base_color        {t.bg.hex6};
@define-color unfocused_selected_bg_color {t.accent.mix(t.bg, 0.25).hex6};
@define-color unfocused_selected_fg_color {t.on_accent.hex6};

/* Disabled */
@define-color insensitive_fg_color   {t.faint.css};
@define-color insensitive_bg_color   {t.bg.hex6};
@define-color insensitive_base_color {t.bg.hex6};

/* Borders */
@define-color borders           {t.edge.css};
@define-color unfocused_borders {t.fg.alpha(9).css};

/* Semantic - fixed, so a red wallpaper cannot hide an error */
@define-color warning_color {t.warn.hex6};
@define-color error_color   {t.bad.hex6};
@define-color success_color {t.good.hex6};
@define-color link_color    {t.link.hex6};
@define-color focus_color   {t.accent.hex6};

/* WM-exported */
@define-color wm_title            {t.fg.hex6};
@define-color wm_unfocused_title  {t.muted.css};
@define-color wm_highlight        {t.rim.css};
@define-color wm_border           {t.edge.css};
@define-color wm_shadow           rgba(0, 0, 0, 0.35);
"""
    return header(tokens=tokens) + body


def gtk4(tokens: Tokens) -> str:
    """~/.config/gtk-4.0/colors.css - libadwaita's named colour set.

    GTK4 apps read a different set of names from GTK3, so this is not the same
    file with a different path. Anything left undefined falls back to Adwaita's
    stock dark palette, which would sit visibly off-key next to the rest.
    """
    t = tokens
    body = f"""
@define-color window_bg_color      {t.bg.hex6};
@define-color window_fg_color      {t.fg.hex6};
@define-color view_bg_color        {t.bg.mix(t.fg, 0.04).hex6};
@define-color view_fg_color        {t.fg.hex6};
@define-color headerbar_bg_color   {t.bg.mix(t.fg, 0.06).hex6};
@define-color headerbar_fg_color   {t.fg.hex6};
@define-color headerbar_border_color {t.edge.css};
@define-color headerbar_backdrop_color {t.bg.hex6};
@define-color popover_bg_color     {t.bg.mix(t.fg, 0.09).hex6};
@define-color popover_fg_color     {t.fg.hex6};
@define-color card_bg_color        {t.raised_hi.css};
@define-color card_fg_color        {t.fg.hex6};
@define-color dialog_bg_color      {t.bg.mix(t.fg, 0.06).hex6};
@define-color dialog_fg_color      {t.fg.hex6};
@define-color sidebar_bg_color     {t.bg.mix(t.fg, 0.03).hex6};
@define-color sidebar_fg_color     {t.fg.hex6};
@define-color sidebar_border_color {t.edge.css};
@define-color sidebar_backdrop_color {t.bg.hex6};

@define-color accent_bg_color      {t.accent.hex6};
@define-color accent_fg_color      {t.on_accent.hex6};
@define-color accent_color         {t.accent.hex6};

@define-color destructive_bg_color {t.bad.hex6};
@define-color destructive_fg_color {t.bg.hex6};
@define-color destructive_color    {t.bad.hex6};
@define-color success_bg_color     {t.good.hex6};
@define-color success_fg_color     {t.bg.hex6};
@define-color success_color        {t.good.hex6};
@define-color warning_bg_color     {t.warn.hex6};
@define-color warning_fg_color     {t.bg.hex6};
@define-color warning_color        {t.warn.hex6};
@define-color error_bg_color       {t.bad.hex6};
@define-color error_fg_color       {t.bg.hex6};
@define-color error_color          {t.bad.hex6};

@define-color borders              {t.edge.css};
@define-color shade_color          rgba(0, 0, 0, 0.36);
@define-color scrollbar_outline_color {t.rim.css};
"""
    return header(tokens=tokens) + body
