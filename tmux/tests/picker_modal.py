#!/usr/bin/env python3
"""Modal search, layout and cross-workspace window movement on a disposable server."""
import curses
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from session_picker import Picker, SearchMode, preview_title
from picker_layout import Screen
from picker_startup import frame


def geometry():
    screen = Screen(34, 64)
    picker = object.__new__(Picker)
    picker.data = {'preferences': {'preview': True}, 'workspaces': {
        'general': {'name': 'General', 'parent': None},
        'personal': {'name': 'PersonalLongWorkspace', 'parent': None},
        'background': {'name': 'Background', 'parent': None, 'shortcut': 21},
        'archived': {'name': 'Archive', 'parent': None, 'shortcut': 22}}}
    picker.workspace = 'general'; picker.notice = 'Notice in reserved corner'
    picker.rows = []; picker.tags = set(); picker.selection_style = 0
    picker.draw_preview = lambda screen, area, accent: screen.addnstr(area.preview_top + 1, 2, 'CONTENT', 7)
    area = picker.render(screen)
    rows = [i for i in range(area.list_top) if '' in screen.text(i)]
    assert len(rows) >= 2 and all(b - a == 2 for a, b in zip(rows, rows[1:]))
    assert all(not screen.text(i + 1).strip() for i in rows[:-1])
    assert 'Notice in reserved corner' in screen.text(33)
    assert screen.text(33).index('Notice') > 30
    assert all('Notice' not in screen.text(i) for i in range(33))
    assert area.preview_top + area.preview_height == 33
    picker._toast_until = 0
    assert picker.render(screen).preview_top + picker.render(screen).preview_height == 34
    assert preview_title({'name': 'work', 'windows': {'@1': {}}}, {'name': 'editor'}) == '● work  1  editor ●'
    for initial in (False, True):
        mode = SearchMode(insert=initial)
        if not initial: assert mode.key('i') == 'mode'
        assert mode.key('j') == 'query' and mode.query == 'j'
        assert mode.key('\x1b') == 'mode' and not mode.insert
        assert mode.key('k') == 'up' and mode.query == 'j'
        assert mode.key('a') == 'mode' and mode.insert
        assert mode.key('\x1b') == 'mode' and mode.key('\x1b') == 'close'
    print('PASS: pill-row gaps; reserved bottom-right notices; compact title; modal search transitions.')


def windows():
    with tempfile.TemporaryDirectory(prefix='tmux-modal-') as folder:
        socket, state = folder + '/socket', Path(folder) / 'state.json'
        env = {**os.environ, 'TERM': 'xterm-256color', 'TMUX_WORKSPACES_STATE': str(state)}
        def tm(*args): return subprocess.check_output(['tmux', '-S', socket, *args], env=env, text=True).strip()
        tm('-f', '/dev/null', 'new-session', '-d', '-s', 'anchor', 'sleep 600')
        server = tm('display-message', '-p', '#{pid}')
        env['TMUX'] = socket + ',' + server + ',0'
        tm('set-option', '-g', 'default-shell', '/bin/sh')
        tm('set-option', '-g', 'renumber-windows', 'on')
        tm('new-window', '-d', '-t', 'anchor:1', 'sleep 600')
        tm('new-session', '-d', '-s', 'target', 'sleep 600')
        source_sid = tm('display-message', '-p', '-t', 'anchor', '#{session_id}')
        target_sid = tm('display-message', '-p', '-t', 'target', '#{session_id}')
        originals = set(tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}').splitlines())
        moving = tm('list-windows', '-t', 'anchor', '-F', '#{window_id}').splitlines()
        target_current = tm('display-message', '-p', '-t', 'target', '#{window_id}')
        helper = str(ROOT / 'scripts/workspaces.py')
        for action in (['init'], ['layout', '--kind', 'custom'], ['assign', '--session', 'target', '--destination', 'background', '--quiet', '1']):
            subprocess.run([helper, *action], env=env, check=True)
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 42, 150, 0, 0))
        proc = subprocess.Popen(['tmux', '-S', socket, 'attach-session', '-t', 'anchor'], stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave); output = bytearray()
        def drain(delay=.3):
            end = time.monotonic() + delay
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
        def links(session): return tm('list-windows', '-t', session, '-F', '#{window_id}').splitlines()
        try:
            drain(.4)
            client, pane = tm('list-clients', '-F', '#{client_name}\t#{pane_id}').split('\t')
            subprocess.run([helper, 'open', '--client', client, '--pane', pane], env=env, check=True)
            assert wait(lambda: bool(tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid')))
            picker = tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid')
            key(b'.'); key(b'itarget'); key(b'\x1b'); key(b'jk\r')
            assert wait(lambda: moving[0] in links('target') and moving[0] not in links('anchor'))
            assert tm('display-message', '-p', '-t', 'target', '#{window_id}') == target_current
            key(b'/anchor'); key(b'\x1b'); key(b'jk\r')
            key(b'.'); key(b'\r')  # Move the last original window; retain source session.
            assert wait(lambda: all(wid in links('target') for wid in moving))
            assert tm('display-message', '-p', '-t', 'anchor', '#{session_id}') == source_sid
            assert len(links('anchor')) == 1
            assert tm('list-clients', '-F', '#{session_id}') == source_sid
            # Move two tagged windows back in one operation, with index renumbering.
            key(b'ghljjtjt'); key(b'.'); key(b'ianchor'); key(b'\x1b'); key(b'\r')
            assert wait(lambda: all(wid in links('anchor') for wid in moving))
            assert len(links('target')) == 1
            pane = tm('list-clients', '-F', '#{pane_id}')
            assert wait(lambda: tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid') == picker)
            key(b'\x00')
            assert tm('display-message', '-p', '-t', pane, '#{pane_marked}') == '0'
            header = tm('show-options', '-pqv', '-t', pane, '@workspace-header')
            assert header == 'General | press ?', header
            assert originals <= set(tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}').splitlines())
            assert tm('display-message', '-p', '#{pid}') == server
            print('PASS: modal destination search; cross-workspace and tagged window moves; source session rescue; removed marking; compact status; all original processes retained.')
        finally:
            log = state.with_suffix('.log')
            if log.exists() and log.read_text(): print(log.read_text())
            tm('detach-client', '-t', client); drain(.4)
            try: proc.wait(timeout=5)
            finally:
                os.close(master)
                for sid in tm('list-sessions', '-F', '#{session_id}').splitlines(): tm('kill-session', '-t', sid)


if __name__ == '__main__':
    geometry(); windows()
