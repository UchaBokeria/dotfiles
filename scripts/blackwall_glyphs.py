"""One glyph per application, shared by every panel that lists them.

Lives in its own file because blackwall-notify and blackwall-quiet both need
it - the notification rows and the per-application silencing list - and a
second copy is a second thing to forget when an application is added.

Every codepoint here was rendered from SymbolsNerdFont-Regular.ttf and looked
at before being used. Three of the first guesses were wrong in ways nothing
would ever report: f0326 is a hat rather than a camera, f0d0a a boxed hash
rather than a send arrow, and f0b0c a letter E in a box.
"""

from __future__ import annotations

# One glyph per application, chosen here rather than in the widget: eww has no
# user-defined functions, so the alternative was a ten-branch ternary inside
# the markup, and the widget is meant to render what it is handed.
#
# Matched on a substring so "org.gnome.Nautilus" and "nautilus" land together.
# Everything unrecognised gets a bell, which is honest - it says "a
# notification" without pretending to know the source.
#
# Every codepoint here was rendered from SymbolsNerdFont-Regular.ttf and looked
# at before being used. Three of the first guesses were wrong in ways no error
# would ever report: f0326 is a hat rather than a camera, f0d0a a boxed hash
# rather than a send arrow, and f0b0c - which "blackwall" was using - is a
# letter E in a box.
GLYPHS: list[tuple[tuple[str, ...], str]] = [
    (("flameshot", "grim", "screenshot", "spectacle"), "\U000f0100"),   # camera
    (("spotify", "mpd", "mpv", "vlc", "music"), "\U000f075a"),          # music
    (("discord", "slack", "element", "signal"), "\U000f0b79"),          # chat
    (("telegram",), "\U000f048a"),                                      # send
    (("thunderbird", "mail", "evolution", "geary"), "\U000f01ee"),      # envelope
    (("firefox", "chrome", "chromium", "brave", "zen"), "\U000f059f"),  # globe
    (("volume", "pipewire", "pulse", "audio"), "\U000f057e"),           # speaker
    (("network", "nm-applet", "wifi", "bluetooth"), "\U000f05a9"),      # wifi
    (("blackwall",), "\U000f062e"),                                     # tune / rice
    (("notify-send", "system", "systemd"), "\U000f02fc"),               # info
]
FALLBACK_GLYPH = "\U000f009a"                                            # bell


def glyph_for(app: str) -> str:
    low = (app or "").lower()
    for names, g in GLYPHS:
        if any(n in low for n in names):
            return g
    return FALLBACK_GLYPH
