#!/usr/bin/env python3
"""Persistent workspace folders around tmux's native session tree."""
import argparse
from contextlib import contextmanager
import fcntl
from functools import cache
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve()
SYSTEM = {"general", "archived", "background"}


def tm(*args):
    return subprocess.check_output(["tmux", *map(str, args)], text=True).rstrip("\n")


def command_queue(commands):
    """One tmux request lets the server coalesce related redraws."""
    return [item for index, command in enumerate(commands)
            for item in (([";"] if index else []) + list(command))]


def launch(*args):
    # Native menus/popups wait for user input. Never hold the state lock then.
    log = state_path().with_suffix(".log")
    with log.open("a") as errors:
        subprocess.Popen(["tmux", *map(str, args)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=errors)


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


def shell_command(action, client="", pane="", **values):
    args = [str(HERE), action, "--client", client, "--pane", pane]
    for key, value in values.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    # Carry isolated state paths through tmux's server environment in tests.
    env = os.environ.get("TMUX_WORKSPACES_STATE")
    return (("TMUX_WORKSPACES_STATE=" + shlex.quote(env) + " ") if env else "") + shlex.join(args)


def callback(action, client="", pane="", **values):
    return "run-shell -b " + quote(shell_command(action, client, pane, **values))


@cache
def state_path():
    override = os.environ.get("TMUX_WORKSPACES_STATE")
    if override:
        return Path(override).absolute()
    socket = os.environ.get("TMUX", "").rsplit(",", 2)[0] or tm("display-message", "-p", "#{socket_path}")
    suffix = "" if Path(socket).name == "default" else "-" + hashlib.sha256(socket.encode()).hexdigest()[:12]
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "tmux" / ("workspaces" + suffix + ".json")


def session_rows(labels=False):
    fmt = "#{session_id}\t#{session_name}\t#{@workspace-id}\t#{@session-picker-hidden}"
    if labels: fmt += "\t#{@workspace-label}"
    return [row.split("\t") for row in tm("list-sessions", "-F", fmt).splitlines()]


def server_identity():
    context = os.environ.get("TMUX", "").rsplit(",", 2)
    pid = context[1] if len(context) == 3 and context[1].isdigit() else tm("display-message", "-p", "#{pid}")
    try:
        if Path("/proc", pid, "comm").read_text().strip() != "tmux: server":
            raise FileNotFoundError
        process = Path("/proc", pid, "stat").read_text().rsplit(") ", 1)[1].split()
        if process[0] in ("Z", "X"): raise FileNotFoundError
        started = process[19]
    except FileNotFoundError:
        pid = tm("display-message", "-p", "#{pid}")
        started = Path("/proc", pid, "stat").read_text().rsplit(") ", 1)[1].split()[19]
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return pid, boot + ":" + pid + ":" + started


@contextmanager
def database():
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.exists() else {
            "version": 1,
            "workspaces": {"general": {"name": "General", "parent": None},
                           "archived": {"name": "Archive", "parent": None}},
            "sessions": {}, "origins": {},
        }
        before = json.dumps(data, sort_keys=True)
        data.setdefault("origins", {})
        data["workspaces"]["archived"]["name"] = "Archive"
        migrate(data)
        yield data
        if not path.exists() or json.dumps(data, sort_keys=True) != before:
            fd, temporary = tempfile.mkstemp(prefix=".workspaces-", dir=path.parent)
            try:
                with os.fdopen(fd, "w") as out:
                    json.dump(data, out, indent=2)
                    out.write("\n")
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, path)
                try:
                    import picker_service
                    picker_service.invalidate()
                except (OSError, RuntimeError, ImportError, SyntaxError): pass
                directory = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)


def path_name(data, wid):
    parts = []
    while wid:
        node = data["workspaces"][wid]
        parts.append(node["name"])
        wid = node["parent"]
    return "/".join(reversed(parts))


def children(data, parent):
    return sorted((key for key, node in data["workspaces"].items() if node["parent"] == parent),
                  key=lambda key: (2 if key == "archived" else 1 if key == "background" else 0,
                                   data["workspaces"][key].get("order", 0)))


def migrate(data):
    nodes = data["workspaces"]
    nodes.setdefault("background", {"name": "Background", "parent": None, "shortcut": 21})
    nodes["archived"]["shortcut"] = 22
    existing = [wid for wid in nodes if wid not in ("background", "archived")]
    for number, wid in enumerate(existing + ["background", "archived"]):
        nodes[wid].setdefault("order", number)
    data.setdefault("preferences", {"preview": True})
    data["preferences"].setdefault("preview", True)
    data["preferences"]["keys"] = False  # Help is an overlay; the inline guide is retired.
    data.setdefault("session_order", {})
    data.setdefault("history", {})
    data.setdefault("clients", {})
    data.setdefault("locations", {})
    data.setdefault("general_fixed", False)
    data.setdefault("picker_layout", "native")
    pid, server = server_identity()
    if data.get("runtime_identity", data.get("runtime_server")) not in (server, pid):
        data["resume_pending"] = bool(data.get("focus"))
    data["runtime_server"] = pid
    data["runtime_identity"] = server


def shortcut_map(data, parent=None):
    result = {1: "general"} if parent is None and data.get("general_fixed", False) else {}
    peers = children(data, parent)
    for wid in peers:
        pin = data["workspaces"][wid].get("shortcut")
        if pin:
            result[int(pin)] = wid
    for wid in peers:
        if wid not in result.values():
            free = next((number for number in range(1, 23) if number not in result), None)
            if free:
                result[free] = wid
    return result


def shortcut_label(number):
    return str(number) if number < 10 else "0" if number == 10 else "F" + str(number - 10)


def nested_parent(data, wid):
    """Enter children from a parent; keep Alt shortcuts among nested siblings."""
    if children(data, wid):
        return wid
    return data["workspaces"][wid]["parent"] or wid


def parse_shortcut(value):
    value = value.upper()
    number = int(value[1:]) + 10 if value.startswith("F") else 10 if value == "0" else int(value)
    if not 1 <= number <= 22:
        raise ValueError("Shortcut must be 1-10 or F1-F12 (11-22).")
    return number


def new_node(data, name, parent):
    wid = uuid.uuid4().hex[:16]
    data["workspaces"][wid] = {"name": name, "parent": parent,
                              "order": max(node.get("order", 0) for node in data["workspaces"].values()) + 1}
    return wid


def client_pane(client):
    for row in tm("list-clients", "-F", "#{client_name}\t#{pane_id}").splitlines():
        name, pane = row.split("\t")
        if name == client:
            return pane
    return ""


def record_focus(data, client, force=False, pane_hint=""):
    if not client or ((data.get("resume_pending") or data.get("detached_focus")) and not force):
        return
    attached_pane = client_pane(client)
    pane = attached_pane or pane_hint or data["clients"].get(client, {}).get("pane_id", "")
    if not pane:
        return
    if not attached_pane:
        # Hook command targets may still name the previously selected pane.
        # Once detached, resolve the session's actual active window and pane.
        sid = tm("display-message", "-p", "-t", pane, "#{session_id}")
        pane = tm("display-message", "-p", "-t", sid, "#{pane_id}")
    name, window, index, group = tm("display-message", "-p", "-t", pane,
        "#{session_name}\t#{window_index}\t#{pane_index}\t#{@workspace-id}").split("\t")
    wid = group if group in data["workspaces"] else data["sessions"].get(name, "general")
    history = data["history"].setdefault(wid, {})
    if history.get("current") != name:
        history["last"] = history.get("current")
        history["current"] = name
    if client not in data["clients"]:
        previous_session = tm("display-message", "-p", "-c", client, "#{client_last_session}") if attached_pane else ""
        seed = data.get("global_history", {}) if data.get("global_history", {}).get("current") == name else {}
        data["clients"][client] = {"current": name, "last": previous_session or seed.get("last"),
                                   "workspace": seed.get("workspace"), "last_workspace": seed.get("last_workspace")}
    global_history = data["clients"][client]
    previous_workspace = global_history.get("workspace")
    if previous_workspace not in data["workspaces"]:
        previous_workspace = next((data["sessions"].get(candidate) for candidate in
            (global_history.get("current"), global_history.get("last"))
            if data["sessions"].get(candidate) in data["workspaces"] and data["sessions"].get(candidate) != wid), None)
    if previous_workspace and previous_workspace != wid:
        global_history["last_workspace"] = previous_workspace
    global_history["workspace"] = wid
    global_history["pane_id"] = pane
    if global_history.get("current") != name:
        previous = global_history.get("current") or tm("display-message", "-p", "-c", client, "#{client_last_session}")
        global_history.update(current=name, last=previous if previous != name else None)
    data["global_history"] = dict(global_history)
    data["locations"][name] = {"window": window, "pane": index}
    data["focus"] = {"session": name, "workspace": wid, "window": window, "pane": index}


def switch_session(data, client, name, remember_current=True):
    if remember_current:
        record_focus(data, client, force=True)
    sid = next((row[0] for row in session_rows() if row[1] == name), None)
    if not sid:
        raise ValueError("Saved session no longer exists.")
    tm("switch-client", "-c", client, "-t", sid)
    where = data["locations"].get(name, {})
    target = sid + ":" + str(where.get("window", 0)) + "." + str(where.get("pane", 0))
    subprocess.run(["tmux", "select-window", "-t", sid + ":" + str(where.get("window", 0))],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["tmux", "select-pane", "-t", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    record_focus(data, client, force=True)
    pane = client_pane(client)
    if pane:
        UI(argparse.Namespace(client=client, pane=pane)).header(data, data["sessions"].get(name, "general"))


def cleanup_panels():
    windows = dict(row.split("\t", 1) for row in
                   tm("list-windows", "-a", "-F", "#{window_id}\t#{@workspaces-border-save}").splitlines())
    for window, saved in windows.items():
        if saved and "tree-mode" not in tm("list-panes", "-t", window, "-F", "#{pane_mode}").splitlines():
            restore_border(window, json.loads(saved))
            tm("set-option", "-wu", "-t", window, "@workspaces-border-save")


def clear_picker_flags(client):
    if not client:
        return
    updates = []
    for row in tm("list-panes", "-a", "-F", "#{pane_id}\t#{@workspace-picker-owner}").splitlines():
        pane, owner = row.split("\t")
        if owner == client:
            updates.extend(("set-option", "-pu", "-t", pane, option) for option in (
                "@workspace-picker-open", "@workspace-picker-owner", "@workspace-picker-pid", "@workspace-picker-jump", "@workspace-picker-menu"))
    if updates: tm(*command_queue(updates))


def restore_border(window, saved):
    for option, value in saved.items():
        tm("set-option", "-w", "-t", window, option, value) if value is not None else tm("set-option", "-wu", "-t", window, option)


def key_panel(data, pane):
    window = tm("display-message", "-p", "-t", pane, "#{window_id}")
    stored = tm("show-options", "-wqv", "-t", window, "@workspaces-border-save")
    saved = json.loads(stored) if stored else {key: tm("show-options", "-wqv", "-t", window, key) or None
                                              for key in ("pane-border-status", "pane-border-format")}
    if not stored:
        tm("set-option", "-w", "-t", window, "@workspaces-border-save", json.dumps(saved))
    if data["preferences"]["keys"]:
        tm("set-option", "-w", "-t", window, "pane-border-format",
           "#[bold] j/k move  Enter open  h/l fold  s workspaces  z archive/restore  m move  w CRUD  x delete  H/L Tab workspace  C-r Archive  v preview  b keys  ? help #[default]")
        tm("set-option", "-w", "-t", window, "pane-border-status", "top")
    else:
        restore_border(window, saved)


def valid_name(data, name, parent, exclude=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}", name):
        raise ValueError("Use 1-40 letters, numbers, spaces, dots, underscores or hyphens.")
    if any(key != exclude and node["parent"] == parent and node["name"].casefold() == name.casefold()
           for key, node in data["workspaces"].items()):
        raise ValueError("That workspace name already exists here.")


def sync(data):
    rows = session_rows(labels=True)
    updates = []
    pid, server = server_identity()
    previous = data.get("live", {})
    same_server = previous.get("identity") == server or (
        not previous.get("identity") and previous.get("server") == pid and not data.get("resume_pending"))
    old_names = previous.get("names", {}) if same_server else {}
    for sid, name, stored, hidden, stored_label in rows:
        old = old_names.get(sid)
        if old and old != name:
            for order in data["session_order"].values():
                order[:] = [name if entry == old else entry for entry in order]
            for table in ("sessions", "origins", "locations"):
                if old in data[table]:
                    data[table][name] = data[table].pop(old)
            for history in [*data["history"].values(), *data["clients"].values(), data.get("global_history", {})]:
                for key in ("current", "last"):
                    if history.get(key) == old:
                        history[key] = name
            for key in ("focus", "detached_focus"):
                if data.get(key, {}).get("session") == old:
                    data[key]["session"] = name
        # Resurrect can rename/reuse its bootstrap session, which may already
        # carry General's option. The persisted name mapping wins on restore.
        wid = data["sessions"].get(name, stored if stored in data["workspaces"] else "general")
        if wid not in data["workspaces"]:
            wid = "general"
        if hidden == "1" and wid != "archived":
            data["origins"][name] = wid
            wid = "archived"
        data["sessions"][name] = wid
        if stored != wid:
            updates.append(("set-option", "-t", sid, "@workspace-id", wid))
        wanted_hidden = "1" if wid == "archived" else "0"
        if hidden != wanted_hidden:
            updates.append(("set-option", "-t", sid, "@session-picker-hidden", wanted_hidden))
        label = path_name(data, wid)
        if stored_label != label:
            updates.append(("set-option", "-t", sid, "@workspace-label", label))
    if updates: tm(*command_queue(updates))
    data["live"] = {"server": pid, "identity": server, "names": {row[0]: row[1] for row in rows}}


def assign(data, sid, wid):
    if wid not in data["workspaces"]:
        raise ValueError("Workspace no longer exists.")
    name = tm("display-message", "-p", "-t", sid, "#{session_name}")
    previous = tm("display-message", "-p", "-t", sid, "#{@workspace-id}")
    if previous != wid:
        for order in data["session_order"].values():
            if name in order:
                order.remove(name)
        order = data["session_order"].setdefault(wid, [])
        ordered = sorted(session_rows(), key=lambda row: int(row[0][1:]))
        order.extend(row[1] for row in ordered if row[2] == wid and row[1] not in order and row[1] != name)
        order.append(name)
    if wid == "archived" and previous != "archived":
        data["origins"][name] = previous if previous in data["workspaces"] else "general"
    elif wid != "archived":
        data["origins"].pop(name, None)
    tm("set-option", "-t", sid, "@workspace-id", wid)
    tm("set-option", "-t", sid, "@workspace-label", path_name(data, wid))
    tm("set-option", "-t", sid, "@session-picker-hidden", "1" if wid == "archived" else "0")
    data["sessions"][name] = wid


def ensure_session(data, wid, pane, excluded=()):
    """Create a rescue session only when needed to preserve attached work/server."""
    if wid == "archived" or any(row[2] == wid and row[0] not in excluded for row in session_rows()):
        return
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", data["workspaces"][wid]["name"]).strip("-") or "workspace"
    base = slug + "-default"
    existing = {row[1] for row in session_rows()}
    name, number = base, 2
    while name in existing:
        name, number = base + "-" + str(number), number + 1
    cwd = tm("display-message", "-p", "-t", pane, "#{pane_current_path}")
    sid = tm("new-session", "-d", "-P", "-F", "#{session_id}", "-s", name, "-c", cwd)
    assign(data, sid, wid)


class UI:
    def __init__(self, args):
        self.a = args
        self.client = args.client
        self.pane = args.pane

    def call(self, action, **values):
        return callback(action, self.client, self.pane, **values)

    def message(self, text):
        tm("display-message", "-c", self.client, "-d", "3000", text)

    def current(self, data):
        if self.a.workspace:
            wid = self.a.workspace
        else:
            wid = tm("show-options", "-pqv", "-t", self.pane, "@workspace-active")
            if wid not in data["workspaces"]:
                wid = tm("display-message", "-p", "-t", self.pane, "#{@workspace-id}")
        return wid if wid in data["workspaces"] else "general"

    def header(self, data, wid, commands=None):
        label = path_name(data, wid) + " | press ?"
        updates = [("set-option", "-p", "-t", self.pane, "@workspace-active", wid),
                   ("set-option", "-p", "-t", self.pane, "@workspace-header", label)]
        if commands is None:
            tm(*command_queue(updates))
        else:
            commands.extend(updates)
        data["active_workspace"] = wid

    def close_tree(self):
        if tm("display-message", "-p", "-t", self.pane, "#{pane_mode}") == "tree-mode":
            tm("send-keys", "-t", self.pane, "q")

    def open(self, data, wid):
        commands = [] if data["picker_layout"] == "custom" else None
        if commands is not None:
            previous, mode, height, width, status, version = tm("display-message", "-p", "-c", self.client, "-t", self.pane,
                "#{@workspace-active}\t#{pane_mode}\t#{client_height}\t#{client_width}\t#{status}\t#{version}").split("\t")
        else:
            previous = tm("show-options", "-pqv", "-t", self.pane, "@workspace-active")
        if wid == "archived" and previous != "archived":
            update = ("set-option", "-p", "-t", self.pane, "@workspace-return", previous if previous in data["workspaces"] else "general")
            commands.append(update) if commands is not None else tm(*update)
        self.header(data, wid, commands)
        if data["picker_layout"] == "custom":
            if mode == "tree-mode": commands.append(("send-keys", "-t", self.pane, "q"))
            cleanup_panels()
            commands.extend([("set-option", "-p", "-t", self.pane, "@workspace-picker-open", "1"),
                             ("set-option", "-p", "-t", self.pane, "@workspace-picker-owner", self.client)])
            height, width = int(height), int(width)
            command = shell_command("session-ui", self.client, self.pane, workspace=wid)
            modern = tuple(map(int, re.match(r"(\d+)\.(\d+)", version).groups())) >= (3, 7)
            popup_env = ["-e", "TMUX_WORKSPACES_STATE=" + str(state_path())]
            command_args = [str(HERE), "session-ui", "--client", self.client, "--pane", self.pane, "--workspace", wid] if modern else [command]
            commands.append(("display-popup", "-c", self.client, "-t", self.pane, "-B", "-E",
                   "-x", "C", "-y", "C", "-w", str(width), "-h", str(height),
                   *popup_env, *command_args))
            launch(*command_queue(commands))
            return
        rows = [row for row in session_rows() if row[2] == wid]
        if not rows:
            self.close_tree()
            self.menu(data, wid, empty=True)
            return
        filter_ = "#{==:#{@workspace-id}," + wid + "}"
        if tm("display-message", "-p", "-t", self.pane, "#{pane_mode}") == "tree-mode":
            tm("send-keys", "-t", self.pane, "f")
            tm("send-keys", "-K", "-c", self.client, "C-u")
            tm("send-keys", "-K", "-c", self.client, "-l", filter_)
            tm("send-keys", "-K", "-c", self.client, "Enter")
        else:
            options = [] if data["preferences"]["preview"] else ["-N"]
            tm("choose-tree", "-t", self.pane, "-Zs", *options, "-f", filter_)
        tm("send-keys", "-t", self.pane, "M--")
        key_panel(data, self.pane)

    def menu(self, data, wid, empty=False):
        if data["picker_layout"] == "custom":
            tm("set-option", "-p", "-t", self.pane, "@workspace-picker-menu", "1")
            if tm("show-options", "-pqv", "-t", self.pane, "@workspace-picker-open") != "1":
                self.open(data, wid)
            return
        self.header(data, wid)
        title = "Workspace: " + path_name(data, wid)
        args = ["display-menu", "-c", self.client, "-t", self.pane, "-T", title, "-x", "C", "-y", "C", "--"]

        def add(label, key="-", action=""):
            args.extend([label, key, action] if label else [""])

        if empty:
            add("-No sessions in this workspace")
        add("List all workspaces (parents and nested)", "s", self.call("workspaces", workspace=wid))
        add("Sessions (j/k navigate; z archive/restore)", "S", self.call("open", workspace=wid))
        add("Toggle shared Archive (Ctrl+R)", "C-r", self.call("toggle-archive", workspace=wid))
        add("All keys / help", "?", self.call("help", workspace=wid))
        add("Change workspace shortcut", "p", self.call("prompt", workspace=wid, kind="shortcut"))
        add("")
        add("Previous workspace (Shift+H)", "H", self.call("previous", workspace=wid))
        add("Next workspace (Shift+L)", "L", self.call("next", workspace=wid))
        add("Previous workspace (Shift+Tab)", "BTab", self.call("previous", workspace=wid))
        add("Next workspace (Tab)", "Tab", self.call("next", workspace=wid))
        parent = data["workspaces"][wid]["parent"]
        if parent:
            add("Parent workspace", "Left", self.call("open", workspace=parent))
        for key, child in zip("1234567890befgijkopqtvyz", children(data, wid)):
            add("Open child: " + data["workspaces"][child]["name"], key, self.call("open", workspace=child))
        add("")
        add("Create sibling workspace", "c", self.call("prompt", workspace=wid, kind="create"))
        add("-Archive has no child workspaces" if wid == "archived" else "Create nested workspace", "C",
            self.call("prompt", workspace=wid, kind="child"))
        add(("-Rename workspace (protected)" if wid in SYSTEM else "Rename workspace"), "r",
            self.call("prompt", workspace=wid, kind="rename"))
        add(("-Move workspace (protected)" if wid in SYSTEM else "Move workspace into..."), "M",
            self.call("destinations", workspace=wid, kind="workspace"))
        blocked = wid in SYSTEM or bool(children(data, wid))
        reason = "protected" if wid in SYSTEM else "delete children first"
        add(("-Delete workspace (" + reason + ")" if blocked else "Delete workspace; archive sessions..."), "d",
            self.call("request-delete", workspace=wid))
        add("")
        sid = self.a.session or tm("display-message", "-p", "-t", self.pane, "#{session_id}")
        name = tm("display-message", "-p", "-t", sid, "#{session_name}")
        add("Create session here", "n", self.call("prompt", workspace=wid, kind="session"))
        add("Move session '" + name.replace("#", "##") + "' to...", "m",
            self.call("destinations", workspace=wid, session=sid, kind="session"))
        add("Rename selected session", "R", self.call("prompt", workspace=wid, session=sid, kind="session-rename"))
        add("Delete ALL sessions; keep workspace...", "E", self.call("request-empty", workspace=wid))
        if wid == "archived":
            add("Permanently delete ALL archived sessions...", "D", self.call("request-purge", workspace=wid))
        add("Close", "Escape", "")
        launch(*args)

    def workspaces(self, data, wid):
        height = min(len(data["workspaces"]) + 13, 28)
        launch("display-popup", "-c", self.client, "-t", self.pane, "-E", "-w", "82", "-h", str(height),
               "-T", "Workspaces", shell_command("list-ui", self.client, self.pane, workspace=wid))

    def selected(self, action):
        self.close_prompt_check()
        command = self.call("selected-" + action, session="#{session_id}")
        tm("send-keys", "-t", self.pane, ":")
        tm("send-keys", "-K", "-c", self.client, "-l", command)
        tm("send-keys", "-K", "-c", self.client, "Enter")

    def close_prompt_check(self):
        if tm("display-message", "-p", "-t", self.pane, "#{pane_mode}") != "tree-mode":
            raise ValueError("Open the session tree first.")

    def prompt(self, wid):
        title = "Restore to workspace (existing name or new path)" if self.a.kind == "restore" else "Workspace / session name"
        launch("display-popup", "-c", self.client, "-t", self.pane, "-E", "-w", "88", "-h", "11",
           "-T", title, shell_command("input", self.client, self.pane,
                workspace=wid, kind=self.a.kind, session=self.a.session))

    def destinations(self, data, wid):
        args = ["display-menu", "-c", self.client, "-T", "Move into workspace", "-x", "C", "-y", "C", "--"]
        candidates = sorted(data["workspaces"], key=lambda key: path_name(data, key).lower())
        if self.a.kind == "workspace":
            candidates = [key for key in candidates if key != wid and not descendant(data, key, wid)]
            args.extend(["Top level", "0", self.call("move-workspace", workspace=wid, destination="top")])
        page = max(0, int(self.a.page or "0"))
        start = page * 30
        for shortcut, target in zip("123456789abcdefghijklmnopqrstuv", candidates[start:start + 30]):
            args.extend([path_name(data, target), shortcut,
                         self.call("move-workspace" if self.a.kind == "workspace" else "assign",
                                   workspace=wid, destination=target, session=self.a.session)])
        for label, key, target_page in (("Previous page", "[", page - 1), ("Next page", "]", page + 1)):
            if (key == "[" and page > 0) or (key == "]" and start + 30 < len(candidates)):
                args.extend([label, key, self.call("destinations", workspace=wid,
                             session=self.a.session, kind=self.a.kind, page=target_page)])
        args.extend(["Cancel", "Escape", ""])
        launch(*args)

    def help(self, wid):
        args = ["display-menu", "-c", self.client, "-T", "Workspace keys", "-x", "C", "-y", "C", "--"]
        for label, key, action in [
            ("List all workspaces (parents and nested)", "s", self.call("workspaces", workspace=wid)),
            ("-Sessions: j/k or arrows; Enter select; q/Esc close", "-", ""),
            ("Previous workspace: Shift+H / Shift+Tab", "H", self.call("previous", workspace=wid)),
            ("Next workspace: Shift+L / Tab", "L", self.call("next", workspace=wid)),
            ("Previous workspace (Shift+Tab)", "BTab", self.call("previous", workspace=wid)),
            ("Next workspace (Tab)", "Tab", self.call("next", workspace=wid)),
            ("Toggle shared Archive / return", "C-r", self.call("toggle-archive", workspace=wid)),
            ("Workspace CRUD / session actions: w (or prefix W)", "w", self.call("menu", workspace=wid)),
            ("-z: archive session / restore from Archive to origin", "-", ""),
            ("-h/l: collapse/expand session or window", "-", ""),
            ("Toggle session preview", "v", self.call("toggle-preview", workspace=wid)),
            ("-Prefix Shift+Tab: last session in workspace", "-", ""),
            ("-Prefix Alt+Tab: last session across workspaces", "-", ""),
            ("Browse previous workspace (toggle)", "^", self.call("browse-last-workspace", workspace=wid)),
            ("-Alt+1-0: workspace; Alt+Shift+6: previous workspace session", "-", ""),
            ("-1-0/F1-F12: workspace; Alt+key: nested workspace", "-", ""),
            ("-Workspace list: Shift+J/K changes sibling order", "-", ""),
            ("-m: move selected session; r: rename; c: new session", "-", ""),
            ("-[: parent workspace; ]: first child workspace", "-", ""),
            ("-x/X: delete selected/tagged session/window/pane; confirms", "-", ""),
            ("-D: permanently delete all Archive sessions; confirms", "-", ""),
            ("Back to sessions", "Escape", self.call("open", workspace=wid)),
        ]:
            args.extend([label, key, action])
        launch(*args)


def descendant(data, wid, ancestor):
    while wid:
        if wid == ancestor:
            return True
        wid = data["workspaces"][wid]["parent"]
    return False


def deletion_token(data, wid):
    members = sorted(name for name, group in data["sessions"].items() if group == wid)
    return hashlib.sha256(json.dumps([wid, data["workspaces"][wid], members,
                                     children(data, wid)], sort_keys=True).encode()).hexdigest()


def destination_from_name(data, name):
    exact = [wid for wid in data["workspaces"] if path_name(data, wid).casefold() == name.casefold()]
    bare = [wid for wid, node in data["workspaces"].items() if node["name"].casefold() == name.casefold()]
    matches = exact or bare
    if len(matches) > 1:
        raise ValueError("More than one workspace has that name; enter the full path.")
    if matches:
        if matches[0] == "archived":
            raise ValueError("Choose a workspace outside Archive to restore into.")
        return matches[0]
    parent = None
    for part in name.split("/"):
        found = next((wid for wid in children(data, parent)
                      if data["workspaces"][wid]["name"].casefold() == part.casefold()), None)
        if found is None:
            valid_name(data, part, parent)
            found = new_node(data, part, parent)
        if found == "archived":
            raise ValueError("Choose a workspace outside Archive to restore into.")
        parent = found
    return parent


def archive_snapshot():
    rows = []
    for sid, name, wid, hidden in session_rows():
        if wid == "archived":
            if int(tm("display-message", "-p", "-t", sid, "#{session_attached}")):
                raise ValueError("Archive has attached sessions. Switch clients out of those sessions before permanent deletion.")
            rows.append((sid, name))
    return sorted(rows)


def snapshot_token(rows):
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def object_rows():
    return [line.split("\t") for line in tm("list-panes", "-a", "-F",
        "#{session_id}\t#{window_id}\t#{pane_id}\t#{pane_pid}").splitlines()]


def target_snapshot(kind, target):
    column = {"session": 0, "window": 1, "pane": 2}.get(kind)
    if column is None or not re.fullmatch(r"[$@%][0-9]+", target):
        raise ValueError("Invalid session/window/pane target.")
    rows = sorted(row for row in object_rows() if row[column] == target)
    if not rows:
        raise ValueError("Selected item no longer exists.")
    return rows


def destruction_token(targets):
    return snapshot_token([(kind, target, target_snapshot(kind, target)) for kind, target in sorted(set(map(tuple, targets)))])


def install_picker_binding(layout=None):
    if layout is None:
        path = state_path()
        layout = json.loads(path.read_text()).get("picker_layout", "native") if path.exists() else "native"
    if layout == "native":
        try:
            import picker_service
            picker_service.request('retire', timeout=.05)
        except (OSError, ValueError, RuntimeError, ImportError, SyntaxError): pass
        tm("bind-key", "s", "run-shell", "-b", shell_command("open", "#{client_name}", "#{pane_id}"))
        return
    version = tm("display-message", "-p", "#{version}")
    modern = tuple(map(int, re.match(r"(\d+)\.(\d+)", version).groups())) >= (3, 7)
    command = [str(HERE), "open-ui", "--client", "#{client_name}", "--pane", "#{pane_id}",
               "--workspace", "#{@workspace-id}"] if modern else ["exec env " + shell_command("open-ui", "#{client_name}", "#{pane_id}")]
    if os.environ.get('TMUX_PICKER_SERVICE', '1') != '0':
        try:
            import picker_service
            binary = picker_service.install_client()
            picker_service.start()
            arguments = [str(binary), str(picker_service.endpoint()), str(HERE),
                         '#{client_name}', '#{pane_id}', '#{@workspace-id}']
            command = arguments if modern else ['exec ' + shlex.join(arguments)]
        except (OSError, RuntimeError, ImportError, SyntaxError, subprocess.SubprocessError):
            # A compiler/service failure retains the ordinary Python picker.
            try:
                import picker_service
                picker_service.request('retire', timeout=.05)
            except (OSError, ValueError, RuntimeError, ImportError, SyntaxError): pass
    else:
        try:
            import picker_service
            picker_service.request('retire', timeout=.05)
        except (OSError, ValueError, RuntimeError, ImportError, SyntaxError): pass
    environment = ["-e", "TMUX_WORKSPACES_STATE=" + str(state_path())]
    if os.environ.get('TMUX_PICKER_RUNTIME'):
        environment += ['-e', 'TMUX_PICKER_RUNTIME=' + str(Path(os.environ['TMUX_PICKER_RUNTIME']).absolute())]
    popup = ["display-popup", "-B", "-E", "-x", "C", "-y", "C",
             "-w", "#{client_width}", "-h", "#{client_height}", *environment, *command]
    # -C expands formats and executes tmux commands without starting a shell.
    tm("bind-key", "s", "run-shell", "-bC", shlex.join(popup))


def install():
    # Preserve theme/plugin output and their hooks. Repeated loads are idempotent.
    current = tm("show-options", "-gqv", "status-left")
    if "@workspace-header" not in current:
        tm("set-option", "-g", "@workspaces-base-status-left", current)
    base = tm("show-options", "-gqv", "@workspaces-base-status-left")
    label = "#{?#{||:#{==:#{pane_mode},tree-mode},#{@workspace-picker-open}},#{@workspace-header},#{?@workspace-label,#{@workspace-label},General}}"
    if tm("show-options", "-gqv", "@bw_accent"):
        prefix = "#[fg=#{@bw_accent},bg=default]#[fg=#{@bw_on_accent},bg=#{@bw_accent},bold] ◈ " + label + " #[fg=#{@bw_accent},bg=default,nobold] "
    else:
        style = re.match(r"#\[[^\]]+\]", base)
        prefix = (style.group() if style else "#[fg=colour232,bg=colour117,bold]") + " ◈ " + label + " #[default] "
    tm("set-option", "-g", "status-left", prefix + base)
    install_picker_binding()
    hook = callback("sync")
    for name in ("after-new-session", "session-renamed"):
        tm("set-hook", "-g", name + "[9271]", hook)
    tm("set-hook", "-g", "client-attached[9271]",
       "run-shell -b -d 0.1 " + quote(shell_command("resume", "#{client_name}", "#{pane_id}")))
    tm("set-hook", "-g", "session-closed[9271]", callback("refresh"))
    tm("set-hook", "-g", "client-session-changed[9271]",
       callback("activate", "#{client_name}", "#{pane_id}"))
    for hook_name in ("after-select-window", "after-select-pane", "session-window-changed", "window-pane-changed"):
        tm("set-hook", "-g", hook_name + "[9271]", callback("focus", "#{client_name}", "#{pane_id}"))
    tm("set-hook", "-g", "client-detached[9271]", callback("focus", "#{hook_client}", "#{hook_pane}", kind="detached"))
    tm("set-hook", "-g", "pane-mode-changed[9271]", callback("cleanup"))


def open_picker_ui(args):
    ui = UI(args)
    with database() as data:
        sync(data)
        context = tm("display-message", "-p", "-t", args.pane,
            "#{session_id}\t#{session_name}\t#{@workspace-id}\t#{@workspace-return}\t#{prefix}\t#{pane_mode}\t#{window_id}\t#{pane_id}").split("\t")
        args.picker_context = context[:5]
        cached = getattr(args, "picker_snapshot", None)
        if cached is not None:
            current = cached.get(context[0], {})
            windows = current.get('windows', {})
            if current.get("name") != context[1] or context[6] not in windows or context[7] not in windows[context[6]]['panes']:
                args.picker_snapshot = None
            else:
                for window in windows.values():
                    window['active'] = window['id'] == context[6]
                    if window['active']:
                        for pane in window['panes'].values(): pane['active'] = pane['id'] == context[7]

        if context[5] == "tree-mode":
            tm("send-keys", "-t", args.pane, "q")
            cleanup_panels()
        wid = args.workspace or args.picker_context[2]
        args.workspace = wid if wid in data["workspaces"] else "general"
        updates = []
        ui.header(data, args.workspace, updates)
        updates.extend(("set-option", "-p", "-t", args.pane, key, value) for key, value in (
            ("@workspace-picker-open", "1"), ("@workspace-picker-owner", args.client)))
        tm(*command_queue(updates))
    from session_picker import run_picker
    run_picker(args, state_path())

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action")
    for key in ("client", "pane", "workspace", "session", "kind", "destination", "token", "name", "page", "direction", "quiet", "slot", "nested", "attempt", "target"):
        parser.add_argument("--" + key, default="")
    args = parser.parse_args()
    ui = UI(args)
    action = args.action
    if action == "list-ui":
        from workspace_ui import workspace_list
        workspace_list(args, state_path())
        return
    if action == "open-ui":
        open_picker_ui(args)
        return
    if action == "session-ui":
        from session_picker import run_picker
        run_picker(args, state_path())
        return
    if action == "input":
        try:
            from workspace_ui import read_name
            initial = ""
            if args.kind == "session-rename":
                initial = tm("display-message", "-p", "-t", args.session, "#{session_name}")
            elif args.kind == "rename":
                initial = json.loads(state_path().read_text())["workspaces"][args.workspace]["name"]
            name = read_name(initial, "Rename" if initial else "Name / shortcut")
            if name:
                pattern = r"[A-Za-z0-9][A-Za-z0-9 _./-]{0,199}" if args.kind == "restore" else r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}"
                if not re.fullmatch(pattern, name):
                    raise ValueError("Use 1-40 letters, numbers, spaces, dots, underscores or hyphens.")
                tm("run-shell", "-b", "-d", "0.2", shell_command("apply-name", args.client, args.pane,
                    workspace=args.workspace, kind=args.kind, session=args.session, name=name))
        except (EOFError, KeyboardInterrupt):
            pass
        return
    if action in ("hide", "restore", "toggle-session-archive", "session-menu", "session-rename", "move"):
        ui.selected(action)
        return
    if action == "init":
        install()
    if action == "cleanup":
        cleanup_panels()
        return
    with database() as data:
        sync(data)
        if action == "numbering-order":
            data["general_fixed"] = False
            data["workspaces"]["general"].pop("shortcut", None)
            return
        if action == "layout":
            if args.kind not in ("native", "custom"):
                raise ValueError("Choose native or custom layout.")
            data["picker_layout"] = args.kind
            install_picker_binding(args.kind)
            return
        if action == "view-context":
            ui.pane = client_pane(ui.client) or ui.pane
            wid = ui.current(data)
            ui.header(data, wid)
            if args.destination:
                tm("set-option", "-p", "-t", ui.pane, "@workspace-return", args.destination)
            tm("set-option", "-p", "-t", ui.pane, "@workspace-picker-open", "1")
            tm("set-option", "-p", "-t", ui.pane, "@workspace-picker-owner", ui.client)
            return
        if action == "close-picker":
            clear_picker_flags(ui.client)
            return
        if action == "move-windows":
            pairs = list(dict.fromkeys(map(tuple, json.loads(args.name))))
            sessions = {row[0] for row in session_rows()}
            if args.destination not in sessions:
                raise ValueError("Destination session no longer exists.")
            links = {(row[0], row[1]) for row in object_rows()}
            if not pairs or any(pair not in links for pair in pairs):
                raise ValueError("Window selection changed; select it again.")
            moving = [(sid, wid) for sid, wid in pairs if sid != args.destination]
            # Tmux sessions cannot be windowless. Keep source sessions alive
            # when their last window moves; no running pane is terminated.
            for sid in dict.fromkeys(sid for sid, wid in moving):
                present = {wid for owner, wid in links if owner == sid}
                selected = {wid for owner, wid in moving if owner == sid}
                if present <= selected:
                    cwd = tm("display-message", "-p", "-t", sid, "#{pane_current_path}")
                    tm("new-window", "-d", "-t", sid + ":", "-n", "shell", "-c", cwd)
            for sid, wid in moving:
                source = next(line.split("\t")[1] for line in tm("list-windows", "-t", sid,
                    "-F", "#{window_id}\t#{window_index}").splitlines() if line.split("\t")[0] == wid)
                if wid in tm("list-windows", "-t", args.destination, "-F", "#{window_id}").splitlines():
                    tm("unlink-window", "-t", sid + ":" + source)
                else:
                    tm("move-window", "-d", "-s", sid + ":" + source, "-t", args.destination + ":")
            clear_picker_flags(ui.client)
            record_focus(data, ui.client, force=True)
            return
        if action in ("assign-many", "restore-many", "rename-many"):
            values = json.loads(args.name)
            pairs = values if action == "rename-many" else [(sid, "") for sid in values]
            live = {row[0]: row[1] for row in session_rows()}
            ids = [sid for sid, value in pairs]
            if not ids or len(ids) != len(set(ids)) or any(not re.fullmatch(r"\$[0-9]+", sid) or sid not in live for sid in ids):
                raise ValueError("Selection changed; select the sessions again.")
            if action == "assign-many":
                if args.destination not in data["workspaces"]:
                    raise ValueError("Destination workspace no longer exists.")
                for sid in ids:
                    assign(data, sid, args.destination)
            elif action == "restore-many":
                if any(data["sessions"].get(live[sid]) != "archived" for sid in ids):
                    raise ValueError("Selection changed; restore sessions from Archive.")
                origins = {sid: data["origins"].get(live[sid]) for sid in ids}
                missing = [sid for sid, origin in origins.items() if origin not in data["workspaces"] or origin == "archived"]
                if missing:
                    if not args.destination:
                        raise ValueError("Specify a workspace name for sessions whose origin no longer exists.")
                    destination = destination_from_name(data, args.destination)
                    origins.update({sid: destination for sid in missing})
                for sid, destination in origins.items():
                    assign(data, sid, destination)
            else:
                names = [name for sid, name in pairs]
                if len(names) != len(set(names)) or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,59}", name) for name in names):
                    raise ValueError("Use distinct session names with letters, numbers, spaces, underscores or hyphens.")
                for sid, name in pairs:
                    if any(other != sid and old == name for other, old in live.items()):
                        raise ValueError("Session name already exists: " + name)
                for sid, name in pairs:
                    if live[sid] != name:
                        tm("rename-session", "-t", sid, name)
                sync(data)
            record_focus(data, ui.client, force=True)
            return
        if action == "reorder-session":
            wid = ui.current(data)
            members = [row[1] for row in sorted(session_rows(), key=lambda row: int(row[0][1:])) if row[2] == wid]
            stored = data["session_order"].setdefault(wid, [])
            order = [name for name in stored if name in members]
            order.extend(name for name in members if name not in order)
            ids = json.loads(args.name) if args.name else [args.session]
            chosen = {tm("display-message", "-p", "-t", sid, "#{session_name}") for sid in ids}
            if not chosen or not chosen <= set(order):
                raise ValueError("Session is no longer in this workspace.")
            if args.direction == "down":
                for index in range(len(order) - 2, -1, -1):
                    if order[index] in chosen and order[index + 1] not in chosen:
                        order[index], order[index + 1] = order[index + 1], order[index]
            else:
                for index in range(1, len(order)):
                    if order[index] in chosen and order[index - 1] not in chosen:
                        order[index], order[index - 1] = order[index - 1], order[index]
            data["session_order"][wid] = order
            return
        if action == "select-target":
            record_focus(data, ui.client, force=True)
            tm("switch-client", "-c", ui.client, "-t", args.target)
            record_focus(data, ui.client, force=True)
            ui.pane = client_pane(ui.client) or ui.pane
            ui.header(data, data["focus"]["workspace"])
            return
        if action == "item-command":
            # Match choose-tree's %% substitution and target context. The user
            # enters this command explicitly in the picker command prompt.
            command = args.name.replace("%%", args.target)
            result = subprocess.run(["tmux", "run-shell", "-bC", "-t", args.target,
                                     command], capture_output=True, text=True)
            if result.returncode:
                raise ValueError(result.stderr.strip())
            return
        if action == "delete-targets":
            targets = sorted(set(map(tuple, json.loads(args.name))))
            if destruction_token(targets) != args.token:
                raise ValueError("Selection changed; confirm deletion again.")
            before = {row[0]: row[1] for row in session_rows()}
            for kind, target in targets:
                try:
                    scope = target_snapshot(kind, target)
                except ValueError:
                    continue  # A linked object may already have been removed.
                rows = object_rows()
                affected = {row[0] for row in scope}
                doomed = {sid for sid in affected if all(row in scope for row in rows if row[0] == sid)}
                groups = {row[0]: row[2] for row in session_rows()}
                rescue = "background" if any(groups.get(sid) == "general" for sid in affected) else "general"
                ui.pane = client_pane(ui.client) or ui.pane
                clients = [line.split("\t") for line in tm("list-clients", "-F",
                    "#{client_name}\t#{session_id}\t#{window_id}\t#{pane_id}").splitlines()]
                moved = [row[0] for row in clients if row[1] in doomed or
                         (kind == "window" and row[2] == target) or (kind == "pane" and row[3] == target)]
                if moved:
                    ensure_session(data, rescue, ui.pane, excluded=doomed)
                    destination = next(row[0] for row in session_rows() if row[2] == rescue and row[0] not in doomed)
                    for client in moved:
                        tm("switch-client", "-c", client, "-t", destination)
                tm({"session": "kill-session", "window": "kill-window", "pane": "kill-pane"}[kind], "-t", target)
            surviving = {row[0] for row in session_rows()}
            for sid, name in before.items():
                if sid not in surviving:
                    for table in ("sessions", "origins", "locations"):
                        data[table].pop(name, None)
            sync(data)
            record_focus(data, ui.client, force=True)
            save = tm("show-options", "-gqv", "@resurrect-save-script-path")
            if save and Path(save).is_file():
                launch("run-shell", "-b", shlex.quote(save))
            return
        if action in ("init", "sync"):
            if action == "init":
                for client in tm("list-clients", "-F", "#{client_name}").splitlines():
                    record_focus(data, client)
            return
        if action == "focus":
            record_focus(data, args.client, pane_hint=args.pane)
            if args.kind == "detached":
                if data.get("focus"):
                    data["detached_focus"] = dict(data["focus"])
                clear_picker_flags(args.client)
            return
        if action == "resume":
            if not data.get("resume_pending") and not data.get("detached_focus"):
                return
            saved = data.get("detached_focus") or data.get("focus")
            exists = next((row[0] for row in session_rows() if saved and row[1] == saved["session"]), None)
            desired = str(saved["window"]) + "." + str(saved["pane"]) if saved else ""
            ready = exists and desired in tm("list-panes", "-s", "-t", exists, "-F", "#{window_index}.#{pane_index}").splitlines()
            if saved and not ready and client_pane(args.client):
                attempt = int(args.attempt or "0")
                if attempt < 30:
                    launch("run-shell", "-b", "-d", "1", shell_command("resume", args.client, args.pane, attempt=attempt + 1))
                else:
                    data["resume_pending"] = False
                    data.pop("detached_focus", None)
                    record_focus(data, args.client, force=True)
            elif saved and ready and client_pane(args.client):
                data["resume_pending"] = False
                data.pop("detached_focus", None)
                data["locations"][saved["session"]] = {"window": saved["window"], "pane": saved["pane"]}
                switch_session(data, args.client, saved["session"], remember_current=False)
                ui.pane = client_pane(args.client)
                ui.header(data, data["active_workspace"] if data.get("active_workspace") in data["workspaces"]
                          else data["sessions"].get(saved["session"], "general"))
            return
        if action == "refresh":
            rows = session_rows()
            for row in tm("list-clients", "-F", "#{client_name}\t#{pane_id}\t#{pane_mode}").splitlines():
                client, pane, mode = row.split("\t")
                if mode != "tree-mode":
                    continue
                args.client, args.pane = client, pane
                active_ui = UI(args)
                wid = active_ui.current(data)
                if not any(r[2] == wid for r in rows):
                    active_ui.open(data, wid)
            return
        wid = (args.workspace or "general") if action == "open" else ui.current(data)
        if action == "activate":
            ui.pane = client_pane(ui.client) or ui.pane
            wid = tm("display-message", "-p", "-t", ui.pane, "#{@workspace-id}")
            ui.header(data, wid if wid in data["workspaces"] else "general")
            record_focus(data, ui.client)
        elif action == "browse-last-workspace":
            current = data['clients'].get(ui.client, data.get('global_history', {}))
            destination = tm('show-options', '-pqv', '-t', ui.pane, '@workspace-browse-last') or current.get('last_workspace')
            if destination in data['workspaces'] and destination != wid:
                tm('set-option', '-p', '-t', ui.pane, '@workspace-browse-last', wid)
                ui.open(data, destination)
            else:
                ui.message('No previous workspace')
        elif action == "last-workspace":
            ui.pane = client_pane(ui.client) or ui.pane
            record_focus(data, ui.client, force=True)
            current = data["clients"].get(ui.client, {})
            group = current.get("workspace", "general")
            rows = [line.split("\t") for line in tm("list-sessions", "-F",
                "#{session_name}\t#{@workspace-id}\t#{session_last_attached}\t#{session_activity}").splitlines()]
            available = [row for row in rows if row[1] != group and row[1] in data["workspaces"]]
            destination = current.get("last_workspace")
            if not any(row[1] == destination for row in available):
                destination = max(available, key=lambda row: (int(row[2] or 0), int(row[3] or 0)))[1] if available else None
            candidates = [row for row in available if row[1] == destination]
            preferred = data["history"].get(destination, {}).get("current")
            target = next((row[0] for row in candidates if row[0] == preferred), None)
            if not target and candidates:
                target = max(candidates, key=lambda row: (int(row[2] or 0), int(row[3] or 0)))[0]
            if target:
                ui.close_tree()
                clear_picker_flags(ui.client)
                switch_session(data, ui.client, target)
            else:
                ui.message("No previous workspace session")
        elif action in ("last-local", "last-global"):
            ui.pane = client_pane(ui.client) or ui.pane
            record_focus(data, ui.client, force=True)
            current_name = tm("display-message", "-p", "-t", ui.pane, "#{session_name}")
            group = data["sessions"].get(current_name, "general")
            history = data["history"].get(group, {}) if action == "last-local" else data["clients"].get(ui.client, data.get("global_history", {}))
            candidates = [history.get("last"), history.get("current")]
            rows = session_rows()
            valid = {row[1] for row in rows if action == "last-global" or row[2] == group}
            target = next((name for name in candidates if name != current_name and name in valid), None)
            if not target and action == "last-local":
                recent = []
                for row in tm("list-sessions", "-F", "#{session_name}\t#{session_last_attached}\t#{session_activity}").splitlines():
                    name, attached, activity = row.split("\t")
                    if name in valid and name != current_name:
                        recent.append((int(attached or "0"), int(activity or "0"), name))
                target = max(recent)[2] if recent else None
            if target:
                switch_session(data, ui.client, target)
            else:
                ui.message("No previous session in this workspace" if action == "last-local" else "No previous session")
        elif action == "jump":
            ui.pane = client_pane(ui.client) or ui.pane
            actual_group = tm("display-message", "-p", "-t", ui.pane, "#{@workspace-id}")
            picker_open = tm("show-options", "-pqv", "-t", ui.pane, "@workspace-picker-open") == "1"
            tree_open = tm("display-message", "-p", "-t", ui.pane, "#{pane_mode}") == "tree-mode"
            current_group = wid if tree_open or picker_open else actual_group
            parent = nested_parent(data, current_group) if args.nested else None
            destination = shortcut_map(data, parent).get(int(args.slot))
            if not destination:
                ui.message("No nested workspace at this shortcut" if args.nested else "No workspace at this shortcut")
                return
            if picker_open:
                tm("set-option", "-p", "-t", ui.pane, "@workspace-picker-jump", destination)
            elif tree_open:
                ui.open(data, destination)
            else:
                rows = [row for row in session_rows() if row[2] == destination]
                preferred = data["history"].get(destination, {}).get("current")
                target = next((row[1] for row in rows if row[1] == preferred), rows[0][1] if rows else None)
                if target:
                    switch_session(data, ui.client, target)
                else:
                    ui.menu(data, destination, empty=True)
        elif action == "reorder":
            peers = children(data, data["workspaces"][wid]["parent"])
            position = peers.index(wid)
            other = position + (1 if args.direction == "down" else -1)
            if 0 <= other < len(peers) and wid not in ("archived", "background") and peers[other] not in ("archived", "background"):
                first, second = data["workspaces"][wid], data["workspaces"][peers[other]]
                first["order"], second["order"] = second["order"], first["order"]
            if not args.quiet:
                ui.workspaces(data, wid)
        elif action in ("toggle-preview", "toggle-keys"):
            if action == "toggle-keys":
                return  # The old inline panel has been removed; ? provides help.
            preference = "preview" if action == "toggle-preview" else "keys"
            data["preferences"][preference] = not data["preferences"][preference]
            if args.quiet:
                return
            if tm("display-message", "-p", "-t", ui.pane, "#{pane_mode}") == "tree-mode":
                if preference == "preview":
                    tm("send-keys", "-t", ui.pane, "v")
                else:
                    key_panel(data, ui.pane)
            else:
                if data["picker_layout"] == "custom":
                    ui.open(data, wid)
                else:
                    ui.menu(data, wid, empty=not any(row[2] == wid for row in session_rows()))
        elif action in ("next", "previous"):
            peers = children(data, data["workspaces"][wid]["parent"])
            wid = peers[(peers.index(wid) + (1 if action == "next" else -1)) % len(peers)]
            ui.open(data, wid)
        elif action in ("parent", "child"):
            parent = data["workspaces"][wid]["parent"]
            nodes = children(data, wid)
            ui.open(data, parent if action == "parent" and parent else nodes[0] if action == "child" and nodes else wid)
        elif action == "open":
            tm("set-option", "-pu", "-t", ui.pane, "@workspace-browse-last")
            if not args.workspace:
                ui.pane = client_pane(ui.client) or ui.pane
                wid = tm("display-message", "-p", "-t", ui.pane, "#{@workspace-id}")
                if wid not in data["workspaces"]:
                    wid = "general"
            ui.open(data, wid)
        elif action == "toggle-archive":
            previous = tm("show-options", "-pqv", "-t", ui.pane, "@workspace-return")
            destination = (previous if previous in data["workspaces"] and previous != "archived" else "general") if wid == "archived" else "archived"
            ui.open(data, destination)
        elif action == "help":
            ui.help(wid)
        elif action == "workspaces":
            ui.workspaces(data, wid)
        elif action in ("menu", "selected-session-menu"):
            ui.menu(data, wid)
        elif action in ("selected-hide", "selected-restore", "selected-toggle-session-archive"):
            if action == "selected-toggle-session-archive":
                name = tm("display-message", "-p", "-t", args.session, "#{session_name}")
                action = "selected-restore" if data["sessions"].get(name) == "archived" else "selected-hide"
            if action == "selected-hide":
                assign(data, args.session, "archived")
                ui.open(data, wid)
                ui.message("Session archived; Ctrl+R toggles Archive")
            else:
                name = tm("display-message", "-p", "-t", args.session, "#{session_name}")
                if data["sessions"].get(name) != "archived":
                    raise ValueError("Select a session in Archive first (Ctrl+R).")
                origin = data["origins"].get(name)
                if origin in data["workspaces"] and origin != "archived":
                    assign(data, args.session, origin)
                    ui.open(data, origin)
                    ui.message("Session restored to " + path_name(data, origin))
                else:
                    args.kind = "restore"
                    ui.prompt(wid)
        elif action == "selected-move":
            args.kind = "session"
            ui.destinations(data, wid)
        elif action == "selected-session-rename":
            args.kind = "session-rename"
            ui.prompt(wid)
        elif action == "prompt":
            ui.prompt(wid)
        elif action == "apply-name":
            node = data["workspaces"][wid]
            if args.kind == "restore":
                wid = destination_from_name(data, args.name)
                assign(data, args.session, wid)
            elif args.kind == "shortcut":
                if wid == "archived":
                    raise ValueError("Archive is fixed at F12.")
                if wid == "general" and data.get("general_fixed", False):
                    raise ValueError("General keeps shortcut 1; its display order can still change.")
                number = parse_shortcut(args.name)
                parent = node["parent"]
                if parent is None and number == 22:
                    raise ValueError("F12 is reserved for Archive.")
                if parent is None and number == 1 and data.get("general_fixed", False):
                    raise ValueError("Shortcut 1 is reserved for General.")
                if any(other != wid and other_node["parent"] == parent and other_node.get("shortcut") == number
                       for other, other_node in data["workspaces"].items()):
                    raise ValueError("Another pinned workspace already uses that shortcut.")
                node["shortcut"] = number
            elif args.kind in ("create", "child", "rename"):
                if args.kind == "child" and wid == "archived":
                    raise ValueError("Archive is shared and cannot contain child workspaces.")
                if args.kind == "rename" and wid in SYSTEM:
                    raise ValueError("Built-in workspaces are protected.")
                parent = wid if args.kind == "child" else node["parent"]
                valid_name(data, args.name, parent, wid if args.kind == "rename" else None)
                if args.kind == "rename":
                    node["name"] = args.name
                else:
                    wid = new_node(data, args.name, parent)
                sync(data)
            elif args.kind in ("session", "session-rename"):
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,59}", args.name):
                    raise ValueError("Session names: letters, numbers, spaces, underscores or hyphens.")
                if args.kind == "session":
                    cwd = tm("display-message", "-p", "-t", ui.pane, "#{pane_current_path}")
                    sid = tm("new-session", "-d", "-P", "-F", "#{session_id}", "-s", args.name, "-c", cwd)
                else:
                    sid = args.session
                    old_name = tm("display-message", "-p", "-t", sid, "#{session_name}")
                    tm("rename-session", "-t", sid, args.name)
                    data["sessions"].pop(old_name, None)
                    if old_name in data["origins"]:
                        data["origins"][args.name] = data["origins"].pop(old_name)
                assign(data, sid, wid)
            if not args.quiet:
                ui.open(data, wid)
        elif action == "destinations":
            ui.destinations(data, wid)
        elif action == "assign":
            assign(data, args.session, args.destination)
            if not args.quiet:
                ui.open(data, args.destination)
        elif action == "move-workspace":
            if wid in SYSTEM:
                raise ValueError("Built-in workspaces are protected.")
            parent = None if args.destination == "top" else args.destination
            if parent == "archived":
                raise ValueError("Archive is shared and cannot contain child workspaces.")
            if parent is not None and (parent not in data["workspaces"] or descendant(data, parent, wid)):
                raise ValueError("A workspace cannot contain itself.")
            valid_name(data, data["workspaces"][wid]["name"], parent, wid)
            data["workspaces"][wid]["parent"] = parent
            sync(data)
            if not args.quiet:
                ui.open(data, wid)
        elif action in ("request-delete", "delete"):
            if wid in SYSTEM:
                raise ValueError("Built-in workspaces cannot be deleted.")
            if children(data, wid):
                raise ValueError("Delete child workspaces first; each deletion needs its own confirmation.")
            token = deletion_token(data, wid)
            if action == "request-delete":
                count = sum(row[2] == wid for row in session_rows())
                launch("confirm-before", "-t", ui.client, "-p",
                   f"Delete {path_name(data, wid)}? Move {count} session(s) to Archive, keep running? (y/n)",
                   ui.call("delete", workspace=wid, token=token))
            else:
                if args.token != token:
                    raise ValueError("Workspace changed. Request deletion and confirm again.")
                parent = data["workspaces"][wid]["parent"] or "general"
                for sid, name, group, hidden in session_rows():
                    if group == wid:
                        assign(data, sid, "archived")
                for name, group in list(data["sessions"].items()):
                    if group == wid:
                        data["origins"][name] = wid
                        data["sessions"][name] = "archived"
                del data["workspaces"][wid]
                for pid in tm("list-panes", "-a", "-F", "#{pane_id}").splitlines():
                    if tm("show-options", "-pqv", "-t", pid, "@workspace-active") == wid:
                        tm("set-option", "-p", "-t", pid, "@workspace-active", parent)
                        tm("set-option", "-p", "-t", pid, "@workspace-header", path_name(data, parent) + " | press ?")
                if not args.quiet:
                    ui.open(data, parent)
                    ui.message("Workspace deleted; sessions kept running in Archive")
        elif action in ("request-purge", "purge"):
            if wid != "archived":
                raise ValueError("Bulk permanent deletion is only available inside Archive.")
            rows = archive_snapshot()
            if not rows:
                raise ValueError("Archive is already empty.")
            if len(rows) >= len(session_rows()):
                raise ValueError("Keep at least one session outside Archive so the server stays running.")
            token = snapshot_token(rows)
            if action == "request-purge":
                launch("confirm-before", "-t", ui.client, "-p",
                       f"PERMANENTLY kill ALL {len(rows)} archived sessions and their processes? (y/n)",
                       ui.call("purge", workspace="archived", token=token))
            else:
                if args.token != token:
                    raise ValueError("Archive changed. Request deletion and confirm again.")
                for sid, name in rows:
                    if int(tm("display-message", "-p", "-t", sid, "#{session_attached}")):
                        raise ValueError("A client attached; permanent deletion stopped.")
                    if tm("display-message", "-p", "-t", sid, "#{@workspace-id}") != "archived":
                        raise ValueError("A session moved; permanent deletion stopped.")
                    tm("kill-session", "-t", sid)
                    data["sessions"].pop(name, None)
                    data["origins"].pop(name, None)
                save = tm("show-options", "-gqv", "@resurrect-save-script-path")
                if save and Path(save).is_file():
                    launch("run-shell", "-b", shlex.quote(save))
                if not args.quiet:
                    ui.open(data, "archived")
                    ui.message("Archive permanently emptied; latest Resurrect save requested")
        elif action in ("request-empty", "empty"):
            rows = sorted((row[0], row[1]) for row in session_rows() if row[2] == wid)
            if not rows:
                raise ValueError("This workspace already has no sessions.")
            if wid == "archived":
                archive_snapshot()  # Keep Archive's attached-session protection.
            token = snapshot_token(rows)
            if action == "request-empty":
                launch("confirm-before", "-t", ui.client, "-p",
                       f"Permanently DELETE {len(rows)} session(s) and processes in {path_name(data, wid)}? Keep workspace; move clients safely? (y/n)",
                       ui.call("empty", workspace=wid, token=token))
            else:
                if args.token != token:
                    raise ValueError("Workspace changed; request deletion and confirm again.")
                rescue = "background" if wid == "general" else "general"
                ensure_session(data, rescue, ui.pane)
                target = next(row[0] for row in session_rows() if row[2] == rescue)
                killed_ids = {sid for sid, name in rows}
                for client_row in tm("list-clients", "-F", "#{client_name}\t#{session_id}").splitlines():
                    other_client, other_session = client_row.split("\t")
                    if other_session in killed_ids:
                        tm("switch-client", "-c", other_client, "-t", target)
                ui.pane = client_pane(ui.client) or ui.pane
                for sid, name in rows:
                    tm("kill-session", "-t", sid)
                    for table in ("sessions", "origins", "locations"):
                        data[table].pop(name, None)
                data["history"].pop(wid, None)
                save = tm("show-options", "-gqv", "@resurrect-save-script-path")
                if save and Path(save).is_file():
                    launch("run-shell", "-b", shlex.quote(save))
                if not args.quiet:
                    ui.open(data, wid)
                    ui.message("All sessions deleted; workspace kept. Use n to create a session.")
        else:
            raise ValueError("Unknown workspace action: " + action)


if __name__ == "__main__":
    # Picker modules import this backend; reuse the running module instead of
    # parsing and executing the same source again during popup startup.
    sys.modules.setdefault("workspaces", sys.modules[__name__])
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, OSError, json.JSONDecodeError) as error:
        message = str(error)
        if "--client" in sys.argv:
            client = sys.argv[sys.argv.index("--client") + 1]
            quiet = "--quiet" in sys.argv and sys.argv[sys.argv.index("--quiet") + 1] == "1"
            if client and not quiet:
                subprocess.run(["tmux", "display-message", "-c", client, "-d", "5000", message])
        print(message, file=sys.stderr)
        sys.exit(1)
