"""Qt: qt6ct's palette and a Kvantum theme.

Qt is the one toolkit in this rice that was not themed at all. Two things were
wrong: `env.conf` set `QT_QFA_PLATFORMTHEME` - a typo for `QT_QPA_` - so
nothing was ever read, and qt6ct was not installed anyway.

Two layers, because Qt splits them:

* **qt6ct** supplies the *palette* - the twenty-one QPalette roles. On its own
  that gives correct colours in stock Fusion shapes: no glass, no matching
  radii.
* **Kvantum** supplies the *shapes* - an SVG-backed style engine that draws
  the widgets themselves, and can make its windows translucent and ask the
  compositor to blur behind them.

The Kvantum theme is derived from KvMojave rather than drawn from scratch.
That theme already ships `translucent_windows=true`, `blurring=true` and
`popup_blurring=true`, and its whole reason for existing is to look like
macOS - so the shapes are already the target and only the colours are wrong.
Generating an SVG widget set from nothing would be a project of its own for no
gain.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..color import Colour
from ..tokens import Tokens
from . import header

#: Base to derive from. Ships with the `kvantum` package.
KV_BASE = Path("/usr/share/Kvantum/KvMojave")
KV_NAME = "blackwall"


def _argb(colour: Colour) -> str:
    """Qt's palette spelling: #AARRGGBB."""
    alpha = round(colour.a * 255)
    return f"#{alpha:02x}{colour.r:02x}{colour.g:02x}{colour.b:02x}"


def qt6ct_colors(tokens: Tokens) -> str:
    """~/.config/qt6ct/colors/blackwall.conf - the twenty-one QPalette roles.

    Order is fixed by Qt and unlabelled in the file, so it is spelled out here
    once. Getting one wrong is not a crash - it just silently paints the wrong
    thing, which is far harder to spot than a parse error.
    """
    t = tokens
    base = t.bg.mix(t.fg, 0.04)
    button = t.bg.mix(t.fg, 0.10)

    roles = [
        ("WindowText", t.fg),
        ("Button", button),
        ("Light", t.bg.mix(t.fg, 0.20)),
        ("Midlight", t.bg.mix(t.fg, 0.15)),
        ("Dark", t.bg.darken(0.35)),
        ("Mid", t.bg.mix(t.fg, 0.12)),
        ("Text", t.fg),
        ("BrightText", t.warn),
        ("ButtonText", t.fg),
        ("Base", base),
        ("Window", t.bg),
        ("Shadow", t.bg.darken(0.75)),
        ("Highlight", t.accent),
        ("HighlightedText", t.on_accent),
        ("Link", t.link),
        ("LinkVisited", t.link.mix(t.bg, 0.35)),
        ("AlternateBase", t.bg.mix(t.fg, 0.06)),
        ("NoRole", t.bg),
        ("ToolTipBase", t.bg.mix(t.fg, 0.11)),
        ("ToolTipText", t.fg),
        ("PlaceholderText", t.faint.over(t.bg)),
    ]

    def row(transform) -> str:
        return ", ".join(_argb(transform(name, c)) for name, c in roles)

    active = row(lambda _n, c: c)
    inactive = row(
        lambda n, c: c if n not in ("Highlight", "WindowText", "Text")
        else c.mix(t.bg, 0.25)
    )
    disabled = row(
        lambda n, c: c.mix(t.bg, 0.55)
        if n in ("WindowText", "Text", "ButtonText", "Highlight", "Link")
        else c
    )

    names = "\n".join(f"#   {i:>2}  {n}" for i, (n, _) in enumerate(roles))
    return header("#", "", tokens=tokens) + f"""
# QPalette roles, in Qt's own fixed order:
{names}

[ColorScheme]
active_colors={active}
disabled_colors={disabled}
inactive_colors={inactive}
"""


def qt6ct(tokens: Tokens) -> str:
    """~/.config/qt6ct/qt6ct.conf.

    Fonts are deliberately not written here. qt6ct stores them as serialised
    QVariant blobs (`@Variant(\\0\\0\\0@...)`), and hand-assembling one to save
    a font name is a lot of fragile bytes for something fontconfig already
    resolves.
    """
    return header("#", "", tokens=tokens) + f"""
[Appearance]
color_scheme_path=~/.config/qt6ct/colors/{KV_NAME}.conf
custom_palette=true
standard_dialogs=default
# kvantum-dark rather than Fusion: Fusion would take the palette above but draw
# stock Qt shapes, with no translucency and none of the rice's radii.
style=kvantum-dark
icon_theme=breeze

[Interface]
double_click_interval=400
cursor_flash_time=1000
buttonbox_layout=0
keyboard_scheme=2
gui_effects=@Invalid()
stylesheets=@Invalid()
underline_shortcut=0
dialog_buttons_have_icons=1
activate_item_on_single_click=1
menus_have_icons=true
show_shortcuts_in_context_menus=true

[Troubleshooting]
force_raster_widgets=1
ignored_applications=@Invalid()
"""


def kvantum(tokens: Tokens) -> str:
    """~/.config/Kvantum/blackwall/blackwall.kvconfig.

    The base theme is read at generation time and only its `[GeneralColors]`
    block is replaced, so every shape, metric and hack KvMojave defines is
    inherited rather than reproduced.
    """
    t = tokens
    source = KV_BASE / f"{KV_BASE.name}.kvconfig"
    try:
        body = source.read_text()
    except OSError:
        return header("#", "", tokens=tokens) + (
            f"\n# {KV_BASE} is not installed - `pacman -S kvantum`.\n"
            "# Without it there is no base theme to derive shapes from.\n"
        )

    colours = f"""[GeneralColors]
window.color={t.bg.hex6}
inactive.window.color={t.bg.hex6}
base.color={t.bg.mix(t.fg, 0.04).hex6}
inactive.base.color={t.bg.hex6}
alt.base.color={t.bg.mix(t.fg, 0.07).hex6}
inactive.alt.base.color={t.bg.mix(t.fg, 0.05).hex6}
button.color={t.bg.mix(t.fg, 0.11).hex6}
light.color={t.bg.mix(t.fg, 0.22).hex6}
mid.light.color={t.bg.mix(t.fg, 0.17).hex6}
dark.color={t.bg.darken(0.35).hex6}
mid.color={t.bg.mix(t.fg, 0.13).hex6}
highlight.color={t.accent.hex6}
inactive.highlight.color={t.accent.mix(t.bg, 0.3).hex6}
tooltip.base.color={t.bg.mix(t.fg, 0.11).hex6}
text.color={t.fg.hex6}
inactive.text.color={t.muted.over(t.bg).hex6}
window.text.color={t.fg.hex6}
inactive.window.text.color={t.muted.over(t.bg).hex6}
button.text.color={t.fg.hex6}
disabled.text.color={t.faint.over(t.bg).hex6}
tooltip.text.color={t.fg.hex6}
highlight.text.color={t.on_accent.hex6}
inactive.highlight.text.color={t.on_accent.hex6}
link.color={t.link.hex6}
link.visited.color={t.link.mix(t.bg, 0.35).hex6}
"""

    body = re.sub(r"\[GeneralColors\].*?(?=\n\[)", colours.rstrip("\n"),
                  body, count=1, flags=re.S)

    # KvMojave makes whole windows translucent. That is one step past this
    # rice's model: chrome is glass, content is solid. A translucent Dolphin
    # would also sit visibly apart from Thunar, which is opaque. Menus,
    # tooltips and popups stay blurred - those *are* chrome.
    for key, value in (
        ("translucent_windows", "false"),
        ("blurring", "false"),
        ("popup_blurring", "true"),
        ("reduce_menu_opacity", "0"),
    ):
        body = re.sub(rf"^{key}=.*$", f"{key}={value}", body, count=1,
                      flags=re.M)
    banner = (
        f"# blackwall design tokens - generated, do not edit\n"
        f"# derived from {KV_BASE.name}; edit theme/blackwall_theme/tokens.py\n"
        f"# palette: {tokens.palette.source}\n"
    )
    return banner + body


def prepare(destination: Path) -> str | None:
    """Copy the base theme's SVG next to the generated kvconfig.

    Kvantum needs `<name>.svg` beside `<name>.kvconfig` - the config carries
    colours and metrics, the SVG carries every widget shape. Only the config is
    generated, so the artwork is copied once and left alone.
    """
    svg = KV_BASE / f"{KV_BASE.name}.svg"
    target = destination.parent / f"{KV_NAME}.svg"
    if target.exists():
        return None
    if not svg.is_file():
        return f"{svg} not found - install kvantum for the widget artwork"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(svg, target)
    return f"copied widget artwork from {KV_BASE.name}.svg"
