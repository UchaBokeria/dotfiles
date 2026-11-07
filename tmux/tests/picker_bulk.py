#!/usr/bin/env python3
"""Exercise real tagged operations and empty workspace creation on an isolated socket."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import termios
import time
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='tmux-tagged-') as folder:
        socket, state = folder + '/socket', Path(folder) / 'state.json'
        env = {**os.environ, 'TERM': 'xterm-256color', 'TMUX_WORKSPACES_STATE': str(state)}
        def tm(*args):
            return subprocess.check_output(['tmux', '-S', socket, *args], env=env, text=True).strip()
        tm('-f', '/dev/null', 'new-session', '-d', '-s', 'anchor', 'sleep 600')
        server = tm('display-message', '-p', '#{pid}')
        env['TMUX'] = socket + ',' + server + ',0'
        tm('set-option', '-g', 'default-shell', '/bin/sh')
        for name in ('bravo', 'charlie', 'delta'):
            tm('new-session', '-d', '-s', name, 'sleep 600')
        original = dict(line.split(':', 1) for line in tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}').splitlines())
        helper = str(ROOT / 'scripts/workspaces.py')
        subprocess.run([helper, 'init'], env=env, check=True)
        subprocess.run([helper, 'layout', '--kind', 'custom'], env=env, check=True)
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 44, 150, 0, 0))
        proc = subprocess.Popen(['tmux', '-S', socket, 'attach-session', '-t', 'anchor'],
                                stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        output = bytearray()
        def drain(seconds=.25):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                if select.select([master], [], [], .01)[0]:
                    try: output.extend(os.read(master, 262144))
                    except OSError: return
        def key(value): os.write(master, value); drain()
        def wait(predicate):
            end = time.monotonic() + 5
            while time.monotonic() < end:
                if predicate(): return True
                drain(.1)
            return predicate()
        def data(): return json.loads(state.read_text())
        def member(name): return tm('display-message', '-p', '-t', name, '#{@workspace-id}')
        drain(.3)
        client, pane = tm('list-clients', '-F', '#{client_name}\t#{pane_id}').split('\t')
        def call(action, expected=0, **values):
            argv = [helper, action, '--client', client, '--pane', pane]
            for name, value in values.items(): argv += ['--' + name, str(value)]
            result = subprocess.run(argv, env=env, text=True, capture_output=True)
            assert result.returncode == expected, result.stderr
            drain(.2)
        try:
            before = tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            call('apply-name', workspace='general', kind='create', name='Parent', quiet='1')
            parent = next(wid for wid, node in data()['workspaces'].items() if node['name'] == 'Parent')
            call('apply-name', workspace=parent, kind='child', name='Nested', quiet='1')
            nested = next(wid for wid, node in data()['workspaces'].items() if node['name'] == 'Nested')
            assert tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}') == before
            assert not any(group in (parent, nested) for group in data()['sessions'].values())
            call('open', workspace='general')
            assert wait(lambda: bool(tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid')))
            picker = tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid')
            key(b'j'); key(b't'); key(b'j'); key(b't')  # Bravo + Charlie.
            key(b'm'); key(b'j\r')
            assert wait(lambda: member('bravo') == member('charlie') == parent)
            assert member('anchor') == member('delta') == 'general'
            key(b'tjt')
            key(b'w'); key(b'm'); key(b'j\r')  # Actions must use both tags too.
            assert wait(lambda: member('bravo') == member('charlie') == nested)
            key(b'tjt')
            key(b'w'); key(b'irename session\r'); key(b'-cancelled\r'); key(b'\x1b')
            assert 'bravo' in tm('list-sessions', '-F', '#{session_name}').splitlines()
            assert 'charlie' in tm('list-sessions', '-F', '#{session_name}').splitlines()
            key(b'w'); key(b'irename session\r'); key(b'-renamed\r'); key(b'-renamed\r')
            assert wait(lambda: member('bravo-renamed') == member('charlie-renamed') == nested)
            key(b":set-option -t '%%' @bulk-test yes\r")
            assert wait(lambda: tm('show-options', '-qv', '-t', 'bravo-renamed', '@bulk-test') == 'yes'
                        and tm('show-options', '-qv', '-t', 'charlie-renamed', '@bulk-test') == 'yes')
            assert tm('show-options', '-qv', '-t', 'anchor', '@bulk-test') == ''
            ids = [tm('display-message', '-p', '-t', name, '#{session_id}') for name in ('bravo-renamed', 'charlie-renamed')]
            call('assign-many', expected=1, name=json.dumps([ids[0], '$999999']), destination=parent)
            assert member('bravo-renamed') == member('charlie-renamed') == nested
            key(b'z')
            assert wait(lambda: member('bravo-renamed') == member('charlie-renamed') == 'archived')
            key(b'\x12'); key(b'tjt'); key(b'w'); key(b'z')
            assert wait(lambda: member('bravo-renamed') == member('charlie-renamed') == nested)
            # Tag two child windows, collapse the parent, and delete from w.
            tm('new-window', '-d', '-t', 'bravo-renamed:1', 'sleep 600')
            tm('new-window', '-d', '-t', 'bravo-renamed:2', 'sleep 600')
            drain(.6)
            key(b'/bravo-renamed\r'); key(b'l'); key(b'jjtjt'); key(b'h')
            key(b'x'); key(b'n')
            assert len(tm('list-windows', '-t', 'bravo-renamed').splitlines()) == 3
            key(b'w'); key(b'x'); key(b'y')
            assert wait(lambda: len(tm('list-windows', '-t', 'bravo-renamed').splitlines()) == 1)
            key(b'g'); key(b'tjt')
            key(b'x'); key(b'n')
            assert all(name in tm('list-sessions', '-F', '#{session_name}').splitlines() for name in ('bravo-renamed', 'charlie-renamed'))
            key(b'x'); key(b'y')
            assert wait(lambda: all(name not in tm('list-sessions', '-F', '#{session_name}').splitlines() for name in ('bravo-renamed', 'charlie-renamed')))
            assert nested in data()['workspaces']
            assert tm('list-clients', '-F', '#{session_name}') == 'anchor'
            assert tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid') == picker
            current = dict(line.split(':', 1) for line in tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}').splitlines())
            assert current['%0'] == original['%0'] and current['%3'] == original['%3']
            assert tm('display-message', '-p', '#{pid}') == server
            print('PASS: empty parent/nested creation; tagged move/actions/rename/commands/archive/restore; hidden child tags; delete confirm/cancel; untouched anchor/server.')
        finally:
            log = state.with_suffix('.log')
            if log.exists() and log.read_text(): print(log.read_text())
            tm('detach-client', '-t', client)
            drain(.4)
            try:
                proc.wait(timeout=5)
            finally:
                os.close(master)
                for sid in tm('list-sessions', '-F', '#{session_id}').splitlines(): tm('kill-session', '-t', sid)


if __name__ == '__main__': main()
