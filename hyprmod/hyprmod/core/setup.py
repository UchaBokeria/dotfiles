"""First-run setup — injects the source line into hyprland.conf."""

import shutil
from pathlib import Path

from hyprland_config import Source, atomic_write
from hyprland_config import load as load_document

from hyprmod.core.config import gui_conf

HYPRLAND_CONF = Path.home() / ".config" / "hypr" / "hyprland.conf"


def _source_line() -> str:
    return f"source = {gui_conf()}"


def _find_source_node(doc, target: Path) -> Source | None:
    """Find the Source node that resolves to *target*."""
    resolved = target.resolve()
    for line in doc.lines:
        if isinstance(line, Source):
            if Path(line.path_str).expanduser().resolve() == resolved:
                return line
    return None


def _has_source_line(doc) -> bool:
    """Check if the document already sources the config file."""
    return _find_source_node(doc, gui_conf()) is not None


def needs_setup() -> bool:
    """Check if the source line needs to be added."""
    if not HYPRLAND_CONF.exists():
        return False
    doc = load_document(HYPRLAND_CONF, follow_sources=False)
    return not _has_source_line(doc)


def run_setup() -> None:
    """Append the source line to hyprland.conf."""
    gui_conf().touch(exist_ok=True)
    doc = load_document(HYPRLAND_CONF, follow_sources=False)
    if _has_source_line(doc):
        return
    content = doc.serialize()
    if not content.endswith("\n"):
        content += "\n"
    source_line = _source_line()
    content += f"\n# HyprMod managed settings\n{source_line}\n"
    atomic_write(HYPRLAND_CONF, content)


def migrate_config_path(old_path: Path, new_path: Path) -> None:
    """Move the config file and update the source line in hyprland.conf.

    1. Move old config to new location.
    2. Rewrite the ``source = ...`` line in hyprland.conf to point to new_path.
    3. If hyprland.conf has no matching source line, append one.
    """
    # Move config file to new location
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if old_path.exists():
        shutil.move(old_path, new_path)

    if not HYPRLAND_CONF.exists():
        return

    doc = load_document(HYPRLAND_CONF, follow_sources=False)
    old_node = _find_source_node(doc, old_path)

    if old_node is not None:
        # Replace the old source line in-place
        old_raw = old_node.raw
        new_raw = old_raw.replace(str(old_path), str(new_path))
        # If the path wasn't found literally (e.g. ~ vs expanded), do a full replace
        if new_raw == old_raw:
            new_raw = f"source = {new_path}\n"
        content = doc.serialize().replace(old_raw, new_raw, 1)
        atomic_write(HYPRLAND_CONF, content)
    elif _find_source_node(doc, new_path) is None:
        # No old source and no new source — append
        content = doc.serialize()
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n# HyprMod managed settings\nsource = {new_path}\n"
        atomic_write(HYPRLAND_CONF, content)
