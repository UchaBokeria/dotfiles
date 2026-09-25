import os
import subprocess

from archpilot import compositor


def test_signature_prefers_a_live_env_value(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    live = tmp_path / "hypr" / "abc123"
    live.mkdir(parents=True)
    (live / ".socket.sock").touch()
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc123")
    assert compositor.instance_signature() == "abc123"


def test_a_stale_env_signature_is_ignored(tmp_path, monkeypatch):
    """After a compositor restart the inherited value points at a dead socket."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    real = tmp_path / "hypr" / "real"
    real.mkdir(parents=True)
    (real / ".socket.sock").touch()
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "gone")
    assert compositor.instance_signature() == "real"


def test_signature_discovered_without_any_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    found = tmp_path / "hypr" / "discovered"
    found.mkdir(parents=True)
    (found / ".socket.sock").touch()
    assert compositor.instance_signature() == "discovered"


def test_no_hyprland_running(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    assert compositor.instance_signature() == ""
    assert compositor.available() is False


def test_dispatch_is_a_noop_without_a_compositor(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    compositor.dispatch("submap", "reset")      # must not raise
    assert compositor.query("clients", "-j") == ""


def _lua_calls(monkeypatch, calls: list):
    """Capture hyprctl argv instead of running it."""

    class FakeProc:
        pass

    def fake_popen(argv, **kwargs):
        calls.append(list(argv))
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)


def test_lua_dispatch_is_a_noop_without_a_compositor(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    compositor.lua('hl.dsp.submap("reset")')      # must not raise
    compositor.focus_class("dev.archpilot.ui")
    compositor.close_class("dev.archpilot.ui")
    compositor.submap_reset()


def test_lua_expressions_use_hl_dsp_spellings(tmp_path, monkeypatch):
    """Regression: legacy `.conf` dispatch strings fail under the Lua config.

    `hyprctl dispatch submap reset` → `')' expected near 'reset'`. Every
    helper here must emit an `hl.dsp.…` expression, never bare dispatcher
    words. Verified live 2026-09-24.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    live = tmp_path / "hypr" / "sig"
    live.mkdir(parents=True)
    (live / ".socket.sock").touch()
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "sig")
    calls: list = []
    _lua_calls(monkeypatch, calls)

    compositor.submap_reset()
    compositor.focus_class("dev.archpilot.ui")
    compositor.close_class("dev.archpilot.ui")

    assert calls[0][:2] == ["hyprctl", "dispatch"]
    assert calls[0][2] == 'hl.dsp.submap("reset")'
    # Double backslash-dot: the Lua string parser eats one layer, the
    # pattern matcher eats the other. Single `\.` is "invalid escape
    # sequence" at the Hyprland end (verified live 2026-09-24).
    assert 'hl.dsp.focus(' in calls[1][2] and "dev\\\\.archpilot\\\\.ui" in calls[1][2]
    assert "legacy" not in calls[1][2]
    assert 'hl.dsp.window.close(' in calls[2][2] and "dev\\\\.archpilot\\\\.ui" in calls[2][2]
    for call in calls:
        # No legacy `.conf` dispatcher form: `hyprctl dispatch <words>`.
        # Every dispatch must be a single hl.dsp.… Lua expression.
        assert call[:2] == ["hyprctl", "dispatch"] and len(call) == 3, call
        assert call[2].startswith("hl.dsp."), call[2]


def test_env_carries_what_clients_need(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    (tmp_path / "hypr" / "sig").mkdir(parents=True)
    (tmp_path / "hypr" / "sig" / ".socket.sock").touch()
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = compositor.env()
    assert result["HYPRLAND_INSTANCE_SIGNATURE"] == "sig"
    assert result["XDG_RUNTIME_DIR"] == str(tmp_path)
