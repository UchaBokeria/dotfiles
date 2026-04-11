"""Hatchling build hook to compile GSettings schemas."""

import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        data_dir = Path(self.root) / "hyprmod" / "data"
        subprocess.run(
            ["glib-compile-schemas", str(data_dir)],
            check=True,
        )
        build_data["force_include"][str(data_dir / "gschemas.compiled")] = (
            "hyprmod/data/gschemas.compiled"
        )
