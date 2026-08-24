#!/usr/bin/env python3
"""GTK-level checks, run under SYSTEM python.

Not a pytest module on purpose. PyGObject is built against system python 3.14
and cannot be imported from the 3.13 uv venv, so a pytest version of this file
would `importorskip` on every run - a test that always skips proves nothing.

Run:  python3 tests/gtk/check_selection.py

Covers the selection-to-clipboard path, which silently did nothing for a long
time: PyGObject returns GtkLabel.get_selection_bounds() as THREE values,
(found, start, end). The old code unpacked two, sliced text[True:0] - that is
text[1:0], always "" - and a `if not text.strip()` guard swallowed the result.
The copy looked implemented and never once ran.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from archpilot.ui.gtk_app import ArchPilotWindow

TEXT = "bluetooth.service exited 1 at boot."


def label(text: str = TEXT) -> Gtk.Label:
    return Gtk.Label(label=text, selectable=True)


def selected(labels) -> str:
    """Call the real method without building a window."""
    window = ArchPilotWindow.__new__(ArchPilotWindow)
    window._selectables = labels
    return ArchPilotWindow._selected_text(window)


def check_bounds_returns_three_values():
    widget = label()
    widget.select_region(0, 9)
    bounds = widget.get_selection_bounds()
    assert len(bounds) == 3, bounds
    assert tuple(bounds) == (True, 0, 9), bounds


def check_the_old_unpacking_yielded_nothing():
    """Why this failed silently instead of raising."""
    widget = label()
    widget.select_region(0, 9)
    bounds = widget.get_selection_bounds()
    assert widget.get_text()[bounds[0]:bounds[1]] == ""      # text[True:0]


def check_selected_text_reads_the_selection():
    widget = label()
    widget.select_region(0, 9)
    assert selected([widget]) == "bluetooth"


def check_no_selection_reads_as_empty():
    assert selected([label()]) == ""


def check_whitespace_only_selection_is_ignored():
    """Selecting the gap between words must not clobber the clipboard."""
    widget = label()
    widget.select_region(17, 18)
    assert selected([widget]) == ""


def check_every_registered_label_is_searched():
    first, second = label("nothing here"), label("the answer text")
    second.select_region(4, 10)
    assert selected([first, second]) == "answer"


def check_selection_is_published_to_primary():
    """The mechanism the watcher relies on: GTK puts every selection on
    PRIMARY itself, whichever gesture made it."""
    display = Gdk.Display.get_default()
    if display is None:
        print("  (skipped: no display)")
        return
    widget = label()
    widget.select_region(0, 9)
    assert display.get_primary_clipboard().is_local()


def main() -> int:
    checks = [v for k, v in sorted(globals().items()) if k.startswith("check_")]
    failed = 0
    for check in checks:
        try:
            check()
            print(f"PASS {check.__name__}")
        except Exception as exc:                      # noqa: BLE001
            failed += 1
            print(f"FAIL {check.__name__}: {exc!r}")
    print(f"\n{len(checks) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
