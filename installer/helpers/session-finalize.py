#!/usr/bin/env python3
"""Install and run the unattended, per-user first-Hyprland-login completion job.

No sudo, package installs, credentials or UI test clicks occur in this job.
Status and the append-only log live in $XDG_STATE_HOME/blackwall-installer.
The timer retries failures; a completed plan is a no-op on subsequent logins.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import signal
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import tomllib


def state_dir():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'blackwall-installer'


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(path)


def register(repo):
    repo = repo.resolve()
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    # No arbitrary environment or secret answers persisted across reboot.
    catalogue = tomllib.loads((repo / 'installer/data/steps.toml').read_text())
    groups = set(os.environ.get('BLACKWALL_INSTALL_GROUPS', '').split(','))
    skipped = set(os.environ.get('BLACKWALL_INSTALL_SKIPPED_STEPS', '').split(','))
    jobs = [step for step in catalogue['step'] if step.get('needs_session') and
            not step.get('interactive') and not step.get('root') and step['id'] != 'selftest' and
            step['id'] not in skipped and
            (not step.get('group') or step['group'] in groups)]
    questions = tomllib.loads((repo / 'installer/data/questions.toml').read_text())
    safe_keys = {q['env'] for q in questions['question'] if not q.get('secret')}
    env = {key: os.environ[key] for key in safe_keys if key in os.environ}
    by_id = {step['id']: step for step in catalogue['step']}
    job_ids = {job['id'] for job in jobs}
    ordered, visiting, visited = [], set(), set()
    def visit(job):
        name = job['id']
        if name in visiting:
            raise RuntimeError('Cyclic first-login dependency: ' + name)
        if name in visited:
            return
        visiting.add(name)
        for dep in job.get('after', []):
            if dep not in by_id:
                raise RuntimeError('Missing first-login dependency: ' + dep)
            if by_id[dep].get('needs_session'):
                if dep not in job_ids:
                    raise RuntimeError('Excluded first-login dependency: ' + dep)
                visit(by_id[dep])
        visiting.remove(name)
        visited.add(name)
        ordered.append(job)
    for job in jobs:
        visit(job)
    jobs = ordered
    plan = {'version': 1, 'repo': str(repo), 'state': 'pending', 'steps': {}, 'jobs': jobs, 'env': env}
    # Recheck read-only offline predicates rather than staging failed setup.
    pending = [dep for job in jobs for dep in job.get('after', [])
               if dep in by_id and not by_id[dep].get('needs_session')]
    check_env = dict(os.environ, BW=str(repo))
    for dependency in dict.fromkeys(pending):
        check = by_id[dependency].get('check', '')
        if check and subprocess.run(['sh', '-c', check], cwd=repo, env=check_env,
                                    stdin=subprocess.DEVNULL, timeout=60).returncode:
            raise RuntimeError('First-login prerequisite is not ready: ' + dependency)
    save(folder / 'session.json', plan)
    config = Path.home() / '.config/systemd/user'
    config.mkdir(parents=True, exist_ok=True)
    helper = repo / 'installer/helpers/session-finalize.py'
    # systemd ExecStart is not a shell. Quote spaces and escape specifiers.
    argument = '"' + str(helper).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    (config / 'blackwall-first-login.service').write_text(
        '[Unit]\nDescription=Complete the Blackwall desktop on first login\n'
        '[Service]\nType=oneshot\nExecStart=/usr/bin/python3 ' + argument + ' run\nTimeoutStartSec=20min\n')
    (config / 'blackwall-first-login.timer').write_text(
        '[Unit]\nDescription=Retry unfinished Blackwall desktop setup\n[Timer]\n'
        'OnStartupSec=30s\nOnUnitInactiveSec=2min\nUnit=blackwall-first-login.service\n'
        '[Install]\nWantedBy=timers.target\n')
    wants = config / 'timers.target.wants'
    wants.mkdir(exist_ok=True)
    link = wants / 'blackwall-first-login.timer'
    if not link.is_symlink():
        link.symlink_to('../blackwall-first-login.timer')
    print('First login completion scheduled; status: ' + str(folder / 'session.json'))


def launch():
    # Called by machine.lua after the compositor has supplied its environment.
    names = [key for key in ('WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE',
             'XDG_CURRENT_DESKTOP', 'XDG_SESSION_TYPE', 'DISPLAY') if os.environ.get(key)]
    if names:
        subprocess.run(['systemctl', '--user', 'import-environment', *names], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['systemctl', '--user', 'start', 'blackwall-first-login.timer'], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Also run directly: startup need not wait for the timer or user manager.
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)



def execute(argv, repo, env, log, timeout=600):
    """A timed out shell must not leave a compiler running across retries."""
    with subprocess.Popen(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                          stdout=log, stderr=log, start_new_session=True) as child:
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            # Kill descendants even if the shell exited promptly on SIGTERM.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise


def run():
    folder = state_dir()
    path = folder / 'session.json'
    if not path.exists():
        return 0
    with (folder / 'session.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        plan = json.loads(path.read_text())
        if plan['state'] in ('complete', 'complete-with-warnings'):
            return 0
        # Timer may fire before SDDM login: that is pending, not a failed install.
        if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            return 0
        probe = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True, timeout=15)
        try:
            ready = probe.returncode == 0 and any(m.get('width', 0) > 0 for m in json.loads(probe.stdout))
        except (ValueError, TypeError):
            ready = False
        if not ready:
            return 0
        plan['state'] = 'running'
        save(path, plan)
        failed = False
        warnings = False
        repo = Path(plan['repo'])
        env = dict(os.environ, **plan.get('env', {}))
        env.update(BW=str(repo), PATH=str(Path.home() / '.local/bin') + ':' + os.environ.get('PATH', ''))
        with (folder / 'session.log').open('a', buffering=1) as log:
            for job in plan['jobs']:
                name, required = job['id'], not job.get('optional', False)
                argv = ['sh', '-ec', '\n'.join(job['run'])]
                record = plan['steps'].get(name, {})
                if record.get('state') == 'complete':
                    continue
                if not required and record.get('attempts', 0) >= 3:
                    warnings = True
                    continue
                deps = {j['id'] for j in plan['jobs']} & set(job.get('after', []))
                if any(plan['steps'].get(dep, {}).get('state') != 'complete' for dep in deps):
                    failed |= required
                    warnings |= not required
                    plan['steps'][name] = {'state': 'blocked', 'attempts': 0}
                    continue
                log.write(f'\n{time.strftime("%Y-%m-%dT%H:%M:%S%z")} {name}: {shlex.join(argv)}\n')
                try:
                    code = execute(argv, repo, env, log)
                    # Autostart and wallpaper scripts can report exit 0 while
                    # logging a failed child. Verify their observable state.
                    predicate = job.get('check', '')
                    if code == 0 and predicate and predicate != 'false':
                        for attempt in range(10):
                            code = execute(['sh', '-c', predicate], repo, env, log, timeout=30)
                            if code == 0:
                                break
                            if attempt < 9:
                                time.sleep(1)
                except (OSError, subprocess.TimeoutExpired) as error:
                    log.write(str(error) + '\n')
                    code = 1
                plan['steps'][name] = {'state': 'complete' if code == 0 else 'failed',
                                      'attempts': record.get('attempts', 0) + 1, 'exit_code': code}
                save(path, plan)
                if code:
                    warnings |= not required
                    if required:
                        failed = True
                        break
            plan['state'] = 'retrying' if failed else ('retrying-optional' if warnings and
                any(s.get('state') in ('failed', 'blocked') and s.get('attempts', 0) < 3 for s in plan['steps'].values())
                else ('complete-with-warnings' if warnings else 'complete'))
            save(path, plan)
            if failed and shutil.which('notify-send'):
                subprocess.run(['notify-send', '-u', 'critical', 'Blackwall setup will retry',
                                  'See ' + str(folder / 'session.log')],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=5, check=False)
        return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register', 'launch', 'run', 'status'))
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.action == 'register':
        register(args.repo)
    elif args.action == 'launch':
        launch()
    elif args.action == 'status':
        path = state_dir() / 'session.json'
        print(path.read_text() if path.exists() else 'No first-login setup scheduled.')
    else:
        return run()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
