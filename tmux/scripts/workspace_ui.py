"""Terminal input and hierarchical workspace list views."""
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


def workspace_list(args, state, screen=None):
    curses.set_escdelay(25)
    from workspaces import SYSTEM, children, deletion_token, path_name, shortcut_map, shortcut_label, shell_command
    from session_picker import read_key, slot_key

    helper = Path(__file__).with_name("workspaces.py")
    selected = args.workspace
    notice = ""

    def command(action, **values):
        argv = [str(helper), action, "--client", args.client, "--pane", args.pane]
        for key, value in values.items():
            argv += ["--" + key, str(value)]
        return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def run(screen):
        nonlocal selected, notice
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
            screen.addnstr(0, 1, "WORKSPACES   j/k move   Enter open   J/K reorder   x delete   Esc close", max(1, width - 2), curses.A_BOLD)
            for y, (wid, depth, shortcut) in enumerate(nodes[top:top + max(1, height - 4)], 2):
                node = data["workspaces"][wid]
                live = set(data.get("live", {}).get("names", {}).values())
                count = sum(group == wid and name in live for name, group in data["sessions"].items())
                label = "  " * depth + shortcut.ljust(7) + " " + node["name"] + " (" + str(count) + ")"
                if wid == args.workspace:
                    label += " [active]"
                screen.addnstr(y, 1, label.ljust(max(1, width - 2)), max(1, width - 2), curses.A_REVERSE if wid == selected else curses.A_NORMAL)
            if notice:
                screen.addnstr(height - 1, 1, notice, max(1, width - 2), curses.A_BOLD)
            screen.refresh()
            try:
                key = read_key(screen)
            except curses.error:
                continue
            if key == "\x1b":
                return None
            alt = isinstance(key, tuple) and key[0] == "alt"
            number = slot_key(key[1] if alt else key)
            if number:
                target = shortcut_map(data, args.workspace if alt else None).get(number)
                if target:
                    return target
            if key in ("j", curses.KEY_DOWN):
                selected = nodes[min(len(nodes) - 1, index + 1)][0]
            elif key in ("k", curses.KEY_UP):
                selected = nodes[max(0, index - 1)][0]
            elif key in ("J", "K"):
                command("reorder", workspace=selected, direction="down" if key == "J" else "up", quiet="1")
            elif key == "x":
                if selected in SYSTEM:
                    notice = "General, Background and Archive are protected."
                elif children(data, selected):
                    notice = "Delete child workspaces first; each has its own confirmation."
                else:
                    count = sum(group == selected and name in live for name, group in data["sessions"].items())
                    question = f"Delete {path_name(data, selected)}? Archive {count} running session(s)?"
                    screen.move(height - 2, 0)
                    screen.clrtoeol()
                    screen.addnstr(height - 2, 1, question, max(1, width - 2), curses.A_BOLD)
                    screen.move(height - 1, 0)
                    screen.clrtoeol()
                    screen.addnstr(height - 1, 1, "y: confirm deletion   n / Esc: cancel   Sessions keep running in Archive.", max(1, width - 2), curses.A_BOLD)
                    screen.refresh()
                    screen.timeout(-1)
                    try:
                        confirmed = screen.get_wch() == "y"
                    finally:
                        screen.timeout(100)
                    if confirmed:
                        parent = data["workspaces"][selected]["parent"] or "general"
                        result = command("delete", workspace=selected, token=deletion_token(data, selected), quiet="1")
                        if result.returncode == 0:
                            if args.workspace not in json.loads(Path(state).read_text())["workspaces"]:
                                args.workspace = parent
                            selected = parent
                            notice = "Workspace deleted. Sessions kept running in Archive."
                        else:
                            notice = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "Deletion failed; please try again."
                    else:
                        notice = "Deletion cancelled."
            elif key in ("\n", "\r", curses.KEY_ENTER):
                return selected
    if screen is not None:
        return run(screen)
    target = curses.wrapper(run)
    if not target and json.loads(Path(state).read_text()).get("picker_layout") == "custom":
        target = args.workspace
    if target:
        subprocess.run(["tmux", "run-shell", "-b", "-d", "0.1",
                        shell_command("open", args.client, args.pane, workspace=target)], check=True)
