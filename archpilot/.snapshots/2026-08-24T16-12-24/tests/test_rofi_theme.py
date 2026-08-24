import re

import pytest

from archpilot import rofi_theme


@pytest.fixture
def scss(tmp_path, monkeypatch):
    path = tmp_path / "colors.scss"
    monkeypatch.setattr(rofi_theme, "COLORS_SCSS", path)
    return path


def test_reads_colours_from_the_rice(scss, tmp_path, monkeypatch):
    scss.write_text("$bg: #111111;\n$fg: #EEEEEE;\n$accent: #FF0066;\n")
    monkeypatch.setattr(rofi_theme.paths, "runtime_dir", lambda: tmp_path)
    body = rofi_theme.render().read_text()
    assert "#111111" in body and "#EEEEEE" in body and "#FF0066" in body


def test_falls_back_when_the_rice_file_is_missing(scss, tmp_path, monkeypatch):
    monkeypatch.setattr(rofi_theme.paths, "runtime_dir", lambda: tmp_path)
    body = rofi_theme.render().read_text()
    assert rofi_theme.FALLBACK["accent"] in body


def test_theme_is_self_contained(scss, tmp_path, monkeypatch):
    """The launcher themes @import a shared/colors.rasi that does not exist on
    this machine; ours must never depend on an external file."""
    scss.write_text("$bg: #111111;\n$fg: #EEEEEE;\n$accent: #FF0066;\n")
    monkeypatch.setattr(rofi_theme.paths, "runtime_dir", lambda: tmp_path)
    body = rofi_theme.render().read_text()
    assert "@import" not in body


def test_every_variable_used_is_defined(scss, tmp_path, monkeypatch):
    """An unresolved var makes rofi discard the whole theme and render unstyled."""
    scss.write_text("$bg: #111111;\n$fg: #EEEEEE;\n$accent: #FF0066;\n")
    monkeypatch.setattr(rofi_theme.paths, "runtime_dir", lambda: tmp_path)
    body = rofi_theme.render().read_text()
    declared = set(re.findall(r"^\s{4}(\w[\w-]*):\s", body, re.MULTILINE))
    used = set(re.findall(r"@([\w-]+)", body))
    assert used <= declared, f"undefined in theme: {used - declared}"


def test_derived_shades_sit_between_bg_and_fg(scss, tmp_path, monkeypatch):
    scss.write_text("$bg: #000000;\n$fg: #FFFFFF;\n$accent: #FF0066;\n")
    monkeypatch.setattr(rofi_theme.paths, "runtime_dir", lambda: tmp_path)
    body = rofi_theme.render().read_text()
    alt = re.search(r"bg-alt:\s+(#\w{6})", body).group(1)
    muted = re.search(r"muted:\s+(#\w{6})", body).group(1)
    assert int(alt[1:3], 16) < int(muted[1:3], 16), "alt should be closer to bg"


def test_mix_endpoints():
    assert rofi_theme._mix("#000000", "#FFFFFF", 0.0) == "#000000"
    assert rofi_theme._mix("#000000", "#FFFFFF", 1.0) == "#FFFFFF"


def test_mix_handles_short_hex():
    assert rofi_theme._mix("#000", "#FFF", 1.0) == "#FFFFFF"


# --------------------------------------------------------------------------
# Repairing the rice's launcher themes.
# --------------------------------------------------------------------------
BASE_VARS = ("background", "background-alt", "foreground", "selected", "active", "urgent")


@pytest.fixture
def launchers(tmp_path, monkeypatch):
    root = tmp_path / "rofi" / "launchers"
    for kind in ("type-1", "type-2"):
        (root / kind / "shared").mkdir(parents=True)
    monkeypatch.setattr(rofi_theme, "LAUNCHERS", root)
    scss = tmp_path / "colors.scss"
    scss.write_text("$bg: #101010;\n$fg: #F0F0F0;\n$accent: #CB1868;\n")
    monkeypatch.setattr(rofi_theme, "COLORS_SCSS", scss)
    return root


def test_writes_colors_for_every_launcher_type(launchers):
    written = rofi_theme.sync_launcher_colors()
    assert len(written) == 2
    assert all(p.name == "colors.rasi" for p in written)


def test_defines_every_variable_the_themes_derive_from(launchers):
    """A single missing base var makes rofi discard the whole theme."""
    body = rofi_theme.sync_launcher_colors()[0].read_text()
    for var in BASE_VARS:
        assert f"{var}:" in body, f"missing {var}"


def test_colours_carry_an_alpha_channel(launchers):
    """The upstream files are #rrggbbaa; rofi needs the alpha byte."""
    import re
    body = rofi_theme.sync_launcher_colors()[0].read_text()
    values = re.findall(r":\s+(#\w+);", body)
    assert values and all(len(v) == 9 for v in values), values


def test_sync_is_idempotent(launchers):
    rofi_theme.sync_launcher_colors()
    assert rofi_theme.sync_launcher_colors() == [], "identical content should not rewrite"


def test_sync_follows_the_palette(launchers, tmp_path, monkeypatch):
    rofi_theme.sync_launcher_colors()
    (tmp_path / "colors.scss").write_text("$bg: #202020;\n$fg: #FAFAFA;\n$accent: #00FF00;\n")
    written = rofi_theme.sync_launcher_colors()
    assert written, "a palette change must rewrite"
    assert "#00FF00FF" in written[0].read_text()


def test_missing_launchers_dir_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(rofi_theme, "LAUNCHERS", tmp_path / "nope")
    assert rofi_theme.sync_launcher_colors() == []
