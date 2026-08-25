"""The blackwall design system.

Every surface in the rice - waybar, rofi, mako, eww, wlogout, GTK, Qt, kitty,
nvim, cava - draws its values from here and nowhere else. This file is the one
place a decision about the *look* of the rice is made.

The system was derived empirically on the ArchPilot widget and is documented in
docs/glass.md. Four rules carry most of the weight:

  1. Alpha lives on the background, never on a compositor opacity rule. A
     window-level opacity fades the text along with the fill, which is the one
     thing frosted glass never does.
  2. Rims are inset rings, not borders. A border is painted at the outer edge
     of a widget, exactly where the compositor's rounding clips it, so the
     hairline dies at each corner. An inset shadow is painted inside the clip
     and follows the radius the whole way round.
  3. Radius is a three-step scale plus a deliberate pill, and a surface the
     compositor rounds must use the same radius the compositor does.
  4. The surface you are acting on sits forward. Depth is carried by three
     shadow steps, not by colour.
"""

from __future__ import annotations

from dataclasses import dataclass

from .color import BLACK, WHITE, Colour
from .palette import Palette

# --------------------------------------------------------------------------
# Fixed colours. These are deliberately NOT palette-derived: a warning has to
# read as a warning whatever the wallpaper is, and a wallpaper that happens to
# be red must not make every error message invisible.
# --------------------------------------------------------------------------
WARN = Colour.parse("#E4B363")
BAD = Colour.parse("#D2696A")
GOOD = Colour.parse("#7FB88A")
#: iOS system blue, mixed toward the palette accent for the informational role.
IOS_BLUE = Colour.parse("#5AC8FA")
#: Used when the wallpaper cannot supply a usable accent of its own.
ACCENT_FALLBACK = Colour.parse("#6397E2")


@dataclass(frozen=True)
class Tokens:
    """Resolved design tokens. Colours are `Colour`; the rest are strings."""

    # ---- source palette, passed through --------------------------------
    palette: Palette
    bg: Colour
    fg: Colour
    accent: Colour

    # ---- glass ---------------------------------------------------------
    #: Panels you read text in: rofi, eww, mako, the widget.
    glass_hi: Colour
    glass: Colour
    glass_lo: Colour
    #: The bar. Thinner, because perceived opacity scales with area - the same
    #: alpha that reads as frosted on a 900x560 panel reads as a solid black
    #: stripe on a 1890x62 one, with too little area for the blurred wallpaper
    #: underneath to register as texture.
    thin_hi: Colour
    thin: Colour
    thin_lo: Colour
    #: Full-screen scrims: wlogout, rofi's fullscreen launcher.
    scrim: Colour

    # ---- rim -----------------------------------------------------------
    rim: Colour
    rim_top: Colour
    rim_bottom: Colour
    edge: Colour

    # ---- surfaces inside a panel ---------------------------------------
    raised_hi: Colour
    raised_lo: Colour
    sunken: Colour
    sunken_deep: Colour
    hover: Colour

    # ---- text ----------------------------------------------------------
    muted: Colour
    faint: Colour
    on_accent: Colour

    # ---- accent family --------------------------------------------------
    accent_hi: Colour
    accent_lo: Colour
    accent_edge: Colour
    accent_deep: Colour
    link: Colour
    link_edge: Colour
    warn: Colour
    warn_hi: Colour
    warn_edge: Colour
    bad: Colour
    bad_hi: Colour
    bad_edge: Colour
    good: Colour

    # ---- geometry (strings; these are lengths, not colours) -------------
    r_window: str
    r_lg: str
    r_md: str
    r_sm: str
    r_pill: str

    # ---- depth ----------------------------------------------------------
    lift_soft: str
    lift: str
    lift_high: str
    drop: str

    # ---- type ------------------------------------------------------------
    font_ui: str
    font_mono: str
    font_icon: str
    t_xs: str
    t_sm: str
    t_md: str
    t_lg: str
    t_xl: str

    # ---- motion ----------------------------------------------------------
    ease: str
    quick: str
    normal: str
    slow: str

    # ---- composites -------------------------------------------------------

    def ring(self, lift: str | None = None) -> str:
        """The standard glass box-shadow: inset hairline, specular top, drop.

        Emitted as one string so every surface in the rice spells the rim the
        same way, and so the inset-before-outset ordering cannot drift.
        """
        parts = [
            f"inset 0 0 0 1px {self.rim.css}",
            f"inset 0 1px 0 {self.rim_top.css}",
        ]
        if lift:
            parts.append(lift)
        return ",\n    ".join(parts)

    def gradient(self, angle: str = "158deg", thin: bool = False) -> str:
        """The three-stop glass fill, lit from the top-left."""
        hi, mid, lo = (
            (self.thin_hi, self.thin, self.thin_lo)
            if thin
            else (self.glass_hi, self.glass, self.glass_lo)
        )
        return (
            f"linear-gradient({angle}, {hi.css} 0%, "
            f"{mid.css} 45%, {lo.css} 100%)"
        )


def usable_accent(accent: Colour, bg: Colour) -> Colour:
    """Guarantee the accent is actually visible against the background.

    An accent has exactly one job: to be obviously different from everything
    around it. A greyscale wallpaper cannot supply one - arch-logo-dark.png is
    48 shades of near-identical grey and yields rgb(37, 37, 37) against a
    background of rgb(31, 31, 31), a contrast ratio of 1.05. Every selected
    state in the rice - the calendar's current day, an enabled toggle, the
    active workspace - rendered invisible.

    The two failures need different repairs. Chroma cannot be invented from
    grey, so a colourless accent is replaced outright. An accent that does have
    a hue but sits too close to the background is brightened instead - keeping
    the wallpaper's colour is the whole point of deriving from it, and only the
    lightness was wrong.
    """
    if accent.chroma < 0.10:
        return ACCENT_FALLBACK.readable_on(bg, 3.0)
    if accent.contrast(bg) < 1.6:
        return accent.readable_on(bg, 1.6)
    return accent


def build(palette: Palette) -> Tokens:
    bg = palette.bg.opaque()
    accent = usable_accent(palette.accent.opaque(), bg)
    # Wallpaper palettes carry no contrast guarantee - a washed-out photo can
    # hand back a foreground a shade off its own background. Everything below
    # derives from `fg`, so correcting it once here corrects the whole system.
    fg = palette.fg.opaque().readable_on(bg, 7.0)

    return Tokens(
        palette=palette,
        bg=bg,
        fg=fg,
        accent=accent,

        # Tuned against a busy wallpaper. 82/78/82 read as painted-on rather
        # than glass; 62/56/64 looked right but lost the footer text entirely.
        glass_hi=bg.mix(fg, 0.13).alpha(72),
        glass=bg.alpha(68),
        glass_lo=bg.darken(0.30).alpha(74),
        thin_hi=bg.mix(fg, 0.16).alpha(58),
        thin=bg.alpha(55),
        thin_lo=bg.darken(0.30).alpha(60),
        scrim=BLACK.alpha(45),

        rim=WHITE.alpha(16),
        rim_top=WHITE.alpha(20),
        rim_bottom=BLACK.alpha(26),
        edge=fg.alpha(13),

        raised_hi=fg.alpha(11),
        raised_lo=fg.alpha(5),
        sunken=BLACK.alpha(22),
        sunken_deep=BLACK.alpha(34),
        hover=fg.alpha(9),

        muted=fg.alpha(66),
        faint=fg.alpha(40),
        # Text sitting on a filled accent. Whichever of the palette's own two
        # poles reads better there, so a pale accent gets dark text.
        on_accent=(bg if bg.contrast(accent) >= fg.contrast(accent) else fg),

        accent_hi=accent.alpha(30),
        accent_lo=accent.alpha(16),
        accent_edge=accent.alpha(48),
        accent_deep=accent.mix(bg, 0.35),
        link=accent.mix(IOS_BLUE, 0.72),
        link_edge=accent.mix(IOS_BLUE, 0.72).alpha(55),
        warn=WARN,
        warn_hi=WARN.alpha(22),
        warn_edge=WARN.alpha(45),
        bad=BAD,
        bad_hi=BAD.alpha(20),
        bad_edge=BAD.alpha(45),
        good=GOOD,

        # Three steps and a pill. The rice had twelve ad-hoc radii before this
        # (7 8 9 10 12 14 15 16 20 28 100% 999); these five replace all of them.
        # r_window must equal the compositor's `rounding` for any real window.
        r_window="22px",
        r_lg="18px",   # panes: panels, popups, list containers
        r_md="12px",   # controls: chips, buttons, list rows, bar modules
        r_sm="8px",    # small marks: close buttons, key hints, scrollbars
        r_pill="999px",

        lift_soft="0 1px 3px rgba(0, 0, 0, 0.18)",
        lift="0 4px 14px rgba(0, 0, 0, 0.28)",
        lift_high="0 10px 30px rgba(0, 0, 0, 0.38)",
        drop="0 30px 80px rgba(0, 0, 0, 0.55)",

        # Inter is the closest free analogue to SF Pro and is what this rice
        # is designed against (`pacman -S inter-font`). Noto Sans sits behind
        # it because it is always present: an earlier stack fell through to
        # JetBrainsMono, so every panel was quietly set in a monospace face.
        #
        # The nerd font stays in the stack for body text so that a stray glyph
        # in a label does not land on the colour emoji font.
        #
        # It is NOT enough on its own, though: Pango resolves a family list to
        # a single font description and then falls back through fontconfig for
        # missing glyphs, not through the remaining families here. A Nerd Font
        # in fourth place is therefore never consulted for a Private Use Area
        # codepoint. Anything that renders an icon must set `font_icon`
        # explicitly on that element - see waybar's icon rules and eww's
        # .vol-icon.
        font_ui='"Inter", "SF Pro Text", "Noto Sans", '
                '"JetBrainsMono Nerd Font", "Symbols Nerd Font", sans-serif',
        font_mono='"JetBrainsMono Nerd Font", "MesloLGS NF", monospace',
        # Symbols Nerd Font, alone and first. Measured, not assumed: rendering
        # U+F036C through every installed Nerd Font with PIL draws a microphone
        # in all of them, but asking GTK for "JetBrainsMono Nerd Font" draws a
        # completely different symbol, while "Symbols Nerd Font" and
        # "JetBrainsMono Nerd Font Mono" both draw the right one. The cause is
        # not understood; the behaviour is reproducible. Prefer the family that
        # works, and keep it a single name - a comma list only makes it harder
        # to tell which member actually answered.
        font_icon='"Symbols Nerd Font"',
        t_xs="10px",
        t_sm="11px",
        t_md="13px",
        t_lg="15px",
        t_xl="24px",

        ease="cubic-bezier(0.32, 0.72, 0, 1)",  # iOS-ish: quick out, long settle
        quick="150ms",
        normal="220ms",
        slow="320ms",
    )
