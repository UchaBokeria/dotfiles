#!/usr/bin/env python3
"""Per-tmux-server preloaded picker; bounded metadata only, private local socket."""
import argparse
import ctypes
import errno
import array
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
MAX_BYTES = 2 * 1024 * 1024
MAX_PANES = 1024
MAX_WORKERS = 4
MAX_AGE = .35
LIBC = ctypes.CDLL(None, use_errno=True)


def runtime():
    base = Path(os.environ.get('TMUX_PICKER_RUNTIME', '/tmp/tmux-picker-' + str(os.getuid()))).absolute()
    try: base.mkdir(mode=0o700)
    except FileExistsError: pass
    info = base.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError('Unsafe picker runtime directory')
    return base


def context():
    value = os.environ.get('TMUX', '').rsplit(',', 2)
    if len(value) == 3:
        value[1] = server_identity()[0]
        return value
    result = subprocess.check_output(['tmux', 'display-message', '-p', '#{socket_path}\t#{pid}'], text=True).strip().split('\t')
    return [*result, '0']


def state_file():
    import workspaces
    return str(Path(os.environ.get('TMUX_WORKSPACES_STATE') or workspaces.state_path()).absolute())


def endpoint():
    value = context()
    key = hashlib.sha256((value[0] + '\0' + state_file()).encode()).hexdigest()[:20]
    return runtime() / (key + '.sock')


def version():
    digest = hashlib.sha256()
    for name in ('picker_service.py', 'picker_client.c', 'workspaces.py', 'session_picker.py',
                 'picker_preview.py', 'picker_theme.py', 'picker_startup.py', 'workspace_ui.py'):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def request(action, path=None, timeout=.25):
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as client:
        client.settimeout(timeout); client.connect(str(path or endpoint()))
        uid = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
        if uid != os.getuid(): raise RuntimeError('Wrong picker service owner')
        client.sendall(action.encode() + b'\0')
        return json.loads(client.recv(16384))


def invalidate():
    # Fire-and-forget: a backend never waits on the worker while holding the
    # workspace database lock. Missing/offline services are simply ignored.
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as client:
            client.settimeout(.01); client.connect(str(endpoint())); client.sendall(b'invalidate\0')
    except (OSError, RuntimeError): pass


def install_client():
    base = runtime()
    digest = hashlib.sha256((HERE / 'picker_client.c').read_bytes()).hexdigest()
    # Stable path: updating a helper must never remove a binary referenced by
    # another live tmux server's prefix binding. Existing processes keep the
    # old inode while new executions use the atomically replaced transport.
    target = base / 'client-current'; signature = base / 'client.version'
    with (base / 'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for abandoned in base.glob('.build-*'):
            if abandoned.is_file() and not abandoned.is_symlink(): abandoned.unlink()
        valid = False
        if target.exists():
            info = target.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError('Unsafe picker client cache')
            if signature.exists() and signature.stat().st_size <= 256 and info.st_size <= 1024*1024:
                valid = signature.read_text().split() == [digest, hashlib.sha256(target.read_bytes()).hexdigest()] and os.access(target, os.X_OK)
        if not valid:
            temporary = base / ('.build-' + str(os.getpid()))
            stamp = base / ('.build-version-' + str(os.getpid()))
            try:
                subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-o', str(temporary),
                                str(HERE / 'picker_client.c')], check=True, capture_output=True, timeout=30)
                temporary.chmod(0o700)
                stamp.write_text(digest + '\n' + hashlib.sha256(temporary.read_bytes()).hexdigest() + '\n')
                os.replace(temporary, target); os.replace(stamp, signature)
            finally:
                temporary.unlink(missing_ok=True); stamp.unlink(missing_ok=True)
    return target


def start():
    current = version()
    try:
        existing = request('status', timeout=.8)
        if existing['version'] == current and existing['server'] == server_identity(): return
    except OSError as error:
        if error.errno not in (errno.ENOENT, errno.ECONNREFUSED): return
    except (ValueError, RuntimeError, KeyError): return
    subprocess.Popen([sys.executable, str(HERE / 'picker_service.py'), 'serve'],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True,
                     env={**os.environ, 'TMUX': ','.join(context()), 'TMUX_WORKSPACES_STATE': state_file()})


def server_identity():
    import workspaces
    return list(workspaces.server_identity())


class Snapshot:
    def __init__(self):
        self.sessions = None; self.at = 0; self.size = 0; self.panes = 0; self.refreshes = 0
    def refresh(self):
        from session_picker import PANE_FORMAT, fetch_sessions
        # Read at most 2 MiB. Never truncate a large server into a partial view:
        # bypass the cache and let the regular fresh query handle it instead.
        proc = subprocess.Popen(['tmux', 'list-panes', '-a', '-F', PANE_FORMAT], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        try:
            raw = bytearray(); deadline = time.monotonic() + .5
            poll = selectors.DefaultSelector(); poll.register(proc.stdout, selectors.EVENT_READ)
            try:
                while time.monotonic() < deadline:
                    if not poll.select(max(0, deadline-time.monotonic())): break
                    chunk = os.read(proc.stdout.fileno(), min(65536, MAX_BYTES+1-len(raw)))
                    if not chunk: break
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES: break
                else: raise subprocess.TimeoutExpired(proc.args, .5)
                if proc.poll() is None and time.monotonic() >= deadline: raise subprocess.TimeoutExpired(proc.args, .5)
            finally: poll.close()
            if len(raw) > MAX_BYTES:
                proc.terminate(); self.clear(); return
            proc.wait(timeout=.2)
            if proc.returncode or raw.count(b'\n') > MAX_PANES:
                self.clear(); return
            parsed = fetch_sessions(None, raw.decode())
            self.sessions = parsed; self.size = len(raw); self.panes = raw.count(b'\n')
            self.at = time.monotonic(); self.refreshes += 1
        except (OSError, ValueError, subprocess.TimeoutExpired): self.clear()
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
            proc.stdout.close()
    def clear(self):
        self.sessions = None; self.at = time.monotonic(); self.size = self.panes = 0


def serve():
    os.environ['TMUX'] = ','.join(context())
    os.environ['TMUX_WORKSPACES_STATE'] = state_file()
    # Preload every UI module before accepting requests. No curses state, tty or
    # database lock exists in the parent; only the forked popup initializes curses.
    import session_picker
    import workspaces
    path = endpoint(); lock_path = runtime() / 'service.lock'
    lock = lock_path.open('a'); fcntl.flock(lock, fcntl.LOCK_EX)
    identity = server_identity(); revision = version()
    for item in runtime().glob('*.sock'):
        if item == path: continue
        try:
            if stat.S_ISSOCK(item.lstat().st_mode):
                with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as probe:
                    probe.settimeout(.03); probe.connect(str(item)); probe.sendall(b'status\0'); probe.recv(16384)
        except (ConnectionRefusedError, FileNotFoundError): item.unlink(missing_ok=True)
        except OSError: pass
    try:
        old = request('status', path, timeout=.8)
        if old['version'] == revision and old['server'] == identity: return
        request('retire', path, timeout=.8)
        deadline = time.monotonic() + .8
        while path.exists() and time.monotonic() < deadline: time.sleep(.01)
        if path.exists(): return
    except OSError as error:
        # A slow live worker keeps its endpoint. Never unlink a live socket and
        # accidentally leave two resident workers refreshing the same server.
        if error.errno not in (errno.ENOENT, errno.ECONNREFUSED): return
    except (ValueError, RuntimeError, KeyError): return
    if path.exists() and not stat.S_ISSOCK(path.lstat().st_mode):
        raise RuntimeError('Unsafe picker service endpoint')
    path.unlink(missing_ok=True)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    listener.bind(str(path)); os.chmod(path, 0o600); listener.listen(8); listener.setblocking(False)
    inode = path.stat().st_ino
    fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
    events = selectors.DefaultSelector(); events.register(listener, selectors.EVENT_READ)
    children = {}; owners = {}; retiring = False; snapshot = Snapshot(); snapshot.refresh()
    last_use = time.monotonic(); checked = 0
    def retire(*_):
        nonlocal retiring
        if not retiring:
            retiring = True
            events.unregister(listener); listener.close()
            try:
                if path.stat().st_ino == inode: path.unlink()
            except FileNotFoundError: pass
    signal.signal(signal.SIGTERM, retire); signal.signal(signal.SIGHUP, retire)
    try:
        while not retiring or children:
            now = time.monotonic()
            if now - checked >= 1:
                checked = now
                try: alive = server_identity() == identity and Path(os.environ['TMUX'].rsplit(',', 2)[0]).exists()
                except (OSError, RuntimeError, subprocess.SubprocessError): alive = False
                if not alive: retire()
            for pid, connection in list(children.items()):
                done, _ = os.waitpid(pid, os.WNOHANG)
                if done:
                    if connection is not None:
                        events.unregister(connection); connection.close()
                    del children[pid]
                    owner, pane = owners.pop(pid)
                    if not retiring and owner not in (entry[0] for entry in owners.values()):
                        try:
                            current = workspaces.tm('display-message', '-p', '-t', pane, '#{@workspace-picker-owner}')
                            if current == owner: workspaces.clear_picker_flags(owner)
                        except (OSError, subprocess.SubprocessError): pass
            if retiring and not children: break
            interval = .3 if now - last_use < 10 else 2
            if not retiring and now - snapshot.at >= interval: snapshot.refresh()
            for key, _ in events.select(.1):
                if key.fileobj is not listener:
                    # A popup's transport died: stop only its own picker worker.
                    connection = key.fileobj
                    if connection.recv(1) is not None:
                        pid = next((p for p, c in children.items() if c is connection), None)
                        if pid:
                            try: os.kill(pid, signal.SIGTERM)
                            except ProcessLookupError: pass
                        events.unregister(connection); connection.close()
                        if pid: children[pid] = None
                    continue
                connection, _ = listener.accept(); connection.settimeout(.25)
                received = []
                try:
                    uid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                    if uid != os.getuid(): raise ValueError('Wrong owner')
                    raw, ancillary, flags, _ = connection.recvmsg(4096, socket.CMSG_SPACE(16))
                    for level, kind, payload in ancillary:
                        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                            values = array.array('i'); values.frombytes(payload[:len(payload) - len(payload) % values.itemsize]); received.extend(values)
                    parts = raw.split(b'\0')[:-1]
                    action = parts[0].decode()
                    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC): raise ValueError('Oversize request')
                    if action == 'status':
                        connection.sendall(json.dumps({'pid': os.getpid(), 'server': identity, 'version': revision,
                            'workers': len(children), 'cache_bytes': snapshot.size, 'cache_panes': snapshot.panes,
                            'cache_age': time.monotonic()-snapshot.at, 'refreshes': snapshot.refreshes,
                            'max_bytes': MAX_BYTES, 'max_panes': MAX_PANES, 'max_workers': MAX_WORKERS}).encode())
                    elif action == 'invalidate':
                        snapshot.at = 0
                    elif action == 'retire':
                        connection.sendall(b'{}'); retire()
                    elif action == 'open':
                        if len(parts) != 10 or len(received) != 1 or not os.isatty(received[0]) or len(children) >= MAX_WORKERS:
                            raise ValueError('Invalid popup')
                        client, pane, workspace = (p.decode() for p in parts[1:4])
                        terminal_env = dict(zip(('TERM', 'LANG', 'LC_ALL', 'LC_CTYPE', 'COLORTERM'), (p.decode() for p in parts[4:9])))
                        requested_server = parts[9].decode().rsplit(',', 2)
                        own_socket = os.environ['TMUX'].rsplit(',', 2)[0]
                        if len(requested_server) != 3 or requested_server[0] != own_socket:
                            raise ValueError('Wrong tmux server')
                        if requested_server[1] != identity[0]:
                            if server_identity() != identity: retire()
                            raise ValueError('Expired tmux server generation')
                        if not pane.startswith('%') or not pane[1:].isdigit(): raise ValueError('Invalid pane')
                        last_use = time.monotonic()
                        if last_use - snapshot.at > MAX_AGE: snapshot.refresh()
                        ready_read, ready_write = os.pipe()
                        parent_pid = os.getpid()
                        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGHUP})
                        try: pid = os.fork()
                        except OSError:
                            os.close(ready_read); os.close(ready_write)
                            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
                            raise
                        if pid == 0:
                            for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGWINCH): signal.signal(sig, signal.SIG_DFL)
                            if LIBC.prctl(1, signal.SIGTERM) or os.getppid() != parent_pid: os._exit(1)
                            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
                            os.close(ready_write)
                            if os.read(ready_read, 1) != b'1': os._exit(1)
                            os.close(ready_read)
                            # No inherited listener/client descriptors keep the service alive.
                            for other in children.values():
                                if other is not None: other.close()
                            listener.close(); events.close()
                            fd = received.pop(); os.dup2(fd, 0); os.dup2(fd, 1); os.dup2(fd, 2)
                            if fd > 2: os.close(fd)
                            for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGWINCH): signal.signal(sig, signal.SIG_DFL)
                            def interrupted(signum, _): raise SystemExit(128+signum)
                            signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGHUP, interrupted)
                            for name, value in terminal_env.items():
                                if value: os.environ[name] = value
                                else: os.environ.pop(name, None)
                            status = 0
                            try:
                                args = argparse.Namespace(action='open-ui', client=client, pane=pane, workspace=workspace)
                                args.picker_snapshot = snapshot.sessions
                                workspaces.open_picker_ui(args)
                            except BaseException:
                                import traceback
                                traceback.print_exc(); status = 1
                            try: connection.sendall(struct.pack('i', status))
                            except OSError: pass
                            os._exit(status)
                        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
                        os.close(ready_read)
                        process_fd = None
                        try:
                            process_fd = os.pidfd_open(pid)
                            connection.sendmsg([struct.pack('i', pid)],
                                               [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [process_fd]))])
                            os.write(ready_write, b'1')
                        except OSError:
                            os.kill(pid, signal.SIGTERM); os.waitpid(pid, 0); raise
                        finally:
                            if process_fd is not None: os.close(process_fd)
                            os.close(ready_write)
                        connection.setblocking(False)
                        events.register(connection, selectors.EVENT_READ); children[pid] = connection; owners[pid] = (client, pane); connection = None
                    else: raise ValueError('Unknown request')
                except (OSError, ValueError, UnicodeError): pass
                finally:
                    for fd in received: os.close(fd)
                    if connection is not None: connection.close()
    finally:
        retire(); events.close()
        # Server-path based names are reused after a server restart. No logs,
        # screenshots, growing cache files or state copies are created here.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('start', 'serve', 'status', 'retire'))
    action = parser.parse_args().action
    if action == 'serve': serve()
    elif action == 'start': start()
    else:
        try: print(json.dumps(request(action)))
        except (OSError, ValueError, RuntimeError): sys.exit('Picker helper is not running for this tmux server.')
