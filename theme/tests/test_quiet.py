"""Tests for blackwall-quiet's do-not-disturb enforcement.

swaync's DND is not absolute: its notify path computes
`bypass_dnd = urgency == CRITICAL || hint SWAYNC_BYPASS_DND` and skips the DND
check entirely when that is true (notiDaemon.vala:224, v0.12.6), so a critical
notification pops while DND is on - and everything blackwall-watch sends is
critical. The one hook that runs before that check is
`notification-visibility`, so DND is enforced here as a `muted` rule covering
every urgency: no popup, still in the centre.

Everything here drives the real script with stub commands on PATH, so the
logic under test is the logic the panels run, not a copy of it. The stubs keep
one shared state file for the DND setting, the way the real gsettings key and
the daemon's `-D` answer agree with each other.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
QUIET = ROOT / "scripts" / "blackwall-quiet"


def write_exe(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(0o755)


@pytest.fixture
def env(tmp_path):
    """A fake session: config dir, data dir, and stub commands on PATH."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    cfg = tmp_path / "config"
    data = tmp_path / "data"
    state = tmp_path / "dnd"  # the shared DND setting, true/false
    state.write_text("false")
    reloads = tmp_path / "reloads.log"
    reloads.write_text("")

    write_exe(
        bindir / "swaync-client",
        'S="$DND_STATE"\n'
        'case "$1" in\n'
        '  -D) cat "$S";;\n'
        '  -dn) printf true > "$S"; cat "$S";;\n'
        '  -df) printf false > "$S"; cat "$S";;\n'
        '  --reload-config) printf x >> "$RELOADS";;\n'
        'esac\nexit 0\n',
    )
    write_exe(
        bindir / "gsettings",
        '[[ "$1" == get ]] && { cat "$DND_STATE"; echo; }\n'
        '[[ "$1" == monitor ]] && { sleep 300; }\n'
        'exit 0\n',
    )
    write_exe(bindir / "busctl", 'printf "Comm=swaync\\n"\nexit 0\n')
    for name in ("eww", "makoctl", "systemctl", "systemd-run",
                 "notify-send", "swaync"):
        write_exe(bindir / name, "exit 0\n")

    base = {
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "XDG_CONFIG_HOME": str(cfg),
        "XDG_DATA_HOME": str(data),
        "DND_STATE": str(state),
        "RELOADS": str(reloads),
        # Skip the detach-and-reexec: the test wants the exit status.
        "BW_DETACHED": "1",
    }
    return base, cfg, state, reloads


def run(env, *args, timeout=30):
    base, _, _, _ = env
    return subprocess.run(
        ["python3", str(QUIET), *args],
        capture_output=True, text=True, timeout=timeout, env=base,
    )


def live_rules(env):
    _, cfg, _, _ = env
    return json.loads((cfg / "swaync" / "config.json").read_text())[
        "notification-visibility"]


def test_dnd_sync_adds_a_muted_rule_covering_every_urgency(env):
    _, _, state, _ = env
    state.write_text("true")
    r = run(env, "dnd-sync")
    assert r.returncode == 0
    assert live_rules(env)["blackwall-dnd"] == {
        "state": "muted", "urgency": ".*",
    }


def test_dnd_sync_removes_only_its_own_rule(env):
    base, cfg, state, _ = env
    (cfg / "swaync").mkdir(parents=True)
    (cfg / "swaync" / "config.json").write_text(json.dumps({
        "notification-visibility": {
            "blackwall-dnd": {"state": "muted", "urgency": ".*"},
            "bw-slack": {"state": "muted", "app-name": "slack"},
        }
    }))
    state.write_text("false")
    assert run(env, "dnd-sync").returncode == 0
    rules = live_rules(env)
    assert "blackwall-dnd" not in rules
    # A per-app rule the user set is none of this feature's business.
    assert rules["bw-slack"] == {"state": "muted", "app-name": "slack"}


def test_dnd_sync_is_idempotent_and_does_not_reload(env):
    _, _, state, reloads = env
    state.write_text("true")
    assert run(env, "dnd-sync").stdout.strip() == "changed"
    assert run(env, "dnd-sync").stdout.strip() == "already in step"
    # One config rewrite means one reload; the no-op must not reload swaync.
    assert reloads.read_text() == "x"


def test_dnd_on_writes_the_rule_alongside_the_setting(env):
    assert run(env, "dnd", "on").returncode == 0
    base, _, state, _ = env
    assert state.read_text() == "true"
    assert live_rules(env)["blackwall-dnd"]["state"] == "muted"


def test_dnd_off_removes_the_rule(env):
    _, _, state, _ = env
    state.write_text("true")
    run(env, "dnd-sync")
    assert run(env, "dnd", "off").returncode == 0
    assert state.read_text() == "false"
    assert "blackwall-dnd" not in live_rules(env)


def test_dnd_watch_applies_the_rule_at_startup(env):
    """The watcher repairs the state after a restart or a config rewrite that
    dropped the rule while DND itself never moved."""
    base, _, state, _ = env
    state.write_text("true")
    proc = subprocess.Popen(
        ["python3", str(QUIET), "dnd-watch"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=base,
    )
    try:
        for _ in range(100):
            time.sleep(0.1)
            try:
                if "blackwall-dnd" in live_rules(env):
                    break
            except (OSError, json.JSONDecodeError, KeyError):
                pass
        else:
            pytest.fail("dnd-watch never applied the rule")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_a_swaync_restart_with_dnd_on_needs_no_repair(env):
    """Checked against the live daemon: a restart or crash neither resets the
    gsettings key nor touches config.json, so with DND on and the rule in place
    a sync after the restart has nothing to do - and, above all, does not
    reload swaync's config in the middle of its startup."""
    _, _, state, reloads = env
    state.write_text("true")
    assert run(env, "dnd-sync").stdout.strip() == "changed"
    reloads.write_text("")
    # The "restart": the daemon comes back and reads the same key.
    assert run(env, "dnd-state").stdout.strip() == "true"
    assert run(env, "dnd-sync").stdout.strip() == "already in step"
    assert reloads.read_text() == ""
    assert live_rules(env)["blackwall-dnd"]["state"] == "muted"


def test_dnd_sync_restores_a_rule_lost_while_dnd_is_still_on(env):
    """The one thing that can drop the rule is something rewriting swaync's
    config (the installer copies the repo's over the live one). gsettings still
    says DND is on, so the next sync puts the rule back."""
    _, cfg, state, _ = env
    state.write_text("true")
    assert run(env, "dnd-sync").returncode == 0
    (cfg / "swaync" / "config.json").write_text(
        json.dumps({"notification-visibility": {}}))
    assert run(env, "dnd-sync").stdout.strip() == "changed"
    assert "blackwall-dnd" in live_rules(env)


def test_dnd_sync_never_overwrites_a_config_it_cannot_read(env):
    """The installer copies config.json with a plain `cp`, so a read can land
    mid-copy and see truncated JSON. Treating that as "empty" and saving
    replaced the whole swaync config with one rule."""
    _, cfg, state, _ = env
    (cfg / "swaync").mkdir(parents=True)
    broken = '{"notification-visibility": {"bw-slack": {"state": "mut'
    (cfg / "swaync" / "config.json").write_text(broken)
    state.write_text("true")
    assert run(env, "dnd-sync").stdout.strip() == "already in step"
    assert (cfg / "swaync" / "config.json").read_text() == broken


def test_dnd_sync_keeps_every_other_key(env):
    _, cfg, state, _ = env
    (cfg / "swaync").mkdir(parents=True)
    original = {"timeout": 8, "positionX": "right",
                "notification-visibility": {}}
    (cfg / "swaync" / "config.json").write_text(json.dumps(original))
    state.write_text("true")
    run(env, "dnd-sync")
    live = json.loads((cfg / "swaync" / "config.json").read_text())
    assert live["timeout"] == 8 and live["positionX"] == "right"


def test_repo_swaync_config_carries_no_runtime_rules():
    """The live file is a copy that this script rewrites. If a rule ever gets
    copied back, every fresh install starts with DND silently on or an app
    muted for good."""
    repo_cfg = json.loads((ROOT / "swaync" / "config.json").read_text())
    rules = repo_cfg.get("notification-visibility", {})
    leaked = [k for k in rules if k == "blackwall-dnd" or k.startswith("bw-")]
    assert not leaked, f"runtime rules found in the repo's swaync/config.json: {leaked}"


def test_concurrent_mutes_do_not_lose_each_other(env):
    """Each mute is load-modify-save on one file; without a lock the last
    writer wins and some apps are 'muted' with no rule."""
    base = env[0]
    apps = [f"app{i}" for i in range(8)]
    procs = [subprocess.Popen(["python3", str(QUIET), "mute", a, "1h"],
                              env=base, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL) for a in apps]
    for p in procs:
        assert p.wait(timeout=60) == 0
    rules = live_rules(env)
    missing = [a for a in apps if f"bw-{a}" not in rules]
    assert not missing, f"lost rules: {missing}"
    st = json.loads((Path(base["XDG_DATA_HOME"]) / "blackwall" / "quiet.json").read_text())
    assert len(st) == len(apps)


def test_dnd_watch_outlives_its_monitor(env):
    """If `gsettings monitor` exits, the daemon must keep enforcing DND on the
    timer instead of quietly ending (nothing restarts it until the next
    autostart pass)."""
    base, cfg, state, _ = env
    # A monitor that dies at once, like a missing schema or restarted dconf.
    write_exe(Path(base["PATH"].split(os.pathsep)[0]) / "gsettings",
              '[[ "$1" == get ]] && { cat "$DND_STATE"; echo; }\nexit 0\n')
    state.write_text("false")
    proc = subprocess.Popen(["python3", str(QUIET), "dnd-watch"], env=base,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        assert proc.poll() is None, "dnd-watch exited when its monitor did"
        state.write_text("true")
        for _ in range(200):
            time.sleep(0.1)
            try:
                if "blackwall-dnd" in live_rules(env):
                    break
            except (OSError, json.JSONDecodeError, KeyError):
                pass
        else:
            pytest.fail("rule never applied after the monitor was gone")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_dnd_watch_takes_its_monitor_down_with_it(env):
    """The monitor is a child; killing the daemon must not leave one behind
    per restart."""
    base, _, _, _ = env
    pidfile = Path(base["DND_STATE"]).parent / "monitor.pid"
    write_exe(Path(base["PATH"].split(os.pathsep)[0]) / "gsettings",
              f'[[ "$1" == get ]] && {{ cat "$DND_STATE"; echo; }}\n'
              f'[[ "$1" == monitor ]] && {{ echo $$ > {pidfile}; exec sleep 300; }}\n'
              "exit 0\n")
    proc = subprocess.Popen(["python3", str(QUIET), "dnd-watch"], env=base,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if pidfile.exists() and pidfile.read_text().strip():
                break
            time.sleep(0.1)
        mon = int(pidfile.read_text().strip())
        assert Path(f"/proc/{mon}").exists()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    for _ in range(30):
        if not Path(f"/proc/{mon}").exists():
            break
        time.sleep(0.1)
    else:
        os.kill(mon, 9)
        pytest.fail("gsettings monitor outlived dnd-watch")


# --------------------------------------------------- cycle 2 regressions ---

def test_a_bad_duration_is_refused_before_the_detach(env):
    """Validation used to happen inside the detached copy, whose output goes
    nowhere: `mute slack 2h` printed nothing and muted nothing."""
    base, _, _, _ = env
    e = {k: v for k, v in base.items() if k != "BW_DETACHED"}
    r = subprocess.run(["python3", str(QUIET), "mute", "slack", "2h"],
                       capture_output=True, text=True, timeout=30, env=e)
    assert r.returncode == 1
    assert "duration must be one of" in r.stderr


def test_the_expiry_timer_runs_unmute_in_the_foreground_and_replaces_the_old_one(env):
    """A transient service's cgroup is killed when its main process exits, so
    the detached copy `unmute` normally forks never finished: timed mutes never
    lifted. And a second mute of the same app must not leave the first timer
    pending (it would lift the longer mute early)."""
    base, _, _, _ = env
    log = Path(base["DND_STATE"]).parent / "calls.log"
    bindir = Path(base["PATH"].split(os.pathsep)[0])
    write_exe(bindir / "systemd-run", f'echo "RUN $*" >> {log}')
    write_exe(bindir / "systemctl", f'echo "CTL $*" >> {log}')
    r = run(env, "mute", "slack", "1h")
    assert r.returncode == 0
    calls = log.read_text().splitlines()
    stop = next(i for i, c in enumerate(calls) if c.startswith("CTL") and "stop" in c
                and "blackwall-unquiet-bw-slack.timer" in c)
    runi = next(i for i, c in enumerate(calls) if c.startswith("RUN"))
    assert stop < runi, "the old timer is stopped before the new one is made"
    assert "--setenv=BW_DETACHED=1" in calls[runi]


def test_dnd_watch_lifts_a_mute_whose_timer_was_lost(env):
    """Transient timers do not survive a reboot; `expire` is the sweep that
    covers for them, and the watcher is what runs it."""
    base, cfg, _, _ = env
    assert run(env, "mute", "slack", "15m").returncode == 0
    assert "bw-slack" in live_rules(env)
    statef = Path(base["XDG_DATA_HOME"]) / "blackwall" / "quiet.json"
    st = json.loads(statef.read_text())
    st["bw-slack"]["until"] = int(time.time()) - 5
    statef.write_text(json.dumps(st))
    proc = subprocess.Popen(["python3", str(QUIET), "dnd-watch"], env=base,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            time.sleep(0.1)
            if "bw-slack" not in live_rules(env):
                break
        else:
            pytest.fail("an expired mute was never lifted")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# --------------------------------------------------- cycle 3 regressions ---

def test_a_blank_application_name_is_refused_before_the_detach(env):
    """swaync reads app-name as a pattern and an empty one matches every
    application: `mute ""` would silence all of them with no way to see why."""
    base, cfg, _, _ = env
    e = {k: v for k, v in base.items() if k != "BW_DETACHED"}
    for cmd in ("mute", "ignore"):
        r = subprocess.run(["python3", str(QUIET), cmd, "  "],
                           capture_output=True, text=True, timeout=30, env=e)
        assert r.returncode == 1 and "name is needed" in r.stderr
    r = run(env, "mute", "")  # detached copy: the guard still holds
    assert r.returncode == 1
    assert not (cfg / "swaync" / "config.json").exists()


def test_an_unknown_dnd_argument_is_refused_not_a_toggle(env):
    base, _, state, _ = env
    e = {k: v for k, v in base.items() if k != "BW_DETACHED"}
    r = subprocess.run(["python3", str(QUIET), "dnd", "banana"],
                       capture_output=True, text=True, timeout=30, env=e)
    assert r.returncode == 1 and "on, off or toggle" in r.stderr
    assert state.read_text() == "false"


def test_dnd_asks_the_bus_for_its_owner_once(env):
    """daemon() is a busctl call with a 4s timeout; `dnd` used to make two."""
    base, _, _, _ = env
    log = Path(base["DND_STATE"]).parent / "busctl.log"
    write_exe(Path(base["PATH"].split(os.pathsep)[0]) / "busctl",
              f'echo x >> {log}\nprintf "Comm=swaync\\n"')
    assert run(env, "dnd", "on").returncode == 0
    assert len(log.read_text().splitlines()) == 1


# --------------------------------------------------- cycle 4 regressions ---

def load_quiet(env, monkeypatch):
    """The script as a module, with its paths taken from the fake session."""
    import importlib.machinery
    import importlib.util
    base = env[0]
    for k in ("PATH", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "DND_STATE", "RELOADS"):
        monkeypatch.setenv(k, base[k])
    loader = importlib.machinery.SourceFileLoader("bwquiet_under_test", str(QUIET))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_expire_does_not_lift_a_mute_renewed_after_it_looked(env, monkeypatch):
    """`expire` reads the state, finds a rule due, and only then takes the lock.
    A longer mute written in that gap must survive the stale decision."""
    mod = load_quiet(env, monkeypatch)
    assert run(env, "mute", "slack", "15m").returncode == 0
    stale = mod.load_state()
    stale["bw-slack"]["until"] = int(time.time()) - 5
    # What expire() saw ...
    real_load = mod.load_state
    mod.load_state = lambda: stale
    seen = mod.load_state()
    # ... and what is on disk by the time it gets the lock: a fresh 1d mute.
    mod.load_state = real_load
    assert run(env, "mute", "slack", "1d").returncode == 0
    assert seen["bw-slack"]["until"] < time.time()
    mod.unmute("slack", only_if_expired=True)
    assert "bw-slack" in live_rules(env), "a renewed mute was lifted by a stale expiry"
    # A genuinely due rule is still lifted.
    st = real_load()
    st["bw-slack"]["until"] = int(time.time()) - 5
    mod.save_state(st)
    mod.unmute("slack", only_if_expired=True)
    assert "bw-slack" not in live_rules(env)


def test_the_lock_file_is_not_touched_by_taking_it(env, monkeypatch):
    """The DND watcher takes the lock every minute; truncating the lock file
    each time was a metadata write for nothing."""
    mod = load_quiet(env, monkeypatch)
    with mod.config_lock():
        pass
    lock = mod.STATE.parent / "config.lock"
    before = lock.stat().st_mtime_ns
    time.sleep(0.05)
    with mod.config_lock():
        pass
    assert lock.stat().st_mtime_ns == before
