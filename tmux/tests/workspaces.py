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
            assert tm("show-options", "-qv", "-t", "beta", "@session-picker-hidden") == "1"
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
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "archived"
            key(b"H")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            key(b"\t")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "archived"
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
                              key=lambda key: (key != "general", key == "archived", ws[key]["name"].lower()))
                for item in keys:
                    nodes.append(item)
                    walk(item)
            walk(None)
            shortcut = "1234567890abdefginoqtv"[nodes.index(child)]
            key(shortcut.encode())
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
            key(b"2")  # Alphabetical destination list: Archive, General, ...
            assert member(next_session) == "general" and member("beta") == "archived"
            call("selected-restore", session="beta")
            assert member("beta") == "general"
            clear()
            call("help", workspace="general")
            key(b"\x1b")
            assert "?:keys" in tm("show-options", "-pqv", "-t", pane, "@workspace-header")
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
            # Actual Resurrect save and restore across a disposable server restart.
            tm("set-option", "-g", "@resurrect-dir", str(saves))
            tm("set-option", "-g", "@resurrect-capture-pane-contents", "off")
            clear()
            subprocess.run([str(resurrect / "save.sh")], env=env, check=True, timeout=30,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert (saves / "last").exists()
            # Only this test socket's sessions are stopped; production is untouched.
            for sid in tm("list-sessions", "-F", "#{session_id}").splitlines():
                tm("kill-session", "-t", sid)
            proc.wait(timeout=5)
            os.close(master)
            master = None
            client = None
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
            assert data()["origins"]["saved-archive"] == projects
            assert data()["workspaces"][projects]["name"] == "Projects"
            assert tm("show-hooks", "-g", "after-new-session").count("9271") == 1
            print("PASS: native session/window/pane confirmations; workspace CRUD and protection; H/L/Tab/Shift-Tab; shared Archive z toggle, native h/l collapse and workspace defaults; direct m move; restore to remembered/deleted/new/existing workspace; help; confirmed purge and attached-session protection; unchanged original process PIDs; real Resurrect save/restart/restore retains workspaces and archive origins.")
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
