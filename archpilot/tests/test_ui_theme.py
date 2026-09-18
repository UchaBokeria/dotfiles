"""The window's stylesheet keeps to the rice's type scale, faces and rims.

Pure string checks on the generated CSS - no display needed. Both paths are
covered: the normal one, fed by theme/blackwall_theme's tokens, and the local
fallback used when that package cannot be imported.
"""

from __future__ import annotations

import re

import pytest

from archpilot import rofi_theme
from archpilot.ui import theme

#: theme/blackwall_theme/tokens.py: t_xs..t_xl.
TYPE_SCALE = {10, 11, 13, 15, 24}


@pytest.fixture(params=["tokens", "fallback"])
def css(request, monkeypatch):
    if request.param == "fallback":
        monkeypatch.setattr(theme, "_shared_tokens", lambda: None)
    elif theme._shared_tokens() is None:
        pytest.skip("theme/blackwall_theme is not importable here")
    return theme.css()


def rules(text: str):
    """(selector, body) pairs, flat - enough for single-level CSS."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        yield " ".join(selector.split()), body


def test_every_font_size_is_on_the_type_scale(css):
    sizes = {int(v) for v in re.findall(r"font-size:\s*(\d+)px", css)}
    assert sizes <= TYPE_SCALE, f"off the scale: {sizes - TYPE_SCALE}"


def test_no_hand_typed_font_family(css):
    """Every face comes from the tokens: font_ui, font_mono or font_icon."""
    assert "JetBrainsMonoNL" not in css
    allowed = {theme.FONT_UI, theme.FONT_MONO, theme.FONT_ICON}
    shared = theme._shared_tokens()
    if shared is not None:
        allowed |= {shared.font_ui, shared.font_mono, shared.font_icon}
    families = set(re.findall(r"font-family:\s*([^;]+);", css))
    assert families <= allowed, families - allowed


def test_the_window_is_set_in_the_ui_face(css):
    body = dict(rules(css))["window.archpilot"]
    assert '"Inter"' in body


def test_glyph_buttons_use_the_icon_face(css):
    """"JetBrainsMono Nerd Font" draws different symbols at the same
    codepoints; only the icon face is reliable for glyphs."""
    table = dict(rules(css))
    for selector in (".icon-btn", ".meter-icon", ".notice-icon"):
        assert "Symbols Nerd Font" in table[selector], selector


def test_rims_are_rings_not_borders(css):
    """Only the attachment tile keeps a real border - its thumbnail would
    cover an inset ring."""
    bordered = {sel for sel, body in rules(css) if re.search(r"border:\s*1(\.\d+)?px solid", body)}
    assert bordered <= {".attachment", ".attachment.hovered"}, bordered


def test_every_placeholder_is_filled(css):
    assert not re.search(r"\{[a-z_]+\}", css), "an unformatted token leaked through"


def test_codex_and_claude_chips_differ(css):
    table = dict(rules(css))
    assert table[".chip.chip-quiet.engine-claude"] != table[".chip.chip-quiet.engine-codex"]


def test_text_on_the_accent_uses_on_accent():
    pale = rofi_theme.on_accent("#101010", "#F0F0F0", "#F5F5A0")
    dark = rofi_theme.on_accent("#101010", "#F0F0F0", "#302060")
    assert pale == "#101010" and dark == "#F0F0F0"
