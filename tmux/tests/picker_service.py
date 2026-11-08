#!/usr/bin/env python3
"""Bounded worker/cache lifecycle and fresh UI state on disposable tmux servers."""
import array
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import picker_service as service


def main():
    previous = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix='tmux-picker-service-test-') as folder:
        root = Path(folder); runtime = root / 'runtime'; runtime.mkdir()
        os.environ.update(TERM='xterm-256color', TMUX_WORKSPACES_STATE=str(root/'state.json'),
                          XDG_RUNTIME_DIR=str(runtime), TMUX_PICKER_RUNTIME=str(runtime/'service'))
        env = os.environ.copy(); sock = str(root/'tmux')
        def tm(*args):
            return subprocess.check_output(['tmux', '-S', sock, *args], env=env, text=True).rstrip('\n')
        helper = str(ROOT/'scripts/workspaces.py')
        def backend(action, **values):
            subprocess.run([helper, action, *[str(item) for key, value in values.items() for item in ('--'+key, value)]],
                           env=env, check=True, stdout=subprocess.DEVNULL)
        master = proc = None
        def drain(duration=.1):
            out = bytearray(); end = time.monotonic()+duration
            while time.monotonic() < end:
                if select.select([master], [], [], .005)[0]:
                    try: out.extend(os.read(master, 262144))
                    except OSError: break
            return bytes(out)
        def wait(check, seconds=5):
            end = time.monotonic()+seconds
            while time.monotonic() < end:
                if check(): return True
                if master is not None: drain(.03)
                else: time.sleep(.03)
            return check()
        def status():
            try: return service.request('status')
            except (OSError, ValueError): return {}
        def open_picker(expect=b'renamed-now'):
            tm('send-keys', '-K', '-c', client, 'C-b', 's')
            output = bytearray(); end = time.monotonic()+4
            while time.monotonic() < end:
                output.extend(drain(.02))
                if b'General' in output and expect in output: return bytes(output)
            raise AssertionError(('Picker did not render', bytes(output[-1400:])))
        def close_picker():
            os.write(master, b'q'); drain(.2)
            assert wait(lambda: status().get('workers') == 0), status()
        try:
            tm('-f', '/dev/null', 'new-session', '-d', '-s', 'alpha', 'sleep 600')
            pid = tm('display-message', '-p', '#{pid}')
            env['TMUX'] = sock+','+pid+',0'; os.environ['TMUX'] = env['TMUX']
            tm('set-option', '-g', 'default-shell', '/bin/sh')
            tm('new-session', '-d', '-s', 'beta', 'sleep 600')
            original = tm('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            backend('init'); backend('layout', kind='custom')
            assert wait(lambda: bool(status())), 'Service did not start'
            initial = status(); daemon = initial['pid']; path = service.endpoint()
            assert path.stat().st_mode & 0o777 == 0o600
            assert path.parent.stat().st_mode & 0o777 == 0o700
            def descriptors(): return len(list(Path('/proc', str(daemon), 'fd').iterdir()))
            baseline_fds = descriptors()
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 150, 0, 0))
            proc = subprocess.Popen(['tmux', '-S', sock, 'attach-session', '-t', 'alpha'], env=env,
                                    stdin=slave, stdout=slave, stderr=slave)
            os.close(slave); drain(.3)
            client = tm('list-clients', '-F', '#{client_name}')
            pane = tm('display-message', '-p', '-t', 'alpha', '#{pane_id}')
            for _ in range(12):
                open_picker(b'alpha'); close_picker()
            assert status()['pid'] == daemon
            assert descriptors() <= baseline_fds+1, (baseline_fds, descriptors())
            assert status()['cache_bytes'] <= service.MAX_BYTES and status()['cache_panes'] <= service.MAX_PANES
            rss = next(line for line in Path('/proc', str(daemon), 'status').read_text().splitlines() if line.startswith('VmRSS:'))
            assert int(rss.split()[1]) < 96*1024, rss
            print('PASS: reused worker parent; bounded metadata/RSS; no descriptor or popup-worker leak.', flush=True)
            # A slow live helper must never be replaced by a duplicate parent.
            inode = path.stat().st_ino
            os.kill(daemon, signal.SIGSTOP)
            try:
                service.start()
                assert path.stat().st_ino == inode
                open_picker(b'alpha'); os.write(master, b'q'); drain(.3)
            finally: os.kill(daemon, signal.SIGCONT)
            assert wait(lambda: status().get('pid') == daemon)
            print('PASS: unresponsive helper keeps one endpoint; timeout uses the regular picker.', flush=True)
            # Fresh current session/window, even if the cache was captured before the switch.
            tm('rename-session', '-t', 'alpha', 'renamed-now')
            open_picker(b'renamed-now'); close_picker()
            tm('new-session', '-d', '-s', 'fresh-now', 'sleep 600'); backend('sync')
            output = open_picker(b'fresh-now'); close_picker()
            # Name reuse cannot resurrect a destroyed cached session ID.
            tm('kill-session', '-t', 'beta'); tm('new-session', '-d', '-s', 'beta', 'sleep 600'); backend('sync')
            open_picker(); close_picker()
            print('PASS: rename/create/destroy/reuse refresh without stale selected targets.', flush=True)
            # Malformed requests, including received descriptors, cannot leak FDs.
            baseline_fds = descriptors()
            for _ in range(12):
                with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as bad:
                    bad.connect(str(path))
                    bad.sendmsg([b'open\0bad\0'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [master]))])
                    bad.recv(100)
            assert wait(lambda: descriptors() <= baseline_fds+1)
            # Kill just the transport: its own UI worker must exit and clear flags.
            open_picker()
            assert wait(lambda: tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid').isdigit())
            child = int(tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid'))
            assert Path('/proc', str(child), 'stat').read_text().rsplit(') ', 1)[1].split()[1] == str(daemon)
            # Identify by fd socket peer/argv rather than touching other active pickers.
            candidates = []
            for p in Path('/proc').iterdir():
                if not p.name.isdigit(): continue
                try:
                    args = (p/'cmdline').read_bytes().split(b'\0')
                    if len(args)>1 and args[1] == str(path).encode(): candidates.append(int(p.name))
                except (OSError, ProcessLookupError): pass
            assert len(candidates) == 1, candidates
            os.kill(candidates[0], signal.SIGKILL)
            assert wait(lambda: status().get('workers') == 0)
            assert wait(lambda: not tm('show-options', '-pqv', '-t', pane, '@workspace-picker-open'))
            print('PASS: rejected bad descriptors; dead transport closes only its own popup and restores flags.', flush=True)
            open_picker()
            child = int(tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid'))
            os.kill(child, signal.SIGKILL)
            drain(.3)
            assert wait(lambda: status().get('workers') == 0)
            assert wait(lambda: not tm('show-options', '-pqv', '-t', pane, '@workspace-picker-open'))
            print('PASS: crashed UI worker is reaped and clears only its own picker flags.', flush=True)
            # A hard-killed parent cannot leave an orphan UI worker behind.
            open_picker()
            child = int(tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid'))
            os.kill(daemon, signal.SIGKILL)
            def worker_gone():
                try: return Path('/proc', str(child), 'stat').read_text().rsplit(') ', 1)[1].split()[0] == 'Z'
                except FileNotFoundError: return True
            assert wait(worker_gone)
            assert wait(lambda: not tm('show-options', '-pqv', '-t', pane, '@workspace-picker-open'))
            open_picker(b'renamed-now'); os.write(master, b'q'); drain(.3)
            assert wait(lambda: bool(status()))
            daemon = status()['pid']
            print('PASS: hard-killed helper leaves no orphan UI; stale socket recovers automatically.', flush=True)
            # Retire/replace the preloader without interrupting an open picker.
            open_picker()
            child = int(tm('show-options', '-pqv', '-t', pane, '@workspace-picker-pid'))
            old_daemon = daemon
            service.request('retire'); assert wait(lambda: not path.exists())
            service.start(); assert wait(lambda: status().get('pid', old_daemon) != old_daemon)
            assert Path('/proc', str(child)).exists()
            assert Path('/proc', str(child), 'stat').read_text().rsplit(') ', 1)[1].split()[1] == str(old_daemon)
            os.write(master, b'jq'); drain(.3)
            def retired():
                try: return Path('/proc', str(old_daemon), 'stat').read_text().rsplit(') ', 1)[1].split()[0] == 'Z'
                except FileNotFoundError: return True
            assert wait(retired)
            daemon = status()['pid']
            open_picker(); close_picker()
            assert tm('display-message', '-p', '-t', pane, '#{pane_id}:#{pane_pid}') in original.splitlines()
            print('PASS: helper replacement drains existing picker; new generation opens normally.', flush=True)
            # Oversized input is never retained or partially displayed.
            fake = root/'bin'; fake.mkdir(); fake_tmux = fake/'tmux'
            fake_tmux.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdout.write("x" * (2*1024*1024+1))\n'); fake_tmux.chmod(0o700)
            old_path = os.environ['PATH']; os.environ['PATH'] = str(fake)+':'+old_path
            cache = service.Snapshot(); cache.refresh(); assert cache.sessions is None and cache.size == 0
            fake_tmux.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdout.write("x\\n" * 1025)\n')
            cache.refresh(); assert cache.sessions is None and cache.panes == 0
            os.environ['PATH'] = old_path
            assert len(list(path.parent.glob('client-*'))) == 1
            assert not list(path.parent.glob('*.json'))
            print('PASS: cache rejects >2 MiB/>1024 panes; one stable client binary; no disk metadata/previews.', flush=True)
            # Broken cached executables are rebuilt atomically; compiler failure
            # retains the regular picker rather than installing a dead binding.
            target = service.install_client(); target.write_bytes(b'broken')
            bad_cc = root/'cc-fail'; bad_cc.mkdir()
            compiler = bad_cc/'cc'; compiler.write_text('#!/bin/sh\nexit 1\n'); compiler.chmod(0o700)
            old_path = env['PATH']; env['PATH'] = str(bad_cc)+':'+old_path
            backend('layout', kind='custom')
            assert '/client-current' not in tm('list-keys')
            open_picker(); os.write(master, b'q'); drain(.3)
            env['PATH'] = old_path
            backend('layout', kind='custom')
            assert wait(lambda: bool(status()))
            assert target.read_bytes()[:4] == b'\x7fELF'
            print('PASS: compiler failure keeps regular picker; corrupted transport is rebuilt.', flush=True)
            from picker_preview import Preview
            preview = Preview(); preview.style = lambda *_: 0
            class Screen:
                def addstr(self, *_): pass
            preview.capture = lambda _: (20, 1, 0, 0, False, [[('a', -1, -1, 0)]*20])
            for n in range(50): preview.pane(Screen(), '%'+str(n), 0, 0, 1, 20)
            assert len(preview.snapshots) <= preview.MAX_PANES
            assert sum(preview.weights.values()) <= preview.MAX_CELLS
            preview.capture = lambda _: (1, 1, 0, 0, False, [[('a', -1, -1, 0)]*(preview.MAX_CELLS+1)])
            preview.pane(Screen(), '%big', 0, 0, 1, 1)
            assert '%big' not in preview.snapshots
            print('PASS: per-popup preview cache is bounded and bypasses oversized screens.', flush=True)
            current = status(); current_pid = current['pid']
            tm('kill-server')
            assert wait(lambda: not path.exists()), 'Service socket survived its tmux server'
            assert wait(lambda: not Path('/proc', str(current_pid)).exists() or
                        '\nState:\tZ' in Path('/proc', str(current_pid), 'status').read_text())
            print('PASS: helper and socket exit with the disposable tmux server.', flush=True)
            tm('new-session', '-d', '-s', 'new-server-only', 'sleep 600')
            new_pid = tm('display-message', '-p', '#{pid}')
            env['TMUX'] = sock+','+new_pid+',0'; os.environ['TMUX'] = env['TMUX']
            backend('init'); backend('layout', kind='custom')
            assert wait(lambda: status().get('server', [''])[0] == new_pid)
            assert wait(lambda: status().get('cache_panes') == 1)
            print('PASS: same-path server restart starts a fresh helper/cache generation.', flush=True)

        finally:
            subprocess.run(['tmux', '-S', sock, 'kill-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc:
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.terminate(); proc.wait(timeout=3)
            if master is not None: os.close(master)
            os.environ.clear(); os.environ.update(previous)


def outside_tmux():
    # SSH initialization has no TMUX variable. Give this subprocess its own
    # default-socket directory so discovery can never reach the live server.
    with tempfile.TemporaryDirectory(prefix='picker-ssh-init-') as folder:
        root = Path(folder)
        env = {**os.environ, 'TMUX_TMPDIR': folder, 'TMUX_WORKSPACES_STATE': str(root/'state.json'),
               'TMUX_PICKER_RUNTIME': str(root/'runtime')}
        env.pop('TMUX', None); env.pop('TMUX_PANE', None); env.pop('XDG_RUNTIME_DIR', None)
        def tm(*args): return subprocess.check_output(['tmux', *args], env=env, text=True).strip()
        try:
            tm('-f', '/dev/null', 'new-session', '-d', '-s', 'ssh-fixture', 'sleep 600')
            pid = tm('display-message', '-p', '#{pid}')
            helper = str(ROOT/'scripts/workspaces.py')
            subprocess.run([helper, 'init'], env=env, check=True)
            subprocess.run([helper, 'layout', '--kind', 'custom'], env=env, check=True)
            end = time.monotonic()+5; result = {}
            while time.monotonic()<end:
                reply = subprocess.run([sys.executable, str(ROOT/'scripts/picker_service.py'), 'status'],
                                       env=env, text=True, capture_output=True)
                if reply.returncode == 0:
                    result = json.loads(reply.stdout); break
                time.sleep(.03)
            assert result.get('server', [''])[0] == pid, result
            assert tm('list-clients') == '', 'Helper attached an extra tmux client'
            print('PASS: SSH/outside-tmux initialization selects only its own default server; no extra attached client.', flush=True)
        finally:
            subprocess.run(['tmux', 'kill-server'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            end = time.monotonic()+3
            while list((root/'runtime').glob('*.sock')) and time.monotonic()<end: time.sleep(.05)
            assert not list((root/'runtime').glob('*.sock'))


if __name__ == '__main__':
    main(); outside_tmux()
