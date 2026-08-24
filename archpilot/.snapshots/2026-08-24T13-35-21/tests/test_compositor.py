import os

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


def test_env_carries_what_clients_need(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    (tmp_path / "hypr" / "sig").mkdir(parents=True)
    (tmp_path / "hypr" / "sig" / ".socket.sock").touch()
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = compositor.env()
    assert result["HYPRLAND_INSTANCE_SIGNATURE"] == "sig"
    assert result["XDG_RUNTIME_DIR"] == str(tmp_path)
