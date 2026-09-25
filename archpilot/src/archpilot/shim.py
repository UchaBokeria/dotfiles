"""The `sudo` shim handed to the claude child.

A command that needs a password would otherwise hang forever: the Bash tool has
no tty, so sudo has nothing to prompt on. Setting SUDO_ASKPASS alone is not
enough - sudo only consults it when invoked with -A - so a wrapper earlier in
PATH supplies the flag.

Why a shim and not a hook rewrite: `updatedInput` on PreToolUse does work, but
then the transcript records a command the user never approved, and the model
notices the mismatch and reports it as tampering. The shim keeps the command
text honest and the diff invisible.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import paths

SUDO_WRAPPER = """#!/usr/bin/env bash
# Installed by archpilot. Adds -A so sudo asks the askpass helper rather than a
# tty that does not exist. Everything else is passed through untouched.
exec {real_sudo} -A "$@"
"""


def install(askpass: Path) -> Path:
    """Write the shim dir and return it. Idempotent.

    H10: the old code chmodded the REPO SOURCE askpass.py (tracked-file dirt
    on every turn, fatal on read-only checkouts). Now only the wrapper in the
    runtime dir is touched; the source helper's own committed mode stands.
    """
    real_sudo = shutil.which("sudo", path="/usr/bin:/bin:/usr/local/bin")
    if real_sudo is None:
        raise RuntimeError("no sudo binary found; cannot arm password broker")
    directory = paths.shim_dir()
    wrapper = directory / "sudo"
    # Write with a restrictive umask window instead of chmod-after: the old
    # order briefly exposed the wrapper at the default umask.
    old_umask = os.umask(0o077)
    try:
        wrapper.write_text(SUDO_WRAPPER.format(real_sudo=real_sudo))
    finally:
        os.umask(old_umask)
    try:
        wrapper.chmod(0o700)
    except OSError:
        pass
    return directory


def env_for(askpass: Path) -> dict[str, str]:
    """PATH and SUDO_ASKPASS additions for the claude child."""
    directory = install(askpass)
    return {
        "PATH": f"{directory}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "SUDO_ASKPASS": str(askpass),
    }
