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


def send(payload: dict, *, expect_reply: bool = False, timeout: float | None = 10) -> dict | None:
    sock = _connect(timeout)
    try:
        sock.sendall(ipc.encode(payload))
        if not expect_reply:
            return None
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        return ipc.decode(buf) if buf.strip() else None
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
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    try:
                        yield ipc.decode(line)
                    except ValueError:
                        continue
    finally:
        sock.close()
