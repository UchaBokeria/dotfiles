"""Workspace session tree with a centered title, guide and live pane preview."""
import curses
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import time

from workspaces import (archive_snapshot, children, client_pane, destruction_token,
                        nested_parent, path_name, shell_command, shortcut_label, shortcut_map, snapshot_token, tm)

HELPER = Path(__file__).with_name("workspaces.py")
GUIDE = [
    ("j/k  ↑/↓", "Select · wraps first / last"), ("0–9  Alt+a–z", "Open numbered row 0–35"),
    ("d/u  Ctrl+D/U", "Half page down / up"), ("PgDn/PgUp", "Full page · Ctrl+F/B"),
    ("g/G  Home/End", "First / last item"), ("Enter", "Open selected item"),
    ("h/l  ←/→  −/+", "Collapse / expand item"), ("Alt+− / Alt++", "Collapse / expand all"),
    ("s", "Workspace list · J/K reorder"), ("H/L  Tab/S-Tab", "Previous / next workspace"),
    ("Prefix 1–0/Fn", "Root workspace shortcut"), ("Alt+1–0/Fn", "Nested workspace shortcut"),
    ("[ / ]", "Parent / first child"), ("Ctrl+R", "Archive / return workspace"),
    ("z", "Archive / restore session"), ("m / w", "Move session / actions"),
    ("c / R", "Create / rename session"), ("x / X", "Delete item / tagged · asks"),
    ("t / T / Ctrl+T", "Toggle / clear / tag all"), ("Ctrl+S  /  n", "Search / repeat search"),
    ("f", "Filter by tmux format"), (":", "Run tmux command on tags"),
    ("Ctrl+Space / M", "Mark pane / clear mark"), ("Alt+H", "Jump to starting pane"),
    ("O / r", "Sort field / reverse order"), ("< / >", "Previous / next preview"),
    ("E / D", "Empty workspace / Archive"), ("Prefix S-Tab", "Previous session in workspace"),
    ("Prefix Alt+Tab", "Previous session globally"), ("v / b", "Toggle preview / shortcuts"),
    ("?", "Help overlay · Esc returns"), ("q / Esc", "Close picker · Ctrl+G too"),
]



@dataclass(frozen=True)
class Layout:
    title: int
    list_top: int
    list_height: int
    keys_top: int | None
    keys_height: int
    preview_top: int | None
    preview_height: int


def layout(height, keys=True, preview=True, header_rows=1):
    """Reserve the header, then keep the guide attached to the preview/bottom."""
    top = min(max(3, header_rows + 3), max(3, height - 5))
    available = max(1, height - top)
    keys_height = min(len(GUIDE) // 2 + 2, max(3, available - 8)) if keys else 0
    preview_height = min(24, max(3, height // 3), max(0, available - keys_height - 3)) if preview else 0
    if preview_height < 3: preview_height = 0
    list_height = max(1, available - keys_height - preview_height)
    return Layout(1 if height >= 20 else 0, top, list_height,
                  top + list_height if keys_height else None, keys_height,
                  height - preview_height if preview_height else None, preview_height)


def clean(value):
    return "".join(char if char.isprintable() or "\ue000" <= char <= "\uf8ff" else " " for char in str(value))


def theme_accent():
    value = tm("show-options", "-gqv", "@bw_accent")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        match = re.search(r"bg=(#[0-9a-fA-F]{6})", tm("show-options", "-gqv", "@workspaces-base-status-left"))
        value = match[1] if match else "#5fd7ff"
    rgb = tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    if curses.COLORS >= 256:
        levels = (0, 95, 135, 175, 215, 255)
        r, g, b = (min(range(6), key=lambda index: abs(levels[index] - channel)) for channel in rgb)
        colour = 16 + 36 * r + 6 * g + b
    else:
        colour = curses.COLOR_CYAN
    return colour, curses.COLOR_BLACK if sum(rgb) / 3 > 140 else curses.COLOR_WHITE


def put(screen, y, x, text, attr=0, width=None):
    height, columns = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < columns:
        limit = min(columns - x - (1 if y == height - 1 else 0), width if width is not None else columns)
        if limit > 0:
            try:
                screen.addnstr(y, x, clean(text), limit, attr)
            except curses.error:
                pass


def guide_columns(screen, top, count, entries=GUIDE, accent=0):
    width = screen.getmaxyx()[1]
    half = width // 2
    column_width = max(1, half - 4)
    label_width = min(17, max(9, column_width // 3))
    for index, (key, description) in enumerate(entries[:count * 2]):
        column, row = index % 2, index // 2
        x = 2 if column == 0 else half + 2
        put(screen, top + row, x, key, accent, label_width)
        put(screen, top + row, x + label_width + 1, description, width=max(1, column_width - label_width - 1))
    for row in range(count):
        put(screen, top + row, half, "│", accent | curses.A_DIM)


def panel(screen, area, accent=0):
    if area.keys_top is None: return
    width = screen.getmaxyx()[1]
    put(screen, area.keys_top, 1, "─" * max(0, width - 2), accent)
    heading = " Shortcuts · b hides · ? all keys "
    put(screen, area.keys_top, max(1, (width - len(heading)) // 2), heading, accent)
    guide_columns(screen, area.keys_top + 1, max(1, area.keys_height - 2), accent=accent)
    if area.preview_top is None:
        put(screen, area.keys_top + area.keys_height - 1, 1, "─" * max(0, width - 2), accent)


def badge_lines(data, active, width):
    badges = []
    def walk(parent):
        slots = {wid: shortcut_label(n) for n, wid in shortcut_map(data, parent).items()}
        for wid in children(data, parent):
            label = ("Alt+" if parent else "") + slots.get(wid, "·") + " " + path_name(data, wid)
            badges.append((wid, " " + label + " "))
            walk(wid)
    walk(None)
    lines, line, used = [], [], 0
    for wid, label in badges:
        if len(label) > width - 4:
            label = label[:max(1, width - 6)] + "…"
        if line and used + len(label) + 2 > width - 4:
            lines.append(line); line, used = [], 0
        line.append((wid, label)); used += len(label) + (2 if used else 0)
    if line: lines.append(line)
    return lines


def overlay(parent, title, width, height, accent=0):
    """A bounded window drawn over the picker; the picker process stays alive."""
    rows, cols = parent.getmaxyx()
    height, width = min(height, max(3, rows - 2)), min(width, max(8, cols - 4))
    window = curses.newwin(height, width, (rows - height) // 2, (cols - width) // 2)
    window.keypad(True); window.timeout(100)
    window.erase(); window.box()
    put(window, 0, max(2, (width - len(title) - 2) // 2), " " + title + " ", accent | curses.A_BOLD)
    return window


def read_key(screen):
    key = screen.get_wch()
    if key == "\x1b":
        screen.timeout(30)
        try:
            following = screen.get_wch()
            if isinstance(following, str) and not following.isprintable() and following != "\t":
                # Preserve a control key typed immediately after closing a view.
                curses.unget_wch(following)
                return "\x1b"
            return ("alt", following)
        except curses.error:
            return "\x1b"
        finally:
            screen.timeout(100)
    return key


def slot_key(key):
    if isinstance(key, str) and key in "1234567890":
        return 10 if key == "0" else int(key)
    if isinstance(key, int):
        for number in range(1, 13):
            if key == curses.KEY_F0 + number:
                return number + 10
    return None


def fetch_sessions(workspace):
    fmt = ("#{session_id}\t#{session_name}\t#{session_attached}\t#{@workspace-id}\t"
           "#{window_id}\t#{window_index}\t#{window_name}\t#{window_active}\t"
           "#{pane_id}\t#{pane_index}\t#{pane_current_command}\t#{pane_active}\t#{session_activity}\t"
           "#{pane_left}\t#{pane_top}\t#{pane_width}\t#{pane_height}\t#{window_activity}")
    sessions = {}
    for line in tm("list-panes", "-a", "-F", fmt).splitlines():
        fields = line.split("\t")
        if len(fields) != 18 or fields[3] != workspace:
            continue
        sid, name, attached, group, window, number, title, active, pane, index, command, selected, activity, left, top, width, height, window_activity = fields
        session = sessions.setdefault(sid, {"id": sid, "name": name, "attached": int(attached),
                                           "activity": int(activity or "0"), "windows": {}})
        win = session["windows"].setdefault(window, {"id": window, "index": int(number), "name": title,
                                                  "active": active == "1", "activity": int(window_activity or "0"), "panes": {}})
        win["panes"][pane] = {"id": pane, "index": int(index), "command": command, "active": selected == "1", "left": int(left), "top": int(top),
                                  "width": int(width), "height": int(height)}
    return sessions


def tree_rows(sessions, expanded, order="index", reverse=False):
    sort = {"index": lambda s: int(s["id"][1:]), "name": lambda s: s["name"].lower(),
            "activity": lambda s: (-s["activity"], s["name"])}[order]
    result = []
    for session in sorted(sessions.values(), key=sort, reverse=reverse):
        sid = session["id"]
        window_sort = {"index": lambda w: w["index"], "name": lambda w: (w["name"], w["index"]),
                       "activity": lambda w: (-w.get("activity", 0), w["name"])}[order]
        windows = sorted(session["windows"].values(), key=window_sort, reverse=reverse)
        active = next((window for window in windows if window["active"]), windows[0])
        pane = next((pane for pane in active["panes"].values() if pane["active"]), next(iter(active["panes"].values())))
        key = "session:" + sid
        label = ("− " if key in expanded else "+ ") + session["name"] + f": {len(windows)} window" + ("s" if len(windows) != 1 else "")
        if session["attached"]:
            label += " (attached)"
        result.append({"key": key, "kind": "session", "id": sid, "session": sid, "name": session["name"],
                       "label": label, "target": sid, "preview": pane["id"], "parent": None})
        if key not in expanded:
            continue
        for window in windows:
            wid = window["id"]
            key = "window:" + sid + ":" + wid
            panes = sorted(window["panes"].values(), key=lambda p: p["index"], reverse=reverse)
            active_pane = next((pane for pane in panes if pane["active"]), panes[0])
            label = "  " + ("− " if key in expanded else "+ ") + str(window["index"]) + ": " + window["name"]
            label += "*" if window["active"] else ""
            result.append({"key": key, "kind": "window", "id": wid, "session": sid, "name": window["name"],
                           "label": label, "target": sid + ":" + str(window["index"]), "preview": active_pane["id"],
                           "parent": "session:" + sid})
            if key in expanded:
                for pane in panes:
                    result.append({"key": "pane:" + sid + ":" + pane["id"], "kind": "pane", "id": pane["id"],
                                   "session": sid, "name": pane["command"], "label": "      " + str(pane["index"]) + ": " + pane["command"] + ("*" if pane["active"] else ""),
                                   "target": sid + ":" + str(window["index"]) + "." + str(pane["index"]),
                                   "preview": pane["id"], "parent": key})
    return result


class Picker:
    def __init__(self, args, state):
        self.args, self.state = args, Path(state)
        self.workspace = args.workspace or "general"
        self.return_workspace = tm("show-options", "-pqv", "-t", args.pane, "@workspace-return") or "general"
        self.expanded, self.tags = set(), set()
        self.selected, self.index, self.offset = "", 0, 0
        self.rows, self.sessions = [], {}
        self.notice, self.search, self.order, self.reverse = "", "", "index", False
        self.pending = None
        self.selection_style = curses.A_REVERSE
        self.data = json.loads(self.state.read_text())
        self.preview, self.last_preview = [], None
        self.preview_at, self.refresh_at = 0, 0
        from picker_preview import Preview
        self.renderer = Preview()
        self.preview_offset = 0
        self.filter = ""
        self.start_pane = args.pane
        self.prefix_key = {"C-a": "\x01", "C-b": "\x02"}.get(tm("show-options", "-gv", "prefix"), "\x01")

    def command(self, action, **values):
        pane = client_pane(self.args.client) or self.args.pane
        if pane != self.args.pane and action != "close-picker":
            tm("set-option", "-p", "-t", pane, "@workspace-picker-pid", str(os.getpid()))
        self.args.pane = pane
        argv = [str(HELPER), action, "--client", self.args.client, "--pane", pane, "--quiet", "1"]
        for key, value in values.items():
            argv += ["--" + key.replace("_", "-"), str(value)]
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            self.notice = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "Action failed."
        self.refresh_at = 0
        return result.returncode == 0

    def refresh(self):
        self.data = json.loads(self.state.read_text())
        if self.workspace not in self.data["workspaces"]:
            self.workspace = "general"
        self.sessions = fetch_sessions(self.workspace)
        self.rows = tree_rows(self.sessions, self.expanded, self.order, self.reverse)
        if self.filter:
            filtered = [r for r in self.rows if tm("display-message", "-p", "-t", r["target"], self.filter) not in ("", "0")]
            if filtered: self.rows = filtered
            else: self.notice = "Filter has no matches; showing all items"
        found = next((i for i, row in enumerate(self.rows) if row["key"] == self.selected), None)
        self.index = found if found is not None else min(self.index, max(0, len(self.rows) - 1))
        self.selected = self.rows[self.index]["key"] if self.rows else ""
        self.tags.intersection_update(row["key"] for row in self.rows)
        self.refresh_at = time.monotonic() + .5

    def row(self):
        return self.rows[self.index] if self.rows else None

    def change_workspace(self, wid):
        if wid not in self.data["workspaces"]:
            return
        if wid == "archived" and self.workspace != "archived":
            self.return_workspace = self.workspace
        self.workspace, self.selected, self.index, self.offset = wid, "", 0, 0
        self.expanded.clear()
        self.preview_offset = 0
        self.tags.clear()
        self.command("view-context", workspace=wid, destination=self.return_workspace)
        self.refresh()

    def box(self, screen, title, initial="", confirm=False, allow_empty=False):
        height, width = screen.getmaxyx()
        box_width = min(width - 4, max(40, min(90, len(title) + 4)))
        box_height = 5
        top, left = max(0, (height - box_height) // 2), max(0, (width - box_width) // 2)
        value = initial
        curses.curs_set(0 if confirm else 1)
        screen.timeout(-1)
        try:
            while True:
                for y in range(top, min(height, top + box_height)):
                    put(screen, y, left, " " * box_width, curses.A_REVERSE, box_width)
                put(screen, top + 1, left + 2, title, curses.A_REVERSE | curses.A_BOLD, box_width - 4)
                text = "y confirms · any other key cancels" if confirm else "> " + value
                put(screen, top + 3, left + 2, text, curses.A_REVERSE, box_width - 4)
                screen.refresh()
                key = screen.get_wch()
                if confirm:
                    return key == "y"
                if key in ("\x1b", "\x03"):
                    return None
                if key in ("\n", "\r", curses.KEY_ENTER):
                    return value.strip() if allow_empty else value.strip() or None
                if key == "\x15":
                    value = ""
                elif key == "\x17":
                    value = value.rstrip().rsplit(" ", 1)[0] if " " in value.rstrip() else ""
                elif key in ("\x7f", "\b", curses.KEY_BACKSPACE):
                    value = value[:-1]
                elif isinstance(key, str) and key.isprintable():
                    value += key
        finally:
            screen.timeout(100)
            curses.curs_set(0)

    def choose_workspace(self, screen):
        nodes = []
        def walk(parent, depth):
            for wid in children(self.data, parent):
                nodes.append((wid, depth)); walk(wid, depth + 1)
        walk(None, 0)
        index = next((i for i, row in enumerate(nodes) if row[0] == self.workspace), 0)
        try:
            while True:
                window = overlay(screen, "Move session to workspace", 78, min(24, len(nodes) + 6))
                height, width = window.getmaxyx()
                put(window, 1, 2, "j/k select · Enter move · Esc cancels", curses.A_DIM)
                visible = max(1, height - 5)
                start = max(0, min(index - visible // 2, len(nodes) - visible))
                for y, (wid, depth) in enumerate(nodes[start:start + visible], 3):
                    put(window, y, 2, ("  " * depth + self.data["workspaces"][wid]["name"]).ljust(width - 4), self.selection_style if start + y - 3 == index else 0, width - 4)
                window.refresh()
                try: key = read_key(window)
                except curses.error: continue
                if key == "\x1b": return None
                if key in ("j", curses.KEY_DOWN): index = (index + 1) % len(nodes)
                elif key in ("k", curses.KEY_UP): index = (index - 1) % len(nodes)
                elif key in ("\r", "\n", curses.KEY_ENTER): return nodes[index][0]
        finally:
            screen.touchwin()

    def help(self, screen, accent):
        offset = 0
        while True:
            window = overlay(screen, "Session picker · all keys", 118, len(GUIDE) // 2 + 5, accent)
            height, width = window.getmaxyx()
            count = max(1, height - 5)
            guide_columns(window, 2, count, GUIDE[offset * 2:], accent)
            put(window, height - 2, 2, "j/k · d/u scroll    ? / Esc / q return", accent, width - 4)
            window.refresh()
            try: key = read_key(window)
            except curses.error: continue
            if key in ("?", "q", "\x1b", "\x07"): break
            if key in ("j", curses.KEY_DOWN, "d", curses.KEY_NPAGE): offset = min(max(0, len(GUIDE) // 2 - count), offset + (count if key in ("d", curses.KEY_NPAGE) else 1))
            if key in ("k", curses.KEY_UP, "u", curses.KEY_PPAGE): offset = max(0, offset - (count if key in ("u", curses.KEY_PPAGE) else 1))
        del window
        screen.touchwin()

    def context_menu(self, screen, accent, preview=False):
        entries = [("Previous preview", "<"), ("Next preview", ">")] if preview else [
            ("Open selected item", "\r"), ("Expand / next", "l"), ("Mark pane", "\x00"),
            ("Toggle tag", "t"), ("Tag all", "\x14"), ("Clear tags", "T"),
            ("Delete selected · confirm", "x"), ("Delete tagged · confirm", "X")]
        index = 0
        while True:
            window = overlay(screen, "Actions", 38, len(entries) + 4, accent)
            for y, (label, key) in enumerate(entries, 2):
                put(window, y, 2, label.ljust(32), self.selection_style if y - 2 == index else 0, 34)
            window.refresh()
            try: key = read_key(window)
            except curses.error: continue
            if key in ("q", "\x1b"): break
            if key in ("j", curses.KEY_DOWN): index = (index + 1) % len(entries)
            elif key in ("k", curses.KEY_UP): index = (index - 1) % len(entries)
            elif key in ("\r", "\n", curses.KEY_ENTER):
                curses.unget_wch(entries[index][1]); break
        screen.touchwin()

    def draw_preview(self, screen, area, accent):
        row = self.row()
        width = screen.getmaxyx()[1]
        caption = " Preview · " + (row["label"].strip() if row else "empty") + " · < > browse "
        put(screen, area.preview_top, 1, "─" * max(0, width - 2), accent)
        put(screen, area.preview_top, 3, caption, accent, width - 6)
        if not row: return
        session = self.sessions[row["session"]]
        windows = sorted(session["windows"].values(), key=lambda win: win["index"])
        window = next((win for win in windows if win["active"]), windows[0]) if row["kind"] == "session" else next(win for win in windows if row["preview"] in win["panes"])
        if row["kind"] == "session": window = windows[(windows.index(window) + self.preview_offset) % len(windows)]
        panes = sorted(window["panes"].values(), key=lambda p: p["index"])
        if row["kind"] == "pane": panes = [next(p for p in panes if p["id"] == row["id"])]
        elif row["kind"] == "window" and self.preview_offset:
            active = next((i for i, p in enumerate(panes) if p["active"]), 0)
            panes = [panes[(active + self.preview_offset) % len(panes)]]
        y, x, height, columns = area.preview_top + 1, 1, area.preview_height - 1, width - 2
        refresh = time.monotonic() >= self.preview_at
        sx = max(p["left"] + p["width"] for p in panes)
        sy = max(p["top"] + p["height"] for p in panes)
        for pane in panes:
            if len(panes) == 1: py, px, ph, pw = y, x, height, columns
            else:
                px = x + pane["left"] * columns // sx
                py = y + pane["top"] * height // sy
                right = x + (pane["left"] + pane["width"]) * columns // sx
                bottom = y + (pane["top"] + pane["height"]) * height // sy
                pw, ph = max(1, right - px), max(1, bottom - py)
                if pane["left"]:
                    for yy in range(py, bottom): put(screen, yy, px - 1, "│", accent)
            title = f" {window['index']}:{window['name']} · {pane['index']} {pane['command']}" + (" ● " if pane["active"] else " ")
            put(screen, py, px, "─" * pw, accent, pw)
            put(screen, py, px + max(0, (pw - len(title)) // 2), title, accent, pw)
            try: self.renderer.pane(screen, pane["id"], py + 1, px, ph - 1, pw, refresh)
            except (subprocess.CalledProcessError, ValueError): pass
        if refresh: self.preview_at = time.monotonic() + .35

    def render(self, screen, accent=0):
        height, width = screen.getmaxyx()
        prefs = self.data["preferences"]
        badges = badge_lines(self.data, self.workspace, width)
        max_rows = max(1, height // 5)
        active_line = next((i for i, line in enumerate(badges) if any(wid == self.workspace for wid, label in line)), 0)
        first = max(0, active_line - max_rows + 1)
        badges = badges[first:first + max_rows]
        area = layout(height, prefs["keys"], prefs["preview"], len(badges))
        screen.erase()
        self.badge_hits = []
        for y, line in enumerate(badges, area.title):
            x = max(1, (width - sum(len(label) for wid, label in line) - 2 * (len(line) - 1)) // 2)
            for wid, label in line:
                self.badge_hits.append((y, x, x + len(label), wid))
                active = wid == self.workspace
                edge = accent if active else getattr(self, "badge_edge", accent | curses.A_DIM)
                interior = self.selection_style if active else getattr(self, "badge_style", curses.A_DIM)
                put(screen, y, x, label[0], edge)
                put(screen, y, x + 1, label[1:-1], interior)
                put(screen, y, x + len(label) - 1, label[-1], edge)
                x += len(label) + 2
        if self.notice: put(screen, area.list_top - 1, 2, self.notice, accent, width - 4)
        if not self.rows:
            text = "No sessions · n creates a session · w opens workspace actions"
            put(screen, area.list_top + min(1, area.list_height - 1), max(1, (width - len(text)) // 2), text)
        else:
            self.offset = max(min(self.offset, self.index), self.index - area.list_height + 1)
            for index in range(self.offset, min(len(self.rows), self.offset + area.list_height)):
                row = self.rows[index]
                shortcut = str(index) if index < 10 else "M-" + chr(97 + index - 10) if index < 36 else ""
                marker = "* " if row["key"] in self.tags else "  "
                label = f"({shortcut}) " + marker + row["label"]
                put(screen, area.list_top + index - self.offset, 1, label.ljust(max(1, width - 2)), self.selection_style if index == self.index else 0, width - 2)
            if len(self.rows) > area.list_height:
                thumb = max(1, area.list_height * area.list_height // len(self.rows))
                start = self.offset * (area.list_height - thumb) // max(1, len(self.rows) - area.list_height)
                for position in range(area.list_height):
                    put(screen, area.list_top + position, width - 2, "┃" if start <= position < start + thumb else "│", accent)
        panel(screen, area, accent)
        if area.preview_top is not None: self.draw_preview(screen, area, accent)
        screen.refresh()
        return area

    def archive(self, screen, row):
        sid = row["session"]
        session = self.sessions[sid]
        if self.workspace != "archived":
            self.command("assign", session=sid, destination="archived", workspace=self.workspace)
            self.notice = "Session archived · Ctrl+R opens Archive"
            return
        origin = self.data["origins"].get(session["name"])
        if origin in self.data["workspaces"] and origin != "archived":
            if self.command("assign", session=sid, destination=origin):
                self.change_workspace(origin)
        else:
            name = self.box(screen, "Restore to existing workspace or new path · Esc cancels")
            if name and self.command("apply-name", workspace="archived", session=sid, kind="restore", name=name):
                self.data = json.loads(self.state.read_text())
                self.change_workspace(self.data["sessions"][session["name"]])
        self.selected = "session:" + sid
        self.index = next((i for i, item in enumerate(self.rows) if item["key"] == self.selected), self.index)

    def delete(self, screen, targets):
        try:
            token = destruction_token(targets)
        except (ValueError, subprocess.CalledProcessError) as error:
            self.notice = str(error)
            return
        label = f"Delete {len(targets)} tagged item(s) and their processes?" if len(targets) > 1 else f"Delete {targets[0][0]} and its processes?"
        if self.box(screen, label, confirm=True):
            if self.command("delete-targets", name=json.dumps(targets), token=token):
                self.command("view-context", workspace=self.workspace, destination=self.return_workspace)
                self.tags.clear()
                self.notice = "Deleted. Running clients moved safely if needed."
        else:
            self.notice = "Deletion cancelled."

    def queue(self, action, **values):
        self.pending = (action, values)

    def run(self, screen):
        curses.set_escdelay(25)
        curses.raw()  # Ctrl+S is search, not terminal XOFF flow control.
        curses.curs_set(0)
        screen.keypad(True)
        screen.timeout(100)
        try:
            curses.use_default_colors()
            colour, foreground = theme_accent()
            curses.init_pair(1, colour, -1)
            curses.init_pair(2, foreground, colour)
            curses.init_pair(3, 252 if curses.COLORS >= 256 else curses.COLOR_WHITE, 236 if curses.COLORS >= 256 else curses.COLOR_BLACK)
            curses.init_pair(4, 236 if curses.COLORS >= 256 else curses.COLOR_BLACK, -1)
            accent = curses.color_pair(1)
            self.selection_style = curses.color_pair(2) | curses.A_BOLD
            self.badge_style = curses.color_pair(3)
            self.badge_edge = curses.color_pair(4)
            curses.mousemask(curses.ALL_MOUSE_EVENTS)
        except curses.error:
            accent = curses.A_BOLD
        tm("set-option", "-p", "-t", self.args.pane, "@workspace-picker-pid", str(os.getpid()))
        prefix = False
        while True:
            if time.monotonic() >= self.refresh_at:
                requested = tm("show-options", "-pqv", "-t", self.args.pane, "@workspace-picker-jump")
                if requested:
                    tm("set-option", "-pu", "-t", self.args.pane, "@workspace-picker-jump")
                    self.change_workspace(requested)
                self.refresh()
            area = self.render(screen, accent)
            try:
                key = read_key(screen)
            except curses.error:
                continue
            row = self.row()
            alt = isinstance(key, tuple) and key[0] == "alt"
            value = key[1] if alt else key
            number = slot_key(value)
            had_prefix = prefix
            prefix = False
            if had_prefix:
                if key == curses.KEY_BTAB:
                    self.queue("last-local"); return
                if alt and value == "\t":
                    self.queue("last-global"); return
                if number:
                    parent = nested_parent(self.data, self.workspace) if alt else None
                    destination = shortcut_map(self.data, parent).get(number)
                    if destination: self.change_workspace(destination)
                    else: self.notice = "No workspace assigned to this shortcut"
                    continue
                if key == "s": continue
            if key == self.prefix_key:
                prefix = True; continue
            if key in ("q", "\x1b", "\x07", "\x03"): return
            if alt and number or (isinstance(value, int) and number):
                parent = nested_parent(self.data, self.workspace) if alt else None
                destination = shortcut_map(self.data, parent).get(number)
                if destination: self.change_workspace(destination)
                else: self.notice = "No nested workspace assigned to this shortcut" if alt else "No workspace assigned to this shortcut"
                continue
            # Native numbered row selection wins over workspace bindings.
            choice = int(key) if isinstance(key, str) and len(key) == 1 and key in "0123456789" else 10 + ord(value) - ord("a") if alt and isinstance(value, str) and len(value) == 1 and "a" <= value <= "z" else None
            if choice is not None:
                if choice < len(self.rows):
                    self.queue("select-target", target=self.rows[choice]["target"]); return
                self.notice = "No item at this row number"
                continue
            if key in ("j", curses.KEY_DOWN, "\x0e"):
                self.index = (self.index + 1) % len(self.rows) if self.rows else 0
            elif key in ("k", curses.KEY_UP, "\x10"):
                self.index = (self.index - 1) % len(self.rows) if self.rows else 0
            elif key in ("g", curses.KEY_HOME): self.index = 0
            elif key in ("G", curses.KEY_END): self.index = max(0, len(self.rows) - 1)
            elif key in (curses.KEY_NPAGE, "\x06"): self.index = min(max(0, len(self.rows) - 1), self.index + area.list_height)
            elif key in (curses.KEY_PPAGE, "\x02"): self.index = max(0, self.index - area.list_height)
            elif key in ("d", "\x04"): self.index = min(max(0, len(self.rows) - 1), self.index + max(1, area.list_height // 2))
            elif key in ("u", "\x15"): self.index = max(0, self.index - max(1, area.list_height // 2))
            elif key in ("h", "-", curses.KEY_LEFT) and row:
                if row["key"] in self.expanded:
                    self.expanded.remove(row["key"])
                elif row["parent"]:
                    self.selected = row["parent"]
                    self.expanded.discard(row["parent"])
                else:
                    self.index = max(0, self.index - 1)
                    self.selected = self.rows[self.index]["key"]
                self.refresh_at = 0
            elif key in ("l", "+", curses.KEY_RIGHT) and row and row["kind"] != "pane":
                if row["key"] in self.expanded:
                    self.index = min(len(self.rows) - 1, self.index + 1)
                    self.selected = self.rows[self.index]["key"]
                else:
                    self.expanded.add(row["key"])
                self.refresh_at = 0
            elif alt and value == "-":
                self.expanded.clear()
                self.refresh_at = 0
            elif alt and value == "+":
                self.expanded.update("session:" + sid for sid in self.sessions)
                self.expanded.update("window:" + sid + ":" + wid for sid, s in self.sessions.items() for wid in s["windows"])
                self.refresh_at = 0
            elif key in ("\n", "\r", curses.KEY_ENTER) and row:
                self.queue("select-target", target=row["target"])
                return
            elif key in ("H", "L", "\t", curses.KEY_BTAB):
                peers = children(self.data, self.data["workspaces"][self.workspace]["parent"])
                step = -1 if key in ("H", curses.KEY_BTAB) else 1
                self.change_workspace(peers[(peers.index(self.workspace) + step) % len(peers)])
            elif key in ("[", "]"):
                parent = self.data["workspaces"][self.workspace]["parent"]
                nested = children(self.data, self.workspace)
                self.change_workspace(parent if key == "[" and parent else nested[0] if key == "]" and nested else self.workspace)
            elif key == "\x12":
                self.change_workspace(self.return_workspace if self.workspace == "archived" and self.return_workspace in self.data["workspaces"] else "general" if self.workspace == "archived" else "archived")
            elif key in ("b", "v"):
                self.command("toggle-keys" if key == "b" else "toggle-preview")
            elif key == "s":
                from workspace_ui import workspace_list
                args = argparse.Namespace(client=self.args.client, pane=self.args.pane, workspace=self.workspace)
                chosen = workspace_list(args, self.state, screen=screen)
                screen.touchwin()
                self.data = json.loads(self.state.read_text())
                destination = chosen or (self.workspace if self.workspace in self.data["workspaces"] else args.workspace)
                if destination != self.workspace:
                    self.change_workspace(destination)
                else:
                    self.command("view-context", workspace=self.workspace, destination=self.return_workspace)
                self.refresh_at = 0
            elif key == "?":
                self.help(screen, accent)
            elif key == "w":
                self.queue("menu", workspace=self.workspace,
                           session=row["session"] if row else "")
                return
            elif key == "z" and row:
                self.archive(screen, row)
            elif key == "m" and row:
                target = self.choose_workspace(screen)
                if target and self.command("assign", session=row["session"], destination=target):
                    self.change_workspace(target)
            elif key in ("c", "R") or (key == "n" and not self.rows):
                if key == "R" and not row:
                    continue
                name = self.box(screen, "New session name" if key != "R" else "Rename selected session")
                if name:
                    self.command("apply-name", kind="session-rename" if key == "R" else "session",
                                 workspace=self.workspace, session=row["session"] if row else "", name=name)
            elif key in ("\x13", "/") or (key == "n" and self.search):
                if key in ("\x13", "/"):
                    self.search = self.box(screen, "Find session/window/pane") or ""
                if self.search:
                    found = next((i for i in list(range(self.index + 1, len(self.rows))) + list(range(0, self.index + 1))
                                  if self.search.casefold() in self.rows[i]["label"].casefold()), None)
                    if found is not None: self.index = found
            elif key == "t" and row:
                if row["key"] in self.tags: self.tags.remove(row["key"])
                else:
                    remove = {"session:" + row["session"]}
                    if row["kind"] == "session":
                        remove.update(item["key"] for item in self.rows if item["session"] == row["session"])
                    elif row["kind"] == "window":
                        remove.update(item["key"] for item in self.rows if item["parent"] == row["key"])
                    elif row["parent"]:
                        remove.add(row["parent"])
                    self.tags.difference_update(remove)
                    self.tags.add(row["key"])
            elif key == "T": self.tags.clear()
            elif key == "\x14": self.tags = {row["key"] for row in self.rows if row["kind"] == "session"}
            elif key == "x" and row: self.delete(screen, [(row["kind"], row["id"])])
            elif key == "X" and self.tags: self.delete(screen, [(r["kind"], r["id"]) for r in self.rows if r["key"] in self.tags])
            elif key == "D" and self.workspace == "archived":
                try:
                    rows = archive_snapshot()
                    if rows and self.box(screen, f"PERMANENTLY delete ALL {len(rows)} archived sessions?", confirm=True):
                        self.command("purge", workspace="archived", token=snapshot_token(rows))
                except ValueError as error: self.notice = str(error)
            elif key == "E":
                rows = sorted((sid, session["name"]) for sid, session in self.sessions.items())
                if rows and self.box(screen, f"DELETE all {len(rows)} sessions, keep workspace?", confirm=True):
                    self.command("empty", workspace=self.workspace, token=snapshot_token(rows))
                    self.command("view-context", workspace=self.workspace)
            elif key == "f":
                value = self.box(screen, "Filter tmux format · Ctrl+U clears · empty shows all", self.filter, allow_empty=True)
                if value is not None:
                    self.filter = "" if value == "1" else value
                    self.selected = ""; self.refresh_at = 0
            elif key == ":" and row:
                template = self.box(screen, "Tmux command on tags / current · %% is target")
                if template:
                    targets = [r["target"] for r in self.rows if r["key"] in self.tags] or [row["target"]]
                    for target in targets:
                        self.command("item-command", target=target, name=template)
                    self.refresh_at = 0
            elif key == "\x00" and row:
                tm("select-pane", "-m", "-t", row["preview"])
                self.notice = "Pane marked · M clears mark"
            elif key == "M":
                tm("select-pane", "-M")
                self.notice = "Pane mark cleared"
            elif alt and value == "H":
                start = next((r for r in self.rows if r["preview"] == self.start_pane), None)
                if start: self.index = self.rows.index(start)
            elif key in ("<", ">"):
                self.preview_offset += -1 if key == "<" else 1
                self.preview_at = 0
            elif key == "O":
                self.order = {"index": "name", "name": "activity", "activity": "index"}[self.order]
                self.refresh_at = 0
            elif key == "r":
                self.reverse = not self.reverse
                self.refresh_at = 0
            elif key == curses.KEY_MOUSE:
                try:
                    _, x, y, _, buttons = curses.getmouse()
                    badge = next((wid for yy, left, right, wid in self.badge_hits if yy == y and left <= x < right), None)
                    if badge and buttons & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED): self.change_workspace(badge)
                    elif buttons & curses.BUTTON4_PRESSED: self.index = (self.index - 1) % len(self.rows) if self.rows else 0
                    elif buttons & getattr(curses, "BUTTON5_PRESSED", 0): self.index = (self.index + 1) % len(self.rows) if self.rows else 0
                    elif buttons & (curses.BUTTON3_PRESSED | curses.BUTTON3_CLICKED):
                        if area.list_top <= y < area.list_top + area.list_height:
                            self.index = min(max(0, len(self.rows) - 1), self.offset + y - area.list_top)
                        self.context_menu(screen, accent, preview=area.preview_top is not None and y >= area.preview_top)
                    elif area.list_top <= y < area.list_top + area.list_height:
                        self.index = min(max(0, len(self.rows) - 1), self.offset + y - area.list_top)
                        if buttons & curses.BUTTON1_DOUBLE_CLICKED and self.rows:
                            self.queue("select-target", target=self.rows[self.index]["target"])
                            return
                except curses.error: pass
            if self.rows:
                self.index = min(self.index, len(self.rows) - 1)
                # Explicit parent selection takes precedence after collapsing.
                if key not in ("h", "-", curses.KEY_LEFT) or not row or not row["parent"] or row["key"] in self.expanded:
                    self.selected = self.rows[self.index]["key"]


def run_picker(args, state):
    picker = Picker(args, state)
    try:
        curses.wrapper(picker.run)
    finally:
        picker.command("close-picker")
    if picker.pending:
        action, values = picker.pending
        subprocess.run(["tmux", "run-shell", "-b", "-d", "0.1",
                        shell_command(action, args.client, client_pane(args.client) or args.pane, **values)], check=True)
