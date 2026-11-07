#!/usr/bin/env python3
"""Geometry and real-terminal checks for the custom workspace session picker."""
import curses
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from session_picker import Picker, badge_lines, layout, tree_rows
from picker_preview import cells, crop_origin


class Screen:
    def __init__(self, height=36, width=120):
        self.height, self.width = height, width
        self.erase()
    def erase(self): self.lines = [[" "] * self.width for _ in range(self.height)]
    def getmaxyx(self): return self.height, self.width
    def addnstr(self, y, x, text, length, attr=0):
        for index, char in enumerate(text[:length]):
            self.lines[y][x + index] = char
    def refresh(self): pass
    def text(self, row): return "".join(self.lines[row])


def geometry():
    picker = object.__new__(Picker)
    picker.data = {"preferences": {"keys": True, "preview": True}, "workspaces": {
        "project": {"name": "Project Alpha", "parent": None}}}
    picker.workspace, picker.notice = "project", ""
    picker.rows = [{"key": "session:$1", "label": "+ alpha: 1 windows", "preview": "%1"}]
    picker.index, picker.offset, picker.tags, picker.selection_style = 0, 0, set(), curses.A_REVERSE
    picker.draw_preview = lambda screen, area, accent: screen.addnstr(area.preview_top + 1, 2, "LIVE PREVIEW", 30)
    screen = Screen()
    area = picker.render(screen)
    assert "Project Alpha" in screen.text(1)
    badge = badge_lines(picker.data, picker.workspace, screen.width)[0][0][1]
    assert screen.text(1).index(badge) == (screen.width - len(badge)) // 2
    assert not screen.text(2).strip() and not screen.text(3).strip()
    assert "alpha" in screen.text(area.list_top)
    assert area.keys_top + area.keys_height == area.preview_top
    assert "j/k" in screen.text(area.keys_top + 1)[:screen.width // 2]
    assert "0–9" in screen.text(area.keys_top + 1)[screen.width // 2:]
    assert "LIVE PREVIEW" in screen.text(area.preview_top + 1)
    picker.data["preferences"]["preview"] = False
    area = picker.render(screen)
    assert area.preview_top is None and area.keys_top + area.keys_height == screen.height
    assert "─" in screen.text(screen.height - 1)
    picker.data["preferences"]["keys"] = False
    area = picker.render(screen)
    assert area.keys_top is None and area.preview_top is None
    for height in (16, 24, 40):
        area = layout(height, True, True)
        assert area.list_height >= 1 and area.list_top + area.list_height <= height and area.preview_top is not None
    decoded = cells(["\x1b[31mred", "still red\x1b[0m normal", "\x1b[38;2;95;135;175mtrue colour"])
    assert decoded[0][0][1] == decoded[1][0][1] == 1 and decoded[1][-1][1] == -1
    assert decoded[2][0][1] == 67
    assert crop_origin(43, 40, 12, True) == 31
    assert crop_origin(43, 40, 12, False) == 0
    print("PASS: centered title and gap; two columns between list/preview; guide moves to bottom without preview.")


def terminal():
    with tempfile.TemporaryDirectory(prefix="tmux-custom-picker-") as directory:
        socket, state = directory + "/socket", Path(directory) / "state.json"
        env = {**os.environ, "TERM": "xterm-256color", "TMUX_WORKSPACES_STATE": str(state)}
        master = None
        screen = bytearray()
        def tm(*args, check=True):
            return subprocess.run(["tmux", "-S", socket, *args], env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check).stdout.strip()
        def drain(delay=.35):
            end = time.monotonic() + delay
            while time.monotonic() < end:
                if select.select([master], [], [], .02)[0]:
                    try: screen.extend(os.read(master, 65536))
                    except OSError: return
        def key(data): os.write(master, data); drain()
        def data(): return json.loads(state.read_text())
        def wait_for(predicate, seconds=4):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if predicate(): return True
                drain(.1)
            return predicate()
        def call(action, expected=0, **values):
            argv = [str(ROOT / "scripts/workspaces.py"), action, "--client", client, "--pane", pane]
            for name, value in values.items(): argv += ["--" + name, str(value)]
            result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=15)
            assert result.returncode == expected, result.stderr
            drain(.2)
        def member(name): return tm("display-message", "-p", "-t", name, "#{@workspace-id}")
        try:
            tm("-f", "/dev/null", "new-session", "-d", "-s", "alpha", "sleep 180")
            server = tm("display-message", "-p", "#{pid}")
            env["TMUX"] = socket + "," + server + ",0"
            tm("set-option", "-g", "default-shell", "/bin/sh")
            tm("new-session", "-d", "-s", "beta", "sleep 180")
            tm("new-window", "-d", "-t", "beta:1", "sleep 180")
            tm("split-window", "-d", "-t", "beta:0", "sleep 180")
            original = set(tm("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}").splitlines())
            subprocess.run([str(ROOT / "scripts/workspaces.py"), "init"], env=env, check=True)
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
            proc = subprocess.Popen(["tmux", "-S", socket, "attach-session", "-t", "alpha"],
                                    stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            drain(.5)
            client, pane = tm("list-clients", "-F", "#{client_name}\t#{pane_id}").split("\t")
            call("layout", kind="custom")
            call("open", workspace="general")
            drain(.5)
            assert b"General" in screen and b"Shortcuts" in screen and b"Preview" in screen
            picker_pid = tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid")
            assert picker_pid
            # Native row shortcuts and wrapping select real sessions.
            key(b"k\r")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "beta")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            key(b"Gj\r")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "alpha")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            key(b"1")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "beta")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            key(b"0")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "alpha")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            key(b"d\r")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "beta")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            key(b"Gu\r")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "alpha")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            picker_pid = tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid")
            key(b"?")
            assert b"Session picker" in screen
            key(b"\x1b")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid") == picker_pid
            # Root shortcuts are prefixed; Alt shortcuts enter children and
            # then select nested siblings. Empty shortcut slots are harmless.
            call("apply-name", workspace="general", kind="child", name="ChildOne", quiet="1")
            first_child = next(wid for wid, node in data()["workspaces"].items() if node["name"] == "ChildOne")
            call("apply-name", workspace="general", kind="child", name="ChildTwo", quiet="1")
            second_child = next(wid for wid, node in data()["workspaces"].items() if node["name"] == "ChildTwo")
            key(b"\x1b1")
            assert wait_for(lambda: tm("show-options", "-pqv", "-t", pane, "@workspace-active") == first_child)
            key(b"\x1b2")
            assert wait_for(lambda: tm("show-options", "-pqv", "-t", pane, "@workspace-active") == second_child)
            key(b"\x1b9")  # No child slot 9: keep picker alive.
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid") == picker_pid
            key(b"\x021")
            assert wait_for(lambda: tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general")
            key(b"q")
            call("jump", nested="1", slot="1")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "ChildOne-default")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("jump", nested="1", slot="2")
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "ChildTwo-default")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("jump", nested="1", slot="9")
            call("jump", slot="1")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            picker_pid = tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid")
            key(b"L")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "background"
            key(b"H")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general"
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid") == picker_pid
            key(b"b")
            assert data()["preferences"]["keys"] is False
            key(b"b")
            key(b"v")
            assert data()["preferences"]["preview"] is False
            key(b"v")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid") == picker_pid
            # Moving also uses a bounded overlay and keeps the picker alive.
            key(b"j")
            key(b"m")
            key(b"j\r")
            assert wait_for(lambda: member("beta") == first_child)
            key(b"m")
            key(b"k\r")
            assert wait_for(lambda: member("beta") == "general")
            # Familiar collapsed session -> window -> pane navigation.
            key(b"j")
            key(b"l")
            key(b"j")
            key(b"l")
            key(b"j")
            key(b"x")
            key(b"n")
            assert original <= set(tm("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}").splitlines())
            key(b"h")
            key(b"h")
            key(b"g")
            key(b"j")
            key(b"z")
            assert member("beta") == "archived"
            key(b"\x12")
            key(b"z")
            assert member("beta") == "general"
            key(b"c")
            key(b"created\r")
            assert member("created") == "general"
            tm("new-window", "-d", "-t", "created:1", "sleep 180")
            tm("split-window", "-d", "-t", "created:0", "sleep 180")
            drain(.6)
            key(b"\x13")
            key(b"created\r")
            key(b"l")
            key(b"j")
            key(b"l")
            key(b"j")
            key(b"x")
            key(b"y")
            assert len(tm("list-panes", "-t", "created:0").splitlines()) == 1
            key(b"G")
            key(b"x")
            key(b"y")
            assert len(tm("list-windows", "-t", "created").splitlines()) == 1
            key(b"g")
            key(b"\x13")
            key(b"created\r")
            key(b"x")
            key(b"y")
            assert "created" not in tm("list-sessions", "-F", "#{session_name}").splitlines()
            key(b"g")
            key(b"j")
            key(b"l")
            key(b"G")
            key(b"\r")
            drain(.4)
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}:#{window_index}.#{pane_index}") == "beta:1.0")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            key(b"\x02\x1b\t")
            drain(.4)
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "alpha")
            pane = tm("list-clients", "-F", "#{pane_id}")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-open") == ""
            # Workspace-list x cancels, protects built-ins, archives members,
            # and remains usable after a confirmed deletion.
            call("apply-name", workspace="general", kind="create", name="Disposable")
            folder = next(wid for wid, node in data()["workspaces"].items() if node["name"] == "Disposable")
            default_pids = tm("list-panes", "-t", "Disposable-default", "-F", "#{pane_id}:#{pane_pid}")
            key(b"s")
            key(b"x")
            key(b"n")
            assert folder in data()["workspaces"]
            key(b"x")
            key(b"y")
            assert folder not in data()["workspaces"]
            assert member("Disposable-default") == "archived"
            assert tm("list-panes", "-t", "Disposable-default", "-F", "#{pane_id}:#{pane_pid}") == default_pids
            key(b"x")
            assert "general" in data()["workspaces"]
            key(b"\x1b")
            assert wait_for(lambda: bool(tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid"))), bytes(screen[-5000:])
            assert wait_for(lambda: tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "general")
            key(b"\x12")
            assert wait_for(lambda: tm("show-options", "-pqv", "-t", pane, "@workspace-active") == "archived"), (tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid"), bytes(screen[-5000:]))
            key(b"z")
            key(b"Restored/New\r")
            assert wait_for(lambda: data()["workspaces"].get(member("Disposable-default"), {}).get("name") == "New"), (data()["origins"], member("Disposable-default"), bytes(screen[-2500:]))
            group = member("Disposable-default")
            assert data()["workspaces"][group]["name"] == "New"
            key(b"v")
            key(b"b")
            key(b"q")
            call("open", workspace=group)
            assert data()["preferences"] == {"preview": False, "keys": False}
            key(b"\r")
            drain(.4)
            assert tm("list-clients", "-F", "#{session_name}") == "Disposable-default"
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace=group)
            key(b"x")
            key(b"y")
            drain(.5)
            assert "Disposable-default" not in tm("list-sessions", "-F", "#{session_name}").splitlines()
            pane = tm("list-clients", "-F", "#{pane_id}")
            if tm("show-options", "-pqv", "-t", pane, "@workspace-picker-open") != "1":
                call("open", workspace="general")
            # Preview reads the alternate screen, preserves colours, follows
            # the cursor and composes both panes of the session's active window.
            key(b"q")
            code = "import sys,time;sys.stdout.write('\\x1b[?1049h\\x1b[?25h\\x1b[30;5H\\x1b[31mBOTTOM-LEFT\\x1b[0m\\x1b[31;5H');sys.stdout.flush();time.sleep(180)"
            tm("new-session", "-d", "-s", "preview-demo", sys.executable, "-c", code)
            right = code.replace("BOTTOM-LEFT", "BOTTOM-RIGHT").replace("[31m", "[34m")
            tm("split-window", "-h", "-d", "-t", "preview-demo:0", sys.executable, "-c", right)
            other = "import sys,time;sys.stdout.write('\\x1b[?1049h\\x1b[?25lOTHER-WINDOW');sys.stdout.flush();time.sleep(180)"
            tm("new-window", "-d", "-t", "preview-demo:1", sys.executable, "-c", other)
            call("assign", session="preview-demo", destination="general", quiet="1")
            screen.clear()
            call("open", workspace="general")
            if not data()["preferences"]["preview"]: key(b"v")
            key(b"/preview-demo\r")
            drain(1)
            plain = re.sub(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\([A-Z])", b"", bytes(screen))
            assert b"BOTTOM-LEFT" in plain and b"BOTTOM-RIGHT" in plain, bytes(screen[-5000:])
            assert b"[31m" in screen and b"[34m" in screen
            key(b">")
            assert b"OTHER-WINDOW" in screen
            assert tm("display-message", "-p", "-t", "preview-demo", "#{window_index}") == "0"
            key(b"<")
            # Filter and command-on-tags keep the picker open and target the item.
            key(b"f#{==:#{session_name},preview-demo}\r")
            picker_pid = tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid")
            key(b"\x00")
            assert tm("display-message", "-p", "-t", "preview-demo", "#{pane_marked}") == "1"
            key(b"M")
            assert tm("display-message", "-p", "-t", "preview-demo", "#{pane_marked}") == "0"
            key(b"t")
            key(b":set-option -t '%%' @picker-command-test yes\r")
            assert wait_for(lambda: tm("show-options", "-qv", "-t", "preview-demo", "@picker-command-test") == "yes")
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-pid") == picker_pid
            key(b"T")
            key(b"f\x15\r")
            for number in range(9):
                name = "accelerator" + str(number)
                tm("new-session", "-d", "-s", name, "sleep 180")
                call("assign", session=name, destination="general", quiet="1")
            key(b"\x1ba")  # Native row 10 accelerator, after 0–9.
            assert wait_for(lambda: tm("list-clients", "-F", "#{session_name}") == "accelerator7")
            pane = tm("list-clients", "-F", "#{pane_id}")
            call("open", workspace="general")
            tm("detach-client", "-t", client)
            proc.wait(timeout=5)
            deadline = time.monotonic() + 3
            while tm("show-options", "-pqv", "-t", pane, "@workspace-picker-open") and time.monotonic() < deadline:
                time.sleep(.05)
            assert tm("show-options", "-pqv", "-t", pane, "@workspace-picker-open") == ""
            assert original <= set(tm("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}").splitlines())
            assert tm("display-message", "-p", "#{pid}") == server
            print("PASS: wrapping and numbered rows; half-page scrolling; nested Alt shortcuts; help/list overlays; colour alternate-screen split preview and browsing; filter/command; persisted b/v; archive/restore and confirmed deletions; original processes/server intact.")
        finally:
            log = state.with_suffix(".log")
            if log.exists() and log.read_text(): print("UI diagnostics:", log.read_text())
            for sid in tm("list-sessions", "-F", "#{session_id}", check=False).splitlines():
                tm("kill-session", "-t", sid, check=False)
            if master is not None:
                os.close(master)
                proc.wait(timeout=5)


if __name__ == "__main__":
    geometry()
    terminal()
