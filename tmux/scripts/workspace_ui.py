"""Terminal input and hierarchical workspace list views."""
import curses
import json
from pathlib import Path
import subprocess
import picker_theme as theme


def read_name(initial="", title="Name / shortcut"):
    from session_picker import input_dialog
    import picker_theme as theme
    def run(screen):
        curses.set_escdelay(25)
        curses.raw()
        theme.apply(force=True)
        return input_dialog(screen, title, initial)
    return curses.wrapper(run)


def workspace_list(args, state, screen=None):
    curses.set_escdelay(25)
    from workspaces import SYSTEM, children, deletion_token, path_name, shortcut_map, shortcut_label, shell_command
    from session_picker import input_dialog, overlay, put, read_key, slot_key
    from workspaces import nested_parent

    helper = Path(__file__).with_name("workspaces.py")
    selected = args.workspace
    notice = ""

    def command(action, **values):
        argv = [str(helper), action, "--client", args.client, "--pane", args.pane]
        for key, value in values.items():
            argv += ["--" + key, str(value)]
        return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def run(parent):
        nonlocal selected, notice
        curses.curs_set(0)
        parent.keypad(True)
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
            screen = overlay(parent, "Workspaces", 86, min(24, len(nodes) + 7), curses.A_BOLD)
            height, width = screen.getmaxyx()
            visible = max(1, height - 6)
            top = max(0, min(index - visible // 2, len(nodes) - visible))
            put(screen, 1, 2, "j/k select · Enter open · J/K reorder · r rename · x delete · Esc back", curses.A_DIM, width - 4)
            live = set(data.get("live", {}).get("names", {}).values())
            for y, (wid, depth, shortcut) in enumerate(nodes[top:top + visible], 3):
                node = data["workspaces"][wid]
                count = sum(group == wid and name in live for name, group in data["sessions"].items())
                label = "  " * depth + shortcut.ljust(7) + " " + node["name"] + " (" + str(count) + ")"
                if wid == args.workspace: label += " [active]"
                put(screen, y, 2, label.ljust(width - 4), theme.SELECTION if wid == selected else theme.BODY, width - 4)
            if notice: put(screen, height - 2, 2, notice, curses.A_BOLD, width - 4)
            screen.refresh()
            try:
                key = read_key(screen, allow_alt="workspace")
            except curses.error:
                continue
            if key == "\x1b":
                return None
            alt = isinstance(key, tuple) and key[0] == "alt"
            number = slot_key(key[1] if alt else key)
            if number:
                target = shortcut_map(data, nested_parent(data, args.workspace) if alt else None).get(number)
                if target:
                    return target
            if key in ("j", curses.KEY_DOWN):
                selected = nodes[(index + 1) % len(nodes)][0]
            elif key in ("k", curses.KEY_UP):
                selected = nodes[(index - 1) % len(nodes)][0]
            elif key in ("J", "K"):
                command("reorder", workspace=selected, direction="down" if key == "J" else "up", quiet="1")
            elif key == "r":
                if selected in SYSTEM:
                    notice = "This workspace is protected."
                else:
                    name = input_dialog(parent, "Rename workspace", data["workspaces"][selected]["name"])
                    if name:
                        result = command("apply-name", workspace=selected, kind="rename", name=name, quiet="1")
                        notice = "Workspace renamed." if result.returncode == 0 else result.stderr.strip().splitlines()[-1]
                    parent.touchwin()
            elif key == "x":
                if selected in SYSTEM:
                    notice = "General, Background and Archive are protected."
                elif children(data, selected):
                    notice = "Delete child workspaces first; each has its own confirmation."
                else:
                    count = sum(group == selected and name in live for name, group in data["sessions"].items())
                    question = f"Delete {path_name(data, selected)}? Archive {count} running session(s)?"
                    put(screen, height - 3, 1, " " * (width - 2))
                    put(screen, height - 3, 2, question, curses.A_BOLD, width - 4)
                    put(screen, height - 2, 1, " " * (width - 2))
                    put(screen, height - 2, 2, "y confirms · n/Esc cancels · sessions keep running in Archive", curses.A_BOLD, width - 4)
                    screen.refresh()
                    screen.timeout(-1)
                    try:
                        confirmed = screen.get_wch() == "y"
                    finally:
                        screen.timeout(100)
                    if confirmed:
                        parent_id = data["workspaces"][selected]["parent"] or "general"
                        result = command("delete", workspace=selected, token=deletion_token(data, selected), quiet="1")
                        if result.returncode == 0:
                            if args.workspace not in json.loads(Path(state).read_text())["workspaces"]:
                                args.workspace = parent_id
                            selected = parent_id
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
