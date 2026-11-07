#!/usr/bin/env python3
"""Verify first-paint buffering and real popup redraws on disposable terminals."""
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


def first_paint():
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 110, 0, 0))
    ready_read, ready_write = os.pipe()
    code = f'''
import curses, os, sys, time
sys.path.insert(0, {str(ROOT / 'scripts')!r})
from picker_startup import FirstPaint
previous = {{key: os.environ.get(key) for key in ('LINES', 'COLUMNS')}}
with FirstPaint() as paint:
    def run(screen):
        assert screen.getmaxyx() == (30, 110), screen.getmaxyx()
        screen.addstr(0, 0, 'SETUP')
        screen.refresh()
        os.write({ready_write}, b'initialized\\n')
        time.sleep(.2)
        screen.addstr(1, 0, 'READY')
        screen.refresh()
        paint.release()
        assert os.get_terminal_size(1) == (110, 30)
        assert {{key: os.environ.get(key) for key in previous}} == previous
        screen.addstr(2, 0, 'LIVE')
        screen.refresh()
    curses.wrapper(run)
'''
    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    proc = subprocess.Popen([sys.executable, '-c', code], stdin=slave, stdout=slave,
                            stderr=slave, env={**os.environ, 'TERM': 'xterm-256color'},
                            preexec_fn=controlling_terminal, pass_fds=(ready_write,))
    os.close(slave)
    os.close(ready_write)
    try:
        assert os.read(ready_read, 100) == b'initialized\n'

        assert not select.select([master], [], [], .08)[0], 'Setup escaped before the first frame was ready'
        output = bytearray()
        while select.select([master], [], [], 1)[0]:
            try: output.extend(os.read(master, 65536))
            except OSError: break
        proc.wait(timeout=3)
        assert proc.returncode == 0, output[-1000:]
        assert all(value in output for value in (b'SETUP', b'READY', b'LIVE'))
        print('PASS: setup stays hidden until ready; first frame, dimensions and live output preserved.')
    finally:
        os.close(master)
        os.close(ready_read)


def opening():
    with tempfile.TemporaryDirectory(prefix='tmux-opening-') as folder:
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
        original = tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
        helper = str(ROOT / 'scripts/workspaces.py')
        subprocess.run([helper, 'init'], env=env, check=True)
        subprocess.run([helper, 'layout', '--kind', 'custom'], env=env, check=True)
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 46, 185, 0, 0))
        proc = subprocess.Popen(['tmux', '-S', socket, 'attach-session', '-t', 'alpha'],
                                stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        def read_for(seconds):
            output = bytearray()
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                if select.select([master], [], [], .01)[0]:
                    try: output.extend(os.read(master, 262144))
                    except OSError: break
            return bytes(output)
        try:
            read_for(.4)
            client, pane = tm('list-clients', '-F', '#{client_name}\t#{pane_id}').split('\t')
            for attempt in range(3):
                subprocess.run([helper, 'open', '--client', client, '--pane', pane], env=env, check=True)
                output = read_for(.8)
                assert b'General' in output and '● alpha'.encode() in output, output[-1000:]
                assert b'\x1b[44S' not in output, 'Startup used a scrolling wipe'
                picker_pid = tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid')
                assert picker_pid.isdigit()
                terminal = os.open('/proc/' + picker_pid + '/fd/0', os.O_RDONLY | os.O_NOCTTY)
                try:
                    rows, columns, _, _ = struct.unpack('HHHH', fcntl.ioctl(terminal, termios.TIOCGWINSZ, bytes(8)))
                    assert (rows, columns) == (45, 185), (rows, columns)
                finally: os.close(terminal)
                if attempt == 1:
                    marker = tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid')
                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 32, 130, 0, 0))
                    os.kill(proc.pid, signal.SIGWINCH)
                    resized = read_for(.4)
                    assert '● alpha'.encode() in resized
                    assert tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid') == marker
                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 46, 185, 0, 0))
                    os.kill(proc.pid, signal.SIGWINCH)
                    read_for(.3)
                os.write(master, b'q')
                read_for(.25)
            assert tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}') == original
            assert tm('display-message', '-p', '#{pid}') == server
            print('PASS: repeated opening publishes one complete frame with no animation or scrolling wipe; resize works; original panes/server untouched.')
        finally:
            tm('detach-client', '-t', client)
            proc.wait(timeout=3)
            os.close(master)
            for sid in tm('list-sessions', '-F', '#{session_id}').splitlines():
                tm('kill-session', '-t', sid)


if __name__ == '__main__':
    first_paint()
    opening()
