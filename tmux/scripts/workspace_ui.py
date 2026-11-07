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
    from session_picker import SearchMode, input_dialog, navigate, overlay, paint_row, put, ranked, read_key, search_prompt, slot_key, toast
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
        mode = SearchMode()
        while True:
            data = json.loads(Path(state).read_text())
            nodes = []
            def walk(parent, depth):
                slots = {wid: shortcut_label(number) for number, wid in shortcut_map(data, parent).items()}
                for wid in children(data, parent):
                    nodes.append((wid, depth, ("Alt+" if parent else "") + slots.get(wid, "-")))
                    walk(wid, depth + 1)
            walk(None, 0)
            matches = ranked(nodes, mode.query, lambda row: path_name(data, row[0]) + ' ' + row[2])
            index = next((i for i, row in enumerate(matches) if row[0] == selected), 0)
            if matches: selected = matches[index][0]
            screen = overlay(parent, "Workspaces", 96, min(26, len(nodes) + 9), curses.A_BOLD)
            height, width = screen.getmaxyx()
            visible = max(1, height - 8)
            top = max(0, min(index - visible // 2, len(matches) - visible))
            live = set(data.get("live", {}).get("names", {}).values())
            for y, (wid, depth, shortcut) in enumerate(matches[top:top + visible], 5):
                node = data["workspaces"][wid]
                count = sum(group == wid and name in live for name, group in data["sessions"].items())
                label = (path_name(data, wid) if mode.query else "  " * depth + node["name"])
                label = shortcut.ljust(7) + " " + label + " (" + str(count) + ")"
                if wid == args.workspace: label += " [active]"
                paint_row(screen, y, 2, label, width - 4, wid == selected)
            search_prompt(screen, mode, len(matches), len(nodes), 'Enter opens')
            if notice: toast(screen, notice, height - 3)
            screen.refresh()
            try:
                key = read_key(screen, allow_alt=False if mode.insert else "workspace")
            except curses.error:
                continue
            action = mode.key(key)
            if action == 'close':
                curses.curs_set(0)
                return None
            if action == 'query':
                selected = ''
                continue
            if action == 'accept' and matches:
                curses.curs_set(0)
                return selected
            if action not in ('action', 'mode', 'edit'):
                index = navigate(index, action, len(matches), visible)
                if matches: selected = matches[index][0]
                continue
            if action != 'action' or not matches: continue
            alt = isinstance(key, tuple) and key[0] == "alt"
            number = slot_key(key[1] if alt else key)
            if number:
                target = shortcut_map(data, nested_parent(data, args.workspace) if alt else None).get(number)
                if target and any(row[0] == target for row in matches):
                    return target
            if key in ("J", "K"):
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
    if screen is not None:
        return run(screen)
    target = curses.wrapper(run)
    if not target and json.loads(Path(state).read_text()).get("picker_layout") == "custom":
        target = args.workspace
    if target:
        subprocess.run(["tmux", "run-shell", "-b", "-d", "0.1",
                        shell_command("open", args.client, args.pane, workspace=target)], check=True)
