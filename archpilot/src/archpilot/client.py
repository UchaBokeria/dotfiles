"""Blocking socket client. The CLI is short-lived, so asyncio buys nothing here."""

from __future__ import annotations

import socket
from typing import Iterator

from . import ipc, paths


class DaemonUnavailable(RuntimeError):
    pass


def _connect(timeout: float | None) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(paths.socket_path()))
    except OSError as exc:
        sock.close()
        raise DaemonUnavailable(
            f"archpilotd is not running ({exc}). Start it with: systemctl --user start archpilotd"
        ) from exc
    return sock


#: A peer that never sends a newline could otherwise grow the buffer forever.
MAX_BUFFER = 4 * 1024 * 1024


def send(payload: dict, *, expect_reply: bool = False, timeout: float | None = 10) -> dict | None:
    sock = _connect(timeout)
    try:
        sock.sendall(ipc.encode(payload))
        if not expect_reply:
            return None
        buf = b""
        while not buf.endswith(b"\n"):
            try:
                chunk = sock.recv(65536)
            except TimeoutError:
                # H5: socket.timeout surfaced as bare TimeoutError, which no
                # CLI caller catches (only DaemonUnavailable) → traceback on a
                # slow daemon. Translate it.
                raise DaemonUnavailable(
                    "archpilotd is not answering (timed out). "
                    "Is it stuck? Try: systemctl --user restart archpilotd"
                )
            if not chunk:
                break
            buf += chunk
            if len(buf) > MAX_BUFFER:
                raise DaemonUnavailable("archpilotd sent an oversized reply")
        if not buf.strip():
            return None
        reply = ipc.decode(buf)
        # U26: a non-object reply used to crash callers on .get.
        return reply if isinstance(reply, dict) else None
    except (OSError, ValueError) as exc:
        raise DaemonUnavailable(f"archpilotd reply was unusable ({exc})")
    finally:
        sock.close()


def stream(payload: dict) -> Iterator[dict]:
    """Yield events until the daemon closes. Used by eww's deflisten."""
    sock = _connect(None)
    try:
        sock.sendall(ipc.encode(payload))
        buf = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                return
            buf += chunk
            if len(buf) > MAX_BUFFER:
                return
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    try:
                        event = ipc.decode(line)
                    except ValueError:
                        continue
                    # U26: non-object frames killed --watch loops on .get.
                    if isinstance(event, dict):
                        yield event
    finally:
        sock.close()
