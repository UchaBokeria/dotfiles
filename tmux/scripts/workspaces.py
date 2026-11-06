#!/usr/bin/env python3
"""Persistent workspace folders around tmux's native session tree."""
import argparse
from contextlib import contextmanager
import fcntl
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
SYSTEM = {"general", "archived"}


def tm(*args):
    return subprocess.check_output(["tmux", *map(str, args)], text=True).rstrip("\n")


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


def state_path():
    override = os.environ.get("TMUX_WORKSPACES_STATE")
    if override:
        return Path(override)
    socket = tm("display-message", "-p", "#{socket_path}")
    suffix = "" if Path(socket).name == "default" else "-" + hashlib.sha256(socket.encode()).hexdigest()[:12]
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "tmux" / ("workspaces" + suffix + ".json")


def session_rows():
    return [row.split("\t") for row in tm("list-sessions", "-F",
        "#{session_id}\t#{session_name}\t#{@workspace-id}\t#{@session-picker-hidden}").splitlines()]


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
                  key=lambda key: (key != "general", key == "archived", data["workspaces"][key]["name"].lower()))


def valid_name(data, name, parent, exclude=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}", name):
        raise ValueError("Use 1-40 letters, numbers, spaces, dots, underscores or hyphens.")
    if any(key != exclude and node["parent"] == parent and node["name"].casefold() == name.casefold()
           for key, node in data["workspaces"].items()):
        raise ValueError("That workspace name already exists here.")


def sync(data):
    rows = session_rows()
    server = tm("display-message", "-p", "#{pid}")
    previous = data.get("live", {})
    old_names = previous.get("names", {}) if previous.get("server") == server else {}
    for sid, name, stored, hidden in rows:
        old = old_names.get(sid)
        if old and old != name:
            for table in ("sessions", "origins"):
                if old in data[table]:
                    data[table][name] = data[table].pop(old)
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
            tm("set-option", "-t", sid, "@workspace-id", wid)
        wanted_hidden = "1" if wid == "archived" else "0"
        if hidden != wanted_hidden:
            tm("set-option", "-t", sid, "@session-picker-hidden", wanted_hidden)
        label = path_name(data, wid)
        if tm("show-options", "-qv", "-t", sid, "@workspace-label") != label:
            tm("set-option", "-t", sid, "@workspace-label", label)
    data["live"] = {"server": server, "names": {row[0]: row[1] for row in rows}}


def assign(data, sid, wid):
    if wid not in data["workspaces"]:
        raise ValueError("Workspace no longer exists.")
    name = tm("display-message", "-p", "-t", sid, "#{session_name}")
    previous = tm("display-message", "-p", "-t", sid, "#{@workspace-id}")
    if wid == "archived" and previous != "archived":
        data["origins"][name] = previous if previous in data["workspaces"] else "general"
    elif wid != "archived":
        data["origins"].pop(name, None)
    tm("set-option", "-t", sid, "@workspace-id", wid)
    tm("set-option", "-t", sid, "@workspace-label", path_name(data, wid))
    tm("set-option", "-t", sid, "@session-picker-hidden", "1" if wid == "archived" else "0")
    data["sessions"][name] = wid


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

    def header(self, data, wid):
        peers = children(data, data["workspaces"][wid]["parent"])
        tabs = " ".join(("[" + data["workspaces"][key]["name"] + "]") if key == wid
                        else data["workspaces"][key]["name"] for key in peers)
        parent = data["workspaces"][wid]["parent"]
        label = "WS " + ((path_name(data, wid) + " | ") if parent else "") + tabs
        if len(label) > 70:
            label = "WS [" + path_name(data, wid) + "]"
        label += " | ?:keys w:menu H/L Tab:WS C-r:Archive m:move"
        tm("set-option", "-p", "-t", self.pane, "@workspace-active", wid)
        tm("set-option", "-p", "-t", self.pane, "@workspace-header", label)

    def close_tree(self):
        if tm("display-message", "-p", "-t", self.pane, "#{pane_mode}") == "tree-mode":
            tm("send-keys", "-t", self.pane, "q")

    def open(self, data, wid):
        previous = tm("show-options", "-pqv", "-t", self.pane, "@workspace-active")
        if wid == "archived" and previous != "archived":
            tm("set-option", "-p", "-t", self.pane, "@workspace-return", previous if previous in data["workspaces"] else "general")
        self.header(data, wid)
        self.close_tree()
        rows = [row for row in session_rows() if row[2] == wid]
        if not rows:
            self.menu(data, wid, empty=True)
            return
        filter_ = "#{==:#{@workspace-id}," + wid + "}"
        tm("choose-tree", "-t", self.pane, "-Zs", "-f", filter_)
        tm("send-keys", "-t", self.pane, "M--")

    def menu(self, data, wid, empty=False):
        self.header(data, wid)
        title = "Workspace: " + path_name(data, wid)
        args = ["display-menu", "-c", self.client, "-t", self.pane, "-T", title, "-x", "C", "-y", "C", "--"]

        def add(label, key="-", action=""):
            args.extend([label, key, action] if label else [""])

        if empty:
            add("-No sessions in this workspace")
        add("Sessions (j/k navigate; h archive; u restore)", "s", self.call("open", workspace=wid))
        add("Toggle shared Archive (Ctrl+R)", "C-r", self.call("toggle-archive", workspace=wid))
        add("All keys / help", "?", self.call("help", workspace=wid))
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
        if wid == "archived":
            add("Permanently delete ALL archived sessions...", "D", self.call("request-purge", workspace=wid))
        add("Close", "Escape", "")
        launch(*args)

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
        launch("display-popup", "-c", self.client, "-t", self.pane, "-E", "-w", "64", "-h", "8",
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
            ("Sessions: j/k or arrows; Enter select; q/Esc close", "s", self.call("open", workspace=wid)),
            ("Previous workspace: Shift+H / Shift+Tab", "H", self.call("previous", workspace=wid)),
            ("Next workspace: Shift+L / Tab", "L", self.call("next", workspace=wid)),
            ("Previous workspace (Shift+Tab)", "BTab", self.call("previous", workspace=wid)),
            ("Next workspace (Tab)", "Tab", self.call("next", workspace=wid)),
            ("Toggle shared Archive / return", "C-r", self.call("toggle-archive", workspace=wid)),
            ("Workspace CRUD / session actions: w (or prefix W)", "w", self.call("menu", workspace=wid)),
            ("-h: archive selected session; u: restore to origin", "-", ""),
            ("-m: move selected session; R: rename; c: new session", "-", ""),
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
            found = uuid.uuid4().hex[:16]
            data["workspaces"][found] = {"name": part, "parent": parent}
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


def install():
    # Preserve theme/plugin output and their hooks. Repeated loads are idempotent.
    current = tm("show-options", "-gqv", "status-left")
    if "@workspace-header" not in current:
        tm("set-option", "-g", "@workspaces-base-status-left", current)
    base = tm("show-options", "-gqv", "@workspaces-base-status-left")
    tm("set-option", "-g", "status-left",
       "#{?#{==:#{pane_mode},tree-mode},#[bold]#{@workspace-header}#[default],"
       "#[bold]WS #{?@workspace-label,#{@workspace-label},General}#[default] | " + base + "}")
    hook = callback("sync")
    for name in ("after-new-session", "session-renamed"):
        tm("set-hook", "-g", name + "[9271]", hook)
    tm("set-hook", "-g", "client-attached[9271]", callback("init"))
    tm("set-hook", "-g", "session-closed[9271]", callback("refresh"))
    tm("set-hook", "-g", "client-session-changed[9271]",
       callback("activate", "#{client_name}", "#{pane_id}"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action")
    for key in ("client", "pane", "workspace", "session", "kind", "destination", "token", "name", "page"):
        parser.add_argument("--" + key, default="")
    args = parser.parse_args()
    ui = UI(args)
    action = args.action
    if action == "input":
        try:
            print("Enter a name (empty cancels).")
            name = input("Name: ").strip()
            if name:
                pattern = r"[A-Za-z0-9][A-Za-z0-9 _./-]{0,199}" if args.kind == "restore" else r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}"
                if not re.fullmatch(pattern, name):
                    raise ValueError("Use 1-40 letters, numbers, spaces, dots, underscores or hyphens.")
                tm("run-shell", "-b", "-d", "0.2", shell_command("apply-name", args.client, args.pane,
                    workspace=args.workspace, kind=args.kind, session=args.session, name=name))
        except (EOFError, KeyboardInterrupt):
            pass
        return
    if action in ("hide", "restore", "session-menu", "session-rename", "move"):
        ui.selected(action)
        return
    if action == "init":
        install()
    with database() as data:
        sync(data)
        if action in ("init", "sync"):
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
        wid = ui.current(data)
        if action == "activate":
            wid = tm("display-message", "-p", "-t", ui.pane, "#{@workspace-id}")
            ui.header(data, wid if wid in data["workspaces"] else "general")
        elif action in ("next", "previous"):
            peers = children(data, data["workspaces"][wid]["parent"])
            wid = peers[(peers.index(wid) + (1 if action == "next" else -1)) % len(peers)]
            ui.open(data, wid)
        elif action in ("parent", "child"):
            parent = data["workspaces"][wid]["parent"]
            nodes = children(data, wid)
            ui.open(data, parent if action == "parent" and parent else nodes[0] if action == "child" and nodes else wid)
        elif action == "open":
            ui.open(data, wid)
        elif action == "toggle-archive":
            previous = tm("show-options", "-pqv", "-t", ui.pane, "@workspace-return")
            destination = (previous if previous in data["workspaces"] and previous != "archived" else "general") if wid == "archived" else "archived"
            ui.open(data, destination)
        elif action == "help":
            ui.help(wid)
        elif action in ("menu", "selected-session-menu"):
            ui.menu(data, wid)
        elif action in ("selected-hide", "selected-restore"):
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
            elif args.kind in ("create", "child", "rename"):
                if args.kind == "child" and wid == "archived":
                    raise ValueError("Archive is shared and cannot contain child workspaces.")
                if args.kind == "rename" and wid in SYSTEM:
                    raise ValueError("General and Archive are protected.")
                parent = wid if args.kind == "child" else node["parent"]
                valid_name(data, args.name, parent, wid if args.kind == "rename" else None)
                if args.kind == "rename":
                    node["name"] = args.name
                else:
                    wid = uuid.uuid4().hex[:16]
                    data["workspaces"][wid] = {"name": args.name, "parent": parent}
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
            ui.open(data, wid)
        elif action == "destinations":
            ui.destinations(data, wid)
        elif action == "assign":
            assign(data, args.session, args.destination)
            ui.open(data, args.destination)
        elif action == "move-workspace":
            if wid in SYSTEM:
                raise ValueError("General and Archive are protected.")
            parent = None if args.destination == "top" else args.destination
            if parent == "archived":
                raise ValueError("Archive is shared and cannot contain child workspaces.")
            if parent is not None and (parent not in data["workspaces"] or descendant(data, parent, wid)):
                raise ValueError("A workspace cannot contain itself.")
            valid_name(data, data["workspaces"][wid]["name"], parent, wid)
            data["workspaces"][wid]["parent"] = parent
            sync(data)
            ui.open(data, wid)
        elif action in ("request-delete", "delete"):
            if wid in SYSTEM:
                raise ValueError("General and Archive cannot be deleted.")
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
                        tm("set-option", "-p", "-t", pid, "@workspace-header", "WS [" + path_name(data, parent) + "]")
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
                ui.open(data, "archived")
                ui.message("Archive permanently emptied; latest Resurrect save requested")
        else:
            raise ValueError("Unknown workspace action: " + action)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, OSError, json.JSONDecodeError) as error:
        message = str(error)
        if "--client" in sys.argv:
            client = sys.argv[sys.argv.index("--client") + 1]
            if client:
                subprocess.run(["tmux", "display-message", "-c", client, "-d", "5000", message])
        print(message, file=sys.stderr)
        sys.exit(1)
