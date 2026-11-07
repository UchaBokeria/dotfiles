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
                        path_name, shell_command, shortcut_map, snapshot_token, tm)

HELPER = Path(__file__).with_name("workspaces.py")
GUIDE = [
    ("j/k  ↑/↓", "Select item"), ("Enter", "Open selected item"),
    ("h/l  ←/→", "Collapse / expand"), ("s", "List workspaces"),
    ("H/L  Tab", "Previous / next workspace"), ("1–0  F1–F12", "Workspace; Alt: nested"),
    ("z", "Archive / restore session"), ("Ctrl+R", "Toggle shared Archive"),
    ("m", "Move session to workspace"), ("c / n", "New session (n when empty)"),
    ("w / R", "Actions / rename session"), ("x / X", "Delete item / tagged"),
    ("t / T", "Tag item / clear tags"), ("Ctrl+S", "Search; n repeats search"),
    ("v / b", "Toggle preview / guide"), ("q / Esc", "Close picker · ? help"),
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


def layout(height, keys=True, preview=True):
    """Guide ends at the preview boundary, or the bottom edge without preview."""
    top = 4 if height >= 20 else 3
    available = max(1, height - top)
    desired_preview = min(10, max(4, height // 3)) if preview else 0
    keys_height = min(10, max(3, available - 3)) if keys else 0
    if preview and keys and available < 17:
        keys_height = min(keys_height, max(3, available - desired_preview - 3))
    preview_height = min(desired_preview, max(0, available - keys_height - 3))
    if preview_height < 3:
        preview_height = 0
    list_height = max(1, available - keys_height - preview_height)
    keys_top = top + list_height if keys_height else None
    preview_top = height - preview_height if preview_height else None
    return Layout(1 if top == 4 else 0, top, list_height, keys_top, keys_height,
                  preview_top, preview_height)


def clean(value):
    return "".join(char if char.isprintable() else " " for char in str(value))


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


def panel(screen, area, accent=0):
    if area.keys_top is None:
        return
    width = screen.getmaxyx()[1]
    put(screen, area.keys_top, 1, "─" * max(0, width - 2), accent)
    heading = " Shortcuts · b hides · ? full help "
    put(screen, area.keys_top, max(1, (width - len(heading)) // 2), heading, accent)
    columns = max(1, (width - 4) // 2)
    rows = max(1, area.keys_height - 2)
    for index, (key, description) in enumerate(GUIDE):
        column, row = index % 2, index // 2
        if row >= rows:
            break
        label = f"{key:<{12 if width < 100 else 15}} {description}"
        put(screen, area.keys_top + 1 + row, 2 + column * (columns + 1), label, width=columns)
        put(screen, area.keys_top + 1 + row, width // 2, "│", accent | curses.A_DIM)
    if area.preview_top is None:
        put(screen, area.keys_top + area.keys_height - 1, 1, "─" * max(0, width - 2), accent)


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
           "#{pane_id}\t#{pane_index}\t#{pane_current_command}\t#{pane_active}\t#{session_activity}")
    sessions = {}
    for line in tm("list-panes", "-a", "-F", fmt).splitlines():
        fields = line.split("\t")
        if len(fields) != 13 or fields[3] != workspace:
            continue
        sid, name, attached, group, window, number, title, active, pane, index, command, selected, activity = fields
        session = sessions.setdefault(sid, {"id": sid, "name": name, "attached": int(attached),
                                           "activity": int(activity or "0"), "windows": {}})
        win = session["windows"].setdefault(window, {"id": window, "index": int(number), "name": title,
                                                  "active": active == "1", "panes": {}})
        win["panes"][pane] = {"id": pane, "index": int(index), "command": command, "active": selected == "1"}
    return sessions


def tree_rows(sessions, expanded, order="index", reverse=False):
    sort = {"index": lambda s: int(s["id"][1:]), "name": lambda s: s["name"].lower(),
            "activity": lambda s: s["activity"]}[order]
    result = []
    for session in sorted(sessions.values(), key=sort, reverse=reverse):
        sid = session["id"]
        windows = sorted(session["windows"].values(), key=lambda w: w["index"])
        active = next((window for window in windows if window["active"]), windows[0])
        pane = next((pane for pane in active["panes"].values() if pane["active"]), next(iter(active["panes"].values())))
        key = "session:" + sid
        label = ("− " if key in expanded else "+ ") + session["name"] + f": {len(windows)} windows"
        if session["attached"]:
            label += " (attached)"
        result.append({"key": key, "kind": "session", "id": sid, "session": sid, "name": session["name"],
                       "label": label, "target": sid, "preview": pane["id"], "parent": None})
        if key not in expanded:
            continue
        for window in windows:
            wid = window["id"]
            key = "window:" + sid + ":" + wid
            panes = sorted(window["panes"].values(), key=lambda p: p["index"])
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
        self.tags.clear()
        self.command("view-context", workspace=wid, destination=self.return_workspace)
        self.refresh()

    def box(self, screen, title, initial="", confirm=False):
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
                    return value.strip() or None
                if key in ("\x7f", "\b", curses.KEY_BACKSPACE):
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
                nodes.append((wid, depth))
                walk(wid, depth + 1)
        walk(None, 0)
        index = next((i for i, row in enumerate(nodes) if row[0] == self.workspace), 0)
        while True:
            height, width = screen.getmaxyx()
            screen.erase()
            put(screen, 1, 2, "Move session to workspace · j/k + Enter · Esc cancels", curses.A_BOLD)
            start = max(0, index - max(1, height - 5) // 2)
            for y, (wid, depth) in enumerate(nodes[start:start + max(1, height - 4)], 3):
                put(screen, y, 2, "  " * depth + self.data["workspaces"][wid]["name"], curses.A_REVERSE if start + y - 3 == index else 0)
            screen.refresh()
            try:
                key = read_key(screen)
            except curses.error:
                continue
            if key == "\x1b":
                return None
            if key in ("j", curses.KEY_DOWN): index = min(len(nodes) - 1, index + 1)
            elif key in ("k", curses.KEY_UP): index = max(0, index - 1)
            elif key in ("\r", "\n", curses.KEY_ENTER): return nodes[index][0]

    def render(self, screen, accent=0):
        height, width = screen.getmaxyx()
        prefs = self.data["preferences"]
        area = layout(height, prefs["keys"], prefs["preview"])
        screen.erase()
        title = path_name(self.data, self.workspace)
        if len(title) > max(1, width - 4):
            title = "…" + title[-max(1, width - 5):]
        put(screen, area.title, max(0, (width - len(title)) // 2), title, accent | curses.A_BOLD)
        if self.notice:
            put(screen, area.title + 1, 2, self.notice, accent, width - 4)
        if not self.rows:
            text = "No sessions · n creates a session · w opens workspace actions"
            put(screen, area.list_top + min(1, area.list_height - 1), max(1, (width - len(text)) // 2), text)
        else:
            self.offset = min(self.offset, self.index)
            self.offset = max(self.offset, self.index - area.list_height + 1)
            for index in range(self.offset, min(len(self.rows), self.offset + area.list_height)):
                row = self.rows[index]
                marker = "* " if row["key"] in self.tags else "  "
                label = f"({index}) " + marker + row["label"]
                put(screen, area.list_top + index - self.offset, 1, label.ljust(max(1, width - 2)),
                    self.selection_style if index == self.index else 0, width - 2)
        panel(screen, area, accent)
        if area.preview_top is not None:
            row = self.row()
            caption = " Preview " + (row["label"].strip() if row else "") + " "
            put(screen, area.preview_top, 1, "─" * max(0, width - 2), accent)
            put(screen, area.preview_top, 2, caption, accent, width - 4)
            pane = row["preview"] if row else None
            if pane != self.last_preview or time.monotonic() >= self.preview_at:
                try:
                    self.preview = tm("capture-pane", "-p", "-t", pane).splitlines() if pane else []
                except subprocess.CalledProcessError:
                    self.preview = []
                self.last_preview, self.preview_at = pane, time.monotonic() + .5
            for index, line in enumerate(self.preview[:max(0, area.preview_height - 1)]):
                put(screen, area.preview_top + 1 + index, 2, line, width=width - 4)
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
            accent = curses.color_pair(1)
            self.selection_style = curses.color_pair(2) | curses.A_BOLD
            curses.mousemask(curses.ALL_MOUSE_EVENTS)
        except curses.error:
            accent = curses.A_BOLD
        tm("set-option", "-p", "-t", self.args.pane, "@workspace-picker-pid", str(os.getpid()))
        prefix = False
        while True:
            if time.monotonic() >= self.refresh_at:
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
            if prefix:
                prefix = False
                if key == curses.KEY_BTAB:
                    self.queue("last-local")
                    return
                if alt and value == "\t":
                    self.queue("last-global")
                    return
                if key == "s":
                    continue
            if key in ("\x01", "\x02"):
                prefix = True
                continue
            if key in ("q", "\x1b", "\x07", "\x03"):
                return
            if number:
                destination = shortcut_map(self.data, self.workspace if alt else None).get(number)
                if destination:
                    self.change_workspace(destination)
                continue
            if key in ("j", curses.KEY_DOWN): self.index = min(max(0, len(self.rows) - 1), self.index + 1)
            elif key in ("k", curses.KEY_UP): self.index = max(0, self.index - 1)
            elif key in ("g", curses.KEY_HOME): self.index = 0
            elif key in ("G", curses.KEY_END): self.index = max(0, len(self.rows) - 1)
            elif key in (curses.KEY_NPAGE, "\x06"): self.index = min(max(0, len(self.rows) - 1), self.index + area.list_height)
            elif key in (curses.KEY_PPAGE, "\x15"): self.index = max(0, self.index - area.list_height)
            elif key in ("h", "-", curses.KEY_LEFT) and row:
                if row["key"] in self.expanded:
                    self.expanded.remove(row["key"])
                elif row["parent"]:
                    self.selected = row["parent"]
                self.refresh_at = 0
            elif key in ("l", "+", curses.KEY_RIGHT) and row and row["kind"] != "pane":
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
                self.data = json.loads(self.state.read_text())
                destination = chosen or (self.workspace if self.workspace in self.data["workspaces"] else args.workspace)
                if destination != self.workspace:
                    self.change_workspace(destination)
                else:
                    self.command("view-context", workspace=self.workspace, destination=self.return_workspace)
                self.refresh_at = 0
            elif key in ("w", "?"):
                self.queue({"s": "workspaces", "w": "menu", "?": "help"}[key], workspace=self.workspace,
                           session=row["session"] if row else "")
                return
            elif key == "z" and row:
                self.archive(screen, row)
            elif key == "u" and row and self.workspace == "archived":
                self.archive(screen, row)
            elif key == "m" and row:
                target = self.choose_workspace(screen)
                if target and self.command("assign", session=row["session"], destination=target):
                    self.change_workspace(target)
            elif key in ("c", "R") or (key == "n" and not self.search):
                if key == "R" and not row:
                    continue
                name = self.box(screen, "New session name" if key != "R" else "Rename selected session")
                if name:
                    self.command("apply-name", kind="session-rename" if key == "R" else "session",
                                 workspace=self.workspace, session=row["session"] if row else "", name=name)
            elif key == "\x13" or (key == "n" and self.search):
                if key == "\x13":
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
            elif key == "O":
                self.order = {"index": "name", "name": "activity", "activity": "index"}[self.order]
                self.refresh_at = 0
            elif key == "r":
                self.reverse = not self.reverse
                self.refresh_at = 0
            elif key == curses.KEY_MOUSE:
                try:
                    _, x, y, _, buttons = curses.getmouse()
                    if buttons & curses.BUTTON4_PRESSED: self.index = max(0, self.index - 1)
                    elif buttons & getattr(curses, "BUTTON5_PRESSED", 0): self.index = min(max(0, len(self.rows) - 1), self.index + 1)
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
