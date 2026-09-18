"""tmux/resurrect-guard keeps resurrect's `last` on a save that has panes.

Not a theme test either, but theme/run-tests is the harness blackwall has.

The failure it covers cost every tmux session once: a save taken while the
server was going down came out empty, resurrect linked it as `last`, and the
next boot restored nothing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GUARD = ROOT / "tmux" / "resurrect-guard"


def _save(d: Path, stamp: str, body: str) -> Path:
    path = d / f"tmux_resurrect_{stamp}.txt"
    path.write_text(body)
    return path


def _run(d: Path) -> None:
    subprocess.run([str(GUARD), str(d)], check=True, env={**os.environ, "TMUX": ""})


def test_empty_newest_save_is_moved_aside_and_last_relinked(tmp_path):
    saves = tmp_path / "resurrect"
    saves.mkdir()
    _save(saves, "20260909T222025", "pane\tanonym\t1\n")
    empty = _save(saves, "20260910T171420", "")
    (saves / "last").symlink_to(empty.name)

    _run(saves)

    assert os.readlink(saves / "last") == "tmux_resurrect_20260909T222025.txt"
    assert not empty.exists()
    assert (tmp_path / "resurrect-empty" / empty.name).exists(), "moved, never deleted"


def test_healthy_last_is_left_alone(tmp_path):
    saves = tmp_path / "resurrect"
    saves.mkdir()
    _save(saves, "20260101T000000", "pane\ta\n")
    keep = _save(saves, "20260102T000000", "pane\tb\n")
    (saves / "last").symlink_to(keep.name)

    _run(saves)

    assert os.readlink(saves / "last") == keep.name
    assert not (tmp_path / "resurrect-empty").exists()


def test_dangling_last_points_at_newest_real_save(tmp_path):
    saves = tmp_path / "resurrect"
    saves.mkdir()
    _save(saves, "20260101T000000", "pane\ta\n")
    _save(saves, "20260103T000000", "pane\tc\n")
    (saves / "last").symlink_to("tmux_resurrect_gone.txt")

    _run(saves)

    assert os.readlink(saves / "last") == "tmux_resurrect_20260103T000000.txt"


def test_no_saves_at_all_is_not_an_error(tmp_path):
    saves = tmp_path / "resurrect"
    saves.mkdir()
    _run(saves)
    assert not (saves / "last").exists()
