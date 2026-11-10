"""Isolated installer acceptance: no package manager, sudo, live service or UI."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), BASE / 'helpers' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

machine = module('machine')
finalizer = module('session-finalize')

class MachineTests(unittest.TestCase):
    def test_managed_block_validates_and_preserves_custom_settings(self):
        old = 'BLACKWALL.terminal = "foot"\n'
        text = machine.machine_text(old, 'ALT', 'radeonsi')
        self.assertTrue(text.startswith(old))
        self.assertIn('session-finalize.py', text)
        self.assertEqual(text, machine.machine_text(text, 'ALT', 'radeonsi'))
        self.assertNotIn('radeonsi', machine.machine_text(text, 'SUPER', 'none'))
        with self.assertRaises(ValueError):
            machine.machine_text(old, "SUPER';os.execute('bad')", 'none')

    def test_legacy_generated_gpu_override_migrates_to_none_preserving_custom_lines(self):
        old = ("-- Written by ./install. Not tracked: every machine has its own.\n"
               "-- Edit freely; see machine.lua.example for what can go in here.\n"
               "BLACKWALL.mod = 'SUPER'\n\n"
               "hl.env('LIBVA_DRIVER_NAME', 'iHD')\n"
               "BLACKWALL.terminal = \"foot\"\n-- custom monitor settings\n")
        text = machine.machine_text(old, 'ALT', 'none')
        self.assertNotIn('LIBVA_DRIVER_NAME', text)
        self.assertNotIn("BLACKWALL.mod = 'SUPER'", text)
        self.assertIn('BLACKWALL.terminal = "foot"', text)
        self.assertIn('-- custom monitor settings', text)
        self.assertEqual(text, machine.machine_text(text, 'ALT', 'none'))

    def test_custom_unmanaged_gpu_override_is_not_migrated(self):
        custom = "-- My driver tuning\nhl.env('LIBVA_DRIVER_NAME', 'iHD')\n"
        self.assertTrue(machine.machine_text(custom, 'SUPER', 'none').startswith(custom))
        managed = machine.machine_text('', 'SUPER', 'none') + custom
        self.assertTrue(machine.machine_text(managed, 'ALT', 'none').endswith(custom))

    def test_sddm_provisions_session_fonts_without_overwriting_auth(self):
        with tempfile.TemporaryDirectory() as temp:
            root, repo = Path(temp) / 'root', Path(temp) / 'repo'
            theme = repo / 'sddm-astronaut-theme'
            (theme / 'Fonts').mkdir(parents=True)
            (theme / 'Main.qml').write_text('theme')
            (theme / 'metadata.desktop').write_text('[SddmGreeterTheme]\nConfigFile=Themes/astronaut.conf\n')
            (theme / 'Fonts/face.ttf').write_bytes(b'font')
            auth = root / 'etc/sddm.conf'
            auth.parent.mkdir(parents=True)
            auth.write_text('[Autologin]\nUser=existing-user\n')
            machine.sddm(root, repo)
            self.assertEqual(auth.read_text(), '[Autologin]\nUser=existing-user\n')
            self.assertTrue(machine.sddm(root, repo, check=True))
            self.assertTrue((root / 'usr/share/fonts/blackwall-sddm/face.ttf').exists())
            launch = (root / 'usr/local/bin/blackwall-session').read_text()
            self.assertIn('"$HOME/.config/hypr/lua/hyprland.lua"', launch)
            self.assertNotIn(str(repo), launch)
            self.assertNotIn('Autologin', (root / 'etc/sddm.conf.d/90-blackwall.conf').read_text())

    def test_sddm_changes_theme_key_and_preserves_auth_with_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root, repo = Path(temp) / 'root', Path(temp) / 'repo'
            theme = repo / 'sddm-astronaut-theme'
            theme.mkdir(parents=True)
            (theme / 'Main.qml').write_text('theme')
            (theme / 'metadata.desktop').write_text('ConfigFile=Themes/astronaut.conf\n')
            main = root / 'etc/sddm.conf'
            main.parent.mkdir(parents=True)
            original = '[Theme]\nCurrent=old\n[Autologin]\nUser=existing-user\n'
            main.write_text(original)
            machine.sddm(root, repo)
            self.assertEqual(main.read_text(), original.replace('Current=old', 'Current=sddm-astronaut-theme'))
            self.assertEqual(main.with_name('sddm.conf.blackwall-backup').read_text(), original)

    def test_gpu_installs_only_selected_userspace_driver(self):
        with patch.object(machine.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as calls:
            machine.gpu('none')
            calls.assert_not_called()
            machine.gpu('radeonsi')
            self.assertEqual(calls.call_args.args[0], ['pacman', '-S', '--needed', '--noconfirm', 'mesa'])
            with self.assertRaises(ValueError):
                machine.gpu('invalid')

    def test_network_refuses_competing_manager(self):
        def fake(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0 if 'systemd-networkd.service' in argv else 1)
        with patch.object(machine.subprocess, 'run', side_effect=fake) as calls:
            with self.assertRaises(RuntimeError):
                machine.network()
            self.assertFalse(any('enable' in c.args[0] for c in calls.call_args_list))

    def test_network_refuses_active_or_enabled_per_interface_managers(self):
        for state in ('active', 'enabled'):
            for unit in ('dhcpcd@enp1s0.service', 'netctl@office.service', 'netctl-auto@wlan0.service'):
                with self.subTest(state=state, unit=unit):
                    def fake(argv, **kwargs):
                        output = ''
                        if argv[1] == ('list-units' if state == 'active' else 'list-unit-files'):
                            output = unit + (' loaded active running' if state == 'active' else ' enabled') + '\n'
                        return subprocess.CompletedProcess(argv, 0 if argv[1].startswith('list-') else 1, output, '')
                    with patch.object(machine.subprocess, 'run', side_effect=fake) as calls:
                        with self.assertRaisesRegex(RuntimeError, unit.replace('.', r'\.')):
                            machine.network()
                        self.assertFalse(any('enable' in c.args[0] for c in calls.call_args_list))

    def test_network_already_working_does_not_switch_or_scan_stacks(self):
        with patch.object(machine.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as calls:
            self.assertTrue(machine.network())
            self.assertEqual([c.args[0][1] for c in calls.call_args_list], ['is-enabled', 'is-active'])

class FinalizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_STATE_HOME': str(self.home / 'state'),
            'BLACKWALL_INSTALL_GROUPS': 'media', 'BLACKWALL_MOD': 'ALT', 'MODEL_API_KEY': 'not-saved'}, clear=True)
        self.env.start()
        self.which = patch.object(finalizer.shutil, "which", return_value=None)
        self.which.start()
        self.repo = self.home / 'clone with spaces'
        (self.repo / 'installer/data').mkdir(parents=True)
        (self.repo / 'installer/data/questions.toml').write_text('''[[question]]
env="BLACKWALL_MOD"
[[question]]
env="MODEL_API_KEY"
secret=true
''')
        (self.repo / 'installer/data/steps.toml').write_text('''[[step]]
id="core"
needs_session=true
run=["echo core"]
[[step]]
id="media"
group="media"
needs_session=true
optional=true
run=["echo media"]
[[step]]
id="dev"
group="dev"
needs_session=true
run=["echo dev"]
[[step]]
id="selftest"
needs_session=true
run=["pointer click"]
[[step]]
id="root"
needs_session=true
root=true
run=["sudo bad"]
''')
        finalizer.register(self.repo)
        self.path = finalizer.state_dir() / 'session.json'

    def tearDown(self):
        self.which.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_registration_filters_secrets_groups_privilege_and_pointer_tests(self):
        plan = json.loads(self.path.read_text())
        self.assertEqual([j['id'] for j in plan['jobs']], ['core', 'media'])
        self.assertEqual(plan['env'], {'BLACKWALL_MOD': 'ALT'})
        self.assertNotIn('not-saved', self.path.read_text())
        service = (self.home / '.config/systemd/user/blackwall-first-login.service').read_text()
        self.assertIn('"' + str(self.repo), service)
        self.assertTrue((self.home / '.config/systemd/user/timers.target.wants/blackwall-first-login.timer').is_symlink())

    def test_registration_respects_explicitly_skipped_session_steps(self):
        os.environ['BLACKWALL_INSTALL_SKIPPED_STEPS'] = 'media'
        finalizer.register(self.repo)
        self.assertEqual([j['id'] for j in json.loads(self.path.read_text())['jobs']], ['core'])

    def test_registration_sorts_session_dependencies_and_rejects_cycles(self):
        source = self.repo / 'installer/data/steps.toml'
        source.write_text('''[[step]]
id="consumer"
needs_session=true
after=["dependency"]
run=["echo consumer"]
[[step]]
id="dependency"
needs_session=true
run=["echo dep"]
''')
        finalizer.register(self.repo)
        self.assertEqual([j['id'] for j in json.loads(self.path.read_text())['jobs']], ['dependency', 'consumer'])
        source.write_text(source.read_text().replace('run=["echo dep"]', 'after=["consumer"]\nrun=["echo dep"]'))
        with self.assertRaisesRegex(RuntimeError, 'Cyclic'):
            finalizer.register(self.repo)

    def test_success_exit_with_failed_postcondition_does_not_complete(self):
        plan = json.loads(self.path.read_text())
        plan['jobs'] = [dict(id='core', run=['echo core'], check='check-state')]
        finalizer.save(self.path, plan)
        os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = 'test'
        with patch.object(finalizer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[{"width":1920}]', '')), \
             patch.object(finalizer, 'execute', side_effect=lambda argv, *a, **kw: int(argv[-1] == 'check-state')), \
             patch.object(finalizer.time, 'sleep'):
            self.assertEqual(finalizer.run(), 1)
        self.assertEqual(json.loads(self.path.read_text())['state'], 'retrying')

    def test_no_session_stays_pending_and_does_no_work(self):
        with patch.object(finalizer.subprocess, 'run') as calls:
            self.assertEqual(finalizer.run(), 0)
            calls.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text())['state'], 'pending')

    def test_required_failure_retries_then_completes_without_repeating_success(self):
        os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = 'test'
        work = []
        fail = True
        def fake(argv, **kwargs):
            if argv[0] == 'hyprctl':
                return subprocess.CompletedProcess(argv, 0, '[{"width":1920}]', '')
            work.append(argv[-1])
            return subprocess.CompletedProcess(argv, 1 if fail and 'core' in argv[-1] else 0)
        with patch.object(finalizer.subprocess, 'run', side_effect=fake), patch.object(finalizer, 'execute', side_effect=lambda argv, *a: fake(argv).returncode):
            self.assertEqual(finalizer.run(), 1)
            self.assertEqual(json.loads(self.path.read_text())['state'], 'retrying')
            self.assertEqual(work, ['echo core'])
            fail = False
            self.assertEqual(finalizer.run(), 0)
            self.assertEqual(json.loads(self.path.read_text())['state'], 'complete')
            self.assertEqual(finalizer.run(), 0)
        self.assertEqual(work, ['echo core', 'echo core', 'echo media'])
        self.assertIn('core', (finalizer.state_dir() / 'session.log').read_text())

    def test_timeout_terminates_shell_and_descendant_process_group(self):
        child = unittest.mock.MagicMock()
        child.pid = 12345
        child.wait.side_effect = [subprocess.TimeoutExpired('test', 1), 0]
        process = unittest.mock.MagicMock()
        process.__enter__.return_value = child
        with patch.object(finalizer.subprocess, 'Popen', return_value=process), \
             patch.object(finalizer.os, 'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                finalizer.execute(['sh', '-c', 'sleep'], self.repo, {}, None, timeout=1)
        self.assertEqual([call.args[1] for call in kill.call_args_list], [finalizer.signal.SIGTERM, finalizer.signal.SIGKILL])

    def test_optional_failure_bounded_and_visible(self):
        os.environ['HYPRLAND_INSTANCE_SIGNATURE'] = 'test'
        def fake(argv, **kwargs):
            if argv[0] == 'hyprctl':
                return subprocess.CompletedProcess(argv, 0, '[{"width":1920}]', '')
            return subprocess.CompletedProcess(argv, int('media' in argv[-1]))
        with patch.object(finalizer.subprocess, 'run', side_effect=fake), patch.object(finalizer, 'execute', side_effect=lambda argv, *a: fake(argv).returncode):
            for _ in range(4):
                finalizer.run()
        plan = json.loads(self.path.read_text())
        self.assertEqual(plan['state'], 'complete-with-warnings')
        self.assertEqual(plan['steps']['media']['attempts'], 3)
        self.assertEqual(plan['steps']['core']['attempts'], 1)

if __name__ == '__main__':
    unittest.main()
