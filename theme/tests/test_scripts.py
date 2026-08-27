"""Tests that the repo's scripts are actually reachable.

These are not theme tests, but theme/run-tests is the only harness blackwall
has outside archpilot, so they live here rather than not existing.

The failure they exist to catch is silent: docs/cheatsheet.md documents
`blackwall-watch --list` as something you type, link-bin decides what is on
PATH, and the two are separate hand-maintained lists. They drifted - nine
documented commands were unreachable, and nothing complained, because a
missing command only shows up when a person types it and gets "command not
found" long after the change that caused it.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
LINK_BIN = ROOT / "scripts" / "link-bin"
CHEATSHEET = ROOT / "docs" / "cheatsheet.md"

# Backends, daemons and privileged helpers. eww, waybar and hypr invoke these
# by full path; a link would add a second name for the same file.
NOT_ON_PATH = {
    "link-bin",
    "sddm-installer",
    "blackwall-cal-ui",
    "blackwall-net-ui",
    "blackwall-clocks",
    "blackwall-bar",
    "blackwall-notifyd",
    "blackwall-ask",
    "blackwall-setkey",
    "blackwall-media-focus",
    "blackwall-wifi.py",
    "blackwall-audio-devices.py",
    # Imported by blackwall-notify and blackwall-quiet, not run.
    "blackwall_glyphs.py",
}


def linked_names() -> set[str]:
    """The names link-bin puts in /usr/local/bin."""
    text = LINK_BIN.read_text()
    block = re.search(r"^SCRIPTS=\((.*?)^\)", text, re.S | re.M)
    assert block, "link-bin no longer has a SCRIPTS=( ... ) block"
    names = set(block.group(1).split())
    # EXTRA carries paths, not bare names.
    names |= {Path(p).name.strip('"') for p in re.findall(r'EXTRA=\((.*?)\)', text)[0].split()}
    return {n for n in names if n and not n.startswith("$")} | {"blackwall-theme"}


def documented_commands() -> set[str]:
    """Commands the cheatsheet shows at the start of a line, i.e. typed."""
    return set(
        re.findall(
            r"^(blackwall-[a-z-]+|setwall|rofi-paper|c2a)\b",
            CHEATSHEET.read_text(),
            re.M,
        )
    )


def test_every_documented_command_is_on_path():
    missing = documented_commands() - linked_names()
    assert not missing, (
        f"documented but not linked: {sorted(missing)}. "
        "Either add them to SCRIPTS in scripts/link-bin, or stop showing them "
        "as bare commands in docs/cheatsheet.md."
    )


def test_every_linked_script_exists():
    for name in linked_names():
        found = (ROOT / "scripts" / name).exists() or (ROOT / "theme" / name).exists()
        assert found, f"link-bin links {name}, which is not in the repo"


def test_user_facing_scripts_are_either_linked_or_explicitly_internal():
    """A new script must be classified, not silently forgotten."""
    on_disk = {p.name for p in (ROOT / "scripts").iterdir() if p.is_file()}
    unclassified = on_disk - linked_names() - NOT_ON_PATH
    assert not unclassified, (
        f"unclassified scripts: {sorted(unclassified)}. Add each to SCRIPTS in "
        "scripts/link-bin if a person types it, or to NOT_ON_PATH here if the "
        "panels call it by path."
    )


@pytest.mark.parametrize("name", sorted({p.name for p in (ROOT / "scripts").iterdir() if p.is_file()}))
def test_shebang_and_exec_bit_agree(name):
    """A shebang is a promise the file can be run; the exec bit has to keep it.

    Not every file in scripts/ is a command. blackwall-wifi.py and
    blackwall-audio-devices.py are helper modules run as `python3 <path>` by
    their parent script, so they carry no shebang and need no exec bit. The
    invariant is that the two agree - a shebang without the bit is a command
    that dies with "permission denied".
    """
    path = ROOT / "scripts" / name
    has_shebang = path.read_bytes()[:2] == b"#!"
    executable = bool(path.stat().st_mode & stat.S_IXUSR)
    assert has_shebang == executable, (
        f"scripts/{name}: shebang={has_shebang} but executable={executable}"
    )


def test_linked_scripts_are_runnable():
    """Whatever link-bin puts on PATH must survive being invoked."""
    for name in linked_names():
        path = ROOT / "scripts" / name
        if not path.exists():
            path = ROOT / "theme" / name
        assert path.read_bytes()[:2] == b"#!", f"{name} is linked but has no shebang"
        assert path.stat().st_mode & stat.S_IXUSR, f"{name} is linked but not executable"


def test_documented_subcommands_exist():
    """Catch invented flags.

    Writing docs from memory produced `blackwall-vpn forti-up`, `wg-down` and
    `tailscale-up`, none of which the script has - the real ones are toggles.
    A subcommand that does not exist reads exactly like one that does, so this
    only surfaces when someone types it.

    The check is deliberately loose: it asks whether the script mentions the
    token at all, which is enough to catch a name that was never implemented
    without needing to understand each script's dispatch.
    """
    text = CHEATSHEET.read_text()
    problems = []
    for script, sub in re.findall(
        r"^(blackwall-[a-z-]+) ([a-z][a-z0-9-]{2,})", text, re.M
    ):
        path = ROOT / "scripts" / script
        if not path.exists():
            continue
        if sub not in path.read_text():
            problems.append(f"{script} {sub}")
    assert not problems, f"documented but absent from the script: {sorted(set(problems))}"
