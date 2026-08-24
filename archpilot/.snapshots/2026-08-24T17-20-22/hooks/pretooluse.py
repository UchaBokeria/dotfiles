#!/usr/bin/env python3
"""PreToolUse hook: the gate between Claude Code and this machine.

Read docs/hook-contract.md before touching this file. The contract was
established by probe, and it has two FAIL-OPEN paths:

  * a hook killed by the harness `timeout` -> the command RUNS
  * a hook that exits non-zero without stdout (a traceback) -> the command RUNS

Only two things block reliably: valid stdout with permissionDecision "deny",
and exit code 2. So every error path in this file funnels to `refuse()`, and
the hook enforces its own deadline strictly inside the harness timeout so that
it always dies by its own hand rather than being killed.

Zero third-party imports on purpose: this runs on the bare interpreter for
every single tool call, so it must not need a venv or pay import cost.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

EXIT_OK = 0
EXIT_BLOCK = 2  # the ONLY safe error exit; see docs/hook-contract.md


def emit(decision: str, reason: str) -> None:
    """Print a decision and exit 0. Stdout carries the decision, nothing else."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(EXIT_OK)


def refuse(reason: str) -> None:
    """Fail closed. Used for every unexpected condition, without exception."""
    print(f"archpilot: {reason}", file=sys.stderr)
    sys.exit(EXIT_BLOCK)


def ask_daemon(payload: dict, deadline_s: float) -> str:
    """Ask the daemon for a human decision, blocking up to deadline_s.

    Returns "allow" or "deny". Raises on anything else so the caller refuses.
    The deadline is ours, not the harness's - see module docstring.
    """
    from archpilot import ipc, paths

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(deadline_s)
    try:
        sock.connect(str(paths.socket_path()))
        sock.sendall(ipc.encode(payload))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("daemon closed the connection")
            buf += chunk
        reply = ipc.decode(buf)
    finally:
        sock.close()

    decision = reply.get("decision")
    if decision not in ("allow", "deny"):
        raise ValueError(f"daemon returned an unusable decision: {decision!r}")
    return decision


def archpilot_mode() -> str:
    """Which archpilot mode this gate is running for.

    Passed as `--mode ask|action` by settings.py. In ask mode nothing that
    would change the machine may run at all - not even with approval - so an
    ASK verdict becomes a refusal rather than a prompt.
    """
    if "--mode" in sys.argv:
        index = sys.argv.index("--mode")
        if index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return "action"


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError as exc:
        refuse(f"could not read hook payload: {exc}")

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        refuse(f"hook payload was not valid JSON: {exc}")

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()

    from archpilot import config
    from archpilot.policy import Verdict, classify

    verdict, reason = classify(tool_name, tool_input, cwd)

    if verdict is Verdict.DENY:
        emit("deny", reason)
    if verdict is Verdict.ALLOW:
        emit("allow", reason)

    if archpilot_mode() == "ask":
        emit("deny", f"ask mode is read-only ({reason}); switch to action mode to run this")

    # Verdict.ASK - a human has to decide. Hand off to the widget.
    deadline = config.load().approval_deadline_s
    try:
        decision = ask_daemon(
            {
                "op": ipc_op(),
                "session_id": event.get("session_id"),
                "tool_use_id": event.get("tool_use_id"),
                "tool_name": tool_name,
                "tool_input": tool_input,
                "cwd": cwd,
                "reason": reason,
            },
            deadline_s=deadline,
        )
    except (OSError, ConnectionError, ValueError, json.JSONDecodeError) as exc:
        # Daemon down, socket missing, user never answered. All of these mean
        # "no human approved this", which must mean deny.
        refuse(f"no approval obtained ({exc}); refusing to run: {reason}")

    if decision == "allow":
        emit("allow", "approved in the archpilot widget")
    emit("deny", "declined in the archpilot widget")


def ipc_op() -> str:
    from archpilot import ipc

    return ipc.OP_ASK_PERMISSION


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - deliberate catch-all
        # Any unhandled error here would otherwise fail OPEN. It must not.
        refuse(f"hook crashed ({type(exc).__name__}: {exc})")
