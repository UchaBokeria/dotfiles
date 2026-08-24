"""Background socket reader for the GTK frontend.

Runs on a thread and hands every state snapshot to the GTK main loop via
`GLib.idle_add`, which is the only safe way to touch widgets from off-thread.
Reconnects on its own: the daemon is restarted often enough (config changes,
upgrades) that a frontend which dies with it would be a nuisance.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable

from .. import ipc, paths


class DaemonClient:
    def __init__(self, on_state: Callable[[dict], None], retry: float = 2.0,
                 on_event: Callable[[dict], None] | None = None):
        self._on_state = on_state
        #: Everything that is not a state snapshot. Without this the
        #: stream loop dropped every other event on the floor.
        self._on_event = on_event
        self._retry = retry
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def send(self, payload: dict, timeout: float = 5.0) -> dict | None:
        """One-shot request. Used for prompts, approvals and settings."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(str(paths.socket_path()))
            sock.sendall(ipc.encode(payload))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
            return ipc.decode(buf) if buf.strip() else None
        except (OSError, ValueError):
            return None
        finally:
            sock.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._stream()
            except (OSError, ValueError):
                pass
            if self._stop.is_set():
                return
            self._on_state({"status": "down"})
            time.sleep(self._retry)

    def _stream(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(None)
        try:
            sock.connect(str(paths.socket_path()))
            sock.sendall(ipc.encode({"op": ipc.OP_SUBSCRIBE}))
            buf = b""
            while not self._stop.is_set():
                chunk = sock.recv(65536)
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        event = ipc.decode(line)
                    except ValueError:
                        continue
                    if event.get("ev") == ipc.EV_STATE:
                        self._on_state(event)
                    elif self._on_event is not None:
                        self._on_event(event)
        finally:
            sock.close()
