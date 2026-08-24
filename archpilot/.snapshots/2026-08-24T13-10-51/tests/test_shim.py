import os
import stat
from pathlib import Path

import pytest

from archpilot import paths, shim


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "shim_dir", lambda: (tmp_path / "bin").resolve()
                        if (tmp_path / "bin").exists() or (tmp_path / "bin").mkdir() is None
                        else (tmp_path / "bin"))
    return tmp_path


def askpass_file(tmp_path):
    helper = tmp_path / "askpass.py"
    helper.write_text("#!/usr/bin/env python3\n")
    return helper


def test_install_writes_a_sudo_wrapper(runtime, tmp_path):
    directory = shim.install(askpass_file(tmp_path))
    wrapper = directory / "sudo"
    assert wrapper.exists()
    body = wrapper.read_text()
    assert "-A" in body, "the wrapper exists to add -A; sudo ignores SUDO_ASKPASS without it"
    assert 'exec' in body and '"$@"' in body


def test_wrapper_points_at_the_real_sudo_not_itself(runtime, tmp_path):
    directory = shim.install(askpass_file(tmp_path))
    body = (directory / "sudo").read_text()
    assert "/sudo -A" in body
    assert str(directory) not in body, "would recurse into the shim forever"


def test_wrapper_is_owner_only(runtime, tmp_path):
    directory = shim.install(askpass_file(tmp_path))
    mode = (directory / "sudo").stat().st_mode
    assert not mode & stat.S_IRWXG and not mode & stat.S_IRWXO


def test_askpass_helper_is_locked_down(runtime, tmp_path):
    """Anything that can run the helper can make the user type a password."""
    helper = askpass_file(tmp_path)
    shim.install(helper)
    mode = helper.stat().st_mode
    assert not mode & stat.S_IRWXG and not mode & stat.S_IRWXO


def test_env_puts_the_shim_first_on_path(runtime, tmp_path):
    env = shim.env_for(askpass_file(tmp_path))
    assert env["PATH"].split(":")[0] == str(paths.shim_dir())
    assert env["SUDO_ASKPASS"].endswith("askpass.py")


def test_env_preserves_the_rest_of_path(runtime, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    env = shim.env_for(askpass_file(tmp_path))
    assert env["PATH"].endswith("/usr/bin:/bin")


def test_install_is_idempotent(runtime, tmp_path):
    helper = askpass_file(tmp_path)
    first = shim.install(helper)
    second = shim.install(helper)
    assert first == second
