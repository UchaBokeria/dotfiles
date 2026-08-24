import json
import time

import pytest

from archpilot import triage
from archpilot.triage import Finding, disk_pressure, mark_reported, unreported


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(triage.paths, "state_dir", lambda: tmp_path)
    return tmp_path / "triage-seen.json"


def finding(key="disk", summary="/ is 91% full"):
    return Finding(key=key, summary=summary, detail="",
                   prompt="The filesystem at / is 91% full. Find what is using the space.")


def test_a_new_finding_is_reported(state):
    assert unreported([finding()]) == [finding()]


def test_an_unchanged_finding_is_not_repeated(state):
    f = finding()
    mark_reported([f])
    assert unreported([f]) == []


def test_a_changed_finding_is_reported_again(state):
    mark_reported([finding(summary="/ is 91% full")])
    assert unreported([finding(summary="/ is 96% full")]) != []


def test_an_old_finding_is_eventually_repeated(state):
    f = finding()
    mark_reported([f], now=time.time() - triage.REMIND_AFTER_S - 60)
    assert unreported([f]) == [f]


def test_corrupt_state_does_not_silence_reporting(state):
    state.write_text("{not json")
    assert unreported([finding()]) != []


def test_disk_pressure_only_fires_above_the_threshold(monkeypatch):
    monkeypatch.setattr(triage, "_run", lambda *a, **k: "Use% Mounted on\n 42% /\n 12% /home")
    assert disk_pressure() is None


def test_disk_pressure_reports_the_worst_mount(monkeypatch):
    monkeypatch.setattr(triage, "_run", lambda *a, **k: "Use% Mounted on\n 91% /\n 97% /data")
    found = disk_pressure()
    assert found is not None and "/data" in found.summary and found.urgent


def test_disk_pressure_ignores_unparseable_rows(monkeypatch):
    monkeypatch.setattr(triage, "_run", lambda *a, **k: "Use% Mounted on\nnonsense\n 99% /")
    assert disk_pressure() is not None


def test_unit_name_skips_the_status_bullet():
    assert triage._unit_name("● mako.service loaded failed failed Notifications") == "mako.service"
    assert triage._unit_name("× foo.service loaded failed") == "foo.service"


def test_a_broken_check_does_not_break_the_scan(monkeypatch):
    def boom():
        raise RuntimeError("nope")
    monkeypatch.setattr(triage, "CHECKS", (boom, lambda: finding()))
    assert len(triage.scan()) == 1


def test_every_finding_carries_an_actionable_prompt(monkeypatch):
    """A notification you cannot act on in one keystroke is just noise."""
    monkeypatch.setattr(triage, "CHECKS", (lambda: finding(),))
    for f in triage.scan():
        assert f.prompt and len(f.prompt) > 10
