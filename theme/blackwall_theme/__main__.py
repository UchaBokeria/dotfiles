"""blackwall-theme - regenerate every surface's tokens from one palette.

    blackwall-theme                 # write every target
    blackwall-theme waybar rofi     # write just these
    blackwall-theme --list          # what exists and where it goes
    blackwall-theme --dry-run       # print instead of writing
    blackwall-theme --check         # audit hand-written files against the scale

Run by `scripts/setwall` immediately after `wallust run`, so a wallpaper change
re-themes the whole rice in one pass.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .emit import gtk, hypr, plain, qt, rasi, scss, spicetify, swaync
from .palette import load
from .tokens import build

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

#: name -> (renderer, destination, one-line description)
TARGETS: dict[str, tuple] = {
    "hypr": (hypr.hypr, ROOT / "hypr" / "configs" / "colors.conf",
             "border, shadow and group colours"),
    "waybar": (gtk.waybar, ROOT / "waybar" / "tokens.css",
               "colours for the bar"),
    "wlogout": (gtk.wlogout, ROOT / "wlogout" / "colors" / "tokens.css",
                "colours for the power menu"),
    "gtk3": (gtk.gtk3, ROOT / ".themes" / "wallust" / "gtk-3.0" / "colors.css",
             "GTK3 app theme (Thunar)"),
    "gtk4": (gtk.gtk4, CONFIG / "gtk-4.0" / "colors.css",
             "GTK4 / libadwaita app theme"),
    "eww": (scss.eww, ROOT / "eww" / "tokens.scss",
            "full token set as SCSS variables"),
    "rofi": (rasi.rofi, ROOT / "rofi" / "shared" / "blackwall.rasi",
             "the shared glass shell for every launcher"),
    "swaync": (swaync.swaync, CONFIG / "swaync" / "style.css",
               "SwayNotificationCenter stylesheet"),
    "mako": (plain.mako, ROOT / "mako" / "config",
             "notification banners"),
    "cava": (plain.cava, ROOT / "cava" / "config",
             "audio visualiser"),
    "kitty": (plain.kitty, ROOT / "kitty" / "colors.conf",
              "all sixteen ANSI colours"),
    "nvim": (plain.nvim, ROOT / "nvim" / "lua" / "custom" / "blackwall_palette.lua",
             "palette table for the colourscheme"),
    "qt6ct": (qt.qt6ct, CONFIG / "qt6ct" / "qt6ct.conf",
              "Qt platform theme settings"),
    "qtcolors": (qt.qt6ct_colors,
                 CONFIG / "qt6ct" / "colors" / f"{qt.KV_NAME}.conf",
                 "the twenty-one QPalette roles"),
    "spotify": (spicetify.colors,
                CONFIG / "spicetify" / "Themes" / "blackwall" / "color.ini",
                "Spotify colour slots (needs `spicetify apply`)"),
    "spotifycss": (spicetify.user_css,
                   CONFIG / "spicetify" / "Themes" / "blackwall" / "user.css",
                   "Spotify radii and scrollbar"),
    "kvantum": (qt.kvantum,
                CONFIG / "Kvantum" / qt.KV_NAME / f"{qt.KV_NAME}.kvconfig",
                "Qt widget style, derived from KvMojave"),
    # Spliced into an existing hand-written file rather than replacing it;
    # see `splice` below and the docstring on plain.tmux.
    "tmux": (plain.tmux, ROOT / "tmux" / "tmux.conf.local",
             "oh-my-tmux theme slots (spliced block)"),
}

BEGIN = "# >>> blackwall theme - generated, do not edit inside this block"
END = "# <<< blackwall theme"
#: Targets written as a marked block inside a hand-written file, because the
#: consumer cannot include a second file. Everything else owns its whole file.
SPLICED = {"tmux"}


def splice(path: Path, body: str) -> str:
    """Replace the marked block in `path`, or append one if none exists."""
    try:
        current = path.read_text()
    except OSError:
        current = ""
    block = f"{BEGIN}\n{body.rstrip()}\n{END}\n"
    if BEGIN in current and END in current:
        head, rest = current.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        return head + block + tail.lstrip("\n")
    return current.rstrip("\n") + "\n\n" + block


# --------------------------------------------------------------------------
# check: the one hole the GTK-CSS limitation leaves open
# --------------------------------------------------------------------------

#: GTK's CSS has only `@define-color`, so radii cannot be passed as tokens and
#: have to be literals in the hand-written stylesheets. That is safe as long as
#: the literals stay on the scale, which is what this audits.
SCALE = {"22px", "18px", "12px", "8px", "999px", "0px", "0", "100%"}
CHECKED = (
    "waybar/style.css",
    "wlogout/style.css",
    "eww/eww.scss",
    "eww/scss/common.scss",
    "eww/scss/control_center.scss",
    "eww/scss/stickers.scss",
)
_RADIUS = re.compile(r"border-radius\s*:\s*([^;]+);")


def check() -> int:
    problems = 0
    for rel in CHECKED:
        path = ROOT / rel
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            found = _RADIUS.search(line)
            if not found:
                continue
            for value in found.group(1).split():
                value = value.strip()
                # SCSS variables resolve to the scale by construction.
                if value.startswith("$") or value in SCALE:
                    continue
                print(f"{rel}:{number}: radius {value!r} is off the scale "
                      f"({', '.join(sorted(SCALE - {'0', '0px'}))})")
                problems += 1
    if problems:
        print(f"\n{problems} off-scale radii")
    else:
        print(f"all radii on the scale across {len(CHECKED)} files")
    return 1 if problems else 0


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="blackwall-theme",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("targets", nargs="*", help="targets to write (default: all)")
    parser.add_argument("--list", action="store_true", help="show targets and exit")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    parser.add_argument("--check", action="store_true",
                        help="audit hand-written files against the radius scale")
    parser.add_argument("--palette", type=Path, default=None,
                        help="read this palette JSON instead of the usual sources")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        width = max(len(n) for n in TARGETS)
        for name, (_, path, what) in TARGETS.items():
            shown = str(path).replace(str(Path.home()), "~")
            print(f"{name:<{width}}  {what}\n{'':<{width}}  -> {shown}")
        return 0

    if args.check:
        return check()

    unknown = set(args.targets) - set(TARGETS)
    if unknown:
        parser.error(f"unknown target(s): {', '.join(sorted(unknown))}")
    wanted = args.targets or list(TARGETS)

    palette = load(args.palette)
    tokens = build(palette)

    if not args.quiet and not args.dry_run:
        print(f"palette: {palette.source}"
              f"  bg {tokens.bg.hex6}  fg {tokens.fg.hex6}"
              f"  accent {tokens.accent.hex6}")

    written = 0
    for name in wanted:
        render, path, _ = TARGETS[name]
        body = render(tokens)
        if name in SPLICED:
            body = splice(path, body)
        if args.dry_run:
            print(f"\n{'=' * 8} {name} -> {path} {'=' * 8}\n{body}")
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
        except OSError as error:
            print(f"  {name}: {error}", file=sys.stderr)
            continue
        if name == "kvantum":
            note = qt.prepare(path)
            if note and not args.quiet:
                print(f"  {'':<8} {note}")
        written += 1
        if not args.quiet:
            shown = str(path).replace(str(Path.home()), "~")
            print(f"  {name:<8} {shown}")

    if not args.quiet and not args.dry_run:
        print(f"{written}/{len(wanted)} written")
    return 0 if args.dry_run or written == len(wanted) else 1


if __name__ == "__main__":
    raise SystemExit(main())
