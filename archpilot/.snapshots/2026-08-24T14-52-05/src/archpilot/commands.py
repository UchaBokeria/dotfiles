"""The `:` command line.

Parsing lives here rather than in the window so it can be tested without a
display, and so the same vocabulary could be reached from the CLI later.

Each command returns an intent - a small dict the frontend acts on - rather
than doing anything itself. That keeps the parser pure and the side effects in
one place.
"""

from __future__ import annotations

from dataclasses import dataclass

MODELS = ("haiku", "sonnet", "opus", "fable")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MODES = ("ask", "action")


@dataclass(frozen=True)
class Intent:
    kind: str
    args: dict
    message: str = ""

    @property
    def failed(self) -> bool:
        return self.kind == "error"


def _error(message: str) -> Intent:
    return Intent("error", {}, message)


#: name -> (aliases, one-line help). Used for completion and for `:help`.
COMMANDS = {
    "new":     (("n",),        "start a fresh conversation"),
    "model":   (("m",),        f"switch model: {' '.join(MODELS)}"),
    "effort":  (("e",),        f"switch effort: {' '.join(EFFORTS)}"),
    "mode":    (("t",),        f"switch mode: {' '.join(MODES)}"),
    "history": (("h", "hist"), "search past prompts"),
    "sessions": (("s",),       "browse Claude Code sessions"),
    "export":  (("w",),        "write the conversation to a file"),
    "copy":    (("y",),        "copy the whole conversation"),
    "mcp":     ((),            "enable/disable an MCP server: :mcp chrome on"),
    "cancel":  (("stop",),     "stop the running turn"),
    "tabnew":  (("tn",),       "open another conversation in a tab"),
    "tabclose": (("tc",),      "close this tab"),
    "quit":    (("q",),        "close the window"),
    "help":    (("?",),        "list commands"),
}


def resolve(name: str) -> str:
    """Full command name for a typed word, or "" if it matches nothing."""
    if name in COMMANDS:
        return name
    for full, (aliases, _help) in COMMANDS.items():
        if name in aliases:
            return full
    # Unambiguous prefix, as vim does: `:mod` is `:model` but `:m` is an alias.
    matches = [full for full in COMMANDS if full.startswith(name)]
    return matches[0] if len(matches) == 1 else ""


def complete(prefix: str) -> list[str]:
    return sorted(name for name in COMMANDS if name.startswith(prefix))


def parse(line: str) -> Intent:
    """Turn a typed `:` line into an intent."""
    parts = line.strip().split()
    if not parts:
        return _error("")

    name = resolve(parts[0].lower())
    if not name:
        return _error(f"not a command: {parts[0]}")
    rest = parts[1:]

    if name in ("new", "history", "sessions", "cancel", "quit", "help", "copy"):
        return Intent(name, {})

    if name in ("tabnew", "tabclose"):
        return Intent("tab", {"action": "new" if name == "tabnew" else "close"})

    if name == "model":
        if not rest:
            return _error("usage: :model " + "|".join(MODELS))
        if rest[0] not in MODELS:
            return _error(f"unknown model: {rest[0]}")
        return Intent("set", {"field": "model", "value": rest[0]})

    if name == "effort":
        if not rest:
            return _error("usage: :effort " + "|".join(EFFORTS))
        if rest[0] not in EFFORTS:
            return _error(f"unknown effort: {rest[0]}")
        return Intent("set", {"field": "effort", "value": rest[0]})

    if name == "mode":
        if not rest:
            return _error("usage: :mode " + "|".join(MODES))
        if rest[0] not in MODES:
            return _error(f"unknown mode: {rest[0]}")
        return Intent("set", {"field": "mode", "value": rest[0]})

    if name == "export":
        return Intent("export", {"path": rest[0] if rest else ""})

    if name == "mcp":
        if len(rest) < 1:
            return _error("usage: :mcp <server> [on|off]")
        state = rest[1] if len(rest) > 1 else "on"
        if state not in ("on", "off"):
            return _error("usage: :mcp <server> [on|off]")
        return Intent("mcp", {"server": rest[0], "enable": state == "on"})

    return _error(f"not a command: {parts[0]}")


def help_lines() -> list[str]:
    return [f":{name:9} {help_text}" for name, (_a, help_text) in COMMANDS.items()]


#: Every key the window binds, grouped for display. Kept here beside the
#: command table so `:help` has one source for both halves and they cannot
#: drift apart the way a hand-written help screen always does.
KEYBINDINGS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("editing", (
        ("i a o", "insert before / after / on a new line"),
        ("escape", "back to normal mode"),
        ("esc esc", "stop a running answer and take the prompt back"),
        ("h j k l", "move by character and line"),
        ("w b e", "move by word"),
        ("0 ^ $", "start / first word / end of line"),
        ("gg G", "top / bottom of the prompt"),
        ("ctrl-d ctrl-u", "half a page down / up"),
        ("d c y + motion", "delete, change, yank"),
        ("dd cc yy", "whole line"),
        ("p P", "paste after / before"),
        ("u ctrl-r", "undo / redo a whole edit"),
        ("v V ctrl-v", "visual, line, block"),
        ("ctrl-v then j/k", "extend the block down / up a line"),
        ("ctrl-v then I A c r", "type, append, change or replace on every line"),
        ("ctrl-a", "select the whole prompt"),
        ("q{reg} … q", "record a macro; @{reg} plays it, @@ repeats"),
        ("ctrl-shift-v", "paste from the system clipboard"),
    )),
    ("sending", (
        ("enter", "send"),
        ("shift+enter", "new line"),
        ("up down", "walk back through messages already sent"),
        ("super+enter", "run the command the answer proposed"),
    )),
    ("multiple cursors", (
        ("ctrl-n", "select this word, again for each next occurrence"),
        ("ctrl-up ctrl-down", "add a cursor on the line above / below"),
        ("c d x y", "change, delete or yank at every cursor"),
        ("I A", "type at the start / end of every cursor"),
        ("escape", "drop the extra cursors"),
    )),

    ("moving around", (
        ("tab", "switch between the input and the chat"),
        ("j k", "select a message (in the chat)"),
        ("y", "copy the selected message"),
        ("u", "continue from the selected message"),
        ("ctrl-h", "search past chats"),
        ("r", "rename a chat (in history)"),
    )),
    ("the window", (
        ("shift+tab", "ask / action"),
        ("ctrl+tab", "change model"),
        ("alt+tab", "change effort"),
        ("ctrl-t", "new chat"),
        ("ctrl-w", "close this tab"),
        ("ctrl-backspace", "delete the previous word (insert mode)"),
        ("alt+1..9", "jump to a tab"),
        ("gt gT", "next / previous tab"),
        ("ctrl-c", "stop the running turn"),
        ("ZZ", "close the window"),
        (":", "command line"),
    )),
)


def describe(name: str) -> str:
    """One-line help for a command, or "" if there is no such command."""
    entry = COMMANDS.get(resolve(name) or name)
    return entry[1] if entry else ""


def suggestions(line: str) -> list[tuple[str, str]]:
    """(command, help) pairs matching what has been typed so far.

    Matches on the FIRST word only: once a command is complete the rest of the
    line is its arguments, and continuing to filter on it would empty the list
    exactly when the user is midway through typing a value.
    """
    head = (line or "").split(" ")[0]
    if " " in (line or ""):
        full = resolve(head)
        return [(full, COMMANDS[full][1])] if full else []
    return [(name, COMMANDS[name][1]) for name in complete(head)]
