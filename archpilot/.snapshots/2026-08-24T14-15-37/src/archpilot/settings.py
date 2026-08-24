"""Render the --settings payloads the engine hands to `claude`.

Written to the runtime dir at daemon startup rather than committed, because the
hook path must be absolute and this repo should stay relocatable.

The `timeout` here is deliberately generous. A harness-killed hook FAILS OPEN
(docs/hook-contract.md), so the hook must always be the one to give up first:
its own deadline (config: safety.approval_deadline_s, 240s) sits well inside
this value, guaranteeing it exits with an explicit refusal instead of being
killed mid-wait.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import paths

#: Must stay comfortably above safety.approval_deadline_s.
HARNESS_TIMEOUT_S = 600

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "pretooluse.py"


def _settings_for(mode: str) -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    # No matcher: every tool goes through the gate, not just Bash.
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {HOOK} --mode {mode}",
                            "timeout": HARNESS_TIMEOUT_S,
                        }
                    ]
                }
            ]
        }
    }


# Ask mode no longer uses `--permission-mode plan`: Claude Code's own plan
# prompt made every answer open with "this is not a planning task". Write tools
# are removed outright instead, and the hook refuses anything mutating rather
# than prompting - so ask still cannot change the machine, it just no longer
# announces that it is planning.


def render() -> dict[str, Path]:
    """Write both settings files and return their paths."""
    out = paths.runtime_dir() / "archpilot-settings"
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for mode in ("ask", "action"):
        path = out / f"{mode}.json"
        path.write_text(json.dumps(_settings_for(mode), indent=2))
        written[mode] = path
    return written
