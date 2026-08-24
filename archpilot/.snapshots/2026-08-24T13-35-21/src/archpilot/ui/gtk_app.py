"""The ArchPilot window.

The prompt is a *rendered label*, not a GtkEntry: vim owns the text, the cursor
and the mode (archpilot.vim), so letting an Entry also handle keys would mean
two editors fighting over one buffer. The block cursor is drawn with a Pango
background span, which is also why it looks like vim.

Layout reads top to bottom like any chat: transcript first, input last.

The one exception to vim owning the keyboard is the sudo password field, which
is a real Entry - it must never be echoed anywhere.
"""

from __future__ import annotations

import atexit
import contextlib
import html
import os
import signal
import shutil
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from .. import ipc  # noqa: E402
from .. import commands  # noqa: E402
from ..markup import linkify  # noqa: E402
from ..vim import INSERT, NORMAL, VBLOCK, VISUAL, VLINE, VimBuffer  # noqa: E402
from .client import DaemonClient  # noqa: E402
from .theme import css, theme_source  # noqa: E402

#: Set ARCHPILOT_UI_DEBUG to a path to trace every keypress.
_DEBUG = os.environ.get("ARCHPILOT_UI_DEBUG")

UI_CLASS = "dev.archpilot.ui"

# Codepoints, never pasted literals: a literal glyph gets stripped somewhere
# between heredoc and file, and `assert "" in text` passes vacuously.
ICON_NEW, ICON_HISTORY, ICON_STOP = "\uf067", "\uf1da", "\uf04d"
ICON_COPY, ICON_PLAY, ICON_KEY = "\uf0c5", "\uf04b", "\uf084"
# A gauge reads as "how full is it" far better than a memory chip did.
ICON_CTX, ICON_CLOCK = "\U000F0F86", "\U000F0150"
ICON_CAL, ICON_DONE = "\U000F0E17", "\uf00c"
ICON_CLOSE = "\uf00d"          # a small x, for closing a tab or chip

#: Application commands live on ctrl-<key> so they never shadow a vim motion -
#: `n`, `y`, `p`, `d` and `r` all mean something in normal mode already.
COMMANDS = {
    "ctrl-n": ("new", {}),
    "ctrl-s": ("picker", {"kind": "sessions"}),
    "ctrl-c": ("cancel", {}),
}

NAMED_KEYS = {
    Gdk.KEY_Escape: "escape", Gdk.KEY_Return: "enter", Gdk.KEY_KP_Enter: "enter",
    Gdk.KEY_BackSpace: "backspace", Gdk.KEY_Left: "left", Gdk.KEY_Right: "right",
    Gdk.KEY_Home: "home", Gdk.KEY_End: "end", Gdk.KEY_Tab: "tab",
    Gdk.KEY_ISO_Left_Tab: "tab", Gdk.KEY_Up: "up", Gdk.KEY_Down: "down",
}

#: Shown next to each button so the keybinding is discoverable without docs.
TIPS = {
    "new": "New chat  (ctrl-n)",
    "history": "History  (ctrl-h)",
    "stop": "Stop  (ctrl-c)",
    "copy": "Copy message  (drag-select also copies)",
    "run": "Run  (super+enter)",
    "mode": "Mode  (tab)",
    "model": "Model  (ctrl+tab)",
    "effort": "Effort  (alt+tab)",
}


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def _wl_copy(text: str, primary: bool = False) -> None:
    """Hand text to wl-copy without waiting on it.

    wl-copy forks and stays resident to serve the selection, so waiting for it
    to exit blocks until something else takes ownership - which froze the UI.
    Write, close stdin, walk away.
    """
    argv = ["wl-copy"] + (["--primary"] if primary else [])
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        return
    try:
        proc.stdin.write(text.encode())
        proc.stdin.close()
    except (OSError, BrokenPipeError):
        pass


def copy_to_clipboard(text: str) -> None:
    """Put text on the system clipboard.

    GTK's own clipboard only lives while this process owns the selection, so
    wl-copy is what actually makes it survive into other apps - that is the
    "synced with the system" half. Both are set so an in-app paste works too.
    """
    if not text:
        return
    display = Gdk.Display.get_default()
    if display is not None:
        try:
            display.get_clipboard().set(text)
        except (TypeError, AttributeError):
            pass
    _wl_copy(text)


def copy_to_primary(text: str) -> None:
    """Mouse-selection clipboard, so drag-select behaves like everywhere else."""
    if text:
        _wl_copy(text, primary=True)


class ArchPilotWindow(Gtk.ApplicationWindow):
    #: Pango markup cannot read GTK CSS, so caret and selection colours are
    #: literals. Chosen to read on both light-ish and dark wallust palettes.
    CARET = "#8ab4f8"
    CARET_FG = "#0d0d0d"
    SELECT = "#3b4a63"

    WIDTH = 900
    MIN_HEIGHT = 176
    #: The window may grow this tall. The `:` panel and the help sheet
    #: need more than a conversation does, or they get clipped by the
    #: bottom of the window with no way to scroll to the rest.
    MAX_HEIGHT = 560
    MAX_HEIGHT_PANEL = 700
    #: Tallest the transcript may get before it scrolls instead of growing.
    TRANSCRIPT_MAX = 330
    #: The prompt scrolls past this rather than pushing the window taller -
    #: an input that grows without limit eats the conversation above it.
    PROMPT_MAX = 118
    #: Every attachment preview is this square. Small enough that a
    #: handful never crowds out the input.
    THUMB = 44
    #: Tiles per row before wrapping onto the next one.
    THUMBS_PER_ROW = 12
    #: How tall the `:` panel may grow, suggesting versus helping.
    SUGGEST_MAX = 260
    HELP_MAX = 430
    MAX_HITS = 7

    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="ArchPilot")
        self.set_default_size(self.WIDTH, self.MIN_HEIGHT)
        self.set_decorated(False)
        self.add_css_class("archpilot")

        self.buffer = VimBuffer(mode=INSERT)
        self.state: dict = {"status": "down"}
        self.client = DaemonClient(self._on_state, on_event=self._on_event_msg)
        self._applied_height = 0
        self._rendered_turns: list = []
        #: How many messages were on screen last render, so a rebuild
        #: can tell an arriving message from a redrawn one.
        self._shown_count = 0

        # Which half of the window the keyboard is aimed at. Tab moves between
        # them; the chat region is a vim-ish list where j/k select messages.
        self.focus_region = "input"          # input | chat
        self._pending_g = False
        self._pending_z = False
        #: The `:` command line, when open.
        self.cmdline = None
        self._rows: list = []
        #: Row index -> its copy button, so `y` can flash the same one a
        #: click would. Rebuilt whenever the transcript is re-rendered.
        self._copy_buttons: dict = {}
        #: Labels whose selection should reach the clipboard. Rebuilt with
        #: the transcript, so it never points at detached widgets.
        self._selectables: list = []
        self._draft_loaded = False
        #: Position while walking back through sent prompts with the arrow
        #: keys. None means not walking.
        self._recall_index = None
        self._recall_draft = ""
        #: When Esc was last pressed, for the double-Esc stop.
        self._last_escape = 0.0
        self.selected = -1                   # -1 means "the newest"
        self.search_active = False
        self.search_query = ""
        self.search_hits: list = []
        self.search_index = 0
        self._all_history: list = []
        #: Index of the history row being renamed, or None.
        self.renaming = None
        self.rename_text = ""
        #: `:` suggestion list state, and whether :help is pinned open.
        self.cmd_hits: list = []
        self.cmd_rows: list = []
        self._cmd_selected_row = None
        self.cmd_index = 0
        self.help_open = False

        self._build()
        self._install_keys()
        # While this window has focus the rest of the SUPER keymap must be
        # inert, or hyprland binds fire underneath whatever you are typing.
        self._watch_theme()
        self._watch_selection()
        self._install_drop_target()
        self.connect("notify::is-active", self._on_focus_change)
        self.connect("close-request", self._on_close)
        self.client.start()

    # -- construction ----------------------------------------------------
    def _build(self) -> None:
        self.problem: dict = {}
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.add_css_class("ap-root")
        self.set_child(root)

        # One row of tabs, hidden until there is more than one conversation -
        # a tab bar with a single tab in it is furniture.
        self.tabbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tabbar.set_visible(False)
        root.append(self.tabbar)

        root.append(self._build_header())
        root.append(self._build_meters())

        # History lives at the top, with its own query line: reusing the prompt
        # at the bottom meant the thing you were typing into was nowhere near
        # the results it was filtering.
        self.search_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search_panel.set_visible(False)
        self.search_field = Gtk.Label(xalign=0)
        self.search_field.set_use_markup(True)
        self.search_field.add_css_class("search-field")
        self.search_panel.append(self.search_field)
        self.search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.search_panel.append(self.search_box)
        root.append(self.search_panel)

        # transcript first, input last - the conversation reads downward
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_propagate_natural_height(True)
        self.scroller.set_max_content_height(self.TRANSCRIPT_MAX)
        self.scroller.add_css_class("chat")
        self.messages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        # #16: a fatter cursor over the conversation. GTK has no block cursor,
        # but "cell" is the closest standard shape and reads very differently
        # from the thin I-beam - which is the point.
        self.messages.set_cursor_from_name("cell")
        self.scroller.set_child(self.messages)
        root.append(self.scroller)

        # #4: everything below this line sits on the bottom edge. The spacer,
        # not the transcript, does the expanding - the transcript is hidden
        # whenever there are no messages, and a hidden widget absorbs nothing,
        # which left the input stranded at the top of an empty window.
        root.append(Gtk.Box(vexpand=True))



        self.approval = self._build_panel()
        root.append(self.approval["root"])
        self.password = self._build_password()
        root.append(self.password["root"])

        self.notice = self._build_notice()
        root.append(self.notice["root"])

        self.error = Gtk.Label(xalign=0, wrap=True)
        self.error.add_css_class("error")
        self.error.set_visible(False)
        root.append(self.error)

        # Command suggestions and the help sheet. Above the input, because
        # that is where you are looking while typing a `:` command.
        self.cmd_panel = Gtk.ScrolledWindow()
        self.cmd_panel.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.cmd_panel.set_propagate_natural_height(True)
        self.cmd_panel.set_max_content_height(self.SUGGEST_MAX)
        self.cmd_panel.add_css_class("cmd-panel")
        self.cmd_panel.set_visible(False)
        self.cmd_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.cmd_panel.set_child(self.cmd_list)
        root.append(self.cmd_panel)

        # Staged images and files, shown directly above the input. Without
        # this a pasted image attached silently and the paste looked like it
        # had done nothing at all.
        # Rows of tiles, wrapped by hand. A FlowBox looks like the obvious
        # choice but stretches each GtkFlowBoxChild to the full width, so nine
        # thumbnails came out as nine full-width bars stacked vertically.
        self.attach_strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.attach_strip.add_css_class("attachments")
        self.attach_strip.set_visible(False)
        root.append(self.attach_strip)

        root.append(self._build_prompt())

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.hint = Gtk.Label(
            label="i insert · tab chat · ctrl-h history · shift+tab mode · ZZ close",
            xalign=0)
        self.hint.add_css_class("hint")
        footer.append(self.hint)
        footer.append(Gtk.Box(hexpand=True))
        self.toast = Gtk.Label(label="", xalign=1)
        self.toast.add_css_class("toast")
        self.toast.set_visible(False)
        footer.append(self.toast)
        root.append(footer)

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.vim_chip = Gtk.Label(label="INS")
        self.vim_chip.add_css_class("vim")
        header.append(self.vim_chip)


        # Mode is the only chip with consequences - ask cannot touch the
        # machine, action can - so it gets the weight. Model and effort are
        # preferences; they sit together in one quiet control instead of
        # three identical pills that all look equally important.
        self.chips = {}
        mode = self._button("", "chip",
                            lambda _b: self._cycle("mode"), tip=TIPS["mode"])
        mode.add_css_class("chip-primary")
        self.chips["mode"] = mode
        header.append(mode)

        engine = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        engine.add_css_class("engine-group")
        for name in ("model", "effort"):
            chip = self._button("", "chip", lambda _b, f=name: self._cycle(f),
                                tip=TIPS[name])
            chip.add_css_class("chip-quiet")
            self.chips[name] = chip
            engine.append(chip)
        header.append(engine)

        self.status = Gtk.Label(label="")
        self.status.add_css_class("status")
        header.append(self.status)
        # A spinner while a turn is in flight - most of that wait is the model
        # thinking, so the honest thing is to show that something is happening
        # rather than pretend it is instant.
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        header.append(self.spinner)
        header.append(Gtk.Box(hexpand=True))

        header.append(self._button(ICON_NEW, "icon-btn", self._cmd_new, TIPS["new"]))
        header.append(self._button(ICON_HISTORY, "icon-btn", self._cmd_history,
                                   TIPS["history"]))
        self.stop_button = self._button(ICON_STOP, "icon-btn", self._cmd_cancel,
                                        TIPS["stop"])
        self.stop_button.set_visible(False)
        header.append(self.stop_button)
        return header

    def _build_meters(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.ctx = self._meter(ICON_CTX, with_bar=True)
        self.lim5 = self._meter(ICON_CLOCK, with_bar=True)
        self.limw = self._meter(ICON_CAL)
        for meter in (self.ctx, self.lim5, self.limw):
            row.append(meter["root"])
        row.append(Gtk.Box(hexpand=True))
        return row

    def _build_prompt(self) -> Gtk.Widget:
        # The prompt scrolls internally once it passes PROMPT_MAX so a long
        # paste cannot push the transcript off the top of the window.
        holder = Gtk.ScrolledWindow()
        holder.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        holder.set_propagate_natural_height(True)
        holder.set_max_content_height(self.PROMPT_MAX)
        holder.add_css_class("prompt")
        self.prompt = Gtk.Label(xalign=0, yalign=0)
        self.prompt.set_use_markup(True)
        self.prompt.set_wrap(True)
        self.prompt.set_wrap_mode(2)          # WORD_CHAR
        holder.set_child(self.prompt)
        self.prompt_holder = holder

        # Half-typed operators ("d", "2f", "\"a) float INSIDE the input, pinned
        # to its bottom-right. An overlay child takes no space in the layout,
        # so the chip appearing and disappearing can no longer resize the
        # footer and shove the input up and down under the cursor.
        overlay = Gtk.Overlay()
        overlay.set_child(holder)
        self.pending_chip = Gtk.Label(label="")
        self.pending_chip.add_css_class("pending-keys")
        self.pending_chip.set_visible(False)
        self.pending_chip.set_halign(Gtk.Align.END)
        self.pending_chip.set_valign(Gtk.Align.END)
        self.pending_chip.set_can_target(False)     # never eat a click
        overlay.add_overlay(self.pending_chip)
        return overlay

    def _meter(self, icon: str, with_bar: bool = False) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.add_css_class("meter")
        glyph = Gtk.Label(label=icon)
        glyph.add_css_class("meter-icon")
        value = Gtk.Label(label="")
        value.add_css_class("meter-value")
        box.append(glyph)
        box.append(value)
        bar = None
        if with_bar:
            bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER)
            bar.add_css_class("meter-bar")
            box.append(bar)
        note = Gtk.Label(label="")
        note.add_css_class("meter-note")
        box.append(note)
        return {"root": box, "value": value, "bar": bar, "note": note}

    def _build_panel(self) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.add_css_class("panel")
        box.set_visible(False)
        title = Gtk.Label(label="waiting on you", xalign=0)
        title.add_css_class("panel-title")
        command = Gtk.Label(xalign=0, wrap=True, selectable=True)
        command.add_css_class("mono")
        reason = Gtk.Label(xalign=0, wrap=True)
        reason.add_css_class("small")
        keys = Gtk.Label(label="y approve · x deny", xalign=0)
        keys.add_css_class("hint")
        for child in (title, command, reason, keys):
            box.append(child)
        return {"root": box, "command": command, "reason": reason}

    def _build_notice(self) -> dict:
        """The yellow panel for a recognised failure.

        Deliberately not styled like the red error line. Being signed out is
        not a crash - it is a five-second fix - and a panel that looks alarming
        for something routine trains the user to ignore it.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("panel")
        box.add_css_class("notice")
        box.set_visible(False)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label="\N{WARNING SIGN}")
        icon.add_css_class("notice-icon")
        title = Gtk.Label(xalign=0)
        title.add_css_class("panel-title")
        head.append(icon)
        head.append(title)
        box.append(head)

        detail = Gtk.Label(xalign=0, wrap=True, selectable=True)
        detail.add_css_class("small")
        box.append(detail)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        command = Gtk.Label(xalign=0, wrap=True, selectable=True, hexpand=True)
        command.add_css_class("mono")
        row.append(command)
        fix = self._button("run it", "notice-fix", self._run_fix,
                           "open a terminal and run this")
        row.append(fix)
        retry = self._button("retry", "notice-retry", self._retry_turn,
                             "send the last prompt again")
        row.append(retry)
        box.append(row)

        keys = Gtk.Label(xalign=0)
        keys.add_css_class("hint")
        box.append(keys)

        return {"root": box, "title": title, "detail": detail, "command": command,
                "row": row, "fix": fix, "retry": retry, "keys": keys}

    def _build_password(self) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.add_css_class("panel")
        box.add_css_class("danger")
        box.set_visible(False)
        title = Gtk.Label(xalign=0)
        title.add_css_class("panel-title")
        entry = Gtk.Entry(visibility=False)
        entry.add_css_class("secret")
        entry.connect("activate", self._submit_password)
        box.append(title)
        box.append(entry)
        return {"root": box, "title": title, "entry": entry}

    @staticmethod
    def _button(label: str, css_class: str, handler,
                tip: str = "", hexpand: bool = False) -> Gtk.Button:
        """A button that can never take keyboard focus.

        GTK activates the focused widget on Space and Enter. With a focusable
        button in the header, typing a space pressed it and the keystroke never
        reached the editor.
        """
        button = Gtk.Button(label=label, hexpand=hexpand)
        button.add_css_class(css_class)
        button.set_can_focus(False)
        button.set_focus_on_click(False)
        if tip:
            button.set_tooltip_text(tip)
        button.connect("clicked", handler)
        return button

    # -- state -----------------------------------------------------------
    def _on_state(self, state: dict) -> None:
        GLib.idle_add(self._apply_state, state)

    def _on_event_msg(self, event: dict) -> None:
        """Non-state events, marshalled onto the GTK thread."""
        GLib.idle_add(self._handle_event, event)

    def _handle_event(self, event: dict) -> bool:
        if event.get("ev") == ipc.EV_RESTORE_INPUT:
            self._restore_input(event.get("text") or "")
        return False

    def _restore_input(self, text: str) -> None:
        """Put a rewound message back in the input, as if it was never sent."""
        self.buffer.text = text
        self.buffer.cursor = len(text)
        self.buffer.mode = INSERT
        self.focus_region = "input"
        self.selected = -1
        self._apply_selection()
        self._render_prompt()
        GLib.idle_add(self._scroll_prompt_to_cursor, priority=GLib.PRIORITY_LOW)

    def _apply_state(self, state: dict) -> bool:
        previous, self.state = self.state, state

        for name, chip in self.chips.items():
            chip.set_label(str(state.get(name) or "-"))
            for css_class in ("mode-ask", "mode-action"):
                chip.remove_css_class(css_class)
            if name == "mode" and state.get("mode"):
                chip.add_css_class(f"mode-{state['mode']}")

        status = state.get("status") or ""
        thinking = status == "thinking"
        self.stop_button.set_visible(thinking)
        self.spinner.set_visible(thinking)
        if thinking:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.status.set_text({"thinking": "thinking", "awaiting_approval": "needs you",
                              "down": "daemon down", "idle": ""}.get(status, status))

        self._render_tabs(state)
        self._update_meters(state)

        turns = state.get("turns") or []
        if turns != self._rendered_turns:
            self._rendered_turns = turns
            self._render_messages(turns)
            GLib.idle_add(self._scroll_to_bottom)
        self.scroller.set_visible(bool(turns) and not self.search_active)

        # The daemon being down is not something the daemon can report, so
        # the widget has to notice its own silence.
        problem = state.get("problem")
        if status == "down":
            problem = {
                "kind": "daemon",
                "title": "ArchPilot daemon is not running",
                "detail": "Nothing can answer until it is back up.",
                "command": "systemctl --user restart archpilotd",
                "retry": False,
            }
        self._render_notice(problem)
        self._render_attachments(state.get("attachments") or [])
        # The raw text only earns space when nothing recognised it - otherwise
        # it is the same failure said twice, once unhelpfully.
        raw = "" if state.get("problem") else (state.get("error") or "")
        self.error.set_text(raw)
        self.error.set_visible(bool(raw))

        pending = state.get("pending") or ""
        self.approval["root"].set_visible(bool(pending))
        self.approval["command"].set_text(pending)
        self.approval["reason"].set_text(state.get("pending_reason") or "")

        needs_password = bool(state.get("needs_password"))
        self.password["root"].set_visible(needs_password)
        if needs_password:
            self.password["title"].set_text(f"{ICON_KEY}  {state.get('password_prompt','')}")
            self.password["entry"].grab_focus()

        # #2: whatever was half-typed survives closing the window.
        if not self._draft_loaded:
            self._draft_loaded = True
            if draft := state.get("draft"):
                self.buffer.text = draft
                self.buffer.cursor = len(draft)
                self.buffer.mode = INSERT

        self.hint.set_visible(not turns and not self.search_active)
        self._render_prompt()
        GLib.idle_add(self._fit_height)
        return False

    def _render_attachments(self, paths: list) -> None:
        """Show what is staged for the next prompt: thumbnail, name, remove."""
        if paths == getattr(self, "_rendered_attachments", None):
            return
        self._rendered_attachments = list(paths)

        while (child := self.attach_strip.get_first_child()) is not None:
            self.attach_strip.remove(child)
        self.attach_strip.set_visible(bool(paths))

        row = None
        for index, path in enumerate(paths):
            if index % self.THUMBS_PER_ROW == 0:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row.set_halign(Gtk.Align.START)
                self.attach_strip.append(row)

            # Every preview is the same square whatever the image's own aspect
            # ratio, so a wide screenshot and a tall one line up instead of
            # making the row ragged. COVER crops to fill rather than letterbox,
            # and HIDDEN keeps the crop inside the rounded corners.
            tile = Gtk.Overlay()
            tile.add_css_class("attachment")
            tile.set_size_request(self.THUMB, self.THUMB)
            tile.set_halign(Gtk.Align.START)
            tile.set_valign(Gtk.Align.START)
            tile.set_overflow(Gtk.Overflow.HIDDEN)
            tile.set_tooltip_text(os.path.basename(path))

            child = None
            if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                child = self._thumbnail(path)
            tile.set_child(child or self._attachment_placeholder(path))

            drop = self._button(
                ICON_CLOSE, "attachment-drop",
                lambda _b, target=path: self._send({"op": ipc.OP_DETACH, "path": target}),
                "remove")
            drop.set_halign(Gtk.Align.END)
            drop.set_valign(Gtk.Align.START)
            tile.add_overlay(drop)

            # An explicit motion controller rather than a CSS :hover rule.
            # The tile is an Overlay whose child fills it, and the hover state
            # did not reach the descendant selector - the x stayed invisible
            # with the pointer right on top of it.
            hover = Gtk.EventControllerMotion()
            hover.connect("enter", lambda *_a, t=tile: t.add_css_class("hovered"))
            hover.connect("leave", lambda *_a, t=tile: t.remove_css_class("hovered"))
            tile.add_controller(hover)
            row.append(tile)

    def _thumbnail(self, path: str) -> Gtk.Widget | None:
        """A square, centre-cropped preview.

        Cropped rather than letterboxed: fitting the whole image inside the
        square leaves dark bands above and below anything wide, and a row of
        differently-banded tiles looks broken even though each one is the same
        size. Filling the square is what a photo grid does.

        Gtk.Image with a pixel size would be uniform but letterboxed, and
        Gtk.Picture reports the image's own dimensions as its natural size -
        set_size_request only sets a MINIMUM - so it stretches the tile.
        """
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception:  # noqa: BLE001
            return None

        size = self.THUMB
        width, height = pixbuf.get_width(), pixbuf.get_height()
        if width <= 0 or height <= 0:
            return None

        scale = max(size / width, size / height)          # cover, not contain
        scaled = pixbuf.scale_simple(max(size, int(width * scale + 0.5)),
                                     max(size, int(height * scale + 0.5)),
                                     GdkPixbuf.InterpType.BILINEAR)
        if scaled is None:
            return None
        left = max(0, (scaled.get_width() - size) // 2)
        top = max(0, (scaled.get_height() - size) // 2)
        cropped = scaled.new_subpixbuf(left, top, size, size) or scaled

        image = Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(cropped))
        image.set_pixel_size(size)
        image.add_css_class("attachment-thumb")
        return image

    @staticmethod
    def _attachment_placeholder(path: str) -> Gtk.Widget:
        """For anything with no preview: the extension, centred."""
        suffix = os.path.splitext(path)[1].lstrip(".").upper() or "FILE"
        label = Gtk.Label(label=suffix[:4])
        label.add_css_class("attachment-kind")
        return label

    def _render_notice(self, problem: dict | None) -> None:
        """Show a recognised failure, with whatever the user can do about it."""
        self.problem = problem or {}
        panel = self.notice
        panel["root"].set_visible(bool(problem))
        if not problem:
            return

        panel["title"].set_text(problem.get("title") or "Something went wrong")
        panel["detail"].set_text(problem.get("detail") or "")

        command = problem.get("command") or ""
        panel["command"].set_text(command)
        panel["command"].set_visible(bool(command))
        panel["fix"].set_visible(bool(command))
        panel["retry"].set_visible(bool(problem.get("retry")))
        panel["row"].set_visible(bool(command) or bool(problem.get("retry")))

        hints = []
        if command:
            hints.append("L run it")
        if problem.get("retry"):
            hints.append("R retry")
        hints.append("esc dismiss")
        panel["keys"].set_text(" \N{MIDDLE DOT} ".join(hints))

    def _run_fix(self, _button=None) -> None:
        """Run the fix in a terminal.

        `claude /login` is an interactive OAuth flow: it needs a tty and opens a
        browser. Reimplementing it inside GTK would mean impersonating Claude
        Code's own auth client, so instead the button gets the user to the real
        flow in one keypress rather than making them type the command.
        """
        command = (self.problem or {}).get("command")
        if not command:
            return
        terminal = next((t for t in ("kitty", "foot", "alacritty", "ghostty",
                                     "wezterm", "xterm")
                         if shutil.which(t)), "")
        if not terminal:
            copy_to_clipboard(command)
            self._toast("no terminal found - command copied")
            return
        # Held open after it exits so a login failure is still readable.
        subprocess.Popen(
            [terminal, "-e", "sh", "-c", f"{command}; echo; read -r _"],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._toast(f"running {command}")

    def _retry_turn(self, _button=None) -> None:
        """Resend the prompt that failed, without making the user retype it."""
        prompt = (self.state.get("prompt") or "").strip()
        if not prompt:
            self._toast("nothing to retry")
            return
        self._send({"cmd": "prompt", "text": prompt})
        self._dismiss_notice()

    def _dismiss_notice(self) -> None:
        self.notice["root"].set_visible(False)
        self.problem = {}

    def _render_tabs(self, state: dict) -> None:
        tabs = state.get("tabs") or []
        self.tabbar.set_visible(len(tabs) > 1)
        if len(tabs) <= 1:
            return
        while (child := self.tabbar.get_first_child()) is not None:
            self.tabbar.remove(child)
        active = state.get("tab_active", 0)
        for index, tab in enumerate(tabs):
            label = tab.get("title") or "new chat"
            if tab.get("busy"):
                label += " ..."
            # A box, not a bare button, so the tab can carry its own close x
            # the way every other tabbed thing on the desktop does.
            # The holder IS the tab - it carries the background and border -
            # and the label and the x sit inside it, both flat. Styling the
            # label as the tab instead left the x sitting outside it.
            holder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            holder.add_css_class("tab-holder")
            button = self._button(label, "tab",
                                  lambda _b, i=index: self._select_tab(i),
                                  f"Tab {index + 1}  (alt+{index + 1}, gt / gT)")
            close = self._button(
                ICON_CLOSE, "tab-close",
                lambda _b, i=index: self._close_tab(i),
                "close this chat  (ctrl+w)")
            if index == active:
                holder.add_css_class("on")
            holder.append(button)
            holder.append(close)
            self.tabbar.append(holder)

    def _close_tab(self, index: int) -> None:
        self._send({"op": ipc.OP_TAB, "action": "close", "index": index})

    def _select_tab(self, index: int) -> None:
        self._send({"op": ipc.OP_TAB, "action": "select", "index": index})

    def _update_meters(self, state: dict) -> None:
        used, total = state.get("context_used"), state.get("context_total")
        self.ctx["root"].set_visible(bool(total))
        if total:
            self.ctx["value"].set_text(f"{used}/{total}")
            self.ctx["bar"].set_fraction(float(state.get("context_frac") or 0))
            self.ctx["note"].set_text(f"{state.get('context_left','')} left")
            self._flag(self.ctx["root"], bool(state.get("context_warn")))

        five, pct5 = state.get("limit_5h"), int(state.get("limit_5h_pct") or 0)
        self.lim5["root"].set_visible(bool(five))
        if five:
            self.lim5["value"].set_text(f"{pct5}%")
            self.lim5["bar"].set_fraction(pct5 / 100)
            self.lim5["note"].set_text(f"{state.get('limit_5h_left','')} left")
            self._flag(self.lim5["root"], pct5 <= 15)

        week, pctw = state.get("limit_week"), int(state.get("limit_week_pct") or 0)
        self.limw["root"].set_visible(bool(week))
        if week:
            self.limw["value"].set_text(f"{pctw}%")
            self.limw["note"].set_text(f"{state.get('limit_week_left','')} left")
            self._flag(self.limw["root"], pctw <= 10)

    @staticmethod
    def _flag(widget: Gtk.Widget, warn: bool) -> None:
        if warn:
            widget.add_css_class("warn")
        else:
            widget.remove_css_class("warn")

    # -- messages --------------------------------------------------------
    def _render_messages(self, turns: list) -> None:
        while (child := self.messages.get_first_child()) is not None:
            self.messages.remove(child)
        self._rows = []
        # Stale entries would point at buttons that are no longer in the tree.
        self._copy_buttons = {}
        self._selectables = []
        # Every state push rebuilds this list, and during streaming that is
        # many times a second. Animating all of them each time would strobe,
        # so only rows that were not there a moment ago get the entrance.
        first_new = self._shown_count
        self._shown_count = len(turns)
        for index, turn in enumerate(turns):
            row = self._message(turn, index)
            if index >= first_new:
                row.add_css_class("fresh")
            self._rows.append(row)
            self.messages.append(row)
        self._apply_selection()

    def _apply_selection(self) -> None:
        """Mark the selected message, defaulting to the newest."""
        if not getattr(self, "_rows", None):
            return
        if self.selected < 0 or self.selected >= len(self._rows):
            self.selected = len(self._rows) - 1
        for index, row in enumerate(self._rows):
            chosen = index == self.selected and self.focus_region == "chat"
            if chosen:
                row.add_css_class("chosen")
            else:
                row.remove_css_class("chosen")

    def _move_selection(self, delta: int) -> None:
        if not getattr(self, "_rows", None):
            return
        self.selected = max(0, min(len(self._rows) - 1, self.selected + delta))
        self._apply_selection()
        self._scroll_selection_into_view()

    def _scroll_selection_into_view(self) -> None:
        if not getattr(self, "_rows", None):
            return
        row = self._rows[self.selected]
        adjustment = self.scroller.get_vadjustment()
        _, y = row.translate_coordinates(self.messages, 0, 0) or (0, 0)
        height = row.get_allocated_height()
        page = adjustment.get_page_size()
        if y < adjustment.get_value():
            adjustment.set_value(y)
        elif y + height > adjustment.get_value() + page:
            adjustment.set_value(y + height - page)

    def _selected_turn(self) -> dict:
        turns = self.state.get("turns") or []
        if 0 <= self.selected < len(turns):
            return turns[self.selected]
        return turns[-1] if turns else {}

    def _message(self, turn: dict, index: int = 0) -> Gtk.Widget:
        """One exchange: the question, the answer, and anything it proposed."""
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        wrap.add_css_class("message")

        if prompt := turn.get("prompt"):
            asked = Gtk.Label(xalign=0, wrap=True, selectable=True)
            # Markup, not plain text: a link you pasted into your own question
            # should be as clickable as one in the answer.
            asked.set_use_markup(True)
            asked.set_markup(linkify(esc(prompt)))
            asked.add_css_class("asked")
            self._auto_copy_selection(asked)
            self._enable_links(asked)
            wrap.append(asked)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True)
        bubble.add_css_class("bubble")
        if turn.get("streaming"):
            bubble.add_css_class("streaming")

        if turn.get("streaming") and not (turn.get("answer") or "").strip():
            # An empty bubble sitting there is indistinguishable from a broken
            # one. Three pulsing dots say "it is coming"; naming the tool says
            # it is not stuck, which is the question you actually have.
            bubble.append(self._typing_dots(turn.get("activity") or ""))
        else:
            answer = Gtk.Label(xalign=0, wrap=True, selectable=True)
            answer.set_use_markup(True)
            answer.set_markup(turn.get("answer_markup") or "")
            answer.add_css_class("answer")
            self._auto_copy_selection(answer)
            self._enable_links(answer)
            bubble.append(answer)

        for action in turn.get("actions") or []:
            bubble.append(self._action_row(action))

        if took := turn.get("took"):
            meta = Gtk.Label(label=f"{took}s", xalign=0)
            meta.add_css_class("took")
            bubble.append(meta)

        row.append(bubble)
        # Each message carries its own copy button, so you never have to work
        # out which part of the transcript a toolbar button was about. Pinned
        # to the top so it does not stretch down the side of a long answer.
        copy = self._button(ICON_COPY, "icon-btn", lambda b, t=turn: self._copy_message(t, b),
                            TIPS["copy"])
        copy.set_valign(Gtk.Align.START)
        # #9: `y` must animate exactly like a click does, so the keyboard path
        # needs a handle on the very same button.
        self._copy_buttons[index] = copy
        row.append(copy)
        wrap.append(row)
        return wrap

    def _enable_links(self, label: Gtk.Label) -> None:
        """Open a clicked link in the user's browser.

        GTK renders Pango anchors on its own, but without a handler
        activate-link does nothing and the link looks decorative.
        """
        label.connect("activate-link", self._open_link)

    def _open_link(self, _label, uri: str) -> bool:
        if not uri.startswith(("http://", "https://")):
            return False          # let GTK deal with anything unexpected
        subprocess.Popen(["xdg-open", uri], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._toast("opened in browser")
        return True               # handled; do not let GTK open it as well

    def _typing_dots(self, activity: str = "") -> Gtk.Widget:
        """Three dots that pulse in sequence while the answer is on its way.

        Driven from a timer rather than CSS keyframes: the timer stops itself
        the moment the widget leaves the tree, so a finished answer can never
        leave an animation running behind it.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.add_css_class("typing")
        dots = []
        for _ in range(3):
            dot = Gtk.Label(label="\N{BULLET}")
            dot.add_css_class("typing-dot")
            box.append(dot)
            dots.append(dot)

        if activity:
            note = Gtk.Label(label=activity, xalign=0)
            note.add_css_class("typing-note")
            note.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(note)

        state = {"step": 0}

        def pulse() -> bool:
            if box.get_parent() is None:       # removed from the tree - stop
                return False
            for index, dot in enumerate(dots):
                if index == state["step"] % 3:
                    dot.add_css_class("lit")
                else:
                    dot.remove_css_class("lit")
            state["step"] += 1
            return True

        pulse()
        GLib.timeout_add(320, pulse)
        return box

    def _action_row(self, action: dict) -> Gtk.Widget:
        command = action.get("command", "")
        if action.get("done"):
            # Already run: it stays in the conversation as a record, but it is
            # no longer something you can press again.
            done = Gtk.Label(label=f"{ICON_DONE}  {command}", xalign=0, wrap=True,
                             selectable=True)
            done.add_css_class("ran")
            self._auto_copy_selection(done)
            return done

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        run = self._button(f"{ICON_PLAY}  {command}", "action",
                           lambda _b, c=command: self._run_command(c),
                           TIPS["run"], hexpand=True)
        row.append(run)
        def copy_command(button, text=command) -> None:
            copy_to_clipboard(text)
            self._flash(button)
            self._toast("command copied")

        copy = self._button(ICON_COPY, "icon-btn", copy_command, TIPS["copy"])
        copy.set_valign(Gtk.Align.CENTER)
        row.append(copy)
        return row

    def _auto_copy_selection(self, label: Gtk.Label) -> None:
        """Register a label whose selection should reach the clipboard.

        The trigger is NOT a mouse gesture. GtkLabel runs its own drag gesture
        for selecting, and it claims the event sequence, so a second
        GestureClick on the same widget gets cancelled instead of released on
        exactly the drag-selects this is meant to catch.

        What is reliable is that GTK publishes every selection to the PRIMARY
        clipboard itself, however it was made - drag, double-click, shift-click
        or select-all. Watching primary means watching the one thing that is
        guaranteed to happen.
        """
        self._selectables.append(label)
        label.connect("copy-clipboard", lambda *_a: self._toast("copied"))

    def _watch_selection(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        primary = display.get_primary_clipboard()
        # There is no "changed" signal, but content/formats are properties, so
        # notify:: gives the same thing.
        primary.connect("notify::formats", self._mirror_selection)

    def _mirror_selection(self, *_args) -> None:
        """Copy a selection made in this window to the real clipboard.

        Only ever copies text taken from our OWN labels. Mirroring whatever
        lands on primary would hijack the clipboard every time the user
        selected text in any other application.
        """
        if not self.is_active():
            return
        text = self._selected_text()
        if not text:
            return
        copy_to_clipboard(text)
        # Deliberately silent. A toast on every mouse-selection fires constantly
        # and trains you to ignore the one place errors appear; the selection
        # highlight is already the feedback that something was selected.

    def _selected_text(self) -> str:
        """Text currently selected in any message label, or ""."""
        for label in list(self._selectables):
            try:
                found, start, end = label.get_selection_bounds()
            except (TypeError, ValueError):
                # get_selection_bounds returns (found, start, end) - THREE
                # values. Unpacking it as two made the old code slice
                # text[True:0], i.e. text[1:0], which is always "" - so the
                # copy silently did nothing no matter how the selection
                # was made.
                continue
            if not found or start == end:
                continue
            if chunk := label.get_text()[start:end].strip():
                return label.get_text()[start:end]
        return ""

    def _copy_message(self, turn: dict, button: Gtk.Button | None = None) -> None:
        """Copy an answer and say so, without a desktop notification.

        A mako popup for something you just clicked is heavy - the feedback
        belongs where the click was. The icon flips to a tick for a moment and
        a small line appears under the input.
        """
        copy_to_clipboard(turn.get("answer", ""))
        self._flash(button)
        self._toast("copied")

    def _flash(self, button: Gtk.Button | None) -> None:
        if button is None:
            return
        button.set_label(ICON_DONE)
        button.add_css_class("done")

        def restore() -> bool:
            button.set_label(ICON_COPY)
            button.remove_css_class("done")
            return False

        GLib.timeout_add(900, restore)

    def _toast(self, text: str) -> None:
        """A short line under the input. Fades itself out."""
        self.toast.set_text(text)
        self.toast.set_visible(True)
        self._toast_token = getattr(self, "_toast_token", 0) + 1
        token = self._toast_token

        def clear() -> bool:
            if token == self._toast_token:
                self.toast.set_visible(False)
            return False

        GLib.timeout_add(1600, clear)

    def _scroll_to_bottom(self) -> bool:
        adjustment = self.scroller.get_vadjustment()
        adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
        return False

    def _scroll_half(self, direction: int) -> None:
        adjustment = self.scroller.get_vadjustment()
        page = adjustment.get_page_size() / 2
        adjustment.set_value(min(
            max(adjustment.get_lower(), adjustment.get_value() + direction * page),
            adjustment.get_upper() - adjustment.get_page_size()))

    def _fit_height(self) -> bool:
        """Resize to fit the content, between MIN_HEIGHT and MAX_HEIGHT.

        Measures the CHILD, not the window: a window's preferred size is
        bounded by the size the compositor already forced on it, so asking it
        just echoes that back and nothing ever grows. hyprctl rather than GTK
        because windowrules.conf forces every window to a fixed size.
        """
        child = self.get_child()
        if child is None:
            return False
        _, natural = child.get_preferred_size()
        ceiling = (self.MAX_HEIGHT_PANEL if self.cmd_panel.get_visible()
                   else self.MAX_HEIGHT)
        wanted = max(self.MIN_HEIGHT, min(ceiling, natural.height + 8))
        if wanted != self._applied_height:
            self._applied_height = wanted
            subprocess.Popen(
                ["hyprctl", "dispatch", "resizewindowpixel",
                 f"exact {self.WIDTH} {wanted},class:{UI_CLASS}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False

    # -- prompt rendering ------------------------------------------------
    def _render_prompt(self) -> None:
        if self.search_active:
            # The query lives in the panel at the top; echoing it down here as
            # well made it look like there were two search boxes.
            self.prompt_holder.set_visible(False)
            self.pending_chip.set_visible(False)
            self.vim_chip.set_text("FIND")
            self._chip_mode("find")
            return
        self.prompt_holder.set_visible(True)

        if self.cmdline is not None:
            self.prompt_holder.set_visible(True)
            self.prompt.set_markup(
                f"<span foreground='{self.CARET}'>:</span>{esc(self.cmdline)}"
                f"<span foreground='{self.CARET}'>|</span>")
            self.pending_chip.set_visible(False)
            self.vim_chip.set_text("CMD")
            self._chip_mode("find")
            return

        snap = self.buffer.snapshot()
        text, cursor, mode = snap["text"], snap["cursor"], snap["mode"]

        if mode in (VISUAL, VLINE, VBLOCK):
            start, end = self.buffer.selection()
            body = (esc(text[:start])
                    + f"<span background='{self.SELECT}'>{esc(text[start:end])}</span>"
                    + esc(text[end:]))
        elif not text:
            body = (f"<span foreground='{self.CARET}'>|</span>" if mode == INSERT
                    else f"<span background='{self.CARET}' foreground='{self.CARET_FG}'> </span>")
        elif mode == INSERT:
            body = (esc(text[:cursor]) + f"<span foreground='{self.CARET}'>|</span>"
                    + esc(text[cursor:]))
        else:
            under = text[cursor] if cursor < len(text) else " "
            tail_text = text[cursor:] if under == "\n" else text[cursor + 1:]
            if under == "\n":
                under = " "
            body = (esc(text[:cursor])
                    + f"<span background='{self.CARET}' foreground='{self.CARET_FG}'>{esc(under)}</span>"
                    + esc(tail_text))

        pending = snap["pending"]
        self.pending_chip.set_text(pending)
        self.pending_chip.set_visible(bool(pending))

        self.prompt.set_markup(body or " ")
        self.vim_chip.set_text({INSERT: "INS", VISUAL: "VIS", VBLOCK: "V-B",
                                VLINE: "V-L", NORMAL: "NOR"}[mode])
        self._chip_mode(mode)
        self.prompt_holder.remove_css_class("insert")
        if mode == INSERT:
            self.prompt_holder.add_css_class("insert")

    def _chip_mode(self, mode: str) -> None:
        for css_class in ("insert", "visual", "find"):
            self.vim_chip.remove_css_class(css_class)
        if mode == INSERT:
            self.vim_chip.add_css_class("insert")
        elif mode in (VISUAL, VLINE, VBLOCK):
            self.vim_chip.add_css_class("visual")
        elif mode == "find":
            self.vim_chip.add_css_class("find")

    # -- history search --------------------------------------------------
    def _picking_command(self) -> bool:
        """True while the command WORD is still being typed.

        j and k only steer the list up to that point. Once there is a space
        the rest of the line is arguments and both letters have to be typable
        again - `:model haiku` would otherwise be impossible to type.
        No command name contains a j or a k, so nothing is lost.
        """
        return bool(self.cmd_hits) and " " not in (self.cmdline or "")

    def _render_cmdline(self) -> None:
        """Live suggestions under the `:` line, or the full help sheet."""
        while (child := self.cmd_list.get_first_child()) is not None:
            self.cmd_list.remove(child)

        if self.cmdline is None and not self.help_open:
            self.cmd_panel.set_visible(False)
            self.scroller.set_visible(bool(self._rendered_turns) and not self.search_active)
            GLib.idle_add(self._fit_height)
            return
        self.cmd_panel.set_visible(True)

        # The transcript steps aside while the panel is up. The window is
        # capped at MAX_HEIGHT, so with both on screen the panel was simply
        # clipped by the bottom of the window - visible but unreachable.
        self.scroller.set_visible(False)

        if self.help_open:
            # The sheet is the whole point of :help, so give it real room -
            # at 260px the keybindings sat below the fold and looked missing.
            self.cmd_panel.set_max_content_height(self.HELP_MAX)
            self._render_help()
            GLib.idle_add(self._fit_height)
            return
        self.cmd_panel.set_max_content_height(self.SUGGEST_MAX)

        hits = commands.suggestions(self.cmdline or "")
        self.cmd_hits = hits
        self.cmd_rows = []
        self._cmd_selected_row = None
        if not hits:
            miss = Gtk.Label(label="no such command", xalign=0)
            miss.add_css_class("hint")
            self.cmd_list.append(miss)
            return
        self.cmd_index = max(0, min(self.cmd_index, len(hits) - 1))

        for index, (name, help_text) in enumerate(hits):
            row = self._button("", "cmd-row",
                               lambda _b, n=name: self._pick_suggestion(n))
            row.set_child(self._cmd_row_content(name, help_text))
            if index == self.cmd_index:
                row.add_css_class("on")
                self._cmd_selected_row = row
            self.cmd_rows.append(row)
            self.cmd_list.append(row)
        GLib.idle_add(self._fit_height)
        GLib.idle_add(self._scroll_cmd_into_view, priority=GLib.PRIORITY_LOW)

    @staticmethod
    def _cmd_row_content(name: str, help_text: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        key = Gtk.Label(label=f":{name}", xalign=0)
        key.add_css_class("cmd-name")
        key.set_size_request(112, -1)
        note = Gtk.Label(label=help_text, xalign=0, hexpand=True)
        note.add_css_class("cmd-help")
        note.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(key)
        box.append(note)
        return box

    def _render_help(self) -> None:
        """Every command and every key, side by side.

        Two columns rather than one long list: 35 keybindings in a single
        column is a scroll nobody reads to the bottom of.
        """
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True)
        columns.append(left)
        columns.append(right)
        self.cmd_list.append(columns)

        def group(into: Gtk.Box, title: str) -> None:
            label = Gtk.Label(label=title, xalign=0)
            label.add_css_class("cmd-group")
            into.append(label)

        def entry(into: Gtk.Box, keys: str, note: str, accent: bool = False) -> None:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("cmd-static")
            key = Gtk.Label(label=keys, xalign=0)
            key.add_css_class("cmd-name" if accent else "cmd-key")
            key.set_size_request(104, -1)
            text = Gtk.Label(label=note, xalign=0, hexpand=True)
            text.add_css_class("cmd-help")
            text.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(key)
            row.append(text)
            into.append(row)

        group(left, "commands")
        for name, (_aliases, help_text) in commands.COMMANDS.items():
            entry(left, f":{name}", help_text, accent=True)

        # Keep the columns near equal: the shorter groups join the commands.
        split = len(commands.KEYBINDINGS) - 2
        for index, (title, entries) in enumerate(commands.KEYBINDINGS):
            into = right if index < split else left
            group(into, title)
            for keys, note in entries:
                entry(into, keys, note)

        closer = Gtk.Label(label="escape to close", xalign=0)
        closer.add_css_class("hint")
        self.cmd_list.append(closer)

    def _scroll_help(self, lines: int, home: bool | None = None) -> None:
        """Scroll the help sheet with the keys you would expect to scroll it."""
        adjustment = self.cmd_panel.get_vadjustment()
        if adjustment is None:
            return
        limit = max(0.0, adjustment.get_upper() - adjustment.get_page_size())
        if home is not None:
            adjustment.set_value(0.0 if home else limit)
            return
        step = 24.0                       # about one row
        adjustment.set_value(
            max(0.0, min(limit, adjustment.get_value() + lines * step)))

    def _move_cmd_selection(self, delta: int) -> None:
        """Move the highlight without rebuilding the list.

        Re-rendering on every keypress reset the scroll position to the top,
        and the scroll-into-view that followed raced with the window resize -
        so walking down the list would intermittently lose the highlight off
        the bottom. Moving a CSS class touches neither.
        """
        if not self.cmd_rows:
            return
        self.cmd_index = max(0, min(self.cmd_index + delta, len(self.cmd_rows) - 1))
        for index, row in enumerate(self.cmd_rows):
            if index == self.cmd_index:
                row.add_css_class("on")
                self._cmd_selected_row = row
            else:
                row.remove_css_class("on")
        self._scroll_cmd_into_view()

    def _scroll_cmd_into_view(self) -> bool:
        """Keep the highlighted suggestion on screen as j/k walk the list.

        Without this the selection kept moving past the bottom of the panel
        and the list appeared frozen - the highlight was simply out of sight.
        """
        row = getattr(self, "_cmd_selected_row", None)
        adjustment = self.cmd_panel.get_vadjustment()
        if row is None or adjustment is None:
            return False
        page = adjustment.get_page_size()
        if page <= 0:
            return False

        found, rect = row.compute_bounds(self.cmd_list)
        if not found:
            return False
        top, bottom = rect.origin.y, rect.origin.y + rect.size.height
        value = adjustment.get_value()
        if top < value:
            adjustment.set_value(max(0, top - 2))
        elif bottom > value + page:
            adjustment.set_value(min(adjustment.get_upper() - page, bottom - page + 2))
        return False

    def _pick_suggestion(self, name: str) -> None:
        """Clicking a suggestion runs it."""
        self.cmdline = None
        self._render_cmdline()
        self._run_cmdline(name)
        self._render_prompt()

    def _commit_rename(self, *_args) -> None:
        """Save the name and go back to the list."""
        if self.renaming is None or self.renaming >= len(self.search_hits):
            self.renaming = None
            return
        entry = self.search_hits[self.renaming]
        self._send({"op": ipc.OP_RENAME, "session_id": entry.session_id,
                    "title": self.rename_text})
        self.renaming = None
        self.rename_text = ""
        # Re-read so the row shows the stored name, trimmed the way it was saved.
        self._all_history = history_ctx.recent(limit=300)
        self._refresh_search()
        self._toast("renamed")

    def _open_search(self) -> None:
        from ..context import history as history_ctx

        self.search_active = True
        self.search_focus = "query"          # query | results
        self.search_query = ""
        self.search_index = 0
        # Hides the transcript rather than sitting under it: the results are
        # what you are looking at, and the window stays the same size.
        self.scroller.set_visible(False)
        self._all_history = history_ctx.recent(limit=300)
        self._refresh_search()

    def _close_search(self) -> None:
        self.search_active = False
        self.search_focus = "query"
        self.search_panel.set_visible(False)
        self.scroller.set_visible(bool(self._rendered_turns))
        self._render_prompt()
        GLib.idle_add(self._fit_height)

    def _refresh_search(self) -> None:
        query = self.search_query.lower()
        hits = [e for e in self._all_history
                if query in e.prompt.lower() or query in (e.title or "").lower()
                ][: self.MAX_HITS]
        self.search_hits = hits
        self.search_index = max(0, min(self.search_index, len(hits) - 1))

        while (child := self.search_box.get_first_child()) is not None:
            self.search_box.remove(child)
        if not hits:
            empty = Gtk.Label(label="no matching prompts", xalign=0)
            empty.add_css_class("hint")
            self.search_box.append(empty)
        for index, entry in enumerate(hits):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("hit")
            if index == self.search_index:
                row.add_css_class("on")
            if self.renaming == index:
                # Inline edit, in place, so the list never jumps around you.
                text = Gtk.Entry(hexpand=True)
                text.set_text(self.rename_text)
                text.add_css_class("rename")
                text.set_placeholder_text("name this chat, enter to save")
                text.connect("activate", self._commit_rename)
                text.connect("changed",
                             lambda e: setattr(self, "rename_text", e.get_text()))
                GLib.idle_add(text.grab_focus)
            else:
                text = Gtk.Label(label=entry.label[:96], xalign=0, hexpand=True)
                text.set_ellipsize(3)
                if entry.title:
                    text.add_css_class("hit-named")
            meta = Gtk.Label(label=f"{entry.when}   {entry.session_id[:6]}", xalign=1)
            meta.add_css_class("hit-meta")
            row.append(text)
            row.append(meta)
            self.search_box.append(row)

        self.search_panel.set_visible(True)
        caret = "" if self.search_focus == "results" else f"<span foreground='{self.CARET}'>|</span>"
        self.search_field.set_markup(
            f"<span alpha='50%'>find </span>{esc(self.search_query)}{caret}"
            f"   <span alpha='38%'>tab: {'query' if self.search_focus == 'results' else 'results'}"
            f" · j/k move · enter open · r rename</span>")
        self._render_prompt()
        GLib.idle_add(self._fit_height)

    def _search_key(self, name: str, shift: bool = False) -> bool:
        # In the results half the keys are vim motions, not text. That is the
        # whole point of tabbing over: j/k should move, not type.
        if self.renaming is not None:
            if name == "escape":
                self.renaming = None
                self.rename_text = ""
                self._refresh_search()
                return True
            if name == "enter":
                self._commit_rename()
                return True
            # Everything else must reach the Gtk.Entry. This handler runs in
            # the CAPTURE phase, so returning True here consumed the keystroke
            # before the entry ever saw it - the box had focus and a caret and
            # simply would not accept text.
            return False

        if self.search_focus == "results" and name == "r" and self.search_hits:
            self.renaming = self.search_index
            self.rename_text = self.search_hits[self.search_index].title
            self._refresh_search()
            return True

        if self.search_focus == "results" and name in ("j", "k", "g", "G"):
            if name == "j":
                self.search_index = min(self.search_index + 1,
                                        max(0, len(self.search_hits) - 1))
            elif name == "k":
                self.search_index = max(0, self.search_index - 1)
            elif name == "G":
                self.search_index = max(0, len(self.search_hits) - 1)
            else:
                self.search_index = 0
            self._refresh_search()
            return True

        if name == "escape":
            self._close_search()
        elif name == "enter":
            if self.search_hits:
                # Open the conversation, do not paste its text into this one.
                chosen = self.search_hits[self.search_index]
                self._send({"op": ipc.OP_OPEN_SESSION,
                            "session_id": getattr(chosen, "session_id", ""),
                            "cwd": getattr(chosen, "cwd", "")})
                self._toast("opening that chat")
            self._close_search()
        elif name in ("down", "ctrl-j"):
            self.search_index = min(self.search_index + 1,
                                    max(0, len(self.search_hits) - 1))
            self._refresh_search()
        elif name in ("up", "ctrl-k"):
            self.search_index = max(0, self.search_index - 1)
            self._refresh_search()
        elif name == "backspace":
            self.search_query = self.search_query[:-1]
            self._refresh_search()
        elif len(name) == 1:
            self.search_query += name
            self._refresh_search()
        return True

    # -- keys ------------------------------------------------------------
    def _install_keys(self) -> None:
        controller = Gtk.EventControllerKey()
        # CAPTURE, not the default bubble phase: children see keys first in the
        # bubble phase, and something in the tree was eating Return.
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self._on_key)
        self.add_controller(controller)

    def _on_key(self, _controller, keyval, _keycode, modifiers) -> bool:
        if self.password["root"].get_visible():
            return False  # the password entry owns the keyboard while it is up

        ctrl = bool(modifiers & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(modifiers & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(modifiers & Gdk.ModifierType.ALT_MASK)
        sup = bool(modifiers & Gdk.ModifierType.SUPER_MASK)
        is_tab = keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)

        # Tab moves the keyboard between regions; the modifiers cycle settings.
        # Plain Tab deliberately does NOT change the mode any more - it is the
        # focus key, and changing state on a focus keystroke was surprising.
        if alt and Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
            self._select_tab(keyval - Gdk.KEY_1)
            return True

        # A visible notice claims L / R / esc, but only outside insert mode -
        # otherwise typing a word with an L in it would launch a terminal.
        # Not while history search, the `:` line or a rename is up: those
        # own their letters, and `r` in particular means rename there.
        if self.notice["root"].get_visible() and self.buffer.mode != INSERT \
                and not self.search_active and self.cmdline is None \
                and not self.help_open and not (ctrl or alt or sup):
            if keyval in (Gdk.KEY_l, Gdk.KEY_L) and self.problem.get("command"):
                self._run_fix()
                return True
            if keyval in (Gdk.KEY_r, Gdk.KEY_R) and self.problem.get("retry"):
                self._retry_turn()
                return True
            if keyval == Gdk.KEY_Escape:
                self._dismiss_notice()
                return True

        if is_tab and self.search_active and not (ctrl or alt or shift):
            # Move between the query and the results. Cycling the mode from
            # here would change the machine's behaviour from a search box.
            self.search_focus = "results" if self.search_focus == "query" else "query"
            self._refresh_search()
            return True

        if is_tab:
            if ctrl:
                self._cycle("model")
            elif alt:
                self._cycle("effort")
            elif shift:
                self._cycle("mode")
            else:
                self._toggle_region()
            return True

        # super+enter runs the command the SELECTED message proposed, and does
        # nothing otherwise - in particular it never sends the prompt.
        if sup and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if commands := self._selected_commands():
                self._run_command(commands[0])
            return True

        name = NAMED_KEYS.get(keyval)
        if name is None:
            point = Gdk.keyval_to_unicode(keyval)
            name = chr(point) if point else None
        if name is None:
            return True

        if self.search_active:
            return self._search_key(f"ctrl-{name.lower()}" if ctrl else name, shift)

        if self.focus_region == "chat":
            return self._chat_key(f"ctrl-{name.lower()}" if ctrl else name, shift)

        if shift and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.buffer.feed("newline")
            self._after_key()
            return True

        if ctrl:
            key = f"ctrl-{name.lower()}"
            if key == "ctrl-h":
                self._open_search()
                return True
            if key in COMMANDS:
                op, extra = COMMANDS[key]
                self._send({"op": op, **extra})
                return True
            if key in ("ctrl-d", "ctrl-u") and self.help_open:
                # The help sheet is taller than the window; the ctrl block runs
                # before the help block, so it has to be caught here.
                self._scroll_help(6 if key == "ctrl-d" else -6)
                return True
            if key in ("ctrl-d", "ctrl-u") and self.buffer.mode != INSERT:
                # Focus is in the INPUT here - the chat region is handled
                # earlier by _chat_key. This used to scroll the transcript
                # instead, so a long prompt could only be scrolled by mouse.
                self.buffer.feed(key)
                self._after_key()
                return True
            if key == "ctrl-v":
                # Normal mode: visual block, as in vim. Insert mode: paste,
                # because that is what ctrl-v means when you are typing.
                if self.buffer.mode == INSERT:
                    self._paste_clipboard()
                else:
                    self.buffer.feed("ctrl-v")
                    self._after_key()
                return True
            if key == "ctrl-w" and self.buffer.mode != INSERT:
                # In insert mode ctrl-w stays vim's "delete previous word".
                self._send({"op": ipc.OP_TAB, "action": "close"})
                return True
            if key not in ("ctrl-r", "ctrl-u", "ctrl-w"):
                return True
            name = key

        if self.cmdline is not None:
            return self._cmdline_key(name)

        if name in ("up", "down") and self._recall_prompt(name):
            return True

        if name == ":" and self.buffer.mode == NORMAL:
            self.cmdline = ""
            self.cmd_index = 0
            self.help_open = False
            self._render_cmdline()
            self._render_prompt()
            return True

        # With the help sheet pinned open it owns the navigation keys: there
        # is more of it than fits, and nothing else on screen to steer.
        if self.help_open:
            if name == "escape":
                self.help_open = False
                self._render_cmdline()
                return True
            if name in ("j", "down"):
                self._scroll_help(1)
                return True
            if name in ("k", "up"):
                self._scroll_help(-1)
                return True
            if name in ("g", "G"):
                self._scroll_help(0, home=name == "g")
                return True

        if self.state.get("pending") and self.buffer.mode == NORMAL and name in ("y", "x"):
            self._send({"op": ipc.OP_APPROVE, "id": self.state.get("pending_id", ""),
                        "decision": "allow" if name == "y" else "deny"})
            return True

        if name == "escape" and self._double_escape():
            return True

        if name not in ("up", "down"):
            self._recall_index = None
        action = self.buffer.feed(name)
        if _DEBUG:
            with open(_DEBUG, "a") as handle:
                handle.write(f"key={name!r} region={self.focus_region} "
                             f"mode={self.buffer.mode} text={self.buffer.text!r} "
                             f"action={action!r}\n")
        if action == "submit":
            self._submit()
        elif action == "close":
            self.close()
        elif action in ("tab-next", "tab-prev"):
            self._send({"op": ipc.OP_TAB,
                        "action": "next" if action == "tab-next" else "prev"})
        self._after_key()
        return True

    # -- the chat region -------------------------------------------------
    def _mark_region(self) -> None:
        """Show which half has the keyboard.

        With no messages, tabbing to the chat used to change nothing on screen
        at all - the only indicator was the selected message's ring, and there
        was no message to ring.
        """
        chat = self.focus_region == "chat"
        if chat:
            self.scroller.add_css_class("region-active")
        else:
            self.scroller.remove_css_class("region-active")
        self.hint.set_text(
            "j k select · y copy · u continue from here · tab back to input"
            if chat else
            "i insert \N{MIDDLE DOT} tab chat \N{MIDDLE DOT} ctrl-h history "
            "\N{MIDDLE DOT} shift+tab mode \N{MIDDLE DOT} ZZ close")

    def _toggle_region(self) -> None:
        turns = self.state.get("turns") or []
        if self.focus_region == "input" and turns:
            self.focus_region = "chat"
            self.selected = len(turns) - 1     # newest message by default
        else:
            self.focus_region = "input"
        self._apply_selection()
        self._mark_region()
        self._render_prompt()

    def _selected_commands(self) -> list:
        """Live (not yet run) commands on the selected message.

        Falls back to the newest message that still has one, so super+enter
        works straight after an answer without moving into the chat first.
        """
        turn = self._selected_turn()
        live = [a["command"] for a in turn.get("actions") or [] if not a.get("done")]
        if live:
            return live
        for other in reversed(self.state.get("turns") or []):
            live = [a["command"] for a in other.get("actions") or [] if not a.get("done")]
            if live:
                return live
        return []

    def _chat_key(self, name: str, shift: bool) -> bool:
        """vim-ish navigation over the messages themselves."""
        if name in ("escape", "i", "a"):
            self.focus_region = "input"
            self._apply_selection()
            self._render_prompt()
        elif name == "j":
            self._move_selection(1)
        elif name == "k":
            self._move_selection(-1)
        elif name == "G":
            self.selected = len(self._rows) - 1 if getattr(self, "_rows", None) else 0
            self._apply_selection()
            self._scroll_selection_into_view()
        elif name == "g":
            # gg jumps to the first message; a single g waits for the second.
            if self._pending_g:
                self.selected = 0
                self._apply_selection()
                self._scroll_selection_into_view()
            self._pending_g = not self._pending_g
            return True
        elif name == "y":
            self._copy_message(self._selected_turn(),
                               self._copy_buttons.get(self.selected))
        elif name == "u":
            self._rewind_here()
        elif name == "Z":
            # ZZ closes from here as well; tabbing into the chat should not
            # take the close key away.
            if self._pending_z:
                self.close()
            self._pending_z = not self._pending_z
            return True
        elif name == "ctrl-d":
            self._scroll_half(1)
        elif name == "ctrl-u":
            self._scroll_half(-1)
        self._pending_g = False
        self._pending_z = False
        return True

    # -- the : command line ----------------------------------------------
    def _cmdline_key(self, name: str) -> bool:
        if name == "escape":
            self.cmdline = None
            self.help_open = False
        elif name in ("down", "ctrl-n") or (name == "j" and self._picking_command()):
            self._move_cmd_selection(1)
            return True
        elif name in ("up", "ctrl-p") or (name == "k" and self._picking_command()):
            self._move_cmd_selection(-1)
            return True
        elif name == "enter":
            line, self.cmdline = self.cmdline, None
            # An empty or partial word runs the highlighted suggestion, so
            # `:` then enter does something sensible instead of nothing.
            if self.cmd_hits and (not line or not commands.resolve(line.split(" ")[0])):
                line = self.cmd_hits[min(self.cmd_index, len(self.cmd_hits) - 1)][0]
            self._run_cmdline(line or "")
        elif name == "backspace":
            if not self.cmdline:
                self.cmdline = None          # backspacing off the ':' closes it
            else:
                self.cmdline = self.cmdline[:-1]
        elif name == "tab":
            # Complete the command word, as vim does.
            head = (self.cmdline or "").split(" ")[0]
            options = commands.complete(head)
            if len(options) == 1:
                rest = (self.cmdline or "")[len(head):]
                self.cmdline = options[0] + (rest or " ")
            elif options:
                chosen = options[min(self.cmd_index, len(options) - 1)]
                rest = (self.cmdline or "")[len(head):]
                self.cmdline = chosen + (rest or " ")
        elif len(name) == 1:
            self.cmdline = (self.cmdline or "") + name
            self.cmd_index = 0
        self._render_cmdline()
        self._render_prompt()
        return True

    def _run_cmdline(self, line: str) -> None:
        intent = commands.parse(line)
        if intent.failed:
            if intent.message:
                self._toast(intent.message)
            return

        kind, args = intent.kind, intent.args
        if kind == "set":
            self._send({"op": ipc.OP_SET, "field": args["field"], "value": args["value"]})
            self._toast(f"{args['field']} → {args['value']}")
        elif kind == "new":
            self._cmd_new(None)
        elif kind == "history":
            self._open_search()
        elif kind == "sessions":
            self._send({"op": ipc.OP_PICKER, "kind": "sessions"})
        elif kind == "cancel":
            self._send({"op": ipc.OP_CANCEL})
        elif kind == "quit":
            self.close()
        elif kind == "copy":
            copy_to_clipboard(self._conversation_text())
            self._toast("conversation copied")
        elif kind == "export":
            self._export(args.get("path") or "")
        elif kind == "mcp":
            self._send({"op": ipc.OP_SET, "field": "mcp",
                        "value": args["server"], "enable": args["enable"]})
            self._toast(f"mcp {args['server']} {'on' if args['enable'] else 'off'}")
        elif kind == "tab":
            self._send({"op": ipc.OP_TAB, "action": args["action"]})
        elif kind == "help":
            self.help_open = True
            self._render_cmdline()

    def _conversation_text(self) -> str:
        lines = []
        for turn in self.state.get("turns") or []:
            lines.append(f"> {turn.get('prompt','')}\n\n{turn.get('answer','')}")
        return "\n\n---\n\n".join(lines)

    def _export(self, path: str) -> None:
        from pathlib import Path as _Path
        import time as _time

        target = _Path(path).expanduser() if path else _Path.home() / (
            f"archpilot-{_time.strftime('%Y%m%d-%H%M%S')}.md")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self._conversation_text())
        except OSError as exc:
            self._toast(f"export failed: {exc}")
            return
        self._toast(f"written to {target}")

    def _double_escape(self) -> bool:
        """Esc twice in quick succession stops a running turn.

        A single Esc has to keep meaning "leave insert mode" - that is the one
        key a vim user presses most - so stopping is deliberately the double.
        The prompt goes back in the input, because a turn you cancelled is one
        you probably want to edit and send again.
        """
        now = GLib.get_monotonic_time() / 1_000_000.0
        recent = (now - self._last_escape) < 0.7
        self._last_escape = now
        if not recent or self.state.get("status") != "thinking":
            return False

        self._last_escape = 0.0
        self._send({"op": ipc.OP_CANCEL})
        if prompt := (self.state.get("prompt") or "").strip():
            self._set_input(prompt)
        self._toast("stopped")
        return True

    def _recall_prompt(self, direction: str) -> bool:
        """Arrow up/down walks back through messages already sent.

        Only when the caret is on the edge line in that direction, so up still
        moves between lines inside a multi-line prompt - the same rule a shell
        and Claude Code itself use. Returns True if it handled the key.
        """
        text, cursor = self.buffer.text, self.buffer.cursor
        at_first_line = "\n" not in text[:cursor]
        at_last_line = "\n" not in text[cursor:]
        if direction == "up" and not at_first_line:
            return False
        if direction == "down" and not at_last_line:
            return False

        prompts = [t.get("prompt", "") for t in (self.state.get("turns") or [])
                   if t.get("prompt")]
        if not prompts:
            return False

        if self._recall_index is None:
            if direction == "down":
                return False              # nothing to come back to yet
            # Keep whatever was half-typed so walking back off the end
            # restores it rather than throwing it away.
            self._recall_draft = text
            self._recall_index = len(prompts)

        index = self._recall_index + (-1 if direction == "up" else 1)
        if index < 0:
            index = 0
        if index >= len(prompts):
            # Past the newest: back to what the user was typing.
            self._recall_index = None
            self._set_input(self._recall_draft)
            self._recall_draft = ""
            return True

        self._recall_index = index
        self._set_input(prompts[index])
        return True

    def _set_input(self, text: str) -> None:
        self.buffer.text = text
        self.buffer.cursor = len(text)
        self.buffer.begin_insert()
        self._render_prompt()
        GLib.idle_add(self._scroll_prompt_to_cursor, priority=GLib.PRIORITY_LOW)

    def _rewind_here(self) -> None:
        """Continue from the selected message, dropping everything after it."""
        if self.selected < 0:
            self._toast("select a message first")
            return
        self._send({"op": ipc.OP_REWIND, "index": self.selected})
        self.focus_region = "input"
        self.selected = -1
        self._apply_selection()
        # Says what actually happens, and avoids "rewound" - which is the
        # correct past tense of rewind but reads like a typo to enough people
        # that it is not worth the doubt in a one-word status message.
        self._toast("continuing from here")

    def _after_key(self) -> None:
        self._render_prompt()
        GLib.idle_add(self._fit_height)
        # #1: a prompt that has grown past its cap must show the line you are
        # typing on, not the top of the paste.
        # PRIORITY_LOW, not the default: GTK recomputes the scrollable area
        # during its own idle pass, and a default-priority callback can beat
        # it there - reading a stale `upper` clamps every scroll back to 0.
        GLib.idle_add(self._scroll_prompt_to_cursor,
                      priority=GLib.PRIORITY_LOW)

    def _scroll_prompt_to_cursor(self) -> bool:
        """Keep the caret in view inside a tall prompt.

        This used to jump to the very bottom on every keystroke, so editing
        line 3 of a 20-line paste scrolled the line you were editing off the
        top - the input could not be scrolled at all, in effect. Pango knows
        exactly where the caret sits, so ask it.
        """
        adjustment = self.prompt_holder.get_vadjustment()
        page = adjustment.get_page_size()
        if page <= 0:
            return False

        top, bottom = self._caret_extent()
        if top is None:
            adjustment.set_value(adjustment.get_upper() - page)
            return False

        value = adjustment.get_value()
        margin = 4                       # a sliver of the neighbouring line
        if top - margin < value:
            adjustment.set_value(max(0, top - margin))
        elif bottom + margin > value + page:
            adjustment.set_value(min(adjustment.get_upper() - page,
                                     bottom + margin - page))
        return False

    def _caret_extent(self) -> tuple:
        """Top and bottom pixel offsets of the caret line, or (None, None).

        The layout holds the RENDERED text, so the offset must be in bytes of
        that text - a character index would land mid-glyph on anything
        non-ASCII and silently scroll to the wrong line.
        """
        if self.cmdline is not None or self.search_active:
            return (None, None)
        layout = self.prompt.get_layout()
        if layout is None:
            return (None, None)
        snap = self.buffer.snapshot()
        index = len(snap["text"][:snap["cursor"]].encode("utf-8"))
        try:
            rect = layout.index_to_pos(index)
        except (TypeError, ValueError):
            return (None, None)
        scale = 1024.0                   # Pango units per pixel
        top = rect.y / scale
        return (top, top + max(rect.height, 0) / scale)

    def _pending_actions(self) -> list:
        for turn in reversed(self.state.get("turns") or []):
            live = [a["command"] for a in turn.get("actions") or [] if not a.get("done")]
            if live:
                return live
        return []

    # -- commands --------------------------------------------------------
    def _send(self, payload: dict) -> None:
        """Fire a request off-thread; a blocking round trip froze the window."""
        threading.Thread(target=self.client.send, args=(payload,), daemon=True).start()

    def _cycle(self, field: str) -> None:
        self._send({"op": ipc.OP_SET, "field": field, "cycle": True})

    def _submit(self) -> None:
        text = self.buffer.text.strip()
        if not text:
            return
        self._send({"op": ipc.OP_PROMPT, "text": text})
        self.buffer.clear()
        self._render_prompt()

    def _submit_password(self, entry: Gtk.Entry) -> None:
        self._send({"op": ipc.OP_PASSWORD, "value": entry.get_text()})
        entry.set_text("")

    def _run_command(self, command: str) -> None:
        for index, entry in enumerate(self._pending_actions()):
            if entry == command:
                self._send({"op": ipc.OP_RUN_ACTION, "index": index})
                return
        self._send({"op": ipc.OP_RUN_ACTION, "index": 0})

    def _cmd_new(self, _button) -> None:
        # Starting a chat while the history panel is up left it covering the
        # empty conversation.
        if self.search_active:
            self._close_search()
        self.selected = -1
        self.focus_region = "input"
        self._send({"op": ipc.OP_NEW})
        self.buffer.clear()
        self._render_prompt()

    def _cmd_history(self, _button) -> None:
        self._open_search()

    def _cmd_cancel(self, _button) -> None:
        self._send({"op": ipc.OP_CANCEL})

    def _install_drop_target(self) -> None:
        """Accept files dropped onto the window as attachments.

        Dropping a screenshot is the obvious gesture; making the user go via
        SUPER+SHIFT+~ for a file they already have is friction.
        """
        from gi.repository import Gdk as _Gdk

        target = Gtk.DropTarget.new(_Gdk.FileList, _Gdk.DragAction.COPY)
        target.connect("drop", self._on_drop)
        self.add_controller(target)

    def _on_drop(self, _target, value, _x, _y) -> bool:
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        if not paths:
            return False
        self._send({"op": ipc.OP_ATTACH, "paths": paths})
        self._toast(f"attached {len(paths)} file" + ("s" if len(paths) > 1 else ""))
        return True

    def _paste_clipboard(self) -> None:
        """ctrl-v in insert mode: text goes into the prompt, an image is attached."""
        clipboard = Gdk.Display.get_default().get_clipboard()

        def got_text(_c, result) -> None:
            try:
                text = clipboard.read_text_finish(result)
            except Exception:  # noqa: BLE001
                text = None
            if not text:
                return
            for char in text:
                self.buffer.feed("newline" if char == "\n" else char)
            self._after_key()

        def got_image(_c, result) -> None:
            try:
                texture = clipboard.read_texture_finish(result)
            except Exception:  # noqa: BLE001
                texture = None
            if texture is None:
                clipboard.read_text_async(None, got_text)
                return
            import time as _time
            from .. import paths as _paths
            target = _paths.shot_dir() / f"paste-{int(_time.time())}.png"
            texture.save_to_png(str(target))
            self._send({"op": ipc.OP_ATTACH, "paths": [str(target)]})
            self._toast("image attached")

        clipboard.read_texture_async(None, got_image)

    def _watch_theme(self) -> None:
        """Restyle when wallust rewrites the palette.

        The rest of the rice re-themes the instant the wallpaper changes; a
        window that only picked up colours at startup looked stale next to it.
        One GFileMonitor, no polling.
        """
        from gi.repository import Gio

        source = Gio.File.new_for_path(str(theme_source()))
        try:
            self._theme_monitor = source.monitor_file(Gio.FileMonitorFlags.NONE, None)
        except Exception:  # noqa: BLE001 - a missing palette is not fatal
            return
        self._theme_monitor.connect("changed", self._on_theme_changed)

    def _on_theme_changed(self, _monitor, _f, _other, event) -> None:
        from gi.repository import Gio

        if event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT,
                         Gio.FileMonitorEvent.CREATED):
            return
        # wallust writes then closes; a beat avoids restyling from a half file.
        GLib.timeout_add(150, self._restyle)

    def _restyle(self) -> bool:
        provider = Gtk.CssProvider()
        try:
            provider.load_from_data(css().encode())
        except Exception:  # noqa: BLE001
            return False
        display = Gdk.Display.get_default()
        if getattr(self, "_provider", None) is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self._provider)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._provider = provider
        self._toast("re-themed")
        return False

    @staticmethod
    def _submap(name: str) -> None:
        subprocess.Popen(["hyprctl", "dispatch", "submap", name],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _on_focus_change(self, *_args) -> None:
        self._submap("archpilot-gtk" if self.is_active() else "reset")

    def _on_close(self, *_args) -> bool:
        # Hand the unsent text back to the daemon so reopening resumes it.
        if self.buffer.text.strip():
            self.client.send({"op": ipc.OP_DRAFT, "text": self.buffer.text})
        self._submap("reset")
        self.client.stop()
        return False


class ArchPilotApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=UI_CLASS)

    def do_activate(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(css().encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window = ArchPilotWindow(self)
        window._provider = provider
        window.present()


def main() -> int:
    # A stranded `archpilot-gtk` submap leaves the whole keyboard inert with
    # no window to explain it, so reset it on the way out however we exit.
    # The launcher traps this too; belt and braces, because the failure is
    # invisible and the user's only clue is that nothing works any more.
    def _reset_submap(*_args) -> None:
        # run(), not Popen(): on the signal path the process is about to die
        # and a detached child could be reaped before hyprctl ever ran.
        with contextlib.suppress(Exception):
            subprocess.run(["hyprctl", "dispatch", "submap", "reset"],
                           timeout=2, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)

    def _die(*_args) -> None:
        _reset_submap()
        os._exit(0)

    atexit.register(_reset_submap)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        with contextlib.suppress(ValueError, OSError):
            signal.signal(sig, _die)
    return ArchPilotApp().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
