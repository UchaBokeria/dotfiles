#!/usr/bin/env python3
"""Closing/reconnecting must retain the exact pane without restarting tmux."""
import fcntl
import json
import os
from pathlib import Path
import pty
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="tmux-reconnect-test-") as directory:
        socket = directory + "/socket"
        state = directory + "/state.json"
        env = {**os.environ, "TERM": "xterm-256color", "TMUX_WORKSPACES_STATE": state}
        handles = []
        def tm(*args, check=True):
            return subprocess.run(["tmux", "-S", socket, *args], env=env, check=check,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
        def attach(name):
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
            proc = subprocess.Popen(["tmux", "-S", socket, "attach-session", "-t", name],
                                    stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            handles.append((master, proc))
            return proc
        try:
            tm("-f", "/dev/null", "new-session", "-d", "-s", "resume-target", "sleep 120")
            server = tm("display-message", "-p", "#{pid}")
            env["TMUX"] = socket + "," + server + ",0"
            tm("set-option", "-g", "default-shell", "/bin/sh")
            tm("set-environment", "-g", "TMUX_WORKSPACES_STATE", state)
            subprocess.run([str(ROOT / "scripts/workspaces.py"), "init"], env=env, check=True)
            tm("new-window", "-d", "-t", "resume-target:3", "sleep 120")
            tm("split-window", "-d", "-t", "resume-target:3", "sleep 120")
            tm("new-session", "-d", "-s", "different", "sleep 120")
            first = attach("resume-target")
            time.sleep(.6)
            client = tm("list-clients", "-F", "#{client_name}")
            # Existing servers have no older per-workspace metadata on the
            # first installation. Seed from tmux's recent sessions locally.
            for expected in ("different", "resume-target"):
                subprocess.run([str(ROOT / "scripts/workspaces.py"), "last-local", "--client", client,
                                "--pane", tm("list-clients", "-F", "#{pane_id}")], env=env, check=True)
                assert tm("list-clients", "-F", "#{session_name}") == expected
            tm("rename-session", "-t", "resume-target", "renamed")
            time.sleep(.3)
            saved = json.loads(Path(state).read_text())
            assert saved["focus"]["session"] == "renamed"
            assert saved["history"]["general"]["current"] == "renamed"
            tm("rename-session", "-t", "renamed", "resume-target")
            time.sleep(.3)
            tm("select-window", "-t", "resume-target:3")
            tm("select-pane", "-t", "resume-target:3.1")
            assert tm("list-clients", "-F", "#{window_index}.#{pane_index}") == "3.1"
            tm("detach-client", "-t", client)
            first.wait(timeout=5)
            time.sleep(.7)
            saved = json.loads(Path(state).read_text())["detached_focus"]
            assert (saved["session"], saved["window"], saved["pane"]) == ("resume-target", "3", "1"), saved
            attach("different")
            time.sleep(2)
            assert tm("list-clients", "-F", "#{session_name}:#{window_index}.#{pane_index}") == "resume-target:3.1"
            assert tm("display-message", "-p", "#{pid}") == server
            client = tm("list-clients", "-F", "#{client_name}")
            subprocess.run([str(ROOT / "scripts/workspaces.py"), "request-empty", "--client", client,
                            "--pane", tm("list-clients", "-F", "#{pane_id}"), "--workspace", "general"], env=env, check=True)
            time.sleep(.3)
            tm("send-keys", "-K", "-c", client, "y")
            time.sleep(1)
            saved = json.loads(Path(state).read_text())
            assert not any(group == "general" for group in saved["sessions"].values())
            assert "general" in saved["workspaces"]
            assert tm("list-clients", "-F", "#{session_name}") == "Background-default"
            assert tm("display-message", "-p", "#{pid}") == server
            print("PASS: legacy local-history seeding; detach/reconnect restores exact focus; emptying all current sessions moves clients to Background and preserves the server.")
        finally:
            for sid in tm("list-sessions", "-F", "#{session_id}", check=False).splitlines():
                tm("kill-session", "-t", sid, check=False)
            for master, proc in handles:
                os.close(master)
                proc.wait(timeout=5)


if __name__ == "__main__":
    main()
