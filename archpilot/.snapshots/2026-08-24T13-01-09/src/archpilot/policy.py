"""Command classification: allow outright, ask a human, or refuse flatly.

This is the brain behind "confirm irreversible only". It runs inside
hooks/pretooluse.py, before anything reaches a shell.

Three verdicts:
  ALLOW - reversible or read-only; runs with no interruption
  ASK   - a human sees the exact command in the widget and answers y/n
  DENY  - catastrophic; refused regardless of mode, never surfaced as a prompt

The safety argument for ALLOW being generous: edits under the dotfiles repo are
auto-committed by the daemon, so `archpilot undo` is a real `git revert`. The
repo IS the undo stack. That property is what makes a fast default defensible,
and it is why "is this path inside the repo" is load-bearing below.
"""

from __future__ import annotations

import re
import shlex
from enum import Enum
from pathlib import Path

from .paths import DOTFILES


class Verdict(Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


#: Patterns that are refused in every mode, with no y/n prompt offered.
#: These are not preferences - there is no context in which ArchPilot should
#: run them on this machine. Kept as regexes against the raw command string so
#: that shell metacharacters (pipes, redirects) cannot smuggle them past
#: token-based inspection.
DENYLIST: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rR][a-zA-Z]*f?[a-zA-Z]*\s+/\s*$"),
     "recursive delete of /"),
    (re.compile(r"\brm\s+.*\s-{1,2}no-preserve-root\b"), "rm --no-preserve-root"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "filesystem creation"),
    (re.compile(r"\bdd\b[^|;&]*\bof=/dev/(sd|nvme|vd|mmcblk|disk)"), "raw write to a block device"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|fi|da)?sh\b"), "piping a download into a shell"),
    (re.compile(r":\s*\(\s*\)\s*\{.*\|.*&.*\}\s*;?\s*:"), "fork bomb"),
    (re.compile(r"\bshred\b"), "unrecoverable file shredding"),
    (re.compile(r"\b(chmod|chown)\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*R[a-zA-Z]*\s+.*\s/\s*$"),
     "recursive ownership/permission change on /"),
    (re.compile(r">\s*/dev/(sd|nvme|vd|mmcblk)"), "redirect onto a block device"),
    (re.compile(r"\bgit\s+push\b[^|;&]*(--force\b|-f\b)[^|;&]*\bmain\b"), "force-push to main"),
)


def is_in_repo(path: str | Path, cwd: str | Path) -> bool:
    """True when `path` resolves inside the git-tracked dotfiles repo.

    Inside the repo means auto-committed and therefore revertable, which is the
    whole basis for treating a write as reversible.
    """
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    try:
        candidate.resolve().relative_to(DOTFILES.resolve())
    except (ValueError, OSError):
        return False
    return True


def check_denylist(command: str) -> str | None:
    """Return a human reason if the command is categorically forbidden."""
    normalized = " ".join(command.split())
    for pattern, reason in DENYLIST:
        if pattern.search(normalized):
            return reason
    return None


def classify_file_write(path: str, cwd: str) -> tuple[Verdict, str]:
    """Edit/Write tools. Inside the repo is revertable; outside is not."""
    if is_in_repo(path, cwd):
        return Verdict.ALLOW, f"{path} is inside the dotfiles repo (git-revertable)"
    return Verdict.ASK, f"{path} is outside the dotfiles repo, so this is not auto-revertable"


#: Verbs that cannot mutate state on their own. A redirect can still make any
#: of these destructive, which is why `find_redirect_targets` runs separately.
READ_ONLY_VERBS = frozenset({
    "ls", "cat", "bat", "head", "tail", "less", "more", "wc", "file", "stat",
    "grep", "rg", "ag", "fd", "find", "tree", "readlink", "realpath", "basename",
    "dirname", "echo", "printf", "date", "uname", "whoami", "id", "pwd", "hostname",
    "which", "type", "env", "printenv", "uptime", "free", "df", "du", "lsblk",
    "lsusb", "lspci", "ps", "top", "htop", "btop", "journalctl", "dmesg",
    "hostnamectl", "checkupdates", "jq", "sort", "uniq", "cut", "tr",
    "diff", "md5sum", "sha256sum", "column", "nl", "seq", "true", "false",
    "playerctl", "wl-paste", "pgrep", "sleep", "test",
})

#: Verbs that are reversible only for particular subcommands. An empty tuple of
#: allowed subcommands means the whole verb is reversible.
#: Reversibility here means "undoable without data loss", not "harmless".
SUBCOMMAND_ALLOW: dict[str, tuple[tuple[str, ...], ...]] = {
    # Runtime-only state; a reload puts it back. NOT blanket-allowed:
    # `hyprctl dispatch exec` launches arbitrary programs (see FORBIDDEN).
    "hyprctl": (),
    "eww": (),
    "makoctl": (),
    "wpctl": (),
    "brightnessctl": (),
    # Reads and additive operations. Reset/clean/rebase are NOT here.
    "git": (
        ("status",), ("diff",), ("log",), ("show",), ("branch",), ("remote",),
        ("fetch",), ("add",), ("commit",), ("blame",), ("describe",), ("tag",),
        ("stash", "list"), ("ls-files",), ("rev-parse",), ("config", "--get"),
    ),
    # restart/reload/start are recoverable; disable/mask/stop change boot state.
    "systemctl": (
        ("status",), ("show",), ("cat",), ("list-units",), ("list-unit-files",),
        ("list-timers",), ("is-active",), ("is-enabled",), ("is-failed",),
        ("restart",), ("reload",), ("start",), ("daemon-reload",),
    ),
    # prune of build/layer caches only re-downloads; volumes hold real data.
    "docker": (
        ("ps",), ("images",), ("logs",), ("inspect",), ("stats",), ("version",),
        ("info",), ("builder", "prune"), ("image", "prune"),
        ("container", "prune"), ("network", "prune"),
    ),
}

#: Redirect targets, ignoring fd duplications like `2>&1`. The negative
#: lookbehind on a digit is what keeps `2>` from reading as a write.
_REDIRECT = re.compile(r"(?<![0-9&])>>?\s*([^\s;|&<>]+)")

_SEPARATORS = re.compile(r"\|\||&&|[;|]")


#: Flags that turn an otherwise read-only verb destructive. These never appear
#: as a shell redirect, so `find_redirect_targets` cannot see them, and the verb
#: allowlist alone would wave them straight through.
ARGUMENT_TRAPS: dict[str, frozenset[str]] = {
    "find": frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir",
                       "-fprint", "-fprintf", "-fls"}),
    "sort": frozenset({"-o", "--output"}),
    "rg": frozenset({"--pre"}),
    "grep": frozenset({"--devices"}),
}

#: Subcommands that hand execution to an arbitrary program, checked BEFORE the
#: allowlist so a permitted verb cannot be used as a launcher.
FORBIDDEN_SUBCOMMANDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "hyprctl": (("dispatch", "exec"), ("dispatch", "execr"), ("keyword", "exec")),
}


def _has_trap_flag(verb: str, tokens: list[str]) -> str | None:
    """Return the offending flag if a destructive-flag trap is tripped."""
    traps = ARGUMENT_TRAPS.get(verb)
    if not traps:
        return None
    for token in tokens[1:]:
        if token in traps:
            return token
        if "=" in token and token.split("=", 1)[0] in traps:
            return token
    return None


def _hits_forbidden_subcommand(verb: str, words: list[str]) -> tuple[str, ...] | None:
    for forbidden in FORBIDDEN_SUBCOMMANDS.get(verb, ()):
        if tuple(words[: len(forbidden)]) == forbidden:
            return forbidden
    return None


def find_redirect_targets(command: str) -> list[str]:
    """Paths this command would write to via > or >>.

    Shell redirects never appear as argv tokens, so a token-based allowlist is
    blind to them: `echo x > /etc/pacman.conf` looks like a harmless `echo`.
    """
    return [m.group(1) for m in _REDIRECT.finditer(command)]


#: Running as root is an escalation worth seeing, whatever the command is.
ELEVATORS = frozenset({"sudo", "doas", "pkexec", "run0"})


def uses_elevation(command: str) -> bool:
    """True if any segment of the command elevates privileges."""
    for segment in _SEPARATORS.split(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        for token in tokens:
            if Path(token).name in ELEVATORS:
                return True
    return False


def _strip_prefixes(tokens: list[str]) -> list[str]:
    """Drop sudo/doas and leading VAR=value assignments."""
    while tokens:
        head = tokens[0]
        if head in ("sudo", "doas", "env") or ("=" in head and not head.startswith("-")):
            tokens = tokens[1:]
            continue
        break
    return tokens


def _pacman_is_reversible(tokens: list[str]) -> bool:
    """Install and query are reversible; remove is not."""
    for token in tokens[1:]:
        if token.startswith("-") and not token.startswith("--"):
            letters = set(token[1:])
            return not (letters & {"R", "D"}) and bool(letters & {"S", "Q", "F", "U"})
    return False


def _segment_is_reversible(segment: str) -> tuple[bool, str]:
    try:
        tokens = shlex.split(segment)
    except ValueError as exc:
        return False, f"could not parse the command safely ({exc})"
    tokens = _strip_prefixes(tokens)
    if not tokens:
        return True, "empty segment"

    verb = Path(tokens[0]).name
    words = [t for t in tokens[1:] if not t.startswith("-")]

    if (forbidden := _hits_forbidden_subcommand(verb, words)) is not None:
        return False, f"{verb} {' '.join(forbidden)} can launch an arbitrary program"

    if (flag := _has_trap_flag(verb, tokens)) is not None:
        return False, f"{verb} {flag} mutates the filesystem"

    if verb in ("pacman", "yay", "paru"):
        if _pacman_is_reversible(tokens):
            return True, f"{verb} install/query is reversible"
        return False, f"{verb} operation removes packages"

    if verb == "sed" and any(t == "-i" or t.startswith("-i") for t in tokens[1:]):
        return False, "sed -i edits files in place"

    if verb in READ_ONLY_VERBS:
        return True, f"{verb} does not mutate state"

    if verb in SUBCOMMAND_ALLOW:
        allowed = SUBCOMMAND_ALLOW[verb]
        if not allowed:
            return True, f"{verb} only changes runtime state"
        for candidate in allowed:
            if tuple(words[: len(candidate)]) == candidate:
                return True, f"{verb} {' '.join(candidate)} is reversible"
        subcommand = words[0] if words else "(none)"
        return False, f"{verb} {subcommand} is not a reversible subcommand"

    return False, f"no reversibility rule covers {verb!r}"


def classify_bash(command: str, cwd: str) -> tuple[Verdict, str]:
    """Decide whether a shell command is reversible enough to run unattended.

    The denylist has already run, so `command` is not catastrophic - the only
    question is reversible (ALLOW) vs irreversible (ASK).

    Default-deny by design: an unrecognised verb ASKs rather than runs. A
    spurious prompt costs a keystroke; a wrong ALLOW costs data. This mirrors
    the lesson from the hook probes, where every accidental path failed open.
    """
    # Command substitution hides a whole second command from this analysis.
    if "$(" in command or "`" in command:
        return Verdict.ASK, "command substitution hides what would actually run"

    for target in find_redirect_targets(command):
        if not is_in_repo(target, cwd):
            return Verdict.ASK, f"writes to {target}, which is outside the dotfiles repo"

    # Elevation always surfaces. The user is about to be asked for a password;
    # showing them the exact command first is strictly better than a prompt
    # appearing out of nowhere, and it is what arms the password broker.
    if uses_elevation(command):
        return Verdict.ASK, "runs with elevated privileges"

    for segment in _SEPARATORS.split(command):
        segment = segment.strip()
        if not segment:
            continue
        ok, reason = _segment_is_reversible(segment)
        if not ok:
            return Verdict.ASK, reason

    return Verdict.ALLOW, "every part of this command is reversible"


def classify(tool_name: str, tool_input: dict, cwd: str) -> tuple[Verdict, str]:
    """Entry point used by hooks/pretooluse.py."""
    if tool_name in ("Read", "Grep", "Glob", "WebSearch", "WebFetch", "TodoWrite"):
        return Verdict.ALLOW, "read-only tool"

    if tool_name in ("Edit", "Write", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not path:
            return Verdict.ASK, "file tool called without a resolvable path"
        return classify_file_write(path, cwd)

    if tool_name == "Bash":
        command = (tool_input.get("command") or "").strip()
        if not command:
            return Verdict.ASK, "empty command"
        if (reason := check_denylist(command)) is not None:
            return Verdict.DENY, f"blocked by archpilot policy: {reason}"
        return classify_bash(command, cwd)

    # Unknown tool: no rule means no basis for waving it through.
    return Verdict.ASK, f"no policy rule for tool {tool_name!r}"
