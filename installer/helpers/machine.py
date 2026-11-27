#!/usr/bin/env python3
"""Small installer actions shared by the catalogue and isolated acceptance tests."""
from __future__ import annotations
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import re
import subprocess

BEGIN = '-- >>> blackwall installer'
END = '-- <<< blackwall installer'


def machine_text(existing, mod, driver, profile=None, headless_mode=None):
    if mod not in ('SUPER', 'ALT', 'CTRL') or driver not in ('none', 'iHD', 'i965', 'radeonsi', 'nvidia'):
        raise ValueError('Invalid modifier or VA-API driver')
    profile = profile or os.environ.get('BLACKWALL_PROFILE', 'desktop')
    if profile not in ('desktop', 'server'):
        raise ValueError('Invalid profile')
    headless_mode = headless_mode or os.environ.get('BLACKWALL_HEADLESS_MODE', '1920x1080@60')
    if BEGIN not in existing:
        # Only migrate the exact pre-managed installer header/assignment
        # shape. Unmarked driver tuning and custom code remain owner-owned.
        legacy = re.compile(
            r"\A(-- Written by \./install\. Not tracked: every machine has its own\.\n"
            r"-- Edit freely; see machine\.lua\.example for what can go in here\.\n)"
            r"BLACKWALL\.mod = '(?:SUPER|ALT|CTRL)'\n"
            r"(?:\nhl\.env\('LIBVA_DRIVER_NAME', '(?:iHD|i965|radeonsi|nvidia)'\)\n)?")
        existing = legacy.sub(r'\1', existing, count=1)
    block = [BEGIN, 'BLACKWALL.mod = ' + json.dumps(mod)]
    if driver != 'none':
        block.append('hl.env("LIBVA_DRIVER_NAME", ' + json.dumps(driver) + ')')
    if profile == 'server':
        # Headless KVM box: no physical outputs, so claim an explicit virtual
        # mode instead of env.lua's wildcard `output = ""` + preferred. The
        # wildcard style is what the Vultr box already proved (cheatsheet
        # "Remote desktop": 1280x800 virtual output via wayvnc); here it is
        # pinned to the configured 1920x1080 mode. Change the mode by setting
        # BLACKWALL_HEADLESS_MODE before running the installer.
        block.append('hl.monitor({ output = "", mode = ' + json.dumps(headless_mode) + ', position = "auto", scale = 1 }) -- server: virtual output; owner changes the mode')
    # The canonical location is installed before configuration consumers.
    command = 'python3 "$HOME/.config/.dotfiles/blackwall/installer/helpers/session-finalize.py" launch'
    block.extend(['hl.exec_cmd(' + json.dumps(command) + ')', END])
    if BEGIN in existing:
        before, rest = existing.split(BEGIN, 1)
        if END not in rest:
            raise ValueError('Incomplete installer block in machine.lua; preserve and repair it first')
        _, after = rest.split(END, 1)
        return before + '\n'.join(block) + after
    return existing.rstrip() + ('\n\n' if existing.strip() else '') + '\n'.join(block) + '\n'


def machine(repo, check=False):
    path = repo / 'hypr/lua/machine.lua'
    old = path.read_text() if path.exists() else ''
    text = machine_text(old, os.environ.get('BLACKWALL_MOD', 'SUPER'), os.environ.get('BLACKWALL_LIBVA', 'none'))
    if check:
        return old == text
    path.write_text(text)
    return True


def sddm(root, repo, check=False):
    theme = root / 'usr/share/sddm/themes/sddm-astronaut-theme'
    config = root / 'etc/sddm.conf.d/90-blackwall.conf'
    session = root / 'usr/share/wayland-sessions/blackwall.desktop'
    launcher = root / 'usr/local/bin/blackwall-session'
    fragment = '[Theme]\nCurrent=sddm-astronaut-theme\n[General]\nInputMethod=qtvirtualkeyboard\n[Users]\nRememberLastSession=true\n'
    desktop = '[Desktop Entry]\nName=Blackwall (Hyprland)\nComment=The configured Blackwall desktop\nExec=/usr/local/bin/blackwall-session\nType=Application\nDesktopNames=Hyprland\n'
    launch = '#!/bin/sh\nexec /usr/bin/start-hyprland -- --config "$HOME/.config/hypr/lua/hyprland.lua"\n'
    if check:
        return all(p.exists() and p.read_text() == text for p, text in [(config, fragment), (session, desktop), (launcher, launch)]) and (theme / 'Main.qml').exists() and 'ConfigFile=Themes/japanese_aesthetic.conf' in (theme / 'metadata.desktop').read_text()
    source = repo / 'sddm-astronaut-theme'
    if not (source / 'Main.qml').is_file():
        raise RuntimeError('SDDM submodule is incomplete')
    shutil.copytree(source, theme, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
    metadata = theme / 'metadata.desktop'
    metadata.write_text('\n'.join('ConfigFile=Themes/japanese_aesthetic.conf' if line.startswith('ConfigFile=') else line for line in metadata.read_text().splitlines()) + '\n')
    for path, text in [(config, fragment), (session, desktop), (launcher, launch)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    launcher.chmod(0o755)
    for font in (source / 'Fonts').rglob('*'):
        if font.is_file() and font.suffix.lower() in ('.ttf', '.otf'):
            dest = root / 'usr/share/fonts/blackwall-sddm' / font.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(font, dest)
    # SDDM's main file takes precedence over conf.d. Change just this
    # presentation key when present; leave all authentication settings intact.
    main = root / 'etc/sddm.conf'
    if main.exists():
        old = main.read_text()
        sections = re.split(r'(?=^\[)', old, flags=re.M)
        updated = []
        for section in sections:
            if section.startswith('[Theme]'):
                section = re.sub(r'^Current=.*$', 'Current=sddm-astronaut-theme', section, flags=re.M)
            updated.append(section)
        text = ''.join(updated)
        if old != text:
            backup = main.with_name('sddm.conf.blackwall-backup')
            if not backup.exists():
                shutil.copy2(main, backup)
            main.write_text(text)
    # Select the desktop for the first login without enabling autologin.
    state = root / 'var/lib/sddm/state.conf'
    if not state.exists():
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text('[Last]\nSession=/usr/share/wayland-sessions/blackwall.desktop\n')
        if root == Path('/'):
            shutil.chown(state, user='sddm', group='sddm')
    return True


def network(check=False):
    ready = all(subprocess.run(['systemctl', state, '--quiet', 'NetworkManager.service']).returncode == 0
                for state in ('is-enabled', 'is-active'))
    if check or ready:
        return ready
    for unit in ('systemd-networkd.service', 'connman.service', 'dhcpcd.service'):
        if subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0 or subprocess.run(['systemctl', 'is-enabled', '--quiet', unit]).returncode == 0:
            raise RuntimeError(f'{unit} already manages networking; choose the network stack before enabling NetworkManager')
    # Per-interface dhcpcd/netctl units need not activate their parent unit.
    # Inspect both running instances and instances scheduled for the reboot.
    listings = (
        ['systemctl', 'list-units', '--type=service', '--state=active', '--plain', '--no-legend', '--no-pager'],
        ['systemctl', 'list-unit-files', '--type=service', '--state=enabled,enabled-runtime', '--no-legend', '--no-pager'],
    )
    for argv in listings:
        result = subprocess.run(argv, check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            columns = line.split()
            if columns and re.fullmatch(r'(?:dhcpcd|netctl|netctl-auto)@.+\.service', columns[0]):
                raise RuntimeError(f'{columns[0]} already manages networking; choose the network stack before enabling NetworkManager')
    subprocess.run(['systemctl', 'enable', '--now', 'NetworkManager.service'], check=True)
    return True


def gpu(driver, check=False):
    packages = {'none': None, 'iHD': 'intel-media-driver', 'i965': 'libva-intel-driver',
                'radeonsi': 'mesa', 'nvidia': 'libva-nvidia-driver'}
    if driver not in packages:
        raise ValueError('Unknown VA-API driver')
    package = packages[driver]
    if package is None:
        return True
    if check:
        return subprocess.run(['pacman', '-Q', package], stdout=subprocess.DEVNULL).returncode == 0
    subprocess.run(['pacman', '-S', '--needed', '--noconfirm', package], check=True)
    return True


def sddm_autologin(user, session, system_root, check=False):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user) or not re.fullmatch(r'[A-Za-z0-9._-]+', session):
        raise ValueError('Invalid autologin user or session name')
    if user == 'root':
        raise ValueError('refusing SDDM autologin as root: default ${SUDO_USER:-$(id -un)} resolves to root under sudo')
    config = system_root / 'etc/sddm.conf.d/10-autologin.conf'
    text = f'[Autologin]\nUser={user}\nSession={session}\n'
    if check:
        return config.exists() and config.read_text() == text
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(text)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('machine', 'sddm', 'sddm-autologin', 'network', 'gpu'))
    parser.add_argument('--driver', default='none')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--system-root', type=Path, default=Path('/'))
    parser.add_argument('--user', default=getpass.getuser())
    parser.add_argument('--session', default='blackwall')
    args = parser.parse_args()
    if args.action == 'machine':
        okay = machine(args.repo, args.check)
    elif args.action == 'sddm':
        okay = sddm(args.system_root, args.repo, args.check)
    elif args.action == 'sddm-autologin':
        okay = sddm_autologin(args.user, args.session, args.system_root, args.check)
    elif args.action == 'network':
        okay = network(args.check)
    else:
        okay = gpu(args.driver, args.check)
    return 0 if okay else 1

if __name__ == '__main__':
    raise SystemExit(main())
