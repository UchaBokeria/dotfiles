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
import picker_theme as theme

from workspaces import (archive_snapshot, children, client_pane, destruction_token,
                        nested_parent, path_name, shell_command, shortcut_label, shortcut_map, snapshot_token, tm,
                        SYSTEM, deletion_token, descendant)

HELPER = Path(__file__).with_name("workspaces.py")
GUIDE = [
    ("j/k  ↑/↓", "Select · wraps first / last"), ("0–9  Alt+a–z", "Open numbered row 0–35"),
    ("d/u  Ctrl+D/U", "Half page down / up"), ("PgDn/PgUp", "Full page · Ctrl+F/B"),
    ("g/G  Home/End", "First / last item"), ("Enter", "Open selected item"),
    ("h/l  ←/→  −/+", "Collapse / expand item"), ("Alt+− / Alt++", "Collapse / expand all"),
    ("s", "Workspace list · J/K reorder"), ("H/L  Tab/S-Tab", "Previous / next workspace"),
    ("Prefix 1–0/Fn", "Root workspace shortcut"), ("Alt+1–0/Fn", "Nested workspace shortcut"),
    ("[ / ]", "Parent / first child"), ("Ctrl+R", "Archive / return workspace"),
    ("z", "Archive / restore tags"), ("m / w", "Move tagged sessions / actions"),
    ("c / r", "Create / rename tagged sessions"), ("x / X", "Delete tags / item · asks"),
    ("t / T / Ctrl+T", "Toggle / clear / tag all"), ("/  Ctrl+S  n", "Fuzzy search / repeat"),
    ("f", "Filter by tmux format"), (":", "Run tmux command on tags"),
    (".", "Move windows to any session"), ("Alt+H", "Jump to starting pane"),
    ("O", "Change sort field"), ("< / >", "Previous / next preview"),
    ("E / D", "Empty workspace / Archive"), ("Prefix S-Tab", "Previous session in workspace"),
    ("Prefix Alt+Tab", "Previous session globally"), ("v", "Toggle preview · remembered"),
    ("J / K", "Move session down / up"), ("Ctrl+U", "Clear input / filter"),
    ("i / a", "Search list menus · Esc normal"), ("q / Esc", "Close picker · Ctrl+G too"),
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


def layout(height, keys=False, preview=True, header_rows=1):
    """The retired inline guide never occupies space; previews get two thirds."""
    top = min(max(3, header_rows + 3), max(3, height - 5))
    available = max(1, height - top)
    preview_height = max(0, min(available - 3, max(5, available * 2 // 3))) if preview else 0
    return Layout(1 if height >= 20 else 0, top, max(1, available - preview_height),
                  None, 0, height - preview_height if preview_height else None, preview_height)


def clean(value):
    return "".join(char if char.isprintable() or "\ue000" <= char <= "\uf8ff" else " " for char in str(value))


def put(screen, y, x, text, attr=0, width=None):
    height, columns = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < columns:
        limit = min(columns - x - (1 if y == height - 1 else 0), width if width is not None else columns)
        if limit > 0:
            try:
                screen.addnstr(y, x, clean(text), limit, attr)
            except curses.error:
                pass


def paint_row(screen, y, x, label, width, selected=False, edge=None):
    if selected and theme.ROUNDED and width >= 4:
        attr = theme.BORDER if edge is None else edge
        put(screen, y, x - 1, '', attr)
        put(screen, y, x, label.ljust(width), theme.SELECTION, width)
        put(screen, y, x + width, '', attr)
    else:
        body = theme.TEXT if edge is not None else theme.BODY
        put(screen, y, x, label.ljust(width), theme.SELECTION if selected else body, width)


def toast(screen, message, y=None, right=2):
    if not message: return
    height, width = screen.getmaxyx()
    label = ' ' + message + ' '
    if theme.ROUNDED: label += '  '
    label = label[:max(1, width - 2 * right)]
    paint_row(screen, height - 1 if y is None else y, max(1, width - right - len(label)), label, len(label), True)


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
    theme.apply()
    window.bkgd(" ", theme.BODY)
    window.erase()
    from picker_startup import frame
    frame(window, 0, 0, height, width, theme.BORDER, theme.ROUNDED)
    accent = theme.BORDER or accent
    put(window, 0, max(2, (width - len(title) - 2) // 2), " " + title + " ", accent | curses.A_BOLD)
    return window


def read_key(screen, allow_alt=True):
    key = screen.get_wch()
    if key == "\x1b":
        if not allow_alt: return key
        screen.timeout(30)
        try:
            following = screen.get_wch()
            if allow_alt == "workspace" and slot_key(following) is None:
                curses.unget_wch(following)
                return "\x1b"
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
    if isinstance(key, str) and len(key) == 1 and key in "1234567890":
        return 10 if key == "0" else int(key)
    if isinstance(key, int):
        for number in range(1, 13):
            if key == curses.KEY_F0 + number:
                return number + 10
    return None


def edit_text(value, cursor, key):
    if key in (curses.KEY_LEFT, '\x02'): return value, max(0, cursor - 1)
    if key in (curses.KEY_RIGHT, '\x06'): return value, min(len(value), cursor + 1)
    if key in (curses.KEY_HOME, '\x01'): return value, 0
    if key in (curses.KEY_END, '\x05'): return value, len(value)
    if key == '\x15': return '', 0
    if key == '\x17':
        left = value[:cursor].rstrip()
        start = left.rfind(' ') + 1
        return value[:start] + value[cursor:], start
    if key in (curses.KEY_BACKSPACE, '\x7f', '\b') and cursor:
        return value[:cursor - 1] + value[cursor:], cursor - 1
    if key == curses.KEY_DC: return value[:cursor] + value[cursor + 1:], cursor
    if isinstance(key, str) and key.isprintable():
        return value[:cursor] + key + value[cursor:], cursor + len(key)
    return value, cursor


def input_dialog(screen, title, initial='', confirm=False, allow_empty=False):
    import textwrap
    value, cursor = initial, len(initial)
    curses.curs_set(0 if confirm else 1)
    try:
        while True:
            window = overlay(screen, 'Confirm' if confirm else title, 84, 8 if confirm else 7)
            height, width = window.getmaxyx()
            if confirm:
                for y, line in enumerate(textwrap.wrap(title, max(1, width - 6))[:max(1, height - 4)], 2):
                    put(window, y, 3, line, theme.BODY, width - 6)
                put(window, height - 2, 3, 'y confirms · any other key cancels', theme.BORDER, width - 6)
            else:
                start = max(0, cursor - max(1, width - 9))
                put(window, 2, 3, '› ', theme.BORDER)
                put(window, 2, 5, value[start:], theme.BODY, width - 8)
                put(window, height - 2, 3, 'Enter accepts · Esc cancels · Ctrl+U clears', theme.MUTED, width - 6)
                window.move(2, min(width - 3, 5 + cursor - start))
            window.refresh()
            try: key = read_key(window, allow_alt=False)
            except curses.error: continue
            if confirm: return key == 'y'
            if key in ('\x1b', '\x03', '\x07'): return None
            if key in ('\n', '\r', curses.KEY_ENTER):
                return value.strip() if allow_empty else value.strip() or None
            value, cursor = edit_text(value, cursor, key)
    finally:
        curses.curs_set(0)
        screen.touchwin()


@dataclass
class SearchMode:
    insert: bool = False
    query: str = ''
    cursor: int = 0

    def key(self, key):
        if key in ('\x03', '\x07'): return 'close'
        if key == '\x1b':
            if self.insert:
                self.insert = False
                return 'mode'
            return 'close'
        if key in ('\n', '\r', curses.KEY_ENTER): return 'accept'
        if key in (curses.KEY_DOWN, '\x0e', '\t') or (not self.insert and key == 'j'): return 'down'
        if key in (curses.KEY_UP, '\x10', curses.KEY_BTAB) or (not self.insert and key == 'k'): return 'up'
        if not self.insert:
            if key in ('i', 'a', '/'):
                self.insert = True
                if key in ('a', '/'): self.cursor = len(self.query)
                return 'mode'
            if key in ('g', curses.KEY_HOME): return 'first'
            if key in ('G', curses.KEY_END): return 'last'
            if key in ('d', '\x04', curses.KEY_NPAGE): return 'page-down'
            if key in ('u', '\x15', curses.KEY_PPAGE): return 'page-up'
            return 'action'
        previous = self.query
        self.query, self.cursor = edit_text(self.query, self.cursor, key)
        return 'query' if self.query != previous else 'edit'


def ranked(items, query, text):
    values = [(fuzzy_score(query, text(item)), index, item) for index, item in enumerate(items)]
    return [item for score, index, item in sorted((value for value in values if value[0] is not None), key=lambda value: (value[0], value[1]))]


def search_prompt(window, mode, count, total, hint='Enter selects'):
    height, width = window.getmaxyx()
    label = 'INSERT' if mode.insert else 'NORMAL'
    start = max(0, mode.cursor - max(1, width - 20))
    put(window, 2, 2, label + ' › ' + mode.query[start:], theme.BORDER, width - 4)
    put(window, 3, 2, f'{count} / {total} matches', theme.MUTED, width - 4)
    footer = ('Esc normal · ↑/↓ select · ' if mode.insert else 'i/a search · j/k select · Esc close · ') + hint
    put(window, height - 2, 2, footer, theme.MUTED, width - 4)
    curses.curs_set(1 if mode.insert else 0)
    if mode.insert: window.move(2, min(width - 3, 2 + len(label) + 3 + mode.cursor - start))


def navigate(index, action, count, page):
    if not count: return 0
    if action == 'down': return (index + 1) % count
    if action == 'up': return (index - 1) % count
    if action == 'first': return 0
    if action == 'last': return count - 1
    if action == 'page-down': return min(count - 1, index + page)
    if action == 'page-up': return max(0, index - page)
    return min(index, count - 1)


def choose_action(screen, title, entries, selected=0):
    """Searchable list: normal first; i/a insert; Esc normal, then Esc close."""
    index, mode = selected, SearchMode()
    try:
        while True:
            matches = ranked(entries, mode.query, lambda item: item[0] + ' ' + item[1])
            window = overlay(screen, title, 92, min(28, len(entries) + 8))
            height, width = window.getmaxyx()
            visible = max(1, height - 7)
            index = min(index, max(0, len(matches) - 1))
            start = max(0, min(index - visible // 2, len(matches) - visible))
            for y, (shortcut, label, value) in enumerate(matches[start:start + visible], 5):
                attr = theme.SELECTION if start + y - 5 == index else theme.BODY
                paint_row(window, y, 2, shortcut.ljust(7) + label, width - 4, start + y - 5 == index)
            search_prompt(window, mode, len(matches), len(entries))
            window.refresh()
            try: key = read_key(window, allow_alt=False)
            except curses.error: continue
            hotkey = {"\x12": "C-r", "\t": "Tab", curses.KEY_BTAB: "S-Tab"}.get(key, key)
            if not mode.insert and key not in ('i', 'a', '/', 'j', 'k'):
                found = next((entry for entry in matches if entry[0] == hotkey and entry[0]), None)
                if found: return found[2]
            action = mode.key(key)
            if action == 'close': return None
            if action == 'accept' and matches: return matches[index][2]
            if action == 'query': index = 0
            elif action == 'action':
                key = {"\x12": "C-r", "\t": "Tab", curses.KEY_BTAB: "S-Tab"}.get(key, key)
                found = next((entry for entry in matches if entry[0] == key and entry[0]), None)
                if found: return found[2]
            else: index = navigate(index, action, len(matches), visible)
    finally:
        curses.curs_set(0)
        screen.touchwin()


def fuzzy_score(query, text):
    """Stable subsequence ranking, preferring contiguous and word-start matches."""
    text = text.casefold()
    total = 0
    for token in query.casefold().split():
        direct = text.find(token)
        if direct >= 0:
            total += direct - len(token) * 8
            continue
        previous, cost = -1, 0
        for char in token:
            index = text.find(char, previous + 1)
            if index < 0: return None
            cost += index - previous - 1
            if index == 0 or text[index - 1] in ' /_-:': cost -= 4
            previous = index
        total += cost + 10
    return total


def preview_title(session, window):
    return f"● {session['name']}  {len(session['windows'])}  {window['name']} ●"


def preview_separator(screen, y, title, accent=0):
    width = screen.getmaxyx()[1]
    if len(title) > width - 6: title = title[:max(1, width - 9)] + '… ●'
    put(screen, y, 1, '─' * max(0, width - 2), accent)
    label = ' ' + title + ' '
    put(screen, y, max(1, (width - len(label)) // 2), label, accent, width - 2)


def pane_regions(panes, y, x, height, columns):
    """Map actual tmux gap cells to consistent divider columns, including odd sizes."""
    if (len(panes) == 2 and min(p['left'] for p in panes) == 0
            and max(p['left'] for p in panes) > 0
            and all(p['top'] == 0 for p in panes)
            and panes[0]['height'] == panes[1]['height']
            and abs(panes[0]['width'] - panes[1]['width']) <= 1):
        # An equal tmux split can give one pane an extra cell. Keep its
        # preview divider on the exact column used by centred help dialogs.
        middle = x + columns // 2
        for pane in panes:
            left = x if pane['left'] == 0 else middle + 1
            right = middle if pane['left'] == 0 else x + columns
            yield pane, y, left, height, max(1, right - left)
        return
    sx = max(p['left'] + p['width'] for p in panes)
    sy = max(p['top'] + p['height'] for p in panes)
    def coord(value, origin, size, full): return origin + int(value * max(0, size - 1) / max(1, full - 1) + .5)
    for pane in panes:
        if len(panes) == 1:
            yield pane, y, x, height, columns
            continue
        px = x if pane['left'] == 0 else coord(pane['left'] - 1, x, columns, sx) + 1
        py = y if pane['top'] == 0 else coord(pane['top'] - 1, y, height, sy) + 1
        right = x + columns if pane['left'] + pane['width'] == sx else coord(pane['left'] + pane['width'], x, columns, sx)
        bottom = y + height if pane['top'] + pane['height'] == sy else coord(pane['top'] + pane['height'], y, height, sy)
        yield pane, py, px, max(1, bottom - py), max(1, right - px)


def fetch_sessions(workspace):
    fmt = ("#{session_id}\t#{session_name}\t#{session_attached}\t#{@workspace-id}\t"
           "#{window_id}\t#{window_index}\t#{window_name}\t#{window_active}\t"
           "#{pane_id}\t#{pane_index}\t#{pane_current_command}\t#{pane_active}\t#{session_activity}\t"
           "#{pane_left}\t#{pane_top}\t#{pane_width}\t#{pane_height}\t#{window_activity}")
    sessions = {}
    for line in tm("list-panes", "-a", "-F", fmt).splitlines():
        fields = line.split("\t")
        if len(fields) != 18 or (workspace is not None and fields[3] != workspace):
            continue
        sid, name, attached, group, window, number, title, active, pane, index, command, selected, activity, left, top, width, height, window_activity = fields
        session = sessions.setdefault(sid, {"id": sid, "name": name, "attached": int(attached),
                                           "activity": int(activity or "0"), "workspace": group, "windows": {}})
        win = session["windows"].setdefault(window, {"id": window, "index": int(number), "name": title,
                                                  "active": active == "1", "activity": int(window_activity or "0"), "panes": {}})
        win["panes"][pane] = {"id": pane, "index": int(index), "command": command, "active": selected == "1", "left": int(left), "top": int(top),
                                  "width": int(width), "height": int(height)}
    return sessions


def tree_rows(sessions, expanded, order="index", reverse=False, session_order=()):
    sort = {"index": lambda s: (session_order.index(s["name"]) if s["name"] in session_order else len(session_order), int(s["id"][1:])), "name": lambda s: s["name"].lower(),
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
        self.expanded, self.tags = set(), set()
        actual = tm("display-message", "-p", "-t", args.pane, "#{session_id}\t#{session_name}\t#{@workspace-id}\t#{@workspace-return}\t#{prefix}").split("\t")
        self.selected = "session:" + actual[0] if len(actual) == 5 and actual[2] == self.workspace else ""
        self.return_workspace = actual[3] or "general"
        self.index, self.offset = 0, 0
        self.rows, self.sessions, self.all_rows = [], {}, []
        self.notice, self.search, self.order, self.reverse = "", "", "index", False
        self.pending = None
        self.selection_style = curses.A_REVERSE
        self.data = json.loads(self.state.read_text())
        self.preferred_name = self.data.get("history", {}).get(self.workspace, {}).get("current")
        self.preview, self.last_preview = [], None
        self.preview_at, self.refresh_at = 0, 0
        from picker_preview import Preview
        self.renderer = Preview()
        self.preview_offset = 0
        self.filter = ""
        self.start_pane = args.pane
        self.prefix_key = {"C-a": "\x01", "C-b": "\x02"}.get(actual[4], "\x01")

    @property
    def notice(self):
        return self._notice if time.monotonic() < self._toast_until else ''

    @notice.setter
    def notice(self, value):
        self._notice, self._toast_until = value, time.monotonic() + 4

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
        self.rows = tree_rows(self.sessions, self.expanded, self.order, self.reverse,
                              self.data.get("session_order", {}).get(self.workspace, []))
        if not self.selected and self.preferred_name:
            preferred = next((r for r in self.rows if r["kind"] == "session" and r["name"] == self.preferred_name), None)
            if preferred: self.selected = preferred["key"]
        if self.filter:
            filtered = [r for r in self.rows if tm("display-message", "-p", "-t", r["target"], self.filter) not in ("", "0")]
            if filtered: self.rows = filtered
            else: self.notice = "Filter has no matches; showing all items"
        found = next((i for i, row in enumerate(self.rows) if row["key"] == self.selected), None)
        self.index = found if found is not None else min(self.index, max(0, len(self.rows) - 1))
        self.selected = self.rows[self.index]["key"] if self.rows else ""
        expanded = {"session:" + sid for sid in self.sessions}
        expanded.update("window:" + sid + ":" + wid for sid, session in self.sessions.items() for wid in session["windows"])
        self.all_rows = tree_rows(self.sessions, expanded, self.order, self.reverse,
                                  self.data.get("session_order", {}).get(self.workspace, []))
        self.tags.intersection_update(row["key"] for row in self.all_rows)
        self.refresh_at = time.monotonic() + .5

    def row(self):
        return self.rows[self.index] if self.rows else None

    def selection_rows(self, row=None):
        if self.tags:
            return [item for item in self.all_rows if item['key'] in self.tags]
        row = row or self.row()
        return [row] if row else []

    def selection_sessions(self, row=None):
        return list(dict.fromkeys(item['session'] for item in self.selection_rows(row)))

    def move_selection(self, screen):
        ids = self.selection_sessions()
        if not ids: return
        target = self.choose_workspace(screen)
        if target and self.command('assign-many', name=json.dumps(ids), destination=target):
            self.change_workspace(target)
            self.selected = 'session:' + ids[0]
            self.refresh()
            self.notice = f'Moved {len(ids)} session(s)'

    def present(self, screen, accent):
        if self.first_paint:
            area = self.render(screen, accent)
            self.first_paint()
            self.first_paint = None
            tm('set-option', '-p', '-t', self.args.pane, '@workspace-picker-pid', str(os.getpid()))
            return area
        return self.render(screen, accent)

    def move_windows(self, screen):
        pairs = []
        for row in self.selection_rows():
            session = self.sessions[row['session']]
            if row['kind'] == 'window': wid = row['id']
            elif row['kind'] == 'pane': wid = next(wid for wid, win in session['windows'].items() if row['id'] in win['panes'])
            else: wid = next(wid for wid, win in session['windows'].items() if win['active'])
            if (row['session'], wid) not in pairs: pairs.append((row['session'], wid))
        sessions = fetch_sessions(None)
        owners = {sid for sid, wid in pairs}
        entries = [('', path_name(self.data, session['workspace']) + ' / ' + session['name'], sid)
                   for sid, session in sessions.items() if session['workspace'] in self.data['workspaces'] and not (len(owners) == 1 and sid in owners)]
        if not entries:
            self.notice = 'Create another session first to move windows into it'
            return
        target = choose_action(screen, f'Move {len(pairs)} window(s) to session · i/a search', entries)
        if target and self.command('move-windows', name=json.dumps(pairs), destination=target):
            self.data = json.loads(self.state.read_text())
            self.command('view-context', workspace=sessions[target]['workspace'], destination=self.return_workspace)
            self.change_workspace(sessions[target]['workspace'])
            self.expanded.add('session:' + target)
            self.selected = 'window:' + target + ':' + pairs[0][1]
            self.tags.clear()
            self.refresh()
            self.notice = f'Moved {len(pairs)} window(s) · source sessions kept open'
            tm('set-option', '-p', '-t', self.args.pane, '@workspace-picker-pid', str(os.getpid()))

    def archive_selection(self, screen):
        ids = self.selection_sessions()
        if not ids: return
        if self.workspace != 'archived':
            if self.command('assign-many', name=json.dumps(ids), destination='archived'):
                self.tags.clear()
                self.notice = f'Archived {len(ids)} session(s) · Ctrl+R opens Archive'
            return
        names = [self.sessions[sid]['name'] for sid in ids]
        missing = [name for name in names if self.data['origins'].get(name) not in self.data['workspaces']
                   or self.data['origins'].get(name) == 'archived']
        destination = ''
        if missing:
            destination = self.box(screen, f'Restore {len(missing)} session(s) · existing workspace or new path')
            if not destination: return
        if self.command('restore-many', name=json.dumps(ids), destination=destination):
            self.data = json.loads(self.state.read_text())
            self.change_workspace(self.data['sessions'][names[0]])
            self.selected = 'session:' + ids[0]
            self.refresh()
            self.notice = f'Restored {len(ids)} session(s) to their workspace(s)'

    def rename_selection(self, screen):
        ids = self.selection_sessions()
        pairs = []
        for index, sid in enumerate(ids):
            title = 'Rename session' if len(ids) == 1 else f'Rename session {index + 1} / {len(ids)}'
            name = self.box(screen, title, self.sessions[sid]['name'])
            if not name: return
            pairs.append([sid, name])
        if pairs: self.command('rename-many', name=json.dumps(pairs))

    def delete_selection(self, screen):
        self.delete(screen, [(item['kind'], item['id']) for item in self.selection_rows()])

    def change_workspace(self, wid):
        if wid not in self.data["workspaces"]:
            return
        if wid == "archived" and self.workspace != "archived":
            self.return_workspace = self.workspace
        self.workspace, self.selected, self.index, self.offset = wid, "", 0, 0
        self.preferred_name = self.data.get("history", {}).get(wid, {}).get("current")
        self.expanded.clear()
        self.preview_offset = 0
        self.tags.clear()
        self.command("view-context", workspace=wid, destination=self.return_workspace)
        self.refresh()

    def box(self, screen, title, initial="", confirm=False, allow_empty=False):
        return input_dialog(screen, title, initial, confirm, allow_empty)

    def choose_workspace(self, screen):
        nodes = []
        def walk(parent):
            for wid in children(self.data, parent):
                nodes.append(wid); walk(wid)
        walk(None)
        entries = [('', path_name(self.data, wid), wid) for wid in nodes]
        index = nodes.index(self.workspace) if self.workspace in nodes else 0
        return choose_action(screen, f'Move {len(self.selection_sessions())} session(s) to workspace', entries, index)

    def workspace_list(self, screen):
        from workspace_ui import workspace_list
        args = argparse.Namespace(client=self.args.client, pane=self.args.pane, workspace=self.workspace)
        chosen = workspace_list(args, self.state, screen=screen)
        screen.touchwin()
        self.data = json.loads(self.state.read_text())
        destination = chosen or (self.workspace if self.workspace in self.data['workspaces'] else args.workspace)
        if destination != self.workspace: self.change_workspace(destination)
        else: self.command('view-context', workspace=self.workspace, destination=self.return_workspace)
        self.refresh_at = 0

    def edit_workspace(self, screen, kind):
        node = self.data['workspaces'][self.workspace]
        if kind == 'rename' and self.workspace in SYSTEM:
            self.notice = 'This workspace is protected'; return
        if kind == 'child' and self.workspace == 'archived':
            self.notice = 'Archive is shared and cannot have children'; return
        initial = node['name'] if kind == 'rename' else ''
        if kind == 'shortcut':
            if self.workspace == 'archived':
                self.notice = 'Archive is fixed at F12'; return
            initial = next((shortcut_label(n) for n, wid in shortcut_map(self.data, node['parent']).items() if wid == self.workspace), '')
        title = {'rename': 'Rename workspace', 'create': 'Create sibling workspace',
                 'child': 'Create nested workspace', 'shortcut': 'Workspace shortcut · 1–0 or F1–F12'}[kind]
        name = self.box(screen, title, initial)
        if not name: return
        parent = self.workspace if kind == 'child' else node['parent']
        if self.command('apply-name', workspace=self.workspace, kind=kind, name=name):
            self.data = json.loads(self.state.read_text())
            target = self.workspace
            if kind in ('create', 'child'):
                target = next(wid for wid, node in self.data['workspaces'].items() if node['name'] == name and node['parent'] == parent)
            if target != self.workspace: self.change_workspace(target)
            else: self.command('view-context', workspace=target, destination=self.return_workspace)

    def actions(self, screen, accent):
        count = len(self.selection_sessions())
        scope = f'{count} tagged session(s)' if self.tags else 'selected session'
        entries = [('S', 'Return to sessions', 'sessions'), ('s', 'List workspaces', 'list'),
                   ('?', 'All keys / help', 'help'), ('C-r', 'Archive / return workspace', 'archive-view'),
                   ('H', 'Previous workspace', 'previous'), ('L', 'Next workspace', 'next'),
                   ('c', 'Create sibling workspace…', 'create'), ('C', 'Create nested workspace…', 'child'),
                   ('r', 'Rename workspace…', 'rename'), ('p', 'Change workspace shortcut…', 'shortcut'),
                   ('M', 'Move workspace into…', 'move-folder'), ('d', 'Delete workspace; archive its sessions…', 'delete-folder'),
                   ('n', 'Create session here…', 'new-session'), ('m', 'Move ' + scope + ' into…', 'move-session'),
                   ('', 'Rename ' + scope + '…', 'rename-session'), ('z', 'Archive / restore ' + scope, 'archive-session'),
                   ('x', 'Delete tagged / selected items…', 'delete-selection'),
                   ('E', 'Delete ALL sessions; keep workspace…', 'empty')]
        if self.workspace == 'archived': entries.append(('D', 'Permanently empty Archive…', 'purge'))
        parent = self.data['workspaces'][self.workspace]['parent']
        if parent: entries.append(('[', 'Open parent workspace', 'open:' + parent))
        entries.extend((str(n + 1) if n < 9 else '', 'Open child: ' + self.data['workspaces'][wid]['name'], 'open:' + wid)
                       for n, wid in enumerate(children(self.data, self.workspace)))
        while True:
            selected = choose_action(screen, path_name(self.data, self.workspace) + ' · Actions', entries)
            if selected in (None, 'sessions'): return
            if selected == 'help': self.help(screen, accent); continue
            row = self.row()
            if selected == 'list': self.workspace_list(screen)
            elif selected in ('create', 'child', 'rename', 'shortcut'): self.edit_workspace(screen, selected)
            elif selected.startswith('open:'): self.change_workspace(selected[5:])
            elif selected in ('previous', 'next'):
                peers = children(self.data, parent)
                self.change_workspace(peers[(peers.index(self.workspace) + (1 if selected == 'next' else -1)) % len(peers)])
            elif selected == 'archive-view':
                target = self.return_workspace if self.workspace == 'archived' else 'archived'
                self.change_workspace(target if target in self.data['workspaces'] else 'general')
            elif selected == 'move-folder':
                if self.workspace in SYSTEM: self.notice = 'This workspace is protected'; return
                candidates = [("0", 'Top level', 'top')]
                candidates.extend(('', path_name(self.data, wid), wid) for wid in self.data['workspaces']
                                  if wid != 'archived' and not descendant(self.data, wid, self.workspace))
                target = choose_action(screen, 'Move workspace into', candidates)
                if target: self.command('move-workspace', workspace=self.workspace, destination=target)
            elif selected == 'delete-folder':
                if self.workspace in SYSTEM: self.notice = 'This workspace is protected'; return
                if children(self.data, self.workspace): self.notice = 'Delete child workspaces first; each deletion asks for confirmation'; return
                token = deletion_token(self.data, self.workspace)
                target = parent or 'general'
                if self.box(screen, f"Delete {path_name(self.data, self.workspace)}? Keep its sessions running in Archive?", confirm=True):
                    if self.command('delete', workspace=self.workspace, token=token):
                        self.data = json.loads(self.state.read_text()); self.change_workspace(target)
            elif selected == 'new-session':
                name = self.box(screen, 'New session')
                if name: self.command('apply-name', workspace=self.workspace, kind='session', name=name)
            elif selected == 'rename-session' and row: self.rename_selection(screen)
            elif selected == 'move-session' and row: self.move_selection(screen)
            elif selected == 'archive-session' and row: self.archive_selection(screen)
            elif selected == 'delete-selection' and row: self.delete_selection(screen)
            elif selected in ('empty', 'purge'): curses.unget_wch('E' if selected == 'empty' else 'D')
            self.refresh_at = 0
            return

    def fuzzy_search(self, screen):
        sessions = fetch_sessions(None)
        expanded = {'session:' + sid for sid in sessions}
        expanded.update('window:' + sid + ':' + wid for sid, session in sessions.items() for wid in session['windows'])
        candidates = []
        for row in tree_rows(sessions, expanded):
            session = sessions[row['session']]
            wid = session['workspace']
            if wid not in self.data['workspaces']: continue
            label = path_name(self.data, wid) + ' / ' + session['name']
            if row['kind'] != 'session': label += ' / ' + row['label'].strip()
            candidates.append((label, wid, row))
        for wid in self.data['workspaces']:
            candidates.append(('Workspace / ' + path_name(self.data, wid), wid, None))
        mode, index, chosen = SearchMode(insert=True), 0, None
        try:
            while True:
                matches = ranked(candidates, mode.query, lambda item: item[0])
                window = overlay(screen, 'Find · sessions / windows / panes / workspaces', 108, min(25, len(candidates) + 8))
                height, width = window.getmaxyx()
                visible = max(1, height - 7)
                index = min(index, max(0, len(matches) - 1))
                start = max(0, min(index - visible // 2, len(matches) - visible))
                for y, item in enumerate(matches[start:start + visible], 5):
                    paint_row(window, y, 2, item[0], width - 4, start + y - 5 == index)
                search_prompt(window, mode, len(matches), len(candidates), 'Enter highlights')
                window.refresh()
                try: key = read_key(window, allow_alt=False)
                except curses.error: continue
                action = mode.key(key)
                if action == 'close': return
                if action == 'accept' and matches:
                    chosen = matches[index]; break
                if action == 'query': index = 0
                else: index = navigate(index, action, len(matches), visible)
        finally:
            curses.curs_set(0); screen.touchwin()
        if chosen:
            label, wid, row = chosen
            self.search = mode.query
            if wid != self.workspace: self.change_workspace(wid)
            if row:
                if row['kind'] != 'session': self.expanded.add('session:' + row['session'])
                if row['kind'] == 'pane': self.expanded.add(row['parent'])
                self.selected = row['key']
            self.refresh()

    def help(self, screen, accent):
        offset, mode = 0, SearchMode()
        try:
            while True:
                entries = ranked(GUIDE, mode.query, lambda entry: ' '.join(entry))
                window = overlay(screen, 'Session picker · all keys', 118, len(GUIDE) // 2 + 8, accent)
                height, width = window.getmaxyx()
                count = max(1, height - 7)
                offset = min(offset, max(0, (len(entries) + 1) // 2 - count))
                guide_columns(window, 5, count, entries[offset * 2:], accent)
                search_prompt(window, mode, len(entries), len(GUIDE), '? returns')
                window.refresh()
                try: key = read_key(window, allow_alt=False)
                except curses.error: continue
                if not mode.insert and key in ('?', 'q'): return
                action = mode.key(key)
                if action == 'close': return
                if action == 'query': offset = 0
                elif action in ('down', 'page-down'): offset += count if action == 'page-down' else 1
                elif action in ('up', 'page-up'): offset = max(0, offset - (count if action == 'page-up' else 1))
                elif action == 'first': offset = 0
                elif action == 'last': offset = max(0, (len(entries) + 1) // 2 - count)
        finally:
            curses.curs_set(0); screen.touchwin()

    def context_menu(self, screen, accent, preview=False):
        entries = [('Previous preview', '<'), ('Next preview', '>')] if preview else [
            ('Open selected item', '\r'), ('Expand / next', 'l'), ('Move window to session', '.'),
            ('Toggle tag', 't'), ('Tag all', '\x14'), ('Clear tags', 'T'),
            ('Delete tagged / selected · confirm', 'x')]
        chosen = choose_action(screen, 'Actions', [('', label, key) for label, key in entries])
        if chosen is not None: curses.unget_wch(chosen)

    def draw_preview(self, screen, area, accent):
        row = self.row()
        width = screen.getmaxyx()[1]
        if not row:
            preview_separator(screen, area.preview_top, '● Empty workspace ●', accent)
            return
        session = self.sessions[row["session"]]
        windows = sorted(session["windows"].values(), key=lambda win: win["index"])
        window = next((win for win in windows if win["active"]), windows[0]) if row["kind"] == "session" else next(win for win in windows if row["preview"] in win["panes"])
        if row["kind"] == "session": window = windows[(windows.index(window) + self.preview_offset) % len(windows)]
        panes = sorted(window["panes"].values(), key=lambda p: p["index"])
        if row["kind"] == "pane": panes = [next(p for p in panes if p["id"] == row["id"])]
        elif row["kind"] == "window" and self.preview_offset:
            active = next((i for i, p in enumerate(panes) if p["active"]), 0)
            panes = [panes[(active + self.preview_offset) % len(panes)]]
        preview_separator(screen, area.preview_top, preview_title(session, window), accent)
        y, x, height, columns = area.preview_top + 1, 1, area.preview_height - 1, width - 2
        refresh = time.monotonic() >= self.preview_at
        for pane, py, px, ph, pw in pane_regions(panes, y, x, height, columns):
            if len(panes) > 1 and pane["left"]:
                for yy in range(py, py + ph): put(screen, yy, px - 1, "│", accent)
            if len(panes) > 1 and pane["top"]:
                put(screen, py - 1, px, "─" * pw, accent, pw)
            try: self.renderer.pane(screen, pane["id"], py, px, ph, pw, refresh)
            except (subprocess.CalledProcessError, ValueError): pass
        if refresh: self.preview_at = time.monotonic() + .35

    def render(self, screen, accent=0, refresh=True):
        height, width = screen.getmaxyx()
        prefs = self.data["preferences"]
        badges = badge_lines(self.data, self.workspace, width)
        max_rows = max(1, (height // 5 + 1) // 2)
        active_line = next((i for i, line in enumerate(badges) if any(wid == self.workspace for wid, label in line)), 0)
        first = max(0, active_line - max_rows + 1)
        badges = badges[first:first + max_rows]
        message = self.notice or (f'{len(self.tags)} tagged · m move · x delete · w actions · T clear' if self.tags else '')
        area = layout(height - bool(message), False, prefs["preview"], max(1, len(badges) * 2 - 1))
        screen.erase()
        self.badge_hits = []
        for line_index, line in enumerate(badges):
            y = area.title + line_index * 2
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
                paint_row(screen, area.list_top + index - self.offset, 1, label, width - 2, index == self.index, accent)
            if len(self.rows) > area.list_height:
                thumb = max(1, area.list_height * area.list_height // len(self.rows))
                start = self.offset * (area.list_height - thumb) // max(1, len(self.rows) - area.list_height)
                for position in range(area.list_height):
                    put(screen, area.list_top + position, width - 2, "┃" if start <= position < start + thumb else "│", accent)
        if area.preview_top is not None: self.draw_preview(screen, area, accent)
        if message: toast(screen, message)
        if refresh: screen.refresh()
        return area

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
        screen.clearok(False)
        screen.idlok(False)
        theme.apply(self.args.pane, force=True)
        self.selection_style, self.badge_style, self.badge_edge = theme.SELECTION, theme.BADGE, theme.EDGE
        accent = theme.ACCENT
        screen.bkgd(" ", theme.TEXT)
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        prefix = False
        while True:
            if time.monotonic() >= self.refresh_at:
                requested, menu_requested = tm("display-message", "-p", "-t", self.args.pane, "#{@workspace-picker-jump}\t#{@workspace-picker-menu}").split("\t")
                if requested:
                    tm("set-option", "-pu", "-t", self.args.pane, "@workspace-picker-jump")
                    self.change_workspace(requested)
                self.refresh()
                if theme.apply(self.args.pane):
                    self.selection_style, self.badge_style, self.badge_edge = theme.SELECTION, theme.BADGE, theme.EDGE
                    accent = theme.ACCENT
                    screen.bkgd(" ", theme.TEXT)
                if menu_requested:
                    tm("set-option", "-pu", "-t", self.args.pane, "@workspace-picker-menu")
                    self.present(screen, accent)
                    self.actions(screen, accent)
            area = self.present(screen, accent)
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
                if key == "W":
                    self.actions(screen, accent); continue
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
            elif key == "v":
                self.command("toggle-preview")
            elif key in ("J", "K") and row:
                if self.command("reorder-session", workspace=self.workspace, name=json.dumps(self.selection_sessions()), direction="down" if key == "J" else "up"):
                    self.order, self.reverse = "index", False
                    self.refresh()
                    continue
            elif key == "s":
                self.workspace_list(screen)
                continue
            elif key == "?":
                self.help(screen, accent)
            elif key == "w":
                self.actions(screen, accent)
                continue
            elif key == "z" and row:
                self.archive_selection(screen)
                continue
            elif key == "m" and row:
                self.move_selection(screen)
                continue
            elif key == "r" and row:
                self.rename_selection(screen)
            elif key == "c" or (key == "n" and not self.rows):
                name = self.box(screen, "New session")
                if name: self.command("apply-name", kind="session", workspace=self.workspace, name=name)
            elif key in ("\x13", "/", "i", "a"):
                self.fuzzy_search(screen)
            elif key == "n" and self.search:
                found = next((i for i in list(range(self.index + 1, len(self.rows))) + list(range(self.index + 1))
                              if fuzzy_score(self.search, self.rows[i]["label"]) is not None), None)
                if found is not None: self.index = found
            elif key == "t" and row:
                if row["key"] in self.tags: self.tags.remove(row["key"])
                else:
                    parents = {item['key']: item['parent'] for item in self.all_rows}
                    def ancestors(key):
                        result = set()
                        while parents.get(key):
                            key = parents[key]; result.add(key)
                        return result
                    self.tags.difference_update(key for key in list(self.tags)
                                                if key in ancestors(row['key']) or row['key'] in ancestors(key))
                    self.tags.add(row["key"])
            elif key == "T": self.tags.clear()
            elif key == "\x14": self.tags = {row["key"] for row in self.rows if row["kind"] == "session"}
            elif key in ("x", "X") and (self.tags or row): self.delete_selection(screen)
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
                    targets = [r["target"] for r in self.selection_rows(row)]
                    for target in targets:
                        self.command("item-command", target=target, name=template)
                    self.refresh_at = 0
            elif key == "." and row:
                self.move_windows(screen)
                continue
            elif alt and value == "H":
                start = next((r for r in self.rows if r["preview"] == self.start_pane), None)
                if start: self.index = self.rows.index(start)
            elif key in ("<", ">"):
                self.preview_offset += -1 if key == "<" else 1
                self.preview_at = 0
            elif key == "O":
                self.order = {"index": "name", "name": "activity", "activity": "index"}[self.order]
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
    from picker_startup import FirstPaint
    picker = Picker(args, state)
    try:
        with FirstPaint() as paint:
            picker.first_paint = paint.release
            curses.wrapper(picker.run)
    except Exception:
        import traceback
        with Path(state).with_suffix(".log").open("a") as log:
            traceback.print_exc(file=log)
        raise
    finally:
        picker.command("close-picker")
    if picker.pending:
        action, values = picker.pending
        subprocess.run(["tmux", "run-shell", "-b", "-d", "0.1",
                        shell_command(action, args.client, client_pane(args.client) or args.pane, **values)], check=True)
