"""Run the doorway only in copied repos with fake package/root commands."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='blackwall-bootstrap-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'clone with spaces'
        self.root.mkdir()
        shutil.copy2(ROOT / 'install', self.root / 'install')
        self.bin = Path(self.tmp.name) / 'bin'
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / 'calls'
        self.env = dict(os.environ, PATH=f'{self.bin}:/usr/bin:/bin', CALLS=str(self.log))
        self.fake('git', 'exit 0')
        self.fake('sudo', 'echo sudo >> "$CALLS"; exit 99')
        self.fake('cargo', 'echo cargo >> "$CALLS"; exit 99')

    def fake(self, name, body):
        f = self.bin / name
        f.write_text('#!/bin/sh\n' + body + '\n')
        f.chmod(0o755)

    def run_install(self, *args):
        return subprocess.run(['bash', str(self.root / 'install'), *args], env=self.env,
                              text=True, capture_output=True, timeout=10)

    def test_help_needs_no_build_root_or_git(self):
        self.fake('git', 'exit 99')
        result = self.run_install('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('reboot', result.stdout)
        self.assertFalse(self.log.exists())

    def test_missing_binary_preview_never_bootstraps(self):
        result = self.run_install('--dry-run', '--apply')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('no changes made', result.stderr)
        self.assertFalse(self.log.exists())

    def test_existing_binary_preview_preserves_arguments_and_status(self):
        binary = self.root / 'installer/target/release/blackwall-install'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nprintf "%s\\n" "$BLACKWALL_ROOT" "$@"\nexit 7\n')
        binary.chmod(0o755)
        result = self.run_install('--dry-run', '--apply')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout.splitlines(), [str(self.root), '--dry-run', '--apply'])
        self.assertFalse(self.log.exists())

    def test_stale_preview_binary_is_not_executed(self):
        binary = self.root / 'installer/target/release/blackwall-install'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\necho unsafe >> "$CALLS"\n')
        binary.chmod(0o755)
        source = self.root / 'installer/src/main.rs'
        source.parent.mkdir(parents=True)
        source.write_text('// newer safe source')
        os.utime(binary, (1, 1))
        result = self.run_install('--dry-run', '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertIn('older than its source', result.stderr)
        self.assertFalse(self.log.exists())

    def test_restore_cannot_bypass_preview_guarantee(self):
        binary = self.root / 'installer/target/release/blackwall-install'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\necho unsafe >> "$CALLS"\n')
        binary.chmod(0o755)
        for flag in ('--dry-run', '--snapshot'):
            result = self.run_install(flag, '--restore', 'backup')
            self.assertEqual(result.returncode, 1)
            self.assertIn('cannot combine', result.stderr)
            self.assertFalse(self.log.exists())

    def test_archive_rejected_before_sudo(self):
        self.fake('git', 'exit 128')
        result = self.run_install('--apply')
        self.assertEqual(result.returncode, 1)
        self.assertIn('not a Git clone', result.stderr)
        self.assertFalse(self.log.exists())


class RepoLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader('repo_link', str(ROOT / 'scripts/blackwall-repo-link'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.module = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.module)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='blackwall-repo-link-test-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.repo = Path(self.tmp.name) / 'arbitrary clone'
        (self.repo / 'installer/data').mkdir(parents=True)
        (self.repo / 'hypr/lua').mkdir(parents=True)
        self.target = self.home / '.config/.dotfiles/blackwall'

    def test_preview_never_creates_alias_then_install_is_idempotent(self):
        self.assertFalse(self.module.ensure_repo_link(self.repo, self.home, True))
        self.assertFalse(self.home.exists())
        self.assertTrue(self.module.ensure_repo_link(self.repo, self.home))
        self.assertEqual(self.target.resolve(), self.repo)
        self.assertTrue(self.module.ensure_repo_link(self.repo, self.home, True))
        self.assertTrue(self.module.ensure_repo_link(self.repo, self.home))

    def test_existing_checkout_preserved(self):
        self.target.mkdir(parents=True)
        marker = self.target / 'mine'
        marker.write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'another checkout'):
            self.module.ensure_repo_link(self.repo, self.home)
        self.assertEqual(marker.read_text(), 'preserve')

    def test_dangling_other_alias_preserved(self):
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(self.home / 'gone')
        with self.assertRaises(ValueError):
            self.module.ensure_repo_link(self.repo, self.home)
        self.assertEqual(os.readlink(self.target), str(self.home / 'gone'))


if __name__ == '__main__':
    unittest.main()
