"""The daemon must actually stop when told to.

This needs a real process: the bug it guards against lives in asyncio's server
teardown, so an in-process test of the same code would not have caught it.
`async with server` awaits wait_closed(), which since Python 3.12 blocks until
every client handler returns - and a `subscribe` connection never returns. The
daemon ignored SIGTERM, and systemd SIGKILLed it 90 seconds later, on every
restart and every reboot.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

DAEMON = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "archpilotd"

pytestmark = pytest.mark.skipif(not DAEMON.exists(), reason="daemon not installed")


def wait_for_socket(path: Path, timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def daemon(tmp_path):
    env = {**os.environ, "XDG_RUNTIME_DIR": str(tmp_path),
           "ARCHPILOT_STATE_DIR": str(tmp_path / "state")}
    proc = subprocess.Popen([str(DAEMON)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sock = tmp_path / "archpilot.sock"
    if not wait_for_socket(sock):
        proc.kill()
        pytest.skip("daemon did not come up")
    yield proc, sock
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)


def test_sigterm_stops_the_daemon_promptly(daemon):
    proc, _ = daemon
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=10) is not None


def test_a_live_subscriber_does_not_block_shutdown(daemon):
    """The exact shape of the real bug: the widget holds a subscription open
    for its whole life, so shutdown must not wait on it."""
    proc, sock_path = daemon
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(str(sock_path))
    client.sendall(json.dumps({"cmd": "subscribe"}).encode() + b"\n")
    time.sleep(0.5)                       # let the handler settle into its loop
    try:
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        assert time.monotonic() - started < 5, "shutdown stalled on the subscriber"
    finally:
        client.close()


def test_the_socket_file_is_cleaned_up(daemon):
    """A SIGKILLed daemon leaves a stale socket behind; a clean one does not."""
    proc, sock_path = daemon
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)
    assert not sock_path.exists()
