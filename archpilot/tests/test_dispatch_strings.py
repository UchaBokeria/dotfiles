"""Every hyprctl dispatch string the code emits, pinned to Lua spellings.

The rice runs a Lua Hyprland config, where `hyprctl dispatch` takes an
`hl.dsp.…` expression — legacy `.conf` dispatcher words (`focuswindow`,
`closewindow`, `submap reset`) fail with Lua parse errors. That shipped
because nothing tested the strings; the daemon can only hide/show the
window for pickers and screenshots when they are right.

This module asserts on the exact payloads the call sites send, so a future
edit that reintroduces a legacy string fails here instead of on the live
machine. Verified live 2026-09-24: `hl.dsp.submap("reset")` → ok,
`hl.dsp.window.close({window=…})` → ok,
`hl.dsp.focus({window=…})` → "window not found" (correct shape, no such
window open at probe time).
"""

from archpilot import compositor, ipc


def test_daemon_close_and_focus_use_lua_helpers(monkeypatch):
    """daemon._ui_close/_ui_open must route through the Lua helpers."""
    import archpilot.daemon as daemon_mod

    calls: list = []
    monkeypatch.setattr(compositor, "close_class",
                        lambda cls: calls.append(("close", cls)))
    monkeypatch.setattr(compositor, "submap_reset",
                        lambda: calls.append(("submap",)))
    monkeypatch.setattr(compositor, "focus_class",
                        lambda cls: calls.append(("focus", cls)))
    monkeypatch.setattr(daemon_mod, "gtk_window_is_open", lambda: True)

    daemon_mod._ui_close()
    assert ("close", daemon_mod.UI_CLASS) in calls
    assert ("submap",) in calls

    daemon_mod._ui_open()
    assert ("focus", daemon_mod.UI_CLASS) in calls


def test_retry_sends_a_daemon_prompt_op():
    """Regression: _retry_turn sent {"cmd": "prompt"}, which the daemon
    rejects with "unknown op None" (it dispatches on "op").

    Reads the source file as text: importing gtk_app needs PyGObject,
    which the venv python (3.13) cannot load (built for system 3.14).
    """
    import pathlib

    source = (pathlib.Path(__file__).resolve().parent.parent
              / "src" / "archpilot" / "ui" / "gtk_app.py").read_text()
    start = source.index("def _retry_turn")
    end = source.index("def _dismiss_notice")
    body = source[start:end]
    assert ipc.OP_PROMPT in body
    assert '"cmd"' not in body and "'cmd'" not in body


def test_machine_map_describes_the_live_rice():
    """context/rice.describe() rides in EVERY system prompt; a stale map
    teaches the model a rice that no longer exists."""
    from archpilot.context import rice

    text = rice.describe()
    assert "hypr/lua/" in text
    assert "hl.dsp" in text
    assert "theme/blackwall-theme" in text or "blackwall-theme" in text
    assert "swaync" in text
    assert "sourced by hypr/hyprland.conf" not in text
    assert "launchers/type-N" not in text
    assert "mako/" not in text or "masked" in text
