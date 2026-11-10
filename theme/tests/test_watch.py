"""Tests for blackwall-watch's alerting rules.

The watch daemon runs unattended, so its two failure modes are both silent:
nag every five minutes about a service that has been dead for a week, or go
quiet and never say a new thing broke. Neither shows up as an error - only as
a person noticing they are being ignored, or missing an alert they needed.

Everything here drives the real script with stub commands on PATH, so the
logic under test is the logic the daemon runs, not a copy of it.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WATCH = ROOT / "scripts" / "blackwall-watch"

STUB = "#!/usr/bin/env bash\n{body}\n"


def write_exe(path: Path, body: str) -> None:
    path.write_text(STUB.format(body=body))
    path.chmod(0o755)


class Harness:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.bindir = tmp / "bin"
        self.bindir.mkdir()
        self.cache = tmp / "cache" / "blackwall" / "watch"
        self.cache.mkdir(parents=True)
        self.log = tmp / "log.txt"
        self.log.write_text("")
        self.fix_sys = tmp / "fix-sys"
        self.fix_user = tmp / "fix-user"
        self.fix_sys.write_text("")
        self.fix_user.write_text("")
        #: Extra environment for the next runs, set per test and private to it
        #: (os.environ would leak into every test after a failed assertion).
        self.extra: dict[str, str] = {}
        (tmp / "home").mkdir()

        write_exe(
            self.bindir / "notify-send",
            'log="${LOG:?}"\n'
            'if [[ "$*" == *" -A "* ]]; then\n'
            "  printf 'CARD %s\\n' \"$*\" >> \"$log\"\n"
            '  printf "%s\\n" "${PICK:-default}"\n'
            "fi",
        )
        write_exe(
            self.bindir / "systemctl",
            '[[ " $* " == *" reset-failed "* ]] && '
            '{ printf \'RESET %s\\n\' "$*" >> "${LOG:?}"; exit 0; }\n'
            '[[ " $* " == *" --user "* ]] && { cat "${FIX_USER:?}"; exit 0; }\n'
            'cat "${FIX_SYS:?}"',
        )
        # A probe that errors out, like a flaky bus: systemctl exits non-zero
        # and prints nothing. Put first so it covers both scopes.
        sysctl = self.bindir / "systemctl"
        sysctl.write_text(
            '#!/usr/bin/env bash\n[[ -n "${SYSTEMCTL_FAIL:-}" ]] && exit 1\n'
            + sysctl.read_text().split("\n", 1)[1]
        )
        write_exe(self.bindir / "kitty", 'printf "KITTY %s\\n" "$*" >> "${LOG:?}"')
        # The default action of a picked card runs for real, so anything that
        # opens a window must be a logging stub. 2026-10-28: without these the
        # downloads test opened Ucha's file manager on a pytest tmp dir.
        for opener in ("xdg-open", "gio", "thunar"):
            write_exe(
                self.bindir / opener,
                f'printf "{opener.upper()} %s\\n" "$*" >> "${{LOG:?}}"',
            )
        # date that can be told to advance, so a 6h cooldown is crossed instantly.
        write_exe(
            self.bindir / "date",
            'if [[ -n "${SKEW:-}" && "$1" == "+%s" ]]; then\n'
            '  echo $(( $(/usr/bin/date +%s) + SKEW ))\n'
            "else\n"
            '  exec /usr/bin/date "$@"\n'
            "fi",
        )
        # Everything else must not be reachable by the checks under test.
        write_exe(self.bindir / "df", 'echo "Use%"; echo " 10%"')
        write_exe(self.bindir / "free", "echo 'Mem: 100 10 90'")

    def env(self, skew: int | None = None, pick: str | None = None) -> dict[str, str]:
        e = {
            **os.environ,
            "PATH": f"{self.bindir}:{os.environ['PATH']}",
            "LOG": str(self.log),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
            "FIX_SYS": str(self.fix_sys),
            "FIX_USER": str(self.fix_user),
            # Checks that look twice before alarming must not sleep in tests.
            "RECHECK_SECONDS": "0",
            # Never the real home: gitdirty and downloads read $HOME.
            "HOME": str(self.tmp / "home"),
            **self.extra,
        }
        e.pop("SKEW", None)
        e.pop("PICK", None)
        if skew is not None:
            e["SKEW"] = str(skew)
        if pick is not None:
            e["PICK"] = pick
        return e

    def run(self, *args: str, skew: int | None = None, pick: str | None = None) -> subprocess.CompletedProcess:
        cp = subprocess.run(
            ["bash", str(WATCH), *args],
            env=self.env(skew, pick),
            capture_output=True,
            text=True,
            timeout=60,
        )
        time.sleep(0.4)  # fire() detaches its own subshell
        return cp

    def run_check(self, check: str, skew: int | None = None, pick: str | None = None,
                  pre: str = "") -> None:
        """Call one check by name, the way run_all does.

        `--check NAME` deliberately clears the state (it means "ignore the
        cooldown"), which would erase the strike count under test, so the
        function is called directly instead.
        """
        # SELF is what the script's own preamble sets from $0; a sourced copy
        # resolves $0 to "bash", so it has to be corrected after the source.
        # Without it the mute buttons the check generates point at "bash".
        script = (
            f"source {WATCH!s} --list >/dev/null; SELF={WATCH!s}; {pre}\n"
            # `wait`: fire() parks each card's waiter in the background, and
            # the run is only over once those have answered and run their
            # action. Waiting for them replaces a sleep that was a guess.
            f"check_{check} || true; wait"
        )
        subprocess.run(
            ["bash", "-c", script],
            env=self.env(skew, pick),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def cards(self) -> int:
        return sum(1 for line in self.log.read_text().splitlines() if line.startswith("CARD"))

    def out(self) -> str:
        return self.log.read_text()

    def failed(self, text: str, scope: str = "system") -> None:
        (self.fix_sys if scope == "system" else self.fix_user).write_text(text)

    def clear_log(self) -> None:
        self.log.write_text("")

    def state(self, name: str) -> Path:
        return self.cache / name


@pytest.fixture()
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# ---------------------------------------------------------------- strikes ---

def test_one_failure_notifies_three_times_then_goes_quiet(h: Harness):
    """Three strikes per unchanged set, spaced by the cooldown."""
    h.failed("a.service loaded failed failed\n")
    counts = []
    for n in range(5):
        h.run_check("units", skew=n * 21601)
        counts.append(h.cards())
    assert counts[0] == 1, f"a new failure must alert at once, got {counts}"
    assert counts[2] == 3, f"the third strike should fire, got {counts}"
    assert counts[3] == 3, f"a fourth repeat must be silent, got {counts}"
    assert counts[4] == 3, f"and stay silent, got {counts}"


def test_same_message_is_quiet_within_the_cooldown(h: Harness):
    """Without advancing the clock, the second pass says nothing."""
    h.failed("a.service loaded failed failed\n")
    h.run_check("units")
    h.run_check("units")
    assert h.cards() == 1


def test_changed_set_notifies_immediately_and_resets_count(h: Harness):
    """A new failure is news even though the old one used all its strikes."""
    h.failed("a.service loaded failed failed\n")
    for n in range(3):
        h.run_check("units", skew=n * 21601)
    assert h.cards() == 3
    h.failed("b.service loaded failed failed\n")
    h.run_check("units")  # no clock advance: a change alone is enough
    assert h.cards() == 4, "a changed set must alert at once"
    # And that new set now gets its own three.
    for n in (1, 2):
        h.run_check("units", skew=n * 21601)
    assert h.cards() == 6


def test_recovery_clears_state_so_the_same_failure_is_news_again(h: Harness):
    h.failed("a.service loaded failed failed\n")
    for n in range(3):
        h.run_check("units", skew=n * 21601)
    assert h.cards() == 3
    h.failed("")
    h.run_check("units")
    assert not h.state("units").exists(), "recovery must clear the state"
    assert not h.state("units.count").exists(), "recovery must clear the strike count"
    h.failed("a.service loaded failed failed\n")
    h.run_check("units")
    assert h.cards() == 4, "the same failure later must alert again"


# ------------------------------------------------------------------ mutes ---

def test_mute_silences_that_exact_message_and_a_change_ignores_it(h: Harness):
    h.failed("a.service loaded failed failed\n")
    h.run_check("units")
    msg = "sys:a.service user:"
    h.run("--mute", "units", msg)
    h.run_check("units", skew=30 * 86400)
    assert h.cards() == 1, "a muted condition must stay silent"
    h.failed("c.service loaded failed failed\n")
    h.run_check("units")
    assert h.cards() == 2, "a different condition is not the muted one"


def test_mute_expires_on_its_own(h: Harness):
    h.failed("a.service loaded failed failed\n")
    h.run_check("units")
    h.run("--mute", "units", "sys:a.service user:", "60")
    assert h.cards() == 1
    h.run_check("units", skew=61)
    assert h.cards() == 2, "a snoozed mute must alert once it lapses"


def test_unmute_removes_the_mute(h: Harness):
    h.run("--mute", "units", "sys:a.service user:")
    assert h.state("units.mute").exists()
    h.run("--unmute", "units")
    assert not h.state("units.mute").exists()


def test_mute_survives_hostile_characters_in_the_message(h: Harness):
    """The mute is generated as an eval'd command, so quoting has to hold.

    A unit name is not usually hostile, but it is arbitrary text from a
    systemctl listing being pasted into a command line, and the mute has to
    survive one parse of eval and one of the state file.
    """
    unit = """a's"service"""
    h.failed(f"{unit} loaded failed failed\n")
    h.run_check("units")
    msg = f"sys:{unit} user:"
    qq = subprocess.run(
        [
            "bash",
            "-c",
            f'source {WATCH!s} --list >/dev/null; SELF={WATCH!s}; mute_cmd units "$1"',
            "x",
            msg,
        ],
        env=h.env(),
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["bash", "-c", qq], env=h.env(), capture_output=True, text=True)
    assert h.state("units.mute").read_text().split("\n", 1)[1] == msg
    h.run_check("units", skew=30 * 86400)
    assert h.cards() == 1, "the hostile message must be suppressed like any other"


# --------------------------------------------------------------- legacy ---

def test_legacy_two_line_state_still_reads(h: Harness):
    """Files written by the previous version have no strike count."""
    h.failed("a.service loaded failed failed\n")
    h.state("units").write_text("1\nsys:a.service user:")
    h.run_check("units")
    assert h.cards() == 1, "an expired legacy state must fire"
    n = int(h.state("units.count").read_text().splitlines()[0])
    assert n == 2, f"the strike continues from 1, got {n}"


# -------------------------------------------------------------- actions ---

def test_every_check_offers_a_default_action():
    """A card with no default is a card clicking does nothing on."""
    text = WATCH.read_text()
    bodies = dict(re.findall(r"^(check_\w+)\(\) \{(.*?)^\}", text, re.M | re.S))
    assert bodies, "no check functions found"
    missing = [name for name, body in bodies.items() if 'default "' not in body]
    assert not missing, f"checks whose card does nothing on click: {missing}"


def test_action_strings_do_not_smuggle_unquoted_paths():
    """Actions run through eval, so paths inside them must use qq.

    The failure this catches produced a kitty trying to run a directory named
    `bash`: a path interpolated raw into a `kitty -e sh -c '...'` body.
    """
    bad = [
        n
        for n, line in enumerate(WATCH.read_text().splitlines(), 1)
        if re.search(r"sh -c '.*\$(HERE|SELF)", line)
    ]
    assert not bad, f"unquoted $HERE/$SELF inside an action at line(s) {bad}"


def test_disk_mute_button_actually_mutes(h: Harness):
    """End to end: choose the mute pill, and the next check is silent."""
    write_exe(h.bindir / "df", 'case "$*" in *--output=pcent*) echo 91;; *) echo 1G;; esac')
    h.run_check("disk", pick="mute")
    h.run_check("disk", skew=7200)
    assert h.cards() == 1, "the mute pill must have taken effect"


# ------------------------------------------------------------- recovery ---

def test_recovery_of_a_threshold_check_gives_it_its_strikes_back(h: Harness):
    """Without this, a disk that used its three alerts, was cleaned, and filled
    again would be silent forever: the identical message stays capped."""
    write_exe(h.bindir / "df", 'case "$*" in *--output=pcent*) echo "$PCT";; *) echo 1G;; esac')
    h.extra["PCT"] = "91"
    try:
        for n in range(4):
            h.run_check("disk", skew=n * 21601)
        assert h.cards() == 3, "three strikes, then quiet"
        h.extra["PCT"] = "40"
        h.run_check("disk", skew=4 * 21601)
        h.extra["PCT"] = "91"
        h.run_check("disk", skew=5 * 21601)
        assert h.cards() == 4, "the same 91% after a recovery is a new event"
    finally:
        h.extra.pop("PCT", None)


def test_recovery_keeps_the_cooldown_so_a_flapping_check_cannot_spam(h: Harness):
    write_exe(h.bindir / "df", 'case "$*" in *--output=pcent*) echo "$PCT";; *) echo 1G;; esac')
    h.extra["PCT"] = "91"
    try:
        h.run_check("disk")
        for pct in ("40", "91", "40", "91"):
            h.extra["PCT"] = pct
            h.run_check("disk")  # no clock advance
        assert h.cards() == 1
    finally:
        h.extra.pop("PCT", None)


def test_a_stamp_from_the_future_does_not_silence_a_check(h: Harness):
    """The clock was set back: a stamp ahead of now must not hold the check
    quiet until the clock catches up."""
    h.failed("a.service loaded failed failed\n")
    h.state("units").write_text(f"{int(time.time()) + 10 * 365 * 86400}\nsys:a.service user:")
    h.run_check("units")
    assert h.cards() == 1


# ------------------------------------------------------------------ cli ---

def test_mute_accepts_human_durations(h: Harness):
    """The cheatsheet shows `--mute units MSG 1h`; a non-number used to mean
    'until the message changes', silently."""
    h.run("--mute", "units", "sys:a.service user:", "1h")
    expiry = int(h.state("units.mute").read_text().splitlines()[0])
    assert abs(expiry - (time.time() + 3600)) < 30


def test_mute_rejects_a_bad_duration(h: Harness):
    cp = h.run("--mute", "units", "sys:a.service user:", "soon")
    assert cp.returncode != 0
    assert not h.state("units.mute").exists()


def test_unknown_check_names_never_become_paths(h: Harness):
    cp = h.run("--mute", "../../escape", "x")
    assert cp.returncode != 0
    assert not (h.tmp / "cache" / "escape.mute").exists()
    assert h.run("--check", "../../escape").returncode != 0
    assert h.run("--unmute", "nope").returncode != 0


def test_unmute_gives_a_capped_check_its_strikes_back(h: Harness):
    h.failed("a.service loaded failed failed\n")
    for n in range(3):
        h.run_check("units", skew=n * 21601)
    h.run_check("units", skew=3 * 21601)
    assert h.cards() == 3
    h.run("--unmute", "units")
    h.run_check("units", skew=4 * 21601)
    assert h.cards() == 4


# -------------------------------------------------------------- quoting ---

def test_reset_action_survives_systemd_escaped_unit_names(h: Harness):
    r"""systemd writes '-' and ' ' inside a path as \x2d / \x20, and the reset
    command is eval'd and then parsed again by `sh -c`."""
    unit = r"fsck@dev-disk-by\x2duuid-1234.service"
    h.failed(f"{unit} loaded failed failed\n", scope="user")
    h.run_check("units", pick="reset")
    reset = [l for l in h.out().splitlines() if l.startswith("RESET")]
    assert reset and unit in reset[0], f"unit name mangled by the shell: {reset}"


# -------------------------------------------------------------- process ---

def test_a_waiting_card_is_not_a_second_copy_of_the_daemon(h: Harness):
    """Parked waiters used to be subshells with the daemon's own command line:
    once the daemon died, blackwall-autostart adopted one as 'the daemon' and
    never started a real one."""
    write_exe(
        h.bindir / "notify-send",
        'pid=$$\n'
        'while [[ $pid -gt 1 ]]; do\n'
        '  printf "CHAIN %s\\n" "$(tr "\\0" " " < /proc/$pid/cmdline)" >> "${LOG:?}"\n'
        '  pid=$(awk "/^PPid/{print \\$2}" /proc/$pid/status)\n'
        'done\n'
        'echo default',
    )
    h.failed("a.service loaded failed failed\n")
    h.run_check("units")
    chain = [l for l in h.out().splitlines() if l.startswith("CHAIN")]
    assert any("--wait" in l for l in chain), "the waiter runs as its own invocation"
    assert not any("--daemon" in l for l in chain)


def test_autostart_matches_the_daemon_by_mode_not_just_by_script():
    """`blackwall-watch --list` or `blackwall-quiet dnd on` running at the
    moment of a pass must not count as the daemon being up."""
    text = (ROOT / "scripts" / "blackwall-autostart").read_text()
    assert re.search(r'^start_script watch "blackwall-watch --daemon"', text, re.M)
    assert re.search(r'^start_script quiet-dnd "blackwall-quiet dnd-watch"', text, re.M)


def test_the_cheap_urgent_check_runs_first():
    text = WATCH.read_text()
    order = re.search(r"^CHECKS=\((.*?)\)", text, re.M).group(1).split()
    assert order[0] == "desktop", "a half-dead desktop must not wait behind slow checks"
    assert order.index("updates") > order.index("memory")


# --------------------------------------------------- cycle 2 regressions ---

def test_mute_duration_with_a_leading_zero_is_not_an_octal_error(h: Harness):
    """`08` is an invalid octal in bash arithmetic. It used to leave the mute
    with no expiry at all - a typo turning a snooze into a permanent mute."""
    h.run("--mute", "units", "sys:a.service user:", "08")
    expiry = int(h.state("units.mute").read_text().splitlines()[0])
    assert abs(expiry - (time.time() + 8)) < 30
    cp = h.run("--mute", "units", "sys:a.service user:", "09m")
    assert cp.returncode == 0
    expiry = int(h.state("units.mute").read_text().splitlines()[0])
    assert abs(expiry - (time.time() + 540)) < 30


def test_a_wobbling_memory_reading_does_not_notify_every_poll(h: Harness):
    """A changed message fires at once, so keying memory on its percentage
    meant one card per five minutes while RAM hovered around the line."""
    write_exe(h.bindir / "free", 'echo "Mem: 100 $MEM 0"')
    try:
        for pct in ("92", "93", "92", "94", "93"):
            h.extra["MEM"] = pct
            h.run_check("memory")  # no clock advance
        assert h.cards() == 1
    finally:
        h.extra.pop("MEM", None)


def test_a_failed_update_check_is_not_a_recovery(h: Harness):
    """checkupdates failing (offline, timeout) used to count as zero updates:
    recovery, which handed back the strikes and dropped any mute."""
    write_exe(h.bindir / "checkupdates", 'exit "${CU_RC:-0}"')
    h.state("updates.mute").write_text(f"0\n30")
    h.extra["CU_RC"] = "1"
    try:
        h.run_check("updates")
    finally:
        h.extra.pop("CU_RC", None)
    assert h.state("updates.mute").exists(), "a failed run must not clear the mute"
    h.extra["CU_RC"] = "2"
    try:
        h.run_check("updates")
    finally:
        h.extra.pop("CU_RC", None)
    assert not h.state("updates.mute").exists(), "'nothing to do' is a real recovery"


# --------------------------------------------------- cycle 3 regressions ---

def df_shim(h: Harness) -> None:
    write_exe(h.bindir / "df", 'case "$*" in *--output=pcent*) echo "$PCT";; *) echo 1G;; esac')


def test_a_wobbling_disk_percentage_does_not_notify_every_poll(h: Harness):
    """The message is the severity tier, not the live percentage: a changed
    message fires at once, so 95 <-> 96 used to be a card on every poll."""
    df_shim(h)
    for pct in ("96", "95", "96", "97", "95", "96"):
        h.extra["PCT"] = pct
        h.run_check("disk")  # no clock advance
    assert h.cards() == 1, "one tier, one card, whatever the points do"


def test_a_worse_disk_tier_fires_but_an_improvement_does_not(h: Harness):
    df_shim(h)
    h.extra["PCT"] = "90"
    h.run_check("disk")
    assert h.cards() == 1
    h.extra["PCT"] = "96"  # crossed into critical: news
    h.run_check("disk")
    assert h.cards() == 2, "a genuinely worse tier fires at once"
    h.extra["PCT"] = "90"  # back down: good news, not a card
    h.run_check("disk")
    h.extra["PCT"] = "88"
    h.run_check("disk")
    h.extra["PCT"] = "96"  # and back up is the same episode
    h.run_check("disk")
    assert h.cards() == 2, "an improvement, or a return to a tier already announced, is silent"
    assert "disk 96% full" in h.out(), "the card still shows the live percentage"


def test_the_disk_tier_starts_over_after_a_recovery(h: Harness):
    df_shim(h)
    h.extra["PCT"] = "97"
    h.run_check("disk")
    h.extra["PCT"] = "40"
    h.run_check("disk")
    assert not h.state("disk.peak").exists()
    h.extra["PCT"] = "88"
    h.run_check("disk", skew=21601)  # past the cooldown the recovery kept
    assert h.cards() == 2
    assert h.state("disk.peak").read_text() == "warn"


def test_a_dip_just_under_the_disk_line_is_not_a_recovery(h: Harness):
    """84 <-> 85 must not hand the strikes back and alert on every crossing."""
    df_shim(h)
    h.extra["PCT"] = "86"
    h.run_check("disk")
    # A recovery drops the mute and writes a zero strike count; neither may
    # happen on a dip. (Counting cards alone could not tell: a recovery inside
    # the cooldown is silent too, which is how this test used to pass for the
    # wrong reason.)
    h.run("--mute", "disk", "warn")
    for pct in ("84", "86", "83", "86"):
        h.extra["PCT"] = pct
        h.run_check("disk", skew=1)
    assert h.cards() == 1
    assert h.state("disk").exists()
    assert h.state("disk.mute").exists(), "a dip is not a recovery: the mute stays"
    assert not h.state("disk.count").exists(), "and no recovery count was written"
    h.extra["PCT"] = "70"
    h.run_check("disk", skew=1)
    assert not h.state("disk.mute").exists(), "a real recovery does drop it"


def test_a_legacy_numeric_disk_state_is_not_a_new_condition(h: Harness):
    """Deploying the tiered key must not re-notify a condition already
    announced under the old numeric one."""
    df_shim(h)
    h.state("disk").write_text(f"{int(time.time())}\n94")
    h.state("disk.mute").write_text("0\n94")
    h.extra["PCT"] = "94"
    h.run_check("disk")
    assert h.cards() == 0
    assert h.state("disk").read_text().split("\n", 1)[1] == "warn"
    assert h.state("disk.mute").read_text().split("\n", 1)[1] == "warn"


def test_a_failed_disk_probe_is_not_a_recovery(h: Harness):
    """df printing nothing used to read as 0% and drop the mute."""
    write_exe(h.bindir / "df", "exit 1")
    h.state("disk.mute").write_text("0\nwarn")
    h.run_check("disk")
    assert h.state("disk.mute").exists()


def test_a_failed_systemctl_does_not_wipe_the_strikes(h: Harness):
    """A timed-out `systemctl --failed` used to mean 'no failed units': the
    state was cleared and the next good poll fired the same set as new."""
    h.failed("a.service loaded failed failed\n")
    h.run_check("units")
    assert h.cards() == 1
    before = (h.state("units").read_text(), h.state("units.count").read_text()
              if h.state("units.count").exists() else "")
    h.extra["SYSTEMCTL_FAIL"] = "1"
    h.run_check("units", skew=21601)
    assert h.state("units").exists(), "a failed probe must leave the state alone"
    assert h.state("units").read_text() == before[0]
    h.extra.pop("SYSTEMCTL_FAIL")
    h.run_check("units")  # good again, inside the cooldown
    assert h.cards() == 1, "no loop of cards across a flaky bus"


def test_a_failed_user_probe_alone_does_not_change_the_message(h: Harness):
    """One scope answering and the other not would change the message just as
    surely as a recovery."""
    h.failed("a.service loaded failed failed\n")
    h.failed("u.service loaded failed failed\n", scope="user")
    write_exe(
        h.bindir / "systemctl",
        '[[ " $* " == *" --user "* && -n "${USER_FAIL:-}" ]] && exit 1\n'
        '[[ " $* " == *" --user "* ]] && { cat "${FIX_USER:?}"; exit 0; }\n'
        'cat "${FIX_SYS:?}"',
    )
    h.run_check("units")
    h.extra["USER_FAIL"] = "1"
    h.run_check("units")
    assert h.cards() == 1


def test_a_wobbling_downloads_size_does_not_notify(h: Harness):
    """Keyed on whole gigabytes, a download crossing a gigabyte line was a new
    message and so a card, whatever the weekly cooldown."""
    (h.tmp / "home" / "Downloads").mkdir()
    write_exe(h.bindir / "du", 'printf "%s\\t%s\\n" "$DU_SIZE" "$3"')
    for gb in (6.1, 5.9, 6.2, 7.5, 6.0):
        h.extra["DU_SIZE"] = str(int(gb * 1073741824))
        h.run_check("downloads")
    assert h.cards() == 1


def test_a_failed_du_is_not_a_recovery(h: Harness):
    (h.tmp / "home" / "Downloads").mkdir()
    write_exe(h.bindir / "du", "exit 1")
    h.state("downloads.mute").write_text("0\nbig")
    h.run_check("downloads")
    assert h.state("downloads.mute").exists()


def test_a_growing_update_list_does_not_notify_daily(h: Harness):
    write_exe(h.bindir / "checkupdates", 'seq 1 "$N_UPDATES"')
    for n in (26, 27, 28, 30):
        h.extra["N_UPDATES"] = str(n)
        h.run_check("updates")  # same cooldown window
    assert h.cards() == 1
    for i, n in enumerate((31, 32), 1):
        h.extra["N_UPDATES"] = str(n)
        h.run_check("updates", skew=i * 86401)
    assert h.cards() == 3, "three strikes spaced by the cooldown, not one per count"
    h.extra["N_UPDATES"] = "33"
    h.run_check("updates", skew=3 * 86401)
    assert h.cards() == 3


def test_a_wobbling_memory_reading_near_the_line_is_not_recovery(h: Harness):
    write_exe(h.bindir / "free", 'echo "Mem: 100 $MEM 0"')
    h.extra["MEM"] = "93"
    h.run_check("memory")
    for pct in ("91", "93", "90", "93"):
        h.extra["MEM"] = pct
        h.run_check("memory", skew=3601)  # past the cooldown, so only strikes decide
    assert h.state("memory").exists()
    assert h.state("memory.count").read_text().split("\n")[0] in ("1", "2", "3")
    assert h.cards() <= 3


def test_a_failed_free_is_not_a_recovery(h: Harness):
    write_exe(h.bindir / "free", "exit 1")
    h.state("memory.mute").write_text("0\nhigh")
    h.run_check("memory")
    assert h.state("memory.mute").exists()


def test_an_unparseable_reminders_list_is_not_a_recovery(h: Harness):
    fake = h.tmp / "fakehere"
    fake.mkdir()
    write_exe(fake / "blackwall-cal", 'echo "Traceback: boom"')
    h.state("reminders.mute").write_text("0\n2")
    h.run_check("reminders", pre=f"HERE={fake}")
    assert h.state("reminders.mute").exists()
    write_exe(fake / "blackwall-cal", "echo '[]'")
    h.run_check("reminders", pre=f"HERE={fake}")
    assert not h.state("reminders.mute").exists(), "an empty list is a real recovery"


def make_old_dirty_repo(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    env = {**os.environ, "GIT_AUTHOR_DATE": "2020-01-01T00:00:00", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *cmd], env=env, check=True, capture_output=True)
    (repo / "dirty").write_text("x")
    return repo


def test_a_git_status_that_times_out_does_not_flip_the_message(h: Harness):
    """A timed-out status used to read as 'clean': the repo vanished from the
    set (a card for the smaller message) and came back on the next poll
    (another)."""
    root = h.tmp / "home" / "dev"
    make_old_dirty_repo(root, "alpha")
    make_old_dirty_repo(root, "beta")
    write_exe(
        h.bindir / "timeout",
        '[[ -n "${GIT_HANG:-}" && " $* " == *" status "* && "$GIT_HANG" == "$(basename "$(echo "$*" | sed "s/.*-C //;s/ status.*//")")" ]] && exit 124\n'
        'shift; exec "$@"',
    )
    h.run_check("gitdirty")
    assert h.cards() == 1
    h.extra["GIT_HANG"] = "alpha"
    h.run_check("gitdirty")
    h.extra.pop("GIT_HANG")
    h.run_check("gitdirty")
    assert h.cards() == 1, "a flaky status must not produce a card per flip"


def test_the_gitdirty_message_does_not_depend_on_directory_order(h: Harness):
    root = h.tmp / "home" / "dev"
    for n in ("zeta", "alpha", "mid"):
        make_old_dirty_repo(root, n)
    h.run_check("gitdirty")
    msg = h.state("gitdirty").read_text().split("\n", 1)[1]
    assert msg == "alpha mid zeta"


def pgrep_shim(h: Harness) -> None:
    write_exe(
        h.bindir / "pgrep",
        '[[ -n "${PGREP_RC:-}" ]] && exit "$PGREP_RC"\n'
        'name="$2"\n'
        'if [[ " ${MISSING:-} " == *" $name "* ]]; then\n'
        '  if [[ -n "${BLIP:-}" && ! -e "${BLIPF:?}" ]]; then touch "$BLIPF"; exit 1; fi\n'
        '  [[ -n "${BLIP:-}" ]] && exit 0\n'
        "  exit 1\n"
        "fi\nexit 0",
    )


def test_desktop_blip_is_not_an_alarm_but_a_lasting_gap_is(h: Harness):
    """A bar being restarted for a theme change is gone for a moment."""
    pgrep_shim(h)
    h.extra.update(HYPRLAND_INSTANCE_SIGNATURE="x", MISSING="waybar", BLIP="1",
                   BLIPF=str(h.tmp / "blip"))
    h.run_check("desktop")
    assert h.cards() == 0, "back on the second look: no card"
    h.extra.pop("BLIP")
    h.run_check("desktop")
    assert h.cards() == 1
    assert "missing: waybar" in h.out()


def test_a_broken_pgrep_is_not_a_dead_desktop_or_a_recovery(h: Harness):
    pgrep_shim(h)
    h.extra.update(HYPRLAND_INSTANCE_SIGNATURE="x", PGREP_RC="2")
    h.state("desktop.mute").write_text("0\nmissing: waybar")
    h.run_check("desktop")
    assert h.cards() == 0
    assert h.state("desktop.mute").exists()


def test_a_route_that_flaps_back_is_not_a_down_network(h: Harness):
    write_exe(
        h.bindir / "ip",
        '[[ -n "${IP_DOWN:-}" && ! -e "${IPF:?}" ]] && { touch "$IPF"; exit 2; }\n'
        '[[ -n "${IP_DOWN:-}" && -n "${IP_BLIP:-}" ]] && exit 0\n'
        '[[ -n "${IP_DOWN:-}" ]] && exit 2\nexit 0',
    )
    h.extra.update(IP_DOWN="1", IP_BLIP="1", IPF=str(h.tmp / "ipf"))
    h.run_check("network")
    assert h.cards() == 0
    h.extra.pop("IP_BLIP")
    h.run_check("network")
    assert h.cards() == 1


def test_no_check_keys_its_message_on_a_live_number():
    """The guard for the whole class: a message built from a measurement
    fires on every poll it moves. Counts of discrete things the user can
    change (pacnew files, reminders) are allowed; a measurement is not."""
    text = WATCH.read_text()
    for name in ("disk", "memory", "downloads", "updates"):
        body = re.search(rf"^check_{name}\(\) \{{(.*?)^\}}", text, re.M | re.S).group(1)
        fired = re.findall(r'should_fire \w+ "\$COOL_\w+" (\S+)', body)
        assert fired, f"{name}: no should_fire found"
        for key in fired:
            assert re.fullmatch(r'"\$tier"|"\w+"', key), f"{name} keys its message on {key}"


# --------------------------------------------------- cycle 4 regressions ---

def test_unmute_gives_a_capped_check_all_three_strikes_back(h: Harness):
    """The docs promise three; deleting only the count file left it at one."""
    h.failed("a.service loaded failed failed\n")
    for n in range(4):
        h.run_check("units", skew=n * 21601)
    assert h.cards() == 3
    h.run("--unmute", "units")
    for n in range(1, 6):
        h.run_check("units", skew=(3 + n) * 21601)
    assert h.cards() == 6, "three more cards after an unmute, then quiet again"


def test_a_legacy_numeric_memory_state_is_not_a_new_condition(h: Harness):
    """Memory moved from a keyed percentage to "high"; without the rekey the
    first alert after deploying looked like a changed condition: it fired at
    once past the cooldown and dropped a mute written under the old key."""
    write_exe(h.bindir / "free", 'echo "Mem: 100 95 0"')
    h.state("memory").write_text(f"{int(time.time())}\n97")
    h.state("memory.mute").write_text("0\n97")
    h.run_check("memory")
    assert h.cards() == 0, "the muted condition stays muted across the rekey"
    assert h.state("memory").read_text().split("\n", 1)[1] == "high"
    assert h.state("memory.mute").read_text().split("\n", 1)[1] == "high"


def test_a_legacy_disk_mute_alone_is_rekeyed(h: Harness):
    """`--check disk` removes the stamp but not the mute: a legacy mute can be
    the only numeric key left, and it must still land on the tier."""
    df_shim(h)
    h.state("disk.mute").write_text("0\n94")
    h.extra["PCT"] = "94"
    h.run_check("disk")
    assert h.cards() == 0
    assert h.state("disk.mute").read_text().split("\n", 1)[1] == "warn"


def test_a_quiet_pass_does_not_rewrite_its_state(h: Harness):
    """Every quiet check calls recovered() on every poll; a temp file and a
    rename each time is pure churn."""
    write_exe(h.bindir / "free", 'echo "Mem: 100 95 0"')
    h.run_check("memory")
    write_exe(h.bindir / "free", 'echo "Mem: 100 10 0"')
    h.run_check("memory")
    cf = h.state("memory.count")
    assert cf.read_text().startswith("0\n"), "recovery writes a zero count"
    before = cf.stat().st_ino
    for _ in range(3):
        h.run_check("memory")
    assert cf.stat().st_ino == before, "an unchanged count must not be rewritten"


def test_check_exits_zero_whether_or_not_it_had_something_to_report(h: Harness):
    """Its status used to depend on whether a mute file happened to exist."""
    assert h.run("--check", "network").returncode == 0  # route shim absent: may fire
    write_exe(h.bindir / "ip", "exit 0")
    plain = h.run("--check", "network")
    assert "nothing to report" in plain.stdout and plain.returncode == 0
    write_exe(h.bindir / "ip", "exit 2")  # down, and muted: nothing to report
    h.state("network.mute").write_text("0\ndown")
    muted = h.run("--check", "network")
    assert "may be muted" in muted.stdout and muted.returncode == 0


def test_help_prints_the_whole_header(h: Harness):
    """The usage text was cut at line 20 and ended mid-sentence."""
    out = h.run("--help").stdout.rstrip()
    assert out.endswith("only when\nclicked.") or out.endswith("clicked."), out[-80:]
    assert "--unmute NAME" in out and "exec.conf" not in out


def test_a_bad_loop_interval_cannot_become_a_busy_loop(h: Harness):
    """`sleep abc` fails instantly, which made the daemon run every check as
    fast as it could."""
    for bad in ("abc", "0", "5", ""):
        h.extra["LOOP_SECONDS"] = bad
        out = subprocess.run(
            ["bash", "-c", f"source {WATCH!s} --list >/dev/null; echo $LOOP_SECONDS"],
            env=h.env(), capture_output=True, text=True,
        ).stdout.strip()
        assert out == "300", f"LOOP_SECONDS={bad!r} gave {out!r}"
    h.extra["LOOP_SECONDS"] = "60"
    out = subprocess.run(
        ["bash", "-c", f"source {WATCH!s} --list >/dev/null; echo $LOOP_SECONDS"],
        env=h.env(), capture_output=True, text=True,
    ).stdout.strip()
    assert out == "60"


def test_the_gitdirty_card_does_not_call_a_busy_repo_untouched(h: Harness):
    make_old_dirty_repo(h.tmp / "home" / "dev", "alpha")
    h.run_check("gitdirty")
    assert "untouched" not in h.out() and "no commit in over a week" in h.out()


# ------------------------------------------------------------- autostart ---

def run_script_up(tmp: Path, tag: str, match: str) -> subprocess.CompletedProcess:
    """Run autostart's script_up/scan_for alone, against a private RUN dir."""
    text = (ROOT / "scripts" / "blackwall-autostart").read_text()
    funcs = re.search(r"^script_up\(\) \{.*?^\}\n\nscan_for\(\) \{.*?^\}\n", text, re.M | re.S)
    assert funcs, "script_up/scan_for not found"
    run = tmp / "run"
    run.mkdir(exist_ok=True)
    # A file, not `bash -c`: the match would then sit in this shell's own
    # command line (and its subshells'), and the scan would find the test. For
    # the same reason the match travels in the environment, not in argv.
    probe = tmp / "probe.sh"
    probe.write_text(f'set -uo pipefail\nRUN={run}\n{funcs.group(0)}\n'
                     f'script_up {tag} "$MATCH"; echo "rc=$?"\n')
    return subprocess.run(["bash", str(probe)], capture_output=True, text=True,
                          timeout=30, env={**os.environ, "MATCH": match})


def test_autostart_adopts_the_daemon_but_not_a_short_lived_run_of_the_same_script(tmp_path: Path):
    """The match is on the mode: a `--list` of the same script is not the daemon.

    The scan reads all of /proc, so the fake carries a name of its own: the real
    blackwall-watch daemon on a developer's machine must not satisfy the test.
    """
    uniq = f"bwtest{os.getpid()}x{time.monotonic_ns()}"
    fake = tmp_path / "fake"
    fake.write_text(f'#!/usr/bin/env bash\nexec -a "bash {uniq} $1" sleep 30\n')
    fake.chmod(0o755)
    match = f"{uniq} --daemon"
    list_run = subprocess.Popen([str(fake), "--list"])
    try:
        time.sleep(0.3)
        cp = run_script_up(tmp_path, "watch", match)
        assert "rc=1" in cp.stdout, "a --list run must not count as the daemon"
        daemon = subprocess.Popen([str(fake), "--daemon"])
        try:
            time.sleep(0.3)
            cp = run_script_up(tmp_path, "watch", match)
            assert "rc=0" in cp.stdout, cp.stdout
            assert (tmp_path / "run" / "watch.pid").read_text().strip() == str(daemon.pid)
            # And through the pidfile alone, once it is written.
            cp = run_script_up(tmp_path, "watch", match)
            assert "rc=0" in cp.stdout
            # A pidfile pointing at something else is not trusted: it falls back
            # to the scan and repairs itself.
            (tmp_path / "run" / "watch.pid").write_text(str(list_run.pid))
            cp = run_script_up(tmp_path, "watch", match)
            assert "rc=0" in cp.stdout
            assert (tmp_path / "run" / "watch.pid").read_text().strip() == str(daemon.pid)
        finally:
            daemon.kill()
            daemon.wait()
    finally:
        list_run.kill()
        list_run.wait()


def test_check_starts_the_disk_episode_over(h: Harness):
    """`--check` means "ignore what you remember": that includes the tier it
    had ratcheted up to, or a re-run at 90% would still call itself critical."""
    df_shim(h)
    h.extra["PCT"] = "97"
    h.run_check("disk")
    assert h.state("disk.peak").read_text() == "crit"
    h.extra["PCT"] = "90"
    h.run("--check", "disk")
    assert h.cards() == 2
    assert h.state("disk.peak").read_text() == "warn"
