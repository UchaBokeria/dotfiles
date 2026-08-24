#!/usr/bin/env python3
"""SUDO_ASKPASS helper. Invoked by sudo, never by Claude.

sudo runs this with the prompt text as argv[1] and reads the password from
stdout. Because sudo is the caller, the password goes
widget -> daemon -> here -> sudo and never passes through the model's context.

The daemon refuses unless it has an *armed* request - a sudo command the user
just approved. Without that check, the model could run this helper itself
(SUDO_ASKPASS is in its environment) and get the user prompted for a password
outside of any approved command.

Failure is silent and empty: printing nothing makes sudo fail the auth attempt,
which is the safe outcome. Never print diagnostics to stdout - sudo would read
them as the password.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

TIMEOUT_S = 180


def fail(reason: str) -> None:
    print(f"archpilot-askpass: {reason}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Password:"

    from archpilot import ipc, paths

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT_S)
    try:
        sock.connect(str(paths.socket_path()))
        sock.sendall(ipc.encode({"op": ipc.OP_ASK_PASSWORD, "prompt": prompt}))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                fail("daemon closed the connection")
            buf += chunk
        reply = ipc.decode(buf)
    except (OSError, ValueError) as exc:
        fail(f"no password obtained ({exc})")
    finally:
        sock.close()

    password = reply.get("password")
    if not isinstance(password, str) or not password:
        fail(reply.get("reason") or "declined")

    # stdout is the password channel and nothing else.
    sys.stdout.write(password + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        fail(f"crashed ({type(exc).__name__}: {exc})")
