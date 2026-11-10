"""Tests for the blackwall token generator.

The interesting failures here are not crashes - every emitter happily produces
*something*. They are silent wrong output: a colour spelled in a syntax the
target rejects, or an alpha dropped so a muted token comes back at full
strength. Both of those shipped during the first pass and neither raised.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from blackwall_theme import palette as palette_mod  # noqa: E402
from blackwall_theme.color import BLACK, WHITE, Colour  # noqa: E402
from blackwall_theme.emit import gtk, hypr, plain, rasi, scss, swaync  # noqa: E402
from blackwall_theme.tokens import build, usable_accent  # noqa: E402


@pytest.fixture
def tokens():
    return build(palette_mod._from_mapping(palette_mod.BUILTIN, "test"))


# ---------------------------------------------------------------- colour ----

class TestColour:
    @pytest.mark.parametrize("text,expected", [
        ("#fff", (255, 255, 255, 1.0)),
        ("#15121B", (21, 18, 27, 1.0)),
        ("15121B", (21, 18, 27, 1.0)),
        ("#15121B80", (21, 18, 27, 128 / 255)),
    ])
    def test_parse(self, text, expected):
        c = Colour.parse(text)
        assert (c.r, c.g, c.b) == expected[:3]
        assert c.a == pytest.approx(expected[3])

    def test_parse_rejects_nonsense(self):
        with pytest.raises(ValueError):
            Colour.parse("#12345")

    def test_mix_endpoints_and_midpoint(self):
        assert BLACK.mix(WHITE, 0.0) == BLACK
        assert BLACK.mix(WHITE, 1.0).hex6 == "#FFFFFF"
        assert BLACK.mix(WHITE, 0.5).hex6 == "#808080"

    def test_mix_keeps_the_left_alpha(self):
        assert BLACK.alpha(40).mix(WHITE, 0.5).a == pytest.approx(0.4)

    def test_alpha_is_clamped(self):
        assert WHITE.alpha(-10).a == 0.0
        assert WHITE.alpha(500).a == 1.0

    def test_over_resolves_alpha_rather_than_dropping_it(self):
        """The bug that shipped: `.hex6` on a muted token returns plain fg.

        tmux, kitty, cava and nvim have no alpha, so a token like
        `muted = fg.alpha(66)` has to be composited against the background to
        mean anything. Truncating instead gives back the undimmed colour, and
        muted, faint and fg all render identically.
        """
        fg, bg = WHITE, BLACK
        muted = fg.alpha(66)
        assert muted.hex6 == fg.hex6            # truncation loses the dimming
        assert muted.over(bg).hex6 != fg.hex6   # compositing keeps it
        assert muted.over(bg).hex6 == "#A8A8A8"

    def test_over_is_opaque(self):
        assert WHITE.alpha(30).over(BLACK).a == 1.0

    def test_contrast_extremes(self):
        assert BLACK.contrast(WHITE) == pytest.approx(21.0, abs=0.01)
        assert WHITE.contrast(WHITE) == pytest.approx(1.0)

    def test_readable_on_lifts_a_low_contrast_foreground(self):
        bg = Colour.parse("#15121B")
        washed = Colour.parse("#211E27")        # barely off the background
        assert washed.contrast(bg) < 4.5
        assert washed.readable_on(bg, 4.5).contrast(bg) >= 4.5

    def test_readable_on_leaves_a_good_pair_alone(self):
        bg, fg = Colour.parse("#15121B"), Colour.parse("#FBFAFC")
        assert fg.readable_on(bg, 7.0) is fg

    def test_spellings(self):
        c = Colour.parse("#15121B").alpha(68)
        assert c.hex6 == "#15121B"
        assert c.hex8 == "#15121BAD"
        assert c.css == "rgba(21, 18, 27, 0.680)"
        assert Colour.parse("#15121B").css == "rgb(21, 18, 27)"
        assert c.rgb_triplet == "21, 18, 27"


# --------------------------------------------------------------- palette ----

class TestPalette:
    def test_builtin_is_complete(self):
        p = palette_mod._from_mapping(palette_mod.BUILTIN, "test")
        assert len(p.ansi) == 16
        assert p.accent == p.ansi[1]

    def test_partial_data_fills_in_from_builtin(self):
        """The eww/colors.scss fallback supplies only three of nineteen."""
        p = palette_mod._from_mapping(
            {"background": "#000000", "foreground": "#FFFFFF"}, "partial")
        assert p.bg.hex6 == "#000000"
        assert p.ansi[7].hex6 == Colour.parse(
            palette_mod.BUILTIN["color7"]).hex6

    def test_empty_values_do_not_override(self):
        p = palette_mod._from_mapping({"color1": ""}, "empty")
        assert p.accent.hex6 == Colour.parse(
            palette_mod.BUILTIN["color1"]).hex6

    def test_explicit_file(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({**palette_mod.BUILTIN,
                                 "background": "#010203"}))
        assert palette_mod.load(f).bg.hex6 == "#010203"

    def test_explicit_file_must_be_a_palette(self, tmp_path):
        f = tmp_path / "junk.json"
        f.write_text('{"nope": 1}')
        with pytest.raises(SystemExit):
            palette_mod.load(f)


# ---------------------------------------------------------------- tokens ----

class TestTokens:
    def test_glass_is_translucent(self, tokens):
        for name in ("glass_hi", "glass", "glass_lo", "thin", "scrim"):
            assert 0 < getattr(tokens, name).a < 1, name

    def test_the_bar_is_thinner_than_a_panel(self, tokens):
        """Perceived opacity scales with area, so the bar carries less."""
        assert tokens.thin.a < tokens.glass.a

    def test_text_tiers_are_ordered(self, tokens):
        assert tokens.fg.a > tokens.muted.a > tokens.faint.a

    def test_on_accent_is_readable_against_the_accent(self, tokens):
        assert tokens.on_accent.contrast(tokens.accent) >= 3.0

    def test_fg_is_corrected_against_a_hostile_palette(self):
        """A washed-out wallpaper must not produce unreadable body text."""
        washed = palette_mod._from_mapping(
            {**palette_mod.BUILTIN,
             "background": "#15121B", "foreground": "#1D1A23"}, "washed")
        assert build(washed).fg.contrast(Colour.parse("#15121B")) >= 7.0

    def test_status_colours_ignore_the_palette(self):
        """A red wallpaper must not make error text invisible."""
        red = palette_mod._from_mapping(
            {**palette_mod.BUILTIN, "color1": "#FF0000"}, "red")
        assert build(red).bad.hex6 == "#D2696A"

    def test_radius_scale_is_three_steps_and_a_pill(self, tokens):
        assert [tokens.r_lg, tokens.r_md, tokens.r_sm] == ["18px", "12px", "8px"]
        assert tokens.r_pill == "999px"

    def test_window_radius_matches_the_compositor(self, tokens):
        """r_window and hyprland's archpilot `rounding` must not drift.

        When they disagree the toolkit's rim is clipped by the compositor's
        rounding and the hairline stops short of each corner.
        """
        conf = (ROOT.parent / "hypr" / "configs" / "archpilot.conf").read_text()
        found = re.search(r"rounding (\d+)", conf)
        assert found, "archpilot.conf no longer sets a rounding"
        assert tokens.r_window == f"{found.group(1)}px"

    def test_ring_is_inset_before_it_is_outset(self, tokens):
        ring = tokens.ring(tokens.lift)
        assert ring.index("inset") < ring.index("0 4px 14px")

    def test_gradient_has_three_stops(self, tokens):
        assert tokens.gradient().count("%") == 3


# --------------------------------------------------------------- emitters ---

ALL_EMITTERS = (
    ("waybar", gtk.waybar), ("wlogout", gtk.wlogout),
    ("gtk3", gtk.gtk3), ("gtk4", gtk.gtk4),
    ("eww", scss.eww), ("rofi", rasi.rofi), ("hypr", hypr.hypr),
    ("mako", plain.mako), ("cava", plain.cava), ("kitty", plain.kitty),
    ("nvim", plain.nvim), ("tmux", plain.tmux),
)

#: Formats with no alpha channel at all. An 8-digit hex reaching one of these
#: is a hard failure, not a cosmetic one: kitty raises `Invalid color name` and
#: refuses to start.
NO_ALPHA = ("kitty", "cava", "tmux", "nvim", "hypr")
_HEX8 = re.compile(r"#[0-9A-Fa-f]{8}\b")


class TestEmitters:
    @pytest.mark.parametrize("name,render", ALL_EMITTERS)
    def test_every_emitter_marks_its_output_generated(self, name, render, tokens):
        # tmux is spliced into a hand-written file, so the markers around the
        # block carry the warning rather than the body itself.
        if name == "tmux":
            pytest.skip("spliced target; the block markers carry the banner")
        assert "do not edit" in render(tokens).splitlines()[0], name

    @pytest.mark.parametrize("name,render", ALL_EMITTERS)
    def test_no_unresolved_placeholders(self, name, render, tokens):
        body = render(tokens)
        assert "{" not in body or name in ("gtk3", "gtk4", "waybar", "wlogout",
                                           "eww", "rofi", "nvim")
        assert "None" not in body
        assert "Colour(" not in body

    @pytest.mark.parametrize("name", NO_ALPHA)
    def test_alpha_less_targets_get_no_eight_digit_hex(self, name, tokens):
        render = dict(ALL_EMITTERS)[name]
        found = _HEX8.findall(render(tokens))
        assert not found, f"{name} emitted {found} - the target has no alpha"

    def test_hypr_uses_hyprlands_own_colour_spelling(self, tokens):
        body = hypr.hypr(tokens)
        # rgba(6397e2d9), not #6397E2D9 and not rgba(99, 151, 226, 0.85)
        assert re.search(r"rgba\([0-9a-f]{8}\)", body)
        assert "#" not in body.replace("# ", "").split("$bw_bg")[1]

    def test_kitty_emits_all_sixteen(self, tokens):
        body = plain.kitty(tokens)
        for i in range(16):
            assert re.search(rf"^color{i}\s", body, re.M), i

    def test_muted_is_distinct_from_fg_in_alpha_less_output(self, tokens):
        """Regression: `.hex6` truncation made muted and fg identical."""
        body = plain.tmux(tokens)
        secondary = next(line for line in body.splitlines()
                         if "secondary text" in line)
        assert tokens.fg.hex6 not in secondary

    def test_tmux_emits_all_seventeen_oh_my_tmux_slots(self, tokens):
        body = plain.tmux(tokens)
        for i in range(1, 18):
            assert f"tmux_conf_theme_colour_{i}=" in body, i

    def test_tmux_splice_is_idempotent(self, tmp_path, tokens):
        """Repeated runs must replace the block, not stack copies of it."""
        from blackwall_theme.__main__ import BEGIN, END, splice
        f = tmp_path / "tmux.conf.local"
        f.write_text(f"before\n{BEGIN}\nold\n{END}\nafter\n")
        once = splice(f, plain.tmux(tokens))
        f.write_text(once)
        twice = splice(f, plain.tmux(tokens))
        assert once == twice
        assert once.count(BEGIN) == 1
        assert once.startswith("before")
        assert once.rstrip().endswith("after")

    def test_tmux_splice_appends_when_no_block_exists(self, tmp_path, tokens):
        from blackwall_theme.__main__ import BEGIN, splice
        f = tmp_path / "fresh.conf"
        f.write_text("existing content\n")
        out = splice(f, plain.tmux(tokens))
        assert "existing content" in out
        assert out.count(BEGIN) == 1

    def test_rofi_declares_real_transparency(self, tokens):
        """Without it rofi composites against black and the alpha is wasted."""
        assert 'transparency:     "real"' in rasi.rofi(tokens)

    def test_gtk_defines_only_colours(self, tokens):
        """GTK's @define-color cannot hold a length; a px value here silently
        breaks every rule that references the token."""
        for line in gtk.waybar(tokens).splitlines():
            if line.startswith("@define-color"):
                assert "px" not in line, line

    # ---- swaync -----------------------------------------------------------
    # These read the emitted CSS rule by rule rather than grepping the whole
    # file, because the failures that shipped were about *which* rule a
    # declaration sat in (a hover rule outranking `.critical`, a selector that
    # went through a node the close button is not inside), not about a string
    # being absent somewhere.

    @staticmethod
    def _rule(body: str, selector: str) -> str:
        """The declaration block of the rule whose selector list ends with
        `selector` exactly (so `.a` does not match `.b .a:hover`). Every such rule, joined: a selector
        may legitimately be declared in more than one place."""
        found = [m.group(2) for m in
                 re.finditer(r"(?m)^([^{}/]+?)\s*\{([^{}]*)\}", body)
                 if selector in [x.strip() for x in m.group(1).split(",")]]
        assert found, f"no rule for {selector!r}"
        return "\n".join(found)

    @staticmethod
    def _colours(css: str) -> list[Colour]:
        return [Colour(int(r), int(g), int(b)) for r, g, b in
                re.findall(r"rgba?\((\d+), (\d+), (\d+)", css)]

    def test_swaync_critical_is_a_glow_not_a_stripe(self, tokens):
        """The old border bar read as a bookmark; the glow replaces it. The
        glow is a bad-tinted gradient from the left on the card's background,
        never a border, so the box cannot differ between urgencies."""
        body = swaync.swaync(tokens)
        assert "border-left" not in body
        for sel in (".notification.critical",
                    ".floating-notifications .notification.critical",
                    ".control-center .notification.critical:hover"):
            rule = self._rule(body, sel)
            assert "linear-gradient(to right" in rule, sel
            assert f"rgba({tokens.bad.r}, {tokens.bad.g}, {tokens.bad.b}" in rule, sel
            assert "border" not in rule.replace("border-radius", ""), sel

    def test_swaync_hover_never_erases_urgency(self, tokens):
        """`.control-center .notification:hover` outranks `.notification.critical`,
        so critical needs its own hover rule or the glow vanishes under the
        pointer."""
        body = swaync.swaync(tokens)
        assert ".control-center .notification.critical:hover" in body

    def test_swaync_card_hover_is_brighter_than_rest(self, tokens):
        """The resting card runs raised_hi -> raised_lo. A hover that starts
        below raised_hi dims the card under the pointer."""
        body = swaync.swaync(tokens)
        rest = self._rule(body, ".notification")
        hover = self._rule(body, ".control-center .notification:hover")
        assert tokens.raised_hi.css in rest and tokens.raised_hi.css in hover
        assert tokens.raised_lo.css not in hover
        assert tokens.hover.a > tokens.raised_lo.a

    def test_swaync_close_button_selectors_can_match(self, tokens):
        """swaync overlays the close button on `.notification-background`, the
        card's PARENT. Any selector that puts `.close-button` under
        `.notification` matches nothing and its rule is silently dead."""
        body = swaync.swaync(tokens)
        assert not re.search(r"\.notification(:\w+)?\s+(\.\w+\s+)*\.close-button", body)
        assert ".control-center .notification-background:hover .close-button" in body
        assert ".control-center .notification-background .close-button:hover" in body

    def test_swaync_cards_share_one_minimum_height(self, tokens):
        """No max-height: it measures the wrong thing and overlaps text
        instead of clamping it (verified against live swaync 0.12.6). The
        floor lives on the content box (card minimum less its padding),
        because a min-height on the card itself leaves the text hanging from
        the top."""
        body = swaync.swaync(tokens)
        pad_y = swaync.px(tokens.s_lg)
        content = self._rule(body, ".notification-content")
        assert f"min-height: {swaync.CARD_MIN - 2 * pad_y}px" in content
        assert "max-height" not in body
        assert f"border-radius: {swaync.CARD_MIN // 2}px" in self._rule(body, ".notification")

    def test_swaync_single_action_is_full_width(self, tokens):
        """A lone action fills the content area like any other row: no
        per-count inset, no margin on the button, and the only horizontal
        spacing is the half-gap each action carries, so one button spans the
        row and N split it evenly."""
        body = swaync.swaync(tokens)
        assert ":only-child > button" not in body
        assert "margin: 0 96px" not in body
        half = swaync.px(tokens.s_md) // 2
        assert f"padding: 0 {half}px;" in self._rule(body, ".notification-action")
        assert "margin: 0;" in self._rule(body, ".notification-action > button")
        assert "max-width" not in body

    def test_swaync_spacing_is_one_scale(self, tokens):
        """Card padding, text-to-button gap, button-to-button gap and card gap
        all derive from the s_* tokens, so changing a token moves them all."""
        import dataclasses
        px = swaync.px
        body = swaync.swaync(tokens)
        pad_y, pad_x, gap = px(tokens.s_lg), px(tokens.s_xl), px(tokens.s_md)
        assert f"padding: {pad_y}px {pad_x}px;" in self._rule(body, ".notification-content")
        assert (f"padding: {gap}px {pad_x - gap // 2}px {pad_y}px;"
                in self._rule(body, ".notification-alt-actions"))
        assert f"margin: 0 0 {gap}px;" in self._rule(body, ".widget")
        wider = swaync.swaync(dataclasses.replace(tokens, s_md="12px"))
        assert "margin: 0 0 12px;" in self._rule(wider, ".widget")
        assert "padding: 0 6px;" in self._rule(wider, ".notification-action")

    def test_swaync_has_one_scrollbar(self, tokens):
        """The control centre nests two scrolled windows; the outer one's bar
        must be hidden, and the hiding rule has to come AFTER the general
        scrollbar rules (equal specificity: the later one wins)."""
        body = swaync.swaync(tokens)
        hide = self._rule(body, ".control-center > scrollbar")
        assert "opacity: 0" in hide and "min-width: 0" in hide
        assert body.index(".control-center > scrollbar {") > body.index("scrollbar slider {")
        assert "min-width: 4px" in self._rule(body, "scrollbar.vertical")

    def test_swaync_has_no_literal_colours(self, tokens):
        """Everything is token-driven; a hex literal means someone hardcoded."""
        body = re.sub(r"/\*.*?\*/", "", swaync.swaync(tokens), flags=re.S)
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body)

    @pytest.mark.parametrize("bg,fg,accent", [
        (palette_mod.BUILTIN["background"], palette_mod.BUILTIN["foreground"], "#C56B3D"),
        ("#101010", "#F0F0F0", "#FF2020"),
        ("#101018", "#F0F0F0", "#3355FF"),
        ("#101010", "#F0F0F0", "#E8D84A"),
        ("#F4F4F6", "#18181C", "#3366DD"),
        ("#F4F4F6", "#18181C", "#223388"),
    ])
    def test_swaync_action_pill_text_stays_legible_on_hover(self, bg, fg, accent):
        """on_accent is chosen against the plain accent. The hover gradient and
        the pressed fill must never be harder to read than that - mixing the
        fill toward bg did exactly that for dark text on a bright accent."""
        pal = palette_mod._from_mapping(
            {**palette_mod.BUILTIN, "background": bg, "foreground": fg,
             "color1": accent}, "t")
        t = build(pal)
        body = swaync.swaync(t)
        plain_ratio = t.on_accent.contrast(t.accent)
        for sel in (".notification-action > button:hover",
                    ".notification-action > button:active"):
            rule = self._rule(body, sel)
            fills = self._colours(rule.split("color:")[0])
            assert fills, sel
            for fill in fills:
                assert t.on_accent.contrast(fill) >= plain_ratio - 0.05, (sel, fill)


# ------------------------------------------------------------------- cli ----

class TestCli:
    def test_every_target_renders_and_writes(self):
        out = subprocess.run(
            [sys.executable, "-m", "blackwall_theme", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.count("========") >= 12 * 2

    def test_list_names_every_target(self):
        out = subprocess.run(
            [sys.executable, "-m", "blackwall_theme", "--list"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert out.returncode == 0
        for name, _ in ALL_EMITTERS:
            assert name in out.stdout

    def test_unknown_target_is_an_error(self):
        out = subprocess.run(
            [sys.executable, "-m", "blackwall_theme", "nope"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert out.returncode != 0
        assert "unknown target" in out.stderr

    def test_radius_check_passes_on_the_live_rice(self):
        out = subprocess.run(
            [sys.executable, "-m", "blackwall_theme", "--check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert out.returncode == 0, out.stdout


class TestUsableAccent:
    """A greyscale wallpaper must not produce an invisible accent.

    arch-logo-dark.png is 48 shades of near-identical grey; wallust hands back
    rgb(37, 37, 37) against a background of rgb(31, 31, 31) - a contrast ratio
    of 1.05. Without a guard, every selected state in the rice (the calendar's
    current day, an enabled toggle, the active workspace) rendered invisible,
    and nothing failed to report it.
    """

    BG = Colour.parse("#1F1F1F")

    def test_colourless_accent_is_replaced(self):
        accent = usable_accent(Colour.parse("#252525"), self.BG)
        assert accent.chroma >= 0.10
        assert accent.contrast(self.BG) >= 3.0

    def test_coloured_accent_is_kept_verbatim(self):
        original = Colour.parse("#F3A46C")
        assert usable_accent(original, self.BG) == original

    def test_dim_but_coloured_accent_is_brightened_not_replaced(self):
        original = Colour.parse("#2A3A55")
        out = usable_accent(original, self.BG)
        assert out != original
        assert out.contrast(self.BG) >= 1.6
        # Keeping the wallpaper's hue is the entire point of deriving from it,
        # so brightening must not quietly swap in the fallback blue.
        assert abs(out.chroma - original.chroma) < 0.2

    def test_grey_palette_still_yields_a_visible_accent(self):
        grey = Colour.parse("#1F1F1F")
        pal = palette_mod.Palette(
            background=grey,
            foreground=Colour.parse("#B7B7B7"),
            cursor=Colour.parse("#B7B7B7"),
            ansi=tuple(Colour.parse("#252525") for _ in range(16)),
        )
        assert build(pal).accent.contrast(grey) >= 3.0

    def test_chroma_is_zero_for_grey_and_high_for_a_hue(self):
        assert Colour.parse("#3A3A3A").chroma == 0.0
        assert Colour.parse("#6397E2").chroma > 0.4
