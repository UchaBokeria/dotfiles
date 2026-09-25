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
    # NOTE: `/` must be a standalone path argument (lookahead), not end of
    # string. The old `\s+/\s*$` anchor let `rm -rf /; echo done` through as
    # merely ASK. `rm -rf /tmp/foo` still does NOT match (`/t` fails lookahead).
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rR][a-zA-Z]*f?[a-zA-Z]*\s+/(?=\s|[;|&#]|$)"),
     "recursive delete of /"),
    (re.compile(r"\brm\s+.*\s-{1,2}no-preserve-root\b"), "rm --no-preserve-root"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "filesystem creation"),
    (re.compile(r"\bdd\b[^|;&]*\bof=/dev/(sd|nvme|vd|mmcblk|disk)"), "raw write to a block device"),
    # `\|&?` covers `curl x |& sh` (stderr+stdout pipe), not just `|`.
    (re.compile(r"\b(curl|wget)\b[^|]*\|&?\s*(sudo\s+)?(ba|z|fi|da)?sh\b"), "piping a download into a shell"),
    (re.compile(r":\s*\(\s*\)\s*\{.*\|.*&.*\}\s*;?\s*:"), "fork bomb"),
    (re.compile(r"\bshred\b"), "unrecoverable file shredding"),
    (re.compile(r"\b(chmod|chown)\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*R[a-zA-Z]*\s+.*\s+/(?=\s|[;|&#]|$)"),
     "recursive ownership/permission change on /"),
    (re.compile(r">\s*/dev/(sd|nvme|vd|mmcblk)"), "redirect onto a block device"),
    # P11: --force-with-lease is the SAFE form (refuses on upstream change);
    # only bare --force / -f deny. The tempered `(?!-with-lease)` keeps the
    # lease form out of the match.
    (re.compile(r"\bgit\s+push\b[^|;&]*--force(?!-with-lease\b)[^|;&]*\bmain\b"), "force-push to main"),
    (re.compile(r"\bgit\s+push\b[^|;&]*(?<![\w-])-f\b[^|;&]*\bmain\b"), "force-push to main"),
    # `+` refspec prefix forces without the word --force: `git push +main`.
    # `(?<=\s)\+` requires the plus at a token start so `feature+main` is safe.
    (re.compile(r"\bgit\s+push\b[^|;&]*(?<=\s)\+[^|;&\s]*main\b"), "force-push to main"),
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
#:
#: Several familiar verbs are deliberately ABSENT from the blanket set because
#: some of their forms mutate: `date -s` sets the clock, `hostname X` sets it,
#: `hostnamectl set-hostname`, `journalctl --vacuum-*` deletes logs, `dmesg -C`
#: clears. Their READ forms are re-admitted explicitly in _segment_is_reversible
#: below; anything else falls through to default-deny ASK.
READ_ONLY_VERBS = frozenset({
    "ls", "cat", "bat", "head", "tail", "less", "more", "wc", "file", "stat",
    "grep", "rg", "ag", "fd", "find", "tree", "readlink", "realpath", "basename",
    "dirname", "echo", "printf", "uname", "whoami", "id", "pwd",
    "which", "type", "env", "printenv", "uptime", "free", "df", "du", "lsblk",
    "lsusb", "lspci", "ps", "top", "htop", "btop",
    "checkupdates", "jq", "sort", "uniq", "cut", "tr",
    "diff", "md5sum", "sha256sum", "column", "nl", "seq", "true", "false",
    "playerctl", "wl-paste", "pgrep", "sleep", "test",
})

#: Read-only argument shapes for verbs whose other forms mutate. Any flag NOT
#: listed here (or any positional that isn't a read selector) means ASK.
READ_ONLY_ARGS: dict[str, frozenset[str]] = {
    # date: display only. -s/--set/--date=STRING (parses+sets with -s) excluded.
    "date": frozenset({"-u", "--utc", "--universal", "-R", "--rfc-email",
                       "--rfc-2822", "--iso-8601", "-I"}),
    # journalctl: reading logs only. --vacuum-*/--rotate/--flush excluded.
    "journalctl": frozenset({"-u", "--unit", "-b", "--boot", "-k", "--dmesg",
                             "-n", "--lines", "-f", "--follow", "-x", "--catalog",
                             "--no-pager", "-o", "--output", "-p", "--priority",
                             "-S", "--since", "-U", "--until", "--user",
                             "--system", "-e", "--pager-end", "-r", "--reverse"}),
    # dmesg: reading only. -C/--clear excluded.
    "dmesg": frozenset({"-T", "--ctime", "-H", "--human", "-l", "--level",
                        "-f", "--facility", "-x", "--decode", "--color",
                        "-r", "--raw", "-t", "--notime"}),
    # hostnamectl with no args or status-ish verbs reads; set-* excluded.
    # hostname bare (no args) reads; any arg sets.
}


def _read_only_verb_with_args(verb: str, tokens: list[str]) -> bool:
    """True when a mutable-capable verb is used in a known read-only shape."""
    if verb == "hostname":
        return len(tokens) == 1
    if verb == "hostnamectl":
        rest = [t for t in tokens[1:] if t not in ("--no-ask-password", "--static",
                                                   "--transient", "--pretty")]
        return not rest or rest == ["status"]
    allowed = READ_ONLY_ARGS.get(verb)
    if allowed is None:
        return False
    args = tokens[1:]
    index = 0
    while index < len(args):
        token = args[index]
        if token in allowed:
            # Flags that take a value consume the next token too.
            if token in ("-u", "--unit", "-n", "--lines", "-o", "--output",
                         "-p", "--priority", "-S", "--since", "-U", "--until",
                         "-l", "--level", "-f", "--facility"):
                index += 2
            else:
                index += 1
            continue
        if token.startswith("-"):
            return False
        index += 1  # positional filter (unit name, pattern) is fine
    return True

#: Verbs that are reversible only for particular subcommands. An empty tuple of
#: allowed subcommands means the whole verb is reversible.
#: Reversibility here means "undoable without data loss", not "harmless".
#:
#: `hyprctl` stays blanket-allowed EXCEPT the forbidden launcher subcommands
#: below: `plugin load` a .so and `dispatch exit/killactive` remain over-broad
#: but out of scope for the gate's threat model (local compositor control, no
#: data loss, no persistence). The FORBIDDEN list covers the arbitrary-program
#: launchers. `brightnessctl set 0` blanks the screen but a reboot/keypress
#: restores it — annoying, not destructive; still ASK-worthy in principle but
#: left allowed to keep the common volume/brightness reads quiet. These are
#: judgment calls; tighten here if the model ever abuses them.
SUBCOMMAND_ALLOW: dict[str, tuple[tuple[str, ...], ...]] = {
    "hyprctl": (),
    "eww": (),
    "makoctl": (),
    "wpctl": (),
    "brightnessctl": (),
    # Reads and additive operations. Reset/clean/rebase are NOT here.
    # NOTE: `words` strips ALL flags, so destructive flag forms (`branch -D`,
    # `tag -d`, `remote remove/set-url`, `branch -m`) match the bare prefix
    # and would wrongly pass. The destructive-flags guard below runs first.
    "git": (
        ("status",), ("diff",), ("log",), ("show",), ("branch",), ("remote",),
        ("fetch",), ("add",), ("commit",), ("blame",), ("describe",), ("tag",),
        ("stash", "list"), ("ls-files",), ("rev-parse",),
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

# `&` (background) also starts a new command: `ls & rm -rf /tmp/x` runs both.
# Negative lookarounds keep `&&`, `&>` and `2>`-style redirections intact —
# those are handled by their own rules, not by splitting.
_SEPARATORS = re.compile(r"\|\||&&|[;|]|(?<![&|>0-9])&(?![&>])")


#: Flags that turn an otherwise read-only verb destructive. These never appear
#: as a shell redirect, so `find_redirect_targets` cannot see them, and the verb
#: allowlist alone would wave them straight through.
ARGUMENT_TRAPS: dict[str, frozenset[str]] = {
    "find": frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir",
                       "-fprint", "-fprintf", "-fls"}),
    # `fd` is find's successor and runs commands the same way: -x/--exec.
    "fd": frozenset({"-x", "--exec", "-X", "--exec-batch"}),
    "sort": frozenset({"-o", "--output"}),
    "rg": frozenset({"--pre"}),
    "grep": frozenset({"--devices"}),
}


def _extra_write_args(verb: str, tokens: list[str]) -> str | None:
    """Positional output args that make an otherwise read-only verb write.

    `uniq in.txt out.txt` writes its second file; `sort -oFILE` (attached
    form, no space) writes FILE. Neither is caught by the exact-flag traps.
    """
    args = [t for t in tokens[1:] if not t.startswith("-") or t in ("-",)]
    if verb == "uniq" and len(args) >= 2:
        return args[1]
    if verb == "sort":
        for token in tokens[1:]:
            if token.startswith("-o") and len(token) > 2 and not token.startswith("--"):
                return token[2:]
    return None

#: Subcommands that hand execution to an arbitrary program, checked BEFORE the
#: allowlist so a permitted verb cannot be used as a launcher.
FORBIDDEN_SUBCOMMANDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "hyprctl": (("dispatch", "exec"), ("dispatch", "execr"), ("keyword", "exec")),
}


def _has_trap_flag(verb: str, tokens: list[str]) -> str | None:
    """Return the offending flag if a destructive-flag trap is tripped."""
    traps = ARGUMENT_TRAPS.get(verb)
    if not traps:
        # `sort -oFILE` (attached) is handled by _extra_write_args, but the
        # bare `-o FILE` (separate token) belongs here.
        if verb == "sort" and "-o" in tokens[1:]:
            return "-o"
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


#: Flags that make an otherwise allowed git subcommand destructive. `words`
#: strips flags before prefix matching, so these are checked against the raw
#: tokens first: `git branch -D gone` must not ride the bare `branch` rule.
GIT_DESTRUCTIVE_FLAGS = frozenset({
    "-D", "-d", "-m", "-M", "-c", "-C", "--delete", "--remove",
    "--set-url", "--unset", "--rename",
})


def _git_has_destructive_flag(tokens: list[str]) -> str | None:
    """Offending flag if a git call mutates refs/remotes beyond the allowlist."""
    for token in tokens[1:]:
        if token in GIT_DESTRUCTIVE_FLAGS:
            return token
        if token.startswith("--delete=") or token.startswith("--unset="):
            return token
    # `remove`/`rm`/`mv`/`rename` as WORDS: `git remote remove origin`,
    # `git branch -m` covered above but `git remote rename` is word-form.
    words = [t.lower() for t in tokens[1:] if not t.startswith("-")]
    for index, word in enumerate(words):
        if word in ("remove", "rm", "rename", "mv") and index > 0:
            return words[index - 1] + " " + word
    return None


def find_redirect_targets(command: str) -> list[str]:
    """Paths this command would write to via > or >>.

    Shell redirects never appear as argv tokens, so a token-based allowlist is
    blind to them: `echo x > /etc/pacman.conf` looks like a harmless `echo`.
    Surrounding quotes are stripped: `> "/tmp/x"` targets /tmp/x, and without
    the strip the quoted form resolved as a relative path inside the repo and
    wrongly passed (U49).
    """
    targets = []
    for match in _REDIRECT.finditer(command):
        target = match.group(1).strip()
        if len(target) >= 2 and target[0] == target[-1] and target[0] in ("'", '"'):
            target = target[1:-1]
        targets.append(target)
    return targets


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
    """Install and query are reversible; remove is not.

    ALL short flags are scanned, not just the first: `pacman -S foo -R bar`
    removes packages and must not pass on the strength of the leading -S.
    """
    seen: set[str] = set()
    for token in tokens[1:]:
        if token.startswith("-") and not token.startswith("--"):
            seen |= set(token[1:])
    return not (seen & {"R", "D"}) and bool(seen & {"S", "Q", "F", "U"})


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

    if verb == "git" and (flag := _git_has_destructive_flag(tokens)) is not None:
        return False, f"git {flag} deletes or rewrites refs"

    if (forbidden := _hits_forbidden_subcommand(verb, words)) is not None:
        return False, f"{verb} {' '.join(forbidden)} can launch an arbitrary program"

    # `sort -o /dev/null` writes nowhere; check before the -o trap fires.
    if verb == "sort" and "-o" in tokens[1:]:
        try:
            target = tokens[tokens.index("-o") + 1]
        except IndexError:
            target = ""
        if target == "/dev/null":
            return True, "sort -o /dev/null discards its output"
    if (flag := _has_trap_flag(verb, tokens)) is not None:
        return False, f"{verb} {flag} mutates the filesystem"

    if (extra := _extra_write_args(verb, tokens)) is not None:
        # Always surfaced: the turn-scoped auto-commit only covers Edit/Write
        # tools, and segment analysis has no cwd to judge repo membership, so
        # a prompt here is cheaper than a wrong ALLOW.
        if extra != "/dev/null":
            return False, f"{verb} writes to {extra}"

    if verb in ("pacman", "yay", "paru"):
        # -Scc/-Sc wipes the package cache (irreversible re-download).
        if any(re.fullmatch(r"-Scc?", token) for token in tokens[1:]):
            return False, f"{verb} -Sc wipes the package cache"
        if _pacman_is_reversible(tokens):
            return True, f"{verb} install/query is reversible"
        return False, f"{verb} operation removes packages"

    if verb == "sed" and any(t == "-i" or t.startswith("-i") for t in tokens[1:]):
        return False, "sed -i edits files in place"

    if verb in READ_ONLY_VERBS:
        return True, f"{verb} does not mutate state"

    if verb in ("date", "journalctl", "dmesg", "hostname", "hostnamectl"):
        if _read_only_verb_with_args(verb, tokens):
            return True, f"{verb} read-only use does not mutate state"
        return False, f"{verb} can change system state with these arguments"

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
