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


def thunar(tokens: Tokens) -> str:
    """~/.themes/wallust/gtk-3.0/thunar.css - Thunar as a pane of glass.

    Imported from ~/.config/gtk-3.0/gtk.css, not from the theme, because
    user CSS outranks theme CSS at equal specificity. The theme underneath is
    Sweet (gtk-dark.css), which paints every container an opaque navy and
    underlines tabs in its own teal. That teal belongs to no wallpaper.

    The split follows Finder: the chrome (sidebar, toolbar, status line) is
    thin glass that hyprglass frosts from behind (Thunar is tagged
    hyprglass_enabled in hypr/lua/glass.lua), and the file view is a denser
    sheet on top of it, so file names stay crisp over any wallpaper. Every
    selector is scoped to `window.thunar`, the style class Thunar puts on its
    main window, so no other GTK3 app changes. The one exception is menus:
    Thunar's context menu is a window of its own and cannot be scoped.
    """
    t = tokens
    # Thin enough for the glass to be the surface rather than a tint behind an
    # opaque panel: hyprglass bends and frosts what is behind the window, and
    # at 52/72 percent fill almost none of that reached the eye. The file view
    # stays the denser of the two - names are read at a glance - but both are
    # now light enough to show the refraction at the rim.
    chrome = t.bg.alpha(34).css
    sheet = t.bg.alpha(56).css
    menu = t.bg.alpha(86).css
    body = f"""
/* ---- one pane of glass: every container paints nothing of its own ---- */
window.thunar,
window.thunar.background {{
    background-color: {chrome};
    color: {t.fg.css};
    font-family: {t.font_ui};
}}
window.thunar menubar,
window.thunar toolbar,
window.thunar .toolbar,
window.thunar statusbar,
window.thunar paned,
window.thunar notebook,
window.thunar notebook > header,
window.thunar notebook > stack,
window.thunar notebook > stack:not(:only-child),
window.thunar scrolledwindow,
window.thunar viewport,
window.thunar viewport.frame,
window.thunar .sidebar,
window.thunar .sidebar .view,
window.thunar box {{
    background-color: transparent;
    background-image: none;
    border-color: transparent;
    box-shadow: none;
}}

/* ---- the file view: a denser sheet, for legibility ---- */
window.thunar notebook > stack .view,
window.thunar notebook > stack iconview,
window.thunar notebook > stack treeview.view {{
    background-color: {sheet};
    color: {t.fg.css};
}}
window.thunar treeview.view header button {{
    background: transparent;
    color: {t.muted.css};
    border: none;
    box-shadow: inset 0 -1px 0 {t.edge.css};
    font-size: {t.t_sm};
    padding: 6px 12px;
}}
window.thunar treeview.view header button:hover {{ color: {t.fg.css}; }}

/* Keyboard selection: accent fill, like every launcher row in the rice. */
window.thunar .view:selected,
window.thunar iconview:selected,
window.thunar .view:selected:focus,
window.thunar iconview:selected:focus {{
    background-color: {t.accent.css};
    color: {t.on_accent.css};
    border-radius: {t.r_md};
}}
window.thunar .view:selected:backdrop,
window.thunar iconview:selected:backdrop {{
    background-color: {t.accent_hi.css};
    color: {t.fg.css};
}}
window.thunar .view rubberband,
window.thunar rubberband {{
    background-color: {t.accent_lo.css};
    border: 1px solid {t.accent_edge.css};
    border-radius: {t.r_sm};
}}

/* The sidebar marks where you are, it does not "select": the checked-item
   style (accent tint), the same as an enabled row in the control centre. */
window.thunar .sidebar .view:selected,
window.thunar .sidebar .view:selected:focus,
window.thunar .sidebar .view:selected:backdrop {{
    background-color: {t.accent_lo.css};
    color: {t.fg.css};
}}

/* ---- tabs: pills, not Sweet's teal underline ---- */
window.thunar notebook > header {{
    padding: 4px 8px;
    border: none;
}}
window.thunar notebook > header > tabs > tab {{
    background: transparent;
    color: {t.muted.css};
    border: none;
    box-shadow: none;
    border-radius: {t.r_md};
    padding: 6px 12px;
    margin: 2px 3px;
    min-height: 0;
}}
window.thunar notebook > header > tabs > tab:hover {{
    background-color: {t.hover.css};
    color: {t.fg.css};
}}
/* The open tab is a checked item: accent tint and accent ring, the same as
   an enabled row in the control centre. A raised fill with a white rim made
   it look like a text field. */
window.thunar notebook > header > tabs > tab:checked {{
    background-color: {t.accent_lo.css};
    color: {t.fg.css};
    box-shadow: inset 0 0 0 1px {t.accent_edge.css};
}}
window.thunar notebook > header > tabs > tab button.flat {{
    min-width: 18px;
    min-height: 18px;
    padding: 0;
    border-radius: {t.r_pill};
}}

/* ---- toolbar and path ---- */
window.thunar toolbar button,
window.thunar .toolbar button,
window.thunar toolbutton > button,
window.thunar .path-bar button,
window.thunar .linked > button {{
    background: transparent;
    color: {t.fg.css};
    border: none;
    box-shadow: none;
    border-radius: {t.r_md};
    padding: 6px 8px;
}}
window.thunar toolbar button:hover,
window.thunar .toolbar button:hover,
window.thunar toolbutton > button:hover,
window.thunar .path-bar button:hover,
window.thunar .linked > button:hover {{
    background-color: {t.hover.css};
}}
window.thunar toolbar button:checked,
window.thunar toolbar button:active,
window.thunar .path-bar button:checked,
window.thunar .linked > button:checked {{
    background-color: {t.raised_hi.css};
    box-shadow: inset 0 0 0 1px {t.rim.css};
}}
window.thunar entry {{
    background-color: {t.sunken.css};
    color: {t.fg.css};
    border: none;
    border-radius: {t.r_md};
    box-shadow: inset 0 0 0 1px {t.edge.css};
    padding: 6px 12px;
    min-height: 0;
    caret-color: {t.accent.css};
}}
window.thunar entry:focus {{ box-shadow: inset 0 0 0 1px {t.accent_edge.css}; }}
window.thunar entry selection {{
    background-color: {t.accent.css};
    color: {t.on_accent.css};
}}

/* ---- the edges between the parts: hairlines, not borders ---- */
window.thunar paned > separator {{
    background-color: {t.edge.css};
    background-image: none;
    min-width: 1px;
    min-height: 1px;
    border: none;
}}
window.thunar statusbar {{
    padding: 4px 12px;
    box-shadow: inset 0 1px 0 {t.edge.css};
}}
window.thunar statusbar,
window.thunar statusbar label {{
    color: {t.muted.css};
    font-size: {t.t_sm};
}}

window.thunar scrollbar,
window.thunar scrollbar trough {{
    background: transparent;
    border: none;
}}
window.thunar scrollbar slider {{
    background-color: {t.faint.css};
    border: none;
    border-radius: {t.r_pill};
    min-width: 5px;
    min-height: 5px;
    margin: 2px;
}}
window.thunar scrollbar slider:hover {{ background-color: {t.muted.css}; }}

window.thunar *:focus {{
    outline-color: {t.accent_edge.css};
    -gtk-outline-radius: {t.r_md};
}}

/* ---- menus, in every GTK3 app ---- */
menu,
.menu,
.context-menu {{
    background-color: {menu};
    color: {t.fg.css};
    border: none;
    border-radius: {t.r_md};
    padding: 6px;
    box-shadow: inset 0 0 0 1px {t.rim.css};
}}
menu menuitem {{
    border-radius: {t.r_sm};
    padding: 6px 10px;
    min-height: 0;
}}
menu menuitem:hover {{
    background-color: {t.accent.css};
    color: {t.on_accent.css};
}}
menu menuitem:hover label,
menu menuitem:hover accelerator {{
    color: {t.on_accent.css};
}}
menu separator {{
    background-color: {t.edge.css};
    min-height: 1px;
    margin: 4px 6px;
}}
.csd.popup decoration,
window.popup decoration {{
    border-radius: {t.r_md};
    box-shadow: {t.lift};
}}
"""
    return header(tokens=tokens) + body
