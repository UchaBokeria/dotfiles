#!/usr/bin/env python3
"""Measure prefix-to-complete-frame latency, without touching live servers."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import statistics
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='tmux-picker-speed-') as folder:
        socket = folder + '/socket'
        env = {**os.environ, 'TERM': 'xterm-256color', 'TMUX_WORKSPACES_STATE': folder + '/state.json'}
        def tm(*args):
            return subprocess.check_output(['tmux', '-S', socket, *args], env=env, text=True).rstrip('\n')
        tm('-f', '/dev/null', 'new-session', '-d', '-s', 'alpha', 'sleep 600')
        server = tm('display-message', '-p', '#{pid}')
        env['TMUX'] = socket + ',' + server + ',0'
        tm('set-option', '-g', 'default-shell', '/bin/sh')
        for name in ('beta', 'gamma', 'delta', 'epsilon', 'zeta'):
            tm('new-session', '-d', '-s', name, 'sleep 600')
        helper = str(ROOT / 'scripts/workspaces.py')
        subprocess.run([helper, 'init'], env=env, check=True)
        subprocess.run([helper, 'layout', '--kind', 'custom'], env=env, check=True)
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 46, 185, 0, 0))
        proc = subprocess.Popen(['tmux', '-S', socket, 'attach-session', '-t', 'alpha'], env=env,
                                stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        def drain(duration):
            result = bytearray(); end = time.monotonic() + duration
            while time.monotonic() < end:
                if select.select([master], [], [], .005)[0]:
                    try: result.extend(os.read(master, 262144))
                    except OSError: break
            return bytes(result)
        try:
            drain(.4)
            client = tm('list-clients', '-F', '#{client_name}')
            original = tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            samples = []
            for _ in range(7):
                started = time.perf_counter(); output = b''
                tm('send-keys', '-K', '-c', client, 'C-b', 's')
                while time.perf_counter() - started < 5:
                    output += drain(.005)
                    if b'General' in output and '● alpha'.encode() in output:
                        break
                else:
                    raise AssertionError('Picker failed to publish the complete frame')
                samples.append(round((time.perf_counter() - started) * 1000, 1))
                os.write(master, b'q'); drain(.35)
            assert tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}') == original
            print(json.dumps({'first_ms': samples[0], 'warm_median_ms': statistics.median(samples[1:]),
                              'samples_ms': samples}))
        finally:
            subprocess.run(['tmux', '-S', socket, 'kill-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait(timeout=5); os.close(master)


if __name__ == '__main__':
    main()
