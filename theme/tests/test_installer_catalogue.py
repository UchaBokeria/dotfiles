"""Tests that the installer catalogue still describes the rice.

The failure these exist to catch is the one that only shows up on somebody
else's machine, months later: a new script, config file or step is added here,
works because it exists on THIS machine, and is missing from
`installer/data/*.toml` - so the next clone installs a rice with a hole in it.

Nothing here talks to pacman or touches the filesystem outside the repo. They
are string-and-path tests over the catalogue, deliberately cheap, so they can
run on every `theme/run-tests`.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "installer" / "data"


def load(name: str) -> dict:
    with (DATA / name).open("rb") as handle:
        return tomllib.load(handle)


@pytest.fixture(scope="module")
def links() -> dict:
    return load("links.toml")


@pytest.fixture(scope="module")
def steps() -> list[dict]:
    return load("steps.toml")["step"]


@pytest.fixture(scope="module")
def questions() -> list[dict]:
    return load("questions.toml")["question"]


@pytest.fixture(scope="module")
def tracked() -> set[str]:
    """What git tracks, or None when git cannot say.

    The installer runs this suite as a step, and `git ls-files` answers nothing
    in a working tree git will not read - an unpacked tarball, or a checkout
    whose ownership git calls dubious. Treating "no output" as "nothing is
    committed" failed the whole install for a reason that had nothing to do
    with the rice.
    """
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return set(out.stdout.split("\n"))


# Sources the catalogue names on purpose without them being files in the repo.
NOT_A_SOURCE = {"(in repo)"}


def test_every_link_source_exists(links: dict) -> None:
    """A catalogue entry pointing at nothing installs nothing."""
    missing = [
        link["repo"]
        for link in links["link"]
        if link.get("kind") not in {"generated", "broken"}
        and link["repo"] not in NOT_A_SOURCE
        and not (ROOT / link["repo"]).exists()
    ]
    assert not missing, f"links.toml names sources that do not exist: {missing}"


def test_every_link_source_is_committed(links: dict, tracked: set[str] | None) -> None:
    """The whole point of the installer: a file that was never committed is
    missing on every other machine, however well it works here."""
    if tracked is None:
        pytest.skip("git cannot read this working tree")
    untracked = []
    for link in links["link"]:
        if link.get("kind") in {"generated", "broken"} or link["repo"] in NOT_A_SOURCE:
            continue
        source = ROOT / link["repo"]
        if not source.exists():
            continue  # the test above owns that failure
        if source.is_file():
            candidates = [link["repo"]]
        else:
            candidates = [
                str(p.relative_to(ROOT)) for p in source.rglob("*") if p.is_file()
            ]
        if candidates and not any(c in tracked for c in candidates):
            untracked.append(link["repo"])
    assert not untracked, (
        "links.toml sources that git does not track - a fresh clone will not "
        f"have them: {untracked}"
    )


def test_every_step_has_a_check(steps: list[dict]) -> None:
    """Without a check a step is not idempotent, and re-running the installer
    on a half-installed machine redoes work it has already done."""
    unchecked = [s["id"] for s in steps if not s.get("check", "").strip()]
    assert not unchecked, f"steps with no check: {unchecked}"


def test_step_ids_are_unique(steps: list[dict]) -> None:
    ids = [s["id"] for s in steps]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate step ids: {duplicates}"


def test_step_ordering_references_real_steps(steps: list[dict]) -> None:
    ids = {s["id"] for s in steps}
    dangling = {
        s["id"]: [a for a in s.get("after", []) if a not in ids] for s in steps
    }
    dangling = {k: v for k, v in dangling.items() if v}
    assert not dangling, f"steps ordered after ids that do not exist: {dangling}"


def test_steps_are_in_dependency_order(steps: list[dict]) -> None:
    """`after` is documentation unless the file order agrees with it.

    plan.rs walks steps in the order they appear in steps.toml - there is no
    topological sort - so a step declaring `after = ["x"]` while x is written
    further down runs BEFORE x and fails for a reason that looks like anything
    but ordering.
    """
    at = {s["id"]: i for i, s in enumerate(steps)}
    wrong = [
        f"{s['id']} (#{i}) is ordered after {a} (#{at[a]}), which runs later"
        for i, s in enumerate(steps)
        for a in s.get("after", [])
        if a in at and at[a] > i
    ]
    assert not wrong, wrong


def test_wallust_fallback_runs_before_the_palette(steps: list[dict]) -> None:
    """The palette step calls wallust; the fallback is what guarantees there
    is one to call after the AUR package failed its checksum."""
    at = {s["id"]: i for i, s in enumerate(steps)}
    assert at["wallust-fallback"] < at["wallust-palette"]


def test_step_groups_exist(steps: list[dict]) -> None:
    """A step in a group nobody can tick never runs."""
    groups = {g["name"] for g in load("packages.toml")["group"]}
    orphans = {
        s["id"]: s["group"]
        for s in steps
        if s.get("group") and s["group"] not in groups
    }
    assert not orphans, f"steps in groups packages.toml does not define: {orphans}"


def test_question_answers_are_used(questions: list[dict], steps: list[dict]) -> None:
    """An answer nothing reads is a question that wastes the user's time."""
    blob = "\n".join(
        " ".join(s.get("run", [])) + " " + s.get("check", "") for s in steps
    )
    unused = [q["env"] for q in questions if q["env"] not in blob]
    assert not unused, f"questions whose answer no step reads: {unused}"


def test_question_envs_are_unique(questions: list[dict]) -> None:
    envs = [q["env"] for q in questions]
    duplicates = {e for e in envs if envs.count(e) > 1}
    assert not duplicates, f"two questions writing the same variable: {duplicates}"


def test_question_defaults_are_offered(questions: list[dict]) -> None:
    """The default has to be one of the choices, or the screen opens on an
    option that is not what will happen."""
    for q in questions:
        values = [o["value"] for o in q.get("option", [])]
        if values:
            assert q["default"] in values, (
                f"question {q['id']}: default {q['default']!r} is not one of {values}"
            )


def test_panel_handlers_exist() -> None:
    """Every script an eww widget calls by path has to be there. A missing one
    is a button that does nothing, which is exactly how it is discovered."""
    import re

    missing = []
    for yuck in (ROOT / "eww").rglob("*.yuck"):
        for match in re.finditer(r'~/\.config/eww/scripts/([\w.-]+)', yuck.read_text()):
            script = ROOT / "eww" / "scripts" / match.group(1)
            if not script.exists():
                missing.append(f"{yuck.relative_to(ROOT)} -> {match.group(1)}")
    assert not missing, f"eww widgets calling scripts that do not exist: {missing}"


def test_machine_overrides_are_not_committed(tracked: set[str] | None) -> None:
    """machine.lua is per machine by definition; committing one would hand the
    next clone this machine's modifier key and GPU."""
    if tracked is None:
        pytest.skip("git cannot read this working tree")
    assert "hypr/lua/machine.lua" not in tracked
    assert (ROOT / "hypr" / "lua" / "machine.lua.example").exists()
