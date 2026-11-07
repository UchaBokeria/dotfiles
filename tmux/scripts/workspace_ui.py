"""Small terminal input/list views; session browsing remains native tmux."""
import curses
import json
from pathlib import Path
import subprocess


def read_name():
    curses.set_escdelay(25)
    def run(screen):
        curses.curs_set(1)
        value = ""
        while True:
            screen.erase()
            screen.addnstr(0, 1, "Name / shortcut (Esc or empty Enter cancels)", max(1, screen.getmaxyx()[1] - 3))
            screen.addnstr(2, 1, "> " + value, max(1, screen.getmaxyx()[1] - 3))
            screen.refresh()
            key = screen.get_wch()
            if key == "\x1b":
                return ""
            if key in ("\n", "\r", curses.KEY_ENTER):
                return value.strip()
            if key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                value = value[:-1]
            elif isinstance(key, str) and key.isprintable():
                value += key
    return curses.wrapper(run)


def workspace_list(args, state):
    curses.set_escdelay(25)
    from workspaces import children, shortcut_map, shortcut_label, shell_command

    helper = Path(__file__).with_name("workspaces.py")
    selected = args.workspace

    def command(action, **values):
        argv = [str(helper), action, "--client", args.client, "--pane", args.pane]
        for key, value in values.items():
            argv += ["--" + key, str(value)]
        return subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run(screen):
        nonlocal selected
        curses.curs_set(0)
        screen.keypad(True)
        while True:
            data = json.loads(Path(state).read_text())
            nodes = []
            def walk(parent, depth):
                slots = {wid: shortcut_label(number) for number, wid in shortcut_map(data, parent).items()}
                for wid in children(data, parent):
                    nodes.append((wid, depth, ("Alt+" if parent else "") + slots.get(wid, "-")))
                    walk(wid, depth + 1)
            walk(None, 0)
            index = next((i for i, row in enumerate(nodes) if row[0] == selected), 0)
            selected = nodes[index][0]
            height, width = screen.getmaxyx()
            top = max(0, min(index - max(1, height - 5) // 2, len(nodes) - max(1, height - 5)))
            screen.erase()
            screen.addnstr(0, 1, "WORKSPACES   j/k move   Enter open   Shift+J/K reorder   Esc close", max(1, width - 2), curses.A_BOLD)
            for y, (wid, depth, shortcut) in enumerate(nodes[top:top + max(1, height - 4)], 2):
                node = data["workspaces"][wid]
                live = set(data.get("live", {}).get("names", {}).values())
                count = sum(group == wid and name in live for name, group in data["sessions"].items())
                label = "  " * depth + shortcut.ljust(7) + " " + node["name"] + " (" + str(count) + ")"
                if wid == args.workspace:
                    label += " [active]"
                screen.addnstr(y, 1, label.ljust(max(1, width - 2)), max(1, width - 2), curses.A_REVERSE if wid == selected else curses.A_NORMAL)
            screen.refresh()
            key = screen.get_wch()
            if key == "\x1b":
                return None
            if key in ("j", curses.KEY_DOWN):
                selected = nodes[min(len(nodes) - 1, index + 1)][0]
            elif key in ("k", curses.KEY_UP):
                selected = nodes[max(0, index - 1)][0]
            elif key in ("J", "K"):
                command("reorder", workspace=selected, direction="down" if key == "J" else "up", quiet="1")
            elif key in ("\n", "\r", curses.KEY_ENTER):
                return selected
    target = curses.wrapper(run)
    if target:
        subprocess.run(["tmux", "run-shell", "-b", "-d", "0.1",
                        shell_command("open", args.client, args.pane, workspace=target)], check=True)
