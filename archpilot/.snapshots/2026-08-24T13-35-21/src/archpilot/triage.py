"""Notice things worth acting on, without being asked.

Everything else in ArchPilot is reactive - you press a key, it answers. Triage
is the one part that speaks first, so its bar for speaking is deliberately
high: only conditions that are (a) actionable, (b) unambiguous, and (c) would
otherwise be discovered at a bad time.

Each finding carries the prompt that would fix it, so acting on one is a single
keystroke rather than a re-description of the problem.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    key: str
    summary: str
    detail: str
    prompt: str
    urgent: bool = False


def _run(*args: str, timeout: float = 8) -> str:
    if not shutil.which(args[0]):
        return ""
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def pacnew() -> Finding | None:
    """Config files pacman parked next to yours during an upgrade.

    Worth surfacing because nothing else does: the upgrade succeeds, the file
    sits there, and the setting you expected to change silently did not.
    """
    found = _run("find", "/etc", "-maxdepth", "5", "-name", "*.pacnew",
                 "-o", "-maxdepth", "5", "-name", "*.pacsave")
    files = [f for f in found.splitlines() if f.strip()]
    if not files:
        return None
    return Finding(
        key="pacnew",
        summary=f"{len(files)} config file(s) awaiting merge",
        detail="\n".join(files[:10]),
        prompt=("These .pacnew/.pacsave files are waiting to be merged:\n"
                + "\n".join(files[:10])
                + "\n\nShow me what differs in each and recommend what to do."),
    )


def _unit_name(line: str) -> str:
    """First real token of a `systemctl --failed` row.

    The rows are prefixed with a status bullet ("● foo.service loaded ..."),
    so a naive split()[0] yields the bullet rather than the unit.
    """
    for token in line.split():
        if token in {"\u25cf", "*", "\u00d7", "\u2716"}:
            continue
        return token
    return ""


def failed_units() -> Finding | None:
    lines = [l for l in _run("systemctl", "--failed", "--no-legend",
                             "--no-pager").splitlines() if l.strip()]
    lines += [l for l in _run("systemctl", "--user", "--failed", "--no-legend",
                              "--no-pager").splitlines() if l.strip()]
    if not lines:
        return None
    names = [_unit_name(l) for l in lines]
    names = [n for n in names if n][:8]
    if not names:
        return None
    return Finding(
        key="failed-units",
        summary=f"{len(names)} failed systemd unit(s)",
        detail="\n".join(names),
        prompt=("These systemd units are failed: " + ", ".join(names)
                + ". Look at their status and recent journal lines and tell me "
                  "what is wrong and how to fix it."),
        urgent=True,
    )


def disk_pressure(threshold: int = 90) -> Finding | None:
    out = _run("df", "--output=pcent,target", "-x", "tmpfs", "-x", "devtmpfs")
    tight = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 2 or not parts[0].endswith("%"):
            continue
        try:
            pct = int(parts[0].rstrip("%"))
        except ValueError:
            continue
        if pct >= threshold:
            tight.append((pct, parts[1]))
    if not tight:
        return None
    worst = max(tight)
    return Finding(
        key="disk",
        summary=f"{worst[1]} is {worst[0]}% full",
        detail="\n".join(f"{p}%  {m}" for p, m in sorted(tight, reverse=True)),
        prompt=(f"The filesystem mounted at {worst[1]} is {worst[0]}% full. "
                "Find what is using the space and suggest what is safe to remove."),
        urgent=worst[0] >= 95,
    )


def docker_reclaimable(min_gb: float = 5.0) -> Finding | None:
    raw = _run("docker", "system", "df", "--format", "{{json .}}")
    if not raw:
        return None
    total = 0.0
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = str(row.get("Reclaimable", "")).split("(")[0].strip()
        try:
            number = float(value[:-2]) if value[-2:].upper() in ("GB", "MB", "KB") else 0.0
        except (ValueError, IndexError):
            continue
        unit = value[-2:].upper()
        total += number if unit == "GB" else number / 1024 if unit == "MB" else 0.0
    if total < min_gb:
        return None
    return Finding(
        key="docker",
        summary=f"{total:.1f} GB reclaimable from Docker",
        detail=raw,
        prompt=(f"Docker reports about {total:.1f} GB reclaimable. Show me the "
                "breakdown and the safest way to reclaim it."),
    )


CHECKS = (pacnew, failed_units, disk_pressure, docker_reclaimable)


def scan() -> list[Finding]:
    findings = []
    for check in CHECKS:
        try:
            if (finding := check()) is not None:
                findings.append(finding)
        except Exception:  # noqa: BLE001 - a broken check must not break triage
            continue
    return findings


# --------------------------------------------------------------------------
# Notification bookkeeping.
# --------------------------------------------------------------------------
import time  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from . import paths  # noqa: E402

#: Do not re-nag about an unchanged finding more often than this.
REMIND_AFTER_S = 12 * 60 * 60


def _seen_file() -> _Path:
    return paths.state_dir() / "triage-seen.json"


def _load_seen() -> dict:
    try:
        return json.loads(_seen_file().read_text())
    except (OSError, ValueError):
        return {}


def unreported(findings: list[Finding], now: float | None = None) -> list[Finding]:
    """Findings worth notifying about right now.

    Silence is the default: an unchanged finding is only repeated after
    REMIND_AFTER_S. A notification that appears every hour about the same
    .pacnew file trains you to ignore the channel entirely.
    """
    now = time.time() if now is None else now
    seen = _load_seen()
    fresh = []
    for finding in findings:
        record = seen.get(finding.key)
        if isinstance(record, dict):
            if record.get("summary") == finding.summary and \
                    now - float(record.get("at", 0)) < REMIND_AFTER_S:
                continue
        fresh.append(finding)
    return fresh


def mark_reported(findings: list[Finding], now: float | None = None) -> None:
    now = time.time() if now is None else now
    seen = _load_seen()
    for finding in findings:
        seen[finding.key] = {"summary": finding.summary, "at": now}
    try:
        _seen_file().write_text(json.dumps(seen))
    except OSError:
        pass


def notify(findings: list[Finding]) -> None:
    if not findings:
        return
    urgent = any(f.urgent for f in findings)
    body = "\n".join(f"\u2022 {f.summary}" for f in findings[:5])
    title = "ArchPilot noticed something" if len(findings) > 1 else "ArchPilot noticed"
    try:
        subprocess.Popen(
            ["notify-send", "-a", "archpilot",
             "-u", "critical" if urgent else "normal",
             title, body + "\n\nSUPER+~ then ask, or: archpilot triage --ask <name>"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
