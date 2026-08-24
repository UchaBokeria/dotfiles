"""archpilot - the command surface Hyprland keybinds and waybar talk to."""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import client, config, ipc, paths, rofi_theme, triage
from .context import history
from .context import sessions as session_index


def _fail(message: str) -> int:
    print(f"archpilot: {message}", file=sys.stderr)
    return 1


def cmd_toggle(args) -> int:
    """Kept as an alias for `ui --toggle`.

    It used to open the eww widget. Anything still bound to `toggle` - waybar,
    old keybinds - now gets the GTK window instead of resurrecting a frontend
    that no longer exists.
    """
    args.toggle = True
    return cmd_ui(args)


def cmd_send(args) -> int:
    text = " ".join(args.text).strip()
    if not text:
        return _fail("nothing to send")
    payload = {"op": ipc.OP_PROMPT, "text": text}
    if args.new:
        payload["new"] = True
    for key in ("mode", "model", "session"):
        if value := getattr(args, key, None):
            payload[key] = value
    try:
        client.send(payload)
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    return 0


DOWN_STATE = {
    "status": "down", "mode": "", "model": "", "answer": "",
    "answer_markup": "", "answer_height": 44, "actions": [], "has_actions": False,
    "action_count": 0, "action0": "", "action1": "", "action2": "",
    "show_action0": False, "show_action1": False, "show_action2": False,
    "pending": "", "pending_id": "", "pending_reason": "", "prompt": "",
    "rate_limit": "", "error": "", "resume": "", "cwd": "", "session": "",
    "attachments": [], "has_attachments": False,
}


def cmd_subscribe(args) -> int:
    """Stream daemon state as newline JSON, reconnecting if the daemon restarts.

    Kept as a general-purpose tap on the daemon - the waybar module and any
    script that wants live state use it.
    """
    announced_down = False
    while True:
        try:
            for event in client.stream({"op": ipc.OP_SUBSCRIBE}):
                announced_down = False
                if args.eww:
                    if event.get("ev") != ipc.EV_STATE:
                        continue
                    event = {k: v for k, v in event.items() if k != "ev"}
                print(json.dumps(event, ensure_ascii=False), flush=True)
        except client.DaemonUnavailable:
            pass
        except (BrokenPipeError, KeyboardInterrupt):
            return 0
        except OSError:
            pass

        if not args.once:
            if args.eww and not announced_down:
                print(json.dumps(DOWN_STATE), flush=True)
                announced_down = True
            time.sleep(args.retry)
            continue
        return 1


def cmd_approve(args) -> int:
    decision = "deny" if args.deny else "allow"
    try:
        reply = client.send(
            {"op": ipc.OP_APPROVE, "id": args.id or "", "decision": decision},
            expect_reply=True,
        )
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    if not (reply or {}).get("ok"):
        return _fail("no approval was waiting")
    return 0


def _prune_shots(keep: int = 20) -> None:
    """Screenshots are a few MB each and nothing else ever deletes them."""
    shots = sorted(paths.shot_dir().glob("shot-*.png"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in shots[keep:]:
        with contextlib.suppress(OSError):
            stale.unlink()


def cmd_shot(args) -> int:
    """Region-grab, then stage the image for the next prompt."""
    cfg = config.load()
    _prune_shots()
    target = paths.shot_dir() / f"shot-{int(time.time())}.png"
    command = cfg.get("screenshot", "cmd").replace("{path}", str(target))

    # The widget sits on the overlay layer: leaving it up would put it on top of
    # slurp's region selector and bake it into the capture. The attach op
    # reopens it afterwards.
    hidden = _ask_daemon_widget("hide")
    _submap("reset")  # slurp needs escape to cancel
    if hidden:
        time.sleep(0.25)  # let the compositor actually unmap it before grabbing

    try:
        result = subprocess.run(command, shell=True, check=False)
    finally:
        if hidden and not target.exists():
            _ask_daemon_widget("show")
    if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        return _fail("screenshot cancelled")
    try:
        client.send({"op": ipc.OP_ATTACH, "paths": [str(target)]})
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    print(target)
    return 0


WIDGET = "archpilot"


def _ask_daemon_widget(action: str) -> bool:
    """Move the widget via the daemon rather than by calling eww.

    These commands are launched BY eww (a button's :onclick). eww waits for the
    process it spawned, so calling `eww` back from inside one deadlocks - the
    button silently does nothing forever. Routing through the daemon avoids
    that entirely, because the daemon is not eww's child.
    """
    try:
        reply = client.send({"op": ipc.OP_WIDGET, "action": action},
                            expect_reply=True, timeout=3)
    except client.DaemonUnavailable:
        return False
    return bool((reply or {}).get("ok"))


def _submap(name: str) -> None:
    subprocess.run(["hyprctl", "dispatch", "submap", name], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _rofi_pick(rows: list[str], prompt: str) -> str:
    """Show a themed rofi menu, temporarily yielding the screen AND the keyboard.

    Three things this exists for:

    1. The widget is a layer-shell surface on the *overlay* layer, which draws
       above ordinary windows - so rofi opens behind it and a click looks like
       it did nothing. Hiding the widget first is what makes the menu visible.
    2. While the widget is up the `archpilot` submap is active, and a submap
       captures every bound key. rofi would open with a search box that cannot
       be typed into, because "s" and "/" and the rest are bindings. The submap
       has to be released for as long as rofi owns the keyboard.
    3. rofi's config.rasi holds settings but no theme; every launcher in this
       rice passes -theme explicitly, so a bare `rofi -dmenu` is unstyled.
    """
    hidden = _ask_daemon_widget("hide")
    _submap("reset")

    argv = ["rofi", "-dmenu", "-i", "-p", prompt, "-format", "s"]
    configured = config.load().rofi_theme
    theme = Path(configured).expanduser() if configured else rofi_theme.render()
    if theme.exists():
        argv += ["-theme", str(theme)]

    try:
        picker = subprocess.run(argv, input="\n".join(rows),
                                capture_output=True, text=True, check=False)
        return picker.stdout.strip()
    finally:
        if hidden:
            _ask_daemon_widget("show")
            _submap("archpilot")


WAYBAR_ICONS = {
    "idle": "\U000F06A9",
    "thinking": "\U000F06A9",
    "awaiting_approval": "\U000F06A9",
    "down": "\U000F06A9",
}


def _waybar_payload(state: dict) -> dict:
    """One waybar custom-module frame."""
    status = state.get("status") or "down"
    icon = WAYBAR_ICONS.get(status, WAYBAR_ICONS["idle"])

    if status == "awaiting_approval":
        text = f"{icon} approve?"
    elif state.get("needs_password"):
        text = f"{icon} password"
        status = "awaiting_approval"
    elif status == "thinking":
        text = f"{icon} ..."
    elif status == "down":
        text = icon
    else:
        text = icon

    tooltip_bits = [f"archpilot - {status.replace('_', ' ')}"]
    if state.get("mode"):
        tooltip_bits.append(f"{state['mode']} / {state.get('model', '')} / {state.get('effort', '')}")
    if state.get("context_label"):
        tooltip_bits.append(state["context_label"])
    if pending := state.get("pending"):
        tooltip_bits.append(f"waiting: {pending.splitlines()[0][:60]}")
    elif answer := state.get("answer"):
        tooltip_bits.append(answer.splitlines()[0][:70])

    return {"text": text, "tooltip": "\n".join(tooltip_bits), "class": status, "alt": status}


SCROLL_DELTAS = {"up": 3, "down": -3, "page-up": 10, "page-down": -10,
                 "top": 10_000, "bottom": -10_000}


def cmd_scroll(args) -> int:
    """Move the transcript viewport. eww cannot scroll, so the daemon renders
    a window over the conversation and this moves it."""
    delta = SCROLL_DELTAS[args.direction]
    try:
        client.send({"op": ipc.OP_SCROLL, "delta": delta}, expect_reply=True)
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    return 0


UI_CLASS = "dev.archpilot.ui"


def _ui_window_exists() -> bool:
    try:
        out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True,
                             text=True, timeout=3, check=False)
        return any(c.get("class") == UI_CLASS for c in json.loads(out.stdout or "[]"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def cmd_ui(args) -> int:
    """Toggle the GTK window.

    Unlike the eww widget this is a real window, so it takes keyboard focus by
    itself and vim editing happens inside the process. Hyprland only needs to
    show or hide it.
    """
    root = Path(__file__).resolve().parent.parent.parent
    launcher = root / "bin" / "archpilot-ui"

    if _ui_window_exists():
        if args.toggle:
            subprocess.run(["hyprctl", "dispatch", "closewindow", f"class:{UI_CLASS}"],
                           check=False, stdout=subprocess.DEVNULL)
            subprocess.run(["hyprctl", "dispatch", "submap", "reset"],
                           check=False, stdout=subprocess.DEVNULL)
            return 0
        subprocess.run(["hyprctl", "dispatch", "focuswindow", f"class:{UI_CLASS}"],
                       check=False, stdout=subprocess.DEVNULL)
        return 0

    if not launcher.exists():
        return _fail(f"missing launcher: {launcher}")
    subprocess.Popen([str(launcher)], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


def cmd_new(_args) -> int:
    """Start a fresh conversation. The old one stays resumable."""
    try:
        client.send({"op": ipc.OP_NEW}, expect_reply=True)
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    return 0


def cmd_triage(args) -> int:
    """Report machine conditions worth acting on."""
    findings = triage.scan()

    if args.ask:
        match = next((f for f in findings if f.key == args.ask), None)
        if match is None:
            return _fail(f"no current finding named {args.ask!r}")
        try:
            client.send({"op": ipc.OP_PROMPT, "text": match.prompt, "new": True})
        except client.DaemonUnavailable as exc:
            return _fail(str(exc))
        _ask_daemon_widget("show")
        return 0

    if args.json:
        print(json.dumps([{"key": f.key, "summary": f.summary, "urgent": f.urgent,
                           "detail": f.detail, "prompt": f.prompt} for f in findings]))
        return 0

    if args.notify:
        fresh = triage.unreported(findings)
        triage.notify(fresh)
        triage.mark_reported(fresh)
        return 0

    if not findings:
        print("nothing to report")
        return 0
    for f in findings:
        print(f"{'!' if f.urgent else ' '} {f.key:14} {f.summary}")
        for line in f.detail.splitlines()[:4]:
            print(f"                 {line}")
    return 0


def cmd_waybar(args) -> int:
    """Emit waybar custom-module JSON.

    Streams by default: waybar reads a line per update, so the bar reflects the
    daemon instantly instead of polling it on a timer.
    """
    if not args.watch:
        try:
            state = client.send({"op": ipc.OP_STATE}, expect_reply=True) or {}
        except client.DaemonUnavailable:
            state = {"status": "down"}
        print(json.dumps(_waybar_payload(state)), flush=True)
        return 0

    announced_down = False
    while True:
        try:
            for event in client.stream({"op": ipc.OP_SUBSCRIBE}):
                if event.get("ev") != ipc.EV_STATE:
                    continue
                announced_down = False
                print(json.dumps(_waybar_payload(event)), flush=True)
        except client.DaemonUnavailable:
            pass
        except (BrokenPipeError, KeyboardInterrupt):
            return 0
        except OSError:
            pass
        if not announced_down:
            print(json.dumps(_waybar_payload({"status": "down"})), flush=True)
            announced_down = True
        time.sleep(args.retry)


def cmd_set(args) -> int:
    """Change mode / model / effort on the live session."""
    if args.value is None and not args.cycle:
        return _fail(f"give a value for {args.field}, or pass --cycle")
    try:
        reply = client.send(
            {"op": ipc.OP_SET, "field": args.field, "value": args.value, "cycle": args.cycle},
            expect_reply=True,
        )
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    if not (reply or {}).get("ok"):
        return _fail(f"could not set {args.field}")
    print((reply or {}).get("value", ""))
    return 0


def cmd_history(args) -> int:
    """Browse past prompts from this machine's Claude Code transcripts."""
    if not (args.json or args.print):
        # Hand off to the daemon: it owns rofi so that a widget button only
        # ever has to write one line to a socket.
        try:
            client.send({"op": ipc.OP_PICKER, "kind": "history"}, expect_reply=True)
            return 0
        except client.DaemonUnavailable as exc:
            return _fail(str(exc))
    entries = history.recent(limit=args.limit)
    if not entries:
        return _fail("no history yet")
    if args.json:
        print(json.dumps([e.as_dict() for e in entries]))
        return 0

    rows = [f"{e.when}\t{e.session_id[:8]}\t{e.prompt}" for e in entries]
    choice = _rofi_pick(rows, "history")
    if not choice:
        return 0
    prompt = choice.split("\t", 2)[-1]
    if args.print:
        print(prompt)
        return 0
    # Re-asking is the useful default; the text is already in the input history.
    try:
        client.send({"op": ipc.OP_PROMPT, "text": prompt})
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    return 0


def cmd_password(args) -> int:
    """Hand a sudo password to the waiting askpass helper.

    Caveat worth knowing: eww can only invoke shell commands, so the value
    arrives as an argument and is briefly visible in /proc/<pid>/cmdline. On a
    single-user desktop that is a narrow window, but it is real - which is why
    archpilot never stores the password anywhere and leans on sudo's own
    timestamp cache for repeats.
    """
    value = args.value if args.value is not None else sys.stdin.readline().rstrip("\n")
    if not value:
        return _fail("no password given")
    try:
        reply = client.send({"op": ipc.OP_PASSWORD, "value": value}, expect_reply=True)
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    if not (reply or {}).get("ok"):
        return _fail("nothing was waiting for a password")
    return 0


def cmd_copy(args) -> int:
    """Copy part of the current answer to the clipboard."""
    try:
        state = client.send({"op": ipc.OP_STATE}, expect_reply=True) or {}
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))

    if args.what == "answer":
        text = state.get("answer") or ""
        if not text:
            # A reply that was nothing but an action block leaves no prose to
            # copy; the command is what the user actually wanted anyway.
            text = "\n".join(a.get("command", "") for a in state.get("actions") or [])
    elif args.what == "prompt":
        text = state.get("prompt") or ""
    else:
        actions = state.get("actions") or []
        if args.index >= len(actions):
            return _fail(f"no action at index {args.index}")
        text = actions[args.index].get("command") or ""

    if not text:
        return _fail(f"nothing to copy for {args.what!r}")

    result = subprocess.run(["wl-copy"], input=text, text=True, check=False)
    if result.returncode != 0:
        return _fail("wl-copy failed")
    with contextlib.suppress(OSError):
        subprocess.Popen(
            ["notify-send", "-a", "archpilot", "-t", "1200", "Copied",
             text.splitlines()[0][:60]],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def cmd_run(args) -> int:
    """Run the Nth suggested action from the current answer."""
    try:
        client.send({"op": ipc.OP_RUN_ACTION, "index": args.index})
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    return 0


def cmd_sessions(args) -> int:
    if not args.json:
        try:
            client.send({"op": ipc.OP_PICKER, "kind": "sessions"}, expect_reply=True)
            return 0
        except client.DaemonUnavailable as exc:
            return _fail(str(exc))
    listing = session_index.index()
    if not listing:
        return _fail("no Claude Code sessions found")
    if args.json:
        print(json.dumps([{"id": s.id, "title": s.title, "state": s.state,
                           "progress": s.progress, "cwd": s.cwd} for s in listing]))
        return 0

    rows = [f"{s.title}\t{s.state}\t{s.progress or '-'}\t{s.cwd}\t{s.id}" for s in listing]
    choice = _rofi_pick(rows, "session")
    if not choice:
        return 0

    fields = choice.split("\t")
    session_id, cwd = fields[-1].strip(), fields[3].strip()
    command = f"claude --resume {session_id}"

    if args.print:
        print(f"cd {cwd} && {command}")
        return 0

    # Opening the session is the point of the picker; printing a command a
    # keybind then throws away is not. Clipboard is the fallback so the choice
    # is never lost if no terminal is available.
    with contextlib.suppress(OSError):
        subprocess.run(["wl-copy", f"cd {cwd} && {command}"], check=False)

    terminal = shutil.which("kitty")
    if terminal is None:
        print(f"cd {cwd} && {command}")
        return 0
    subprocess.Popen([terminal, "--directory", cwd, "--", "claude", "--resume", session_id],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def cmd_state(_args) -> int:
    try:
        reply = client.send({"op": ipc.OP_STATE}, expect_reply=True)
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    print(json.dumps(reply, indent=2))
    return 0


def cmd_cancel(args) -> int:
    try:
        client.send({"op": ipc.OP_CANCEL, "session": args.session or ""})
    except client.DaemonUnavailable as exc:
        return _fail(str(exc))
    return 0


def cmd_undo(_args) -> int:
    """Revert the most recent commit ArchPilot made to the dotfiles repo."""
    repo = paths.DOTFILES
    found = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%H %s", "--grep=^archpilot:"],
        capture_output=True, text=True, check=False,
    )
    line = found.stdout.strip()
    if not line:
        return _fail("no archpilot commit to undo")
    sha, subject = line.split(" ", 1)
    revert = subprocess.run(
        ["git", "-C", str(repo), "revert", "--no-edit", sha],
        capture_output=True, text=True, check=False,
    )
    if revert.returncode != 0:
        return _fail(f"revert failed: {revert.stderr.strip()}")
    print(f"reverted {sha[:8]} {subject}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archpilot", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    toggle = sub.add_parser("toggle", help="alias for `ui --toggle`")
    toggle.set_defaults(func=cmd_toggle, toggle=True)

    send = sub.add_parser("send", help="send a prompt")
    send.add_argument("text", nargs="+")
    send.add_argument("--mode", choices=("ask", "action"))
    send.add_argument("--model")
    send.add_argument("--session")
    send.add_argument("--new", action="store_true",
                      help="start a fresh conversation instead of continuing the current one")
    send.set_defaults(func=cmd_send)

    subscribe = sub.add_parser("subscribe", help="stream daemon events")
    subscribe.add_argument("--eww", action="store_true", help="emit state snapshots only")
    subscribe.add_argument("--once", action="store_true",
                           help="exit when the daemon goes away instead of reconnecting")
    subscribe.add_argument("--retry", type=float, default=2.0,
                           help="seconds between reconnect attempts")
    subscribe.set_defaults(func=cmd_subscribe)

    approve = sub.add_parser("approve", help="answer a pending approval")
    approve.add_argument("id", nargs="?")
    approve.add_argument("--deny", action="store_true")
    approve.set_defaults(func=cmd_approve)

    sub.add_parser("shot", help="region screenshot, staged for the next prompt").set_defaults(func=cmd_shot)

    sub.add_parser("new", help="start a fresh conversation").set_defaults(func=cmd_new)

    ui = sub.add_parser("ui", help="open or toggle the GTK window")
    ui.add_argument("--toggle", action="store_true", help="close it if already open")
    ui.set_defaults(func=cmd_ui)

    scroll = sub.add_parser("scroll", help="move the transcript viewport")
    scroll.add_argument("direction", choices=tuple(SCROLL_DELTAS))
    scroll.set_defaults(func=cmd_scroll)

    tri = sub.add_parser("triage", help="report machine conditions worth acting on")
    tri.add_argument("--notify", action="store_true", help="send a notification for new findings")
    tri.add_argument("--json", action="store_true")
    tri.add_argument("--ask", metavar="KEY", help="ask archpilot to deal with one finding")
    tri.set_defaults(func=cmd_triage)

    bar = sub.add_parser("waybar", help="emit waybar custom-module JSON")
    bar.add_argument("--watch", action="store_true", help="stream updates continuously")
    bar.add_argument("--retry", type=float, default=3.0)
    bar.set_defaults(func=cmd_waybar)

    setter = sub.add_parser("set", help="change mode / model / effort")
    setter.add_argument("field", choices=("mode", "model", "effort"))
    setter.add_argument("value", nargs="?")
    setter.add_argument("--cycle", action="store_true", help="advance to the next value")
    setter.set_defaults(func=cmd_set)

    hist = sub.add_parser("history", help="browse and re-ask past prompts")
    hist.add_argument("--limit", type=int, default=200)
    hist.add_argument("--json", action="store_true")
    hist.add_argument("--print", action="store_true", help="print instead of re-asking")
    hist.set_defaults(func=cmd_history)

    password = sub.add_parser("password", help="answer a pending sudo password prompt")
    password.add_argument("value", nargs="?", help="omit to read from stdin")
    password.set_defaults(func=cmd_password)

    copy = sub.add_parser("copy", help="copy answer / prompt / a command to the clipboard")
    copy.add_argument("what", choices=("answer", "prompt", "action"), default="answer", nargs="?")
    copy.add_argument("index", nargs="?", type=int, default=0)
    copy.set_defaults(func=cmd_copy)

    run = sub.add_parser("run", help="run a suggested action by index")
    run.add_argument("index", nargs="?", type=int, default=0)
    run.set_defaults(func=cmd_run)

    listing = sub.add_parser("sessions", help="browse Claude Code sessions")
    listing.add_argument("--json", action="store_true")
    listing.add_argument("--print", action="store_true",
                         help="print the resume command instead of opening it")
    listing.set_defaults(func=cmd_sessions)

    sub.add_parser("state", help="print current daemon state").set_defaults(func=cmd_state)

    cancel = sub.add_parser("cancel", help="stop the running turn")
    cancel.add_argument("--session")
    cancel.set_defaults(func=cmd_cancel)

    sub.add_parser("undo", help="revert the last archpilot commit").set_defaults(func=cmd_undo)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
