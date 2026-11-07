#!/usr/bin/env python3
"""Exercise actual native keys and Resurrect on a disposable tmux socket."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/workspaces.py"


def main():
    with tempfile.TemporaryDirectory(prefix="tmux-workspaces-test-") as folder:
        directory = Path(folder)
        socket = str(directory / "socket")
        state = directory / "state.json"
        env = {**os.environ, "TERM": "xterm-256color", "TMUX_WORKSPACES_STATE": str(state)}
        client = None
        master = None
        screen = bytearray()

        def tm(*args, check=True):
            result = subprocess.run(["tmux", "-S", socket, *args], text=True,
                                    capture_output=True, check=check, env=env)
            return result.stdout.rstrip("\n")

        def start(name):
            tm("-f", "/dev/null", "new-session", "-d", "-s", name, "sleep 600")
            env["TMUX"] = socket + "," + tm("display-message", "-p", "#{pid}") + ",0"
            tm("set-environment", "-g", "TMUX_WORKSPACES_STATE", str(state))
            tm("set-option", "-g", "default-shell", "/bin/sh")
            tm("set-option", "-g", "default-command", "")
            tm("set-option", "-g", "mode-keys", "vi")
            tm("set-option", "-g", "status-keys", "vi")

        def drain(seconds=.5):
            if master is None:
                time.sleep(seconds)
                return
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                if select.select([master], [], [], .03)[0]:
                    try:
                        screen.extend(os.read(master, 65536))
                    except OSError:
                        return

        def key(value):
            os.write(master, value)
            drain()

        def wait_for(predicate, seconds=4):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if predicate(): return True
                drain(.1)
            return predicate()

        def data():
            return json.loads(state.read_text())

        def call(action, expected=0, **values):
            args = [str(HELPER), action]
            if client:
                args += ["--client", client, "--pane", pane]
            for name, value in values.items():
                args += ["--" + name.replace("_", "-"), str(value)]
            result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=15)
            assert result.returncode == expected, (args, result.stdout, result.stderr)
            drain(.2)
            return result

        def workspace(name):
            return next(wid for wid, node in data()["workspaces"].items() if node["name"] == name)

        def member(name):
            return tm("display-message", "-p", "-t", name, "#{@workspace-id}")

        def clear():
            key(b"\x1b")

        def select_session(name):
            key(b"g")
            key(b"\x13")
            key(name.encode() + b"\r")

        def originals_alive():
            current = set(tm("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}").splitlines())
            assert set(baseline.splitlines()) <= current

        def create(name, parent="general", kind="create"):
            clear()
            call("apply-name", workspace=parent, kind=kind, name=name)
            assert tm("display-message", "-p", "-t", pane, "#{pane_mode}") == "tree-mode"
            wid = workspace(name)
            assert any(group == wid for group in data()["sessions"].values())
            clear()
            return wid

        try:
            start("alpha")
            tm("new-session", "-d", "-s", "beta", "sleep 600")
            baseline = tm("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            # Existing plugin hooks must survive initialization untouched.
            tm("set-option", "-g", "@resurrect-hook-post-save-all", "true")
            tm("set-option", "-g", "@resurrect-hook-post-restore-all", "true")
            call("init")
            assert member("alpha") == member("beta") == "general"
            assert tm("show-options", "-gqv", "@resurrect-hook-post-restore-all") == "true"
            tm("source-file", str(ROOT / "scripts/session-picker.conf"))
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 48, 160, 0, 0))
            proc = subprocess.Popen(["tmux", "-S", socket, "attach-session", "-t", "alpha"],
                                    stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            drain(1)
            client = tm("list-clients", "-F", "#{client_name}")
            pane = tm("display-message", "-p", "-t", "alpha", "#{pane_id}")
            key(b"\x02s")
            assert tm("display-message", "-p", "-t", pane, "#{pane_mode}") == "tree-mode"
            key(b"j")
            key(b"z")
            assert wait_for(lambda: tm("show-options", "-qv", "-t", "beta", "@session-picker-hidden") == "1")
            key(b"\x12")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "archived"
            key(b"\x12")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            key(b"\x12")
            key(b"G")
            key(b"z")
            assert tm("show-options", "-qv", "-t", "beta", "@session-picker-hidden") == "0"
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            key(b"L")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "background"
            key(b"H")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            key(b"\t")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "background"
            key(b"\x1b[Z")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            # Actual native manager -> name popup -> new session -> kill prompt.
            key(b"w")
            key(b"c")
            key(b"Keyboard\r")
            drain(1)
            keyboard = workspace("Keyboard")
            assert tm("display-message", "-p", "-t", pane, "#{pane_mode}") == "tree-mode"
            assert member("Keyboard-default") == keyboard
            key(b"c")
            key(b"from-menu\r")
            drain(1)
            assert member("from-menu") == keyboard
            tm("new-window", "-d", "-t", "from-menu", "-n", "extra", "sleep 600")
            tm("split-window", "-d", "-t", "from-menu:0", "sleep 600")
            clear()
            call("open", workspace=keyboard)
            select_session("from-menu")
            key(b"\x1b[C")
            key(b"j")
            key(b"x")
            key(b"n")
            assert len(tm("list-windows", "-t", "from-menu").splitlines()) == 2
            key(b"\x1b[C")
            key(b"j")
            key(b"x")
            key(b"n")
            assert len(tm("list-panes", "-t", "from-menu:0").splitlines()) == 2
            clear()
            call("open", workspace=keyboard)
            select_session("from-menu")
            key(b"x")
            key(b"n")
            assert member("from-menu") == keyboard
            key(b"x")
            key(b"y")
            drain(1)
            assert "from-menu" not in tm("list-sessions", "-F", "#{session_name}").splitlines()
            assert tm("display-message", "-p", "-t", pane, "#{pane_mode}") == "tree-mode", "Workspace must retain its default session"
            projects = create("Projects")
            child = create("App", projects, "child")
            assert data()["workspaces"][child]["parent"] == projects
            # s lists every level, and selecting a nested row returns to the
            # native session tree rather than the workspace options menu.
            call("open", workspace="general")
            before_list = len(screen)
            key(b"s")
            rendered = bytes(screen[before_list:])
            assert all(name.encode() in rendered for name in ("General", "Projects", "App", "Keyboard", "Archive"))
            nodes = []
            def walk(parent):
                ws = data()["workspaces"]
                keys = sorted((key for key, node in ws.items() if node["parent"] == parent),
                              key=lambda key: (2 if key == "archived" else 1 if key == "background" else 0, ws[key]["order"]))
                for item in keys:
                    nodes.append(item)
                    walk(item)
            walk(None)
            # The list starts on active General; navigate to the nested row.
            key(b"j" * nodes.index(child))
            key(b"\r")
            drain(.5)
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == child
            assert tm("display-message", "-p", "-t", pane, "#{pane_mode}") == "tree-mode"
            assert member("App-default") == child
            call("request-delete", expected=1, workspace=projects)
            call("apply-name", workspace=child, kind="rename", name="Mobile")
            clear()
            assert data()["workspaces"][child]["name"] == "Mobile"
            call("assign", workspace="general", destination=child, session="beta")
            assert member("beta") == child
            call("move-workspace", workspace=child, destination="general")
            assert data()["workspaces"][child]["parent"] == "general"
            call("move-workspace", expected=1, workspace="general", destination=child)
            call("move-workspace", expected=1, workspace=child, destination=child)
            call("request-delete", expected=1, workspace="general")
            call("request-delete", expected=1, workspace="archived")
            call("delete", expected=1, workspace=child, token="not-confirmed")
            assert child in data()["workspaces"] and member("beta") == child
            call("request-delete", workspace=child)
            key(b"n")
            assert child in data()["workspaces"]
            call("request-delete", workspace=child)
            key(b"y")
            assert child not in data()["workspaces"]
            assert member("beta") == "archived"
            originals_alive()
            # Shared archive, missing-origin prompt, creating nested destinations.
            clear()
            call("open", workspace=projects)
            key(b"\x12")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "archived"
            select_session("beta")
            key(b"z")
            key(b"Recovered/New\r")
            drain(1)
            recovered = workspace("New")
            assert member("beta") == recovered
            assert data()["workspaces"][recovered]["parent"] == workspace("Recovered")
            call("selected-hide", session="beta")
            key(b"\x12")
            select_session("beta")
            key(b"z")
            assert member("beta") == recovered, "Restore must return to remembered origin"
            call("request-delete", workspace=recovered)
            key(b"y")
            key(b"\x12")
            select_session("beta")
            key(b"z")
            key(b"General\r")
            drain(1)
            assert member("beta") == "general", "Missing origin can restore into existing workspace"
            # Archive must be collapsed: j then m acts on the next SESSION.
            clear()
            call("selected-hide", session="beta")
            tm("new-session", "-d", "-s", "gamma", "sleep 600")
            call("assign", session="gamma", destination="archived")
            archive_rows = sorted((r.split("\t") for r in tm("list-sessions", "-F", "#{session_id}\t#{session_name}\t#{@workspace-id}").splitlines() if r.split("\t")[2] == "archived"), key=lambda r: int(r[0][1:]))
            next_session = archive_rows[1][1]
            key(b"g")
            key(b"l")
            key(b"h")  # Must collapse again, with no archiving side effect.
            key(b"j")
            key(b"m")
            key(b"3")  # Alphabetical destination list: Archive, Background, General, ...
            assert wait_for(lambda: member(next_session) == "general" and member("beta") == "archived"), (next_session, tm("list-sessions", "-F", "#{session_name}:#{@workspace-id}"), bytes(screen[-2500:]))
            call("selected-restore", session="beta")
            assert member("beta") == "general"
            clear()
            call("help", workspace="general")
            key(b"\x1b")
            header = tm("show-options", "-pqv", "-t", pane, "@workspace-header")
            assert "b:keys" not in header and "?:help" in header and "m:move" not in header
            # Purge requires confirmation and protects all attached sessions.
            resurrect = ROOT / "plugins/tmux-resurrect/scripts"
            saves = directory / "resurrect"
            tm("set-option", "-g", "@resurrect-dir", str(saves))
            tm("set-option", "-g", "@resurrect-save-script-path", str(resurrect / "save.sh"))
            for name in ("purge-a", "purge-b"):
                tm("new-session", "-d", "-s", name, "sleep 600")
                call("assign", session=name, destination="archived")
            clear()
            call("assign", session="alpha", destination="archived")
            call("request-purge", expected=1, workspace="archived")
            clear()
            call("assign", session="alpha", destination="general")
            clear()
            call("open", workspace="archived")
            key(b"D")
            key(b"n")
            assert member("purge-a") == "archived"
            call("purge", expected=1, workspace="archived", token="unconfirmed")
            key(b"D")
            key(b"y")
            drain(1)
            assert not any(name.startswith("purge-") for name in tm("list-sessions", "-F", "#{session_name}").splitlines())
            assert "purge-a" not in data()["sessions"]
            deadline = time.monotonic() + 8
            while not (saves / "last").exists() and time.monotonic() < deadline:
                drain(.2)
            snapshot = (saves / "last").read_text()
            assert "purge-a" not in snapshot and "purge-b" not in snapshot
            originals_alive()
            # Persistent preview/help toggles, and no native-mode teardown when
            # filtering between two populated workspaces.
            clear()
            call("open", workspace="general")
            key(b"v")
            key(b"b")
            assert data()["preferences"] == {"preview": False, "keys": False}
            clear()
            drain()
            call("open", workspace=keyboard)
            assert data()["preferences"] == {"preview": False, "keys": False}
            mode_log = str(directory / "mode-events")
            tm("set-hook", "-g", "pane-mode-changed[9800]", 'run-shell "printf mode >> ' + mode_log + '"')
            call("open", workspace="general")
            drain()
            assert not Path(mode_log).exists(), "Workspace navigation tore down native mode"
            tm("set-hook", "-gu", "pane-mode-changed[9800]")
            # Enter must activate the HIGHLIGHTED menu item. Escape and an
            # empty name cancel without creating anything.
            clear()
            call("menu", workspace="general")
            key(b"\x1b[B" * 9)
            before_prompt = len(screen)
            key(b"\r")
            assert b"Name / shortcut" in bytes(screen[before_prompt:])
            before_names = set(data()["workspaces"])
            key(b"\x1b")
            assert set(data()["workspaces"]) == before_names
            call("prompt", workspace="general", kind="child")
            key(b"\r")
            assert set(data()["workspaces"]) == before_names
            call("prompt", workspace="general", kind="child")
            key(b"\x1b")
            assert set(data()["workspaces"]) == before_names
            # The workspace list reorders the highlighted sibling with J/K.
            clear()
            call("open", workspace="general")
            before_list = len(screen)
            key(b"s")
            assert b"F11" in bytes(screen[before_list:]) and b"F12" in bytes(screen[before_list:])
            original_order = data()["workspaces"]["general"]["order"]
            key(b"J")
            assert data()["workspaces"]["general"]["order"] != original_order
            assert data()["general_fixed"] is False
            key(b"\x1b")
            call("open", workspace="general")
            key(b"1")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == keyboard
            key(b"2")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            key(b"s")
            key(b"K")
            assert data()["workspaces"]["general"]["order"] == original_order
            key(b"\x1b")
            call("apply-name", workspace="background", kind="shortcut", name="F2")
            assert data()["workspaces"]["background"]["shortcut"] == 12
            clear()
            call("apply-name", workspace="background", kind="shortcut", name="F11")
            clear()
            key(b"\x02\x1b[23~")  # prefix F11 -> Background
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "background"
            clear()
            key(b"\x02\x1b[24~")  # prefix F12 -> Archive
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "archived"
            clear()
            key(b"\x021")  # General is back at position 1 after moving up.
            assert tm("list-clients", "-F", "#{session_name}") in {row.split("\t")[0] for row in tm("list-sessions", "-F", "#{session_name}\t#{@workspace-id}").splitlines() if row.endswith("\tgeneral")}
            right_style = tm("show-options", "-gqv", "status-right")
            for option, value in (("@bw_accent", "#c56b3d"), ("@bw_on_accent", "#111211")):
                tm("set-option", "-g", option, value)
            call("init")
            styled = tm("show-options", "-gqv", "status-left")
            assert "" in styled and "@bw_accent" in styled and "m:move" not in styled
            assert tm("show-options", "-gqv", "status-right") == right_style
            history_ws = create("History")
            nested_ws = create("Nested", history_ws, "child")
            for name in ("hist-one", "hist-two"):
                tm("new-session", "-d", "-s", name, "sleep 600")
                call("assign", session=name, destination=history_ws)
            clear()
            for name in ("hist-one", "hist-two", "alpha", "hist-two"):
                tm("switch-client", "-c", client, "-t", name)
                drain()
            key(b"\x02\x1b[Z")
            assert tm("list-clients", "-F", "#{session_name}") == "hist-one"
            key(b"\x02\x1b[Z")
            assert tm("list-clients", "-F", "#{session_name}") == "hist-two"
            tm("switch-client", "-c", client, "-t", "alpha")
            drain()
            tm("switch-client", "-c", client, "-t", "hist-two")
            drain()
            key(b"\x02\x1b\t")
            assert tm("list-clients", "-F", "#{session_name}") == "alpha"
            key(b"\x02\x1b\t")
            assert tm("list-clients", "-F", "#{session_name}") == "hist-two"
            key(b"\x02\x1b1")
            assert tm("list-clients", "-F", "#{session_name}") == "Nested-default"
            key(b"\x02\x1b\t")
            assert tm("list-clients", "-F", "#{session_name}") == "hist-two"
            pane = tm("list-clients", "-F", "#{pane_id}")
            # Confirmed emptying can remove the current workspace's sessions;
            # clients are moved safely, its folder and nested folders survive.
            call("request-empty", workspace=history_ws)
            key(b"n")
            assert member("hist-two") == history_ws
            call("request-empty", workspace=history_ws)
            key(b"y")
            pane = tm("list-clients", "-F", "#{pane_id}")
            assert history_ws in data()["workspaces"] and nested_ws in data()["workspaces"]
            assert not any(group == history_ws for group in data()["sessions"].values())
            assert tm("display-message", "-p", "-t", pane, "#{pane_mode}") != "tree-mode"
            key(b"n")
            key(b"reborn\r")
            drain(1)
            assert member("reborn") == history_ws
            clear()
            originals_alive()
            # Persistence and external rename hooks.
            clear()
            call("assign", workspace="general", destination=projects, session="beta")
            tm("rename-session", "-t", "beta", "beta-renamed")
            drain()
            assert data()["sessions"]["beta-renamed"] == projects
            clear()
            call("assign", session="alpha", destination=projects)
            tm("new-session", "-d", "-s", "saved-archive", "sleep 600")
            call("assign", session="saved-archive", destination=projects)
            call("selected-hide", session="saved-archive")
            clear()
            tm("new-window", "-d", "-t", "beta-renamed:4", "sleep 600")
            tm("split-window", "-d", "-t", "beta-renamed:4", "sleep 600")
            tm("switch-client", "-c", client, "-t", "beta-renamed")
            tm("select-window", "-t", "beta-renamed:4")
            tm("select-pane", "-t", "beta-renamed:4.1")
            drain(1)
            assert data()["focus"] == {"session": "beta-renamed", "workspace": projects, "window": "4", "pane": "1"}
            call("reorder-session", workspace=projects, session="beta-renamed", direction="down")
            saved_order = data()["session_order"][projects][:]
            assert "beta-renamed" in saved_order and "beta" not in saved_order
            # Actual Resurrect save and restore across a disposable server restart.
            tm("set-option", "-g", "@resurrect-dir", str(saves))
            tm("set-option", "-g", "@resurrect-capture-pane-contents", "off")
            clear()
            subprocess.run([str(resurrect / "save.sh")], env=env, check=True, timeout=30,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert (saves / "last").exists()
            # Only this test socket's sessions are stopped; production is untouched.
            old_server = tm("display-message", "-p", "#{pid}")
            for sid in tm("list-sessions", "-F", "#{session_id}").splitlines():
                tm("kill-session", "-t", sid)
            proc.wait(timeout=5)
            os.close(master)
            master = None
            client = None
            deadline = time.monotonic() + 8
            status = Path("/proc") / old_server / "status"
            while status.exists() and time.monotonic() < deadline:
                try:
                    if status.read_text().split("State:", 1)[1].split()[0] == "Z":
                        break
                except (FileNotFoundError, ProcessLookupError):
                    break
                time.sleep(.05)
            start("bootstrap")
            tm("source-file", str(ROOT / "scripts/session-picker.conf"))
            call("init")
            tm("set-option", "-g", "@resurrect-dir", str(saves))
            subprocess.run([str(resurrect / "restore.sh")], env=env, check=True, timeout=30,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            drain(2)
            assert member("alpha") == projects
            assert member("beta-renamed") == projects
            assert member("saved-archive") == "archived"
            assert data()["session_order"][projects] == saved_order
            assert data()["origins"]["saved-archive"] == projects
            assert data()["workspaces"][projects]["name"] == "Projects"
            assert tm("show-hooks", "-g", "after-new-session").count("9271") == 1
            assert data()["preferences"] == {"preview": False, "keys": False}
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 48, 160, 0, 0))
            proc = subprocess.Popen(["tmux", "-S", socket, "attach-session", "-t", "bootstrap"],
                                    stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            drain(2)
            assert tm("list-clients", "-F", "#{session_name}:#{window_index}.#{pane_index}") == "beta-renamed:4.1"
            print("PASS: native CRUD/delete guards; local/global session history; numeric/nested shortcuts and reordering; Enter and Escape; empty workspace retention; persistent preview and session order; in-place native navigation; theme pills; archive/move/purge; unchanged original processes; real Resurrect restart restores exact session/window/pane and preferences.")
        finally:
            tm("set-hook", "-gu", "session-closed[9271]", check=False)
            log = state.with_suffix(".log")
            if log.exists() and log.read_text():
                print("Native UI diagnostics:", log.read_text())
            result = tm("list-sessions", "-F", "#{session_id}", check=False)
            for sid in result.splitlines():
                tm("kill-session", "-t", sid, check=False)
            if master is not None:
                os.close(master)


if __name__ == "__main__":
    main()
