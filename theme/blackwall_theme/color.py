"""Colour primitives.

Everything the design system computes is built from two operations - take a
colour and make it partly transparent, or slide it toward another colour - so
those are the only two that need to exist. The rest of the tokens are named
combinations of them.

A `Colour` carries its alpha with it rather than baking it into a string,
because the same token has to come out as `rgba(21,18,27,0.68)` for GTK CSS,
`#15121BAD` for rofi, and `#15121B` for kitty, which has no alpha at all.
Serialising at the emitter instead of at the token means the value is defined
once and only its spelling changes.
"""

from __future__ import annotations

from dataclasses import dataclass


def _clamp8(value: float) -> int:
    return max(0, min(255, int(round(value))))


@dataclass(frozen=True)
class Colour:
    r: int
    g: int
    b: int
    a: float = 1.0

    # ---- constructors -------------------------------------------------

    @classmethod
    def parse(cls, text: str) -> "Colour":
        """Accept #RGB, #RRGGBB and #RRGGBBAA, with or without the hash."""
        raw = text.strip().lstrip("#")
        if len(raw) == 3:
            raw = "".join(c * 2 for c in raw)
        if len(raw) == 6:
            return cls(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
        if len(raw) == 8:
            return cls(
                int(raw[0:2], 16),
                int(raw[2:4], 16),
                int(raw[4:6], 16),
                int(raw[6:8], 16) / 255,
            )
        raise ValueError(f"not a colour: {text!r}")

    # ---- the two operations -------------------------------------------

    def alpha(self, percent: float) -> "Colour":
        """Same colour, `percent` opaque. 0 is invisible, 100 is solid."""
        return Colour(self.r, self.g, self.b, max(0.0, min(1.0, percent / 100)))

    def mix(self, other: "Colour", t: float) -> "Colour":
        """Slide `t` of the way from self toward `other`, keeping self's alpha.

        Mixing happens in plain sRGB rather than a perceptual space on purpose:
        these are small nudges between colours that are already close, where
        the two agree, and sRGB keeps the arithmetic checkable by eye.
        """
        t = max(0.0, min(1.0, t))
        return Colour(
            _clamp8(self.r + (other.r - self.r) * t),
            _clamp8(self.g + (other.g - self.g) * t),
            _clamp8(self.b + (other.b - self.b) * t),
            self.a,
        )

    # ---- conveniences built on the two --------------------------------

    def lighten(self, t: float) -> "Colour":
        return self.mix(WHITE, t)

    def darken(self, t: float) -> "Colour":
        return self.mix(BLACK, t)

    def opaque(self) -> "Colour":
        return Colour(self.r, self.g, self.b, 1.0)

    def over(self, background: "Colour") -> "Colour":
        """Composite self onto `background` and return an opaque result.

        For formats that have no alpha at all - kitty, cava, tmux, nvim
        highlight groups - this is what a token *means* once it is painted.
        Dropping the alpha instead (`.hex6`) silently returns the colour at
        full strength, which turns `muted` and `faint` back into plain `fg`.
        """
        if self.a >= 1.0:
            return self.opaque()
        return background.opaque().mix(self.opaque(), self.a)

    # ---- readability ---------------------------------------------------

    @property
    def luminance(self) -> float:
        """Relative luminance per WCAG 2.1, for contrast checks."""

        def channel(v: int) -> float:
            s = v / 255
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

        return (
            0.2126 * channel(self.r)
            + 0.7152 * channel(self.g)
            + 0.0722 * channel(self.b)
        )

    @property
    def chroma(self) -> float:
        """How far this colour is from grey, 0.0 (grey) to 1.0 (pure hue).

        The spread between the strongest and weakest channel. Crude next to a
        proper colour space, but it answers the only question asked of it -
        "is there a hue here at all" - and it answers it the same way at every
        lightness, which Lch chroma does not.
        """
        return (max(self.r, self.g, self.b) - min(self.r, self.g, self.b)) / 255

    def contrast(self, other: "Colour") -> float:
        """WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white)."""
        a, b = self.luminance, other.luminance
        hi, lo = max(a, b), min(a, b)
        return (hi + 0.05) / (lo + 0.05)

    def readable_on(self, background: "Colour", ratio: float = 4.5) -> "Colour":
        """Push self away from `background` until it clears `ratio`.

        Wallpaper-derived palettes have no contrast guarantee whatsoever - a
        washed-out photo can hand back a foreground only a shade off its own
        background. Rather than let that render as unreadable text, walk the
        colour toward white or black (whichever the background is further from)
        until it clears the threshold.
        """
        if self.contrast(background) >= ratio:
            return self
        target = WHITE if background.luminance < 0.5 else BLACK
        current = self
        for step in range(1, 21):
            current = self.mix(target, step / 20)
            if current.contrast(background) >= ratio:
                return current
        return target.alpha(self.a * 100)

    # ---- spellings -----------------------------------------------------

    @property
    def hex6(self) -> str:
        """#RRGGBB - alpha dropped. For formats with no alpha (kitty, cava)."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @property
    def hex8(self) -> str:
        """#RRGGBBAA - rofi and GTK both accept this."""
        return f"{self.hex6}{_clamp8(self.a * 255):02X}"

    @property
    def css(self) -> str:
        """rgb()/rgba() - the spelling GTK CSS and SCSS are happiest with."""
        if self.a >= 1.0:
            return f"rgb({self.r}, {self.g}, {self.b})"
        return f"rgba({self.r}, {self.g}, {self.b}, {self.a:.3f})".replace(
            "0.000", "0"
        )

    @property
    def rgb_triplet(self) -> str:
        """`r, g, b` decimal - Qt palettes and Kvantum want bare components."""
        return f"{self.r}, {self.g}, {self.b}"

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return self.hex8


WHITE = Colour(255, 255, 255)
BLACK = Colour(0, 0, 0)
