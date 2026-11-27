"""Tests for blackwall-clone (inventory / backup / restore / reauth).

Everything runs against a fake HOME and fixture files in tmp_path, plus the
real gpg binary with a GNUPGHOME in tmp. Restore tests pass
--skip-packages --skip-repos and drive the plan builder directly, so no test
ever calls pacman -S, sudo, or systemctl enable.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CLONE = ROOT / "scripts" / "blackwall-clone"

sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util
from importlib.machinery import SourceFileLoader

_loader = SourceFileLoader("blackwall_clone", str(CLONE))
_spec = importlib.util.spec_from_loader("blackwall_clone", _loader)
assert _spec is not None
bw = importlib.util.module_from_spec(_spec)
_loader.exec_module(bw)


def write_exe(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(0o755)


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """A HOME with a small repo tree, a local bin, and tool stubs."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # A tracked-scripts-style repo layout the inventory walks.
    for name in ("dev", ".config", "opt"):
        (home / name).mkdir()

    monkeypatch.setenv(
        "PATH",
        os.pathsep.join([str(p) for p in os.environ["PATH"].split(os.pathsep)
                         if "local/bin" not in p]),
    )
    return home


def run_clone(home: Path, *args: str, extra_env: dict | None = None,
              timeout: int = 60) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOME"] = str(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CLONE), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


# ------------------------------------------------------------ manifest tests

def test_manifest_parses_and_expands(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    entries = bw.load_manifest(ROOT / "clone" / "manifest.toml")
    assert entries, "seeded manifest is empty"
    # Every seeded entry needs a why; the manifest is public, so a reviewer
    # can tell what each path is for.
    assert all(e["why"].strip() for e in entries), [
        e["path"] for e in entries if not e["why"].strip()
    ]
    (home / ".ssh").mkdir()
    target = bw.expand_clone_path("~/.ssh", home)
    assert target == home / ".ssh"
    assert bw.expand_clone_path(
        "/etc/NetworkManager/system-connections", home).is_absolute()


def test_manifest_excludes_apply(tmp_path):
    """Exclude patterns drop cache-y subtrees from the bundle (round trip)."""
    home = tmp_path / "home"
    home.mkdir()
    claude = home / ".claude"
    (claude / "projects" / "x").mkdir(parents=True)
    (claude / "settings.json").write_text("{}")
    (claude / "cache").mkdir(parents=True)
    (claude / "cache" / "big.bin").write_text("cached")
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(textwrap.dedent("""\
        [[path]]
        path = "~/.claude"
        why = "settings"
        root = false
        exclude = ["cache"]
    """))
    env = _gpg_env(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"
    r = run_clone(home, "backup", "--to", str(bundle),
                  "--manifest", str(manifest), extra_env=env)
    assert r.returncode == 0, r.stderr + r.stdout
    new_home = tmp_path / "newhome"
    new_home.mkdir()
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (new_home / ".claude" / "settings.json").exists()
    assert not (new_home / ".claude" / "cache").exists(), \
        "excluded cache/ must not restore"


def test_reauth_seed_has_required_entries():
    entries = bw.load_reauth(ROOT / "clone" / "reauth.toml")
    names = " ".join(e["name"] for e in entries).lower()
    for required in ("browser", "github", "readb", "whatsapp", "spotify",
                     "tailscale", "claude", "codex", "tpm", "fido"):
        assert required in names, f"reauth.toml missing {required}"
    assert all(e["how"].strip() for e in entries)


# ----------------------------------------------------------- inventory tests

def test_extras_subtract_catalogue_names(tmp_path):
    """Extras = installed minus every name the installer catalogue holds."""
    catalogue = tmp_path / "packages.toml"
    catalogue.write_text(textwrap.dedent("""\
        [[group]]
        name = "core"
        required = true
        description = "fixture"
        packages = [
          { name = "fish", source = "repo", why = "fixture" },
          { name = "kitty", source = "repo", why = "fixture" },
        ]

        [[group]]
        name = "extra"
        required = false
        description = "fixture"
        packages = [
          { name = "yay-helper", source = "aur", why = "fixture" },
        ]
    """))
    known = bw.catalogue_package_names(catalogue)
    assert known == {"fish", "kitty", "yay-helper"}
    assert bw.extras(["fish", "kitty", "x11vnc", "xdotool"],
                     known) == ["x11vnc", "xdotool"]


def test_inventory_marks_symlink_into_repo_not_regular(fake_home):
    home = fake_home
    bindir = home / ".local" / "bin"
    bindir.mkdir(parents=True)
    plain = bindir / "c2a"
    plain.write_text("secret")
    plain.chmod(0o755)
    link = bindir / "repo-tool"
    link.symlink_to(ROOT / "scripts" / "blackwall-clone")
    entries = bw.collect_local_bin(home, ROOT)
    by_name = {e["name"]: e for e in entries}
    assert by_name["c2a"]["kind"] == "file"
    assert "repo-tool" not in by_name  # links into the repo are skipped


def test_inventory_repos_reports_dirty_ahead_and_empty_origin(fake_home):
    home = fake_home
    repo = home / "dev" / "proj"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email",
                    "t@t.t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name",
                    "t"], check=True)
    (repo / "f.txt").write_text("one")
    subprocess.run(["git", "-C", str(repo), "add", "."],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"],
                   check=True, capture_output=True)
    (repo / "f.txt").write_text("two")  # dirty, no origin
    found = bw.find_repos(home, ROOT)
    match = next(r for r in found if r["path"] == "dev/proj")
    assert match["dirty"] == 1
    assert match["ahead"] == 0
    assert match["origin"] == ""
    # node_modules is never descended into.
    (repo / "node_modules" / "inner" / ".git").mkdir(parents=True)
    found2 = bw.find_repos(home, ROOT)
    assert not any(r["path"].startswith("dev/proj/node_modules")
                   for r in found2)


def test_inventory_renders_parseable_toml(fake_home):
    inv = {
        "native": ["b"], "foreign": [], "system": ["s.service"],
        "user": [], "tools": {"cargo": ["just"]},
        "tool_notes": ["# cargo: boom"], "local_bin": [],
        "repos": [{"path": "dev/p", "origin": "", "branch": "main",
                   "dirty": 1, "ahead": 0}],
    }
    text = bw.render_inventory(inv)
    parsed = tomllib.loads(text)
    assert parsed["packages"]["native"] == ["b"]
    assert parsed["repos"][0]["dirty"] == 1


# -------------------------------------------------- backup -> restore tests

def _gpg_env(tmp_path: Path) -> dict:
    gnupghome = tmp_path / "gnupg"
    gnupghome.mkdir(mode=0o700)
    return {
        "BLACKWALL_CLONE_PASSPHRASE": "test",
        "GNUPGHOME": str(gnupghome),
    }


def _seed_home(home: Path) -> None:
    ssh = home / ".ssh"
    ssh.mkdir(parents=True, mode=0o700)
    (ssh / "config").write_text("Host example\n")
    (home / ".config" / "gh").mkdir(parents=True)
    (home / ".config" / "gh" / "hosts.yml").write_text("github.com\n")
    notes = home / "notes"
    notes.mkdir()
    (notes / "today.md").write_text("hello\n")


def _fixture_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(textwrap.dedent("""\
        [[path]]
        path = "~/.ssh"
        why = "ssh keys"
        root = false

        [[path]]
        path = "~/.config/gh"
        why = "gh token"
        root = false
        exclude = ["*.sock"]

        [[path]]
        path = "~/notes"
        why = "notes"
        root = false
    """))
    return manifest


def test_backup_restore_round_trip(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _seed_home(home)
    env = _gpg_env(tmp_path)
    manifest = _fixture_manifest(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"

    r = run_clone(home, "backup", "--to", str(bundle),
                  "--manifest", str(manifest), extra_env=env)
    assert r.returncode == 0, r.stderr
    assert bundle.is_file()
    # The bundle is gpg-encrypted; its members are verified by restoring.

    # Restore into a fresh home: files reappear with contents and perms.
    new_home = tmp_path / "newhome"
    new_home.mkdir()
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert (new_home / ".ssh" / "config").read_text() == "Host example\n"
    assert (new_home / "notes" / "today.md").read_text() == "hello\n"
    mode = stat.S_IMODE(os.stat(new_home / ".ssh").st_mode)
    assert mode == 0o700
    inv_text = (new_home / ".config" / "gh" / "hosts.yml").read_text()
    assert "github.com" in inv_text


def test_restore_pre_clone_backup_and_identical_skip(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _seed_home(home)
    env = _gpg_env(tmp_path)
    manifest = _fixture_manifest(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"
    assert run_clone(home, "backup", "--to", str(bundle),
                     "--manifest", str(manifest),
                     extra_env=env).returncode == 0

    new_home = tmp_path / "newhome"
    new_home.mkdir()
    # First restore populates the fresh home.
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "copied 3" in r.stdout
    # Second restore proposes nothing new: identical trees read as identical.
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already matches the bundle" in r.stdout

    # Different content: the old target moves to .pre-clone-TIMESTAMP.
    # Granularity is the manifest entry: differing ~/.ssh restores as the
    # whole directory, so the backup is `.ssh.pre-clone-*` holding config.
    (new_home / ".ssh" / "config").write_text("different\n")
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (new_home / ".ssh" / "config").read_text() == "Host example\n"
    backups = list(new_home.glob(".ssh.pre-clone-*"))
    assert len(backups) == 1
    assert (backups[0] / "config").read_text() == "different\n"

    # Identical entries are skipped, not backed up.
    other = list(new_home.glob("notes.pre-clone-*"))
    assert other == []


def test_dry_run_writes_nothing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _seed_home(home)
    manifest = _fixture_manifest(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"
    # Stub PATH: tar/du must resolve, sudo must NOT (dry-run never escalates).
    bindir = tmp_path / "nonsudo-bin"
    bindir.mkdir()
    for tool in ("tar", "du", "gpg"):
        target = bindir / tool
        target.symlink_to(__import__("shutil").which(tool))
    env = {"PATH": str(bindir) + os.pathsep + "/usr/bin:/bin",
           "HOME": str(home)}
    r = run_clone(home, "backup", "--to", str(bundle),
                  "--manifest", str(manifest), "--dry-run", extra_env=env)
    assert r.returncode == 0, r.stderr
    assert "~/.ssh" in r.stdout
    assert "missing" not in r.stdout  # all fixture paths exist
    assert not bundle.exists()
    assert "sudo" not in (r.stdout + r.stderr).lower()
    missing_manifest = _fixture_manifest(tmp_path)
    missing_manifest.write_text('[[path]]\npath = "~/.nope"\nwhy = "x"\n')
    r = run_clone(home, "backup", "--to", str(bundle),
                  "--manifest", str(missing_manifest), "--dry-run",
                  extra_env=env)
    assert "missing" in r.stdout


def test_dry_run_lists_root_entries(tmp_path):
    """Root entries are listed with a [root] flag and never need sudo."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".ssh").mkdir()
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(textwrap.dedent("""\
        [[path]]
        path = "~/.ssh"
        why = "x"
        root = false

        [[path]]
        path = "/etc/wireguard-test-blackwall-clone"
        why = "y"
        root = true
    """))
    bindir = tmp_path / "nonsudo-bin"
    bindir.mkdir()
    for tool in ("tar", "du", "gpg"):
        target = bindir / tool
        target.symlink_to(__import__("shutil").which(tool))
    env = {"PATH": str(bindir) + os.pathsep + "/usr/bin:/bin",
           "HOME": str(home)}
    r = run_clone(home, "backup", "--to", str(tmp_path / "b.tar.gpg"),
                  "--manifest", str(manifest), "--dry-run", extra_env=env)
    assert r.returncode == 0, r.stderr
    assert "[root]" in r.stdout
    assert "sudo" not in (r.stdout + r.stderr).lower()


def test_partial_removed_when_gpg_fails(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _seed_home(home)
    manifest = _fixture_manifest(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"
    env = dict(_gpg_env(tmp_path))
    env["GNUPGHOME"] = str(tmp_path / "does-not-exist")
    r = run_clone(home, "backup", "--to", str(bundle),
                  "--manifest", str(manifest), extra_env=env)
    assert r.returncode != 0
    assert not bundle.exists()
    assert not (tmp_path / (bundle.name + ".tmp-clone")).exists()


def test_backup_fails_closed_on_wrong_passphrase_and_tar_failure(tmp_path):
    """Wrong passphrase and tar errors both fail closed with no bundle."""
    home = tmp_path / "home"
    home.mkdir()
    _seed_home(home)
    manifest = _fixture_manifest(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"
    env = dict(_gpg_env(tmp_path))
    good_env = dict(env)
    env["BLACKWALL_CLONE_PASSPHRASE"] = "wrong-passphrase"
    # First make a good bundle, then confirm the wrong passphrase cannot
    # restore it (decrypt gate refuses), and leaves the home untouched.
    assert run_clone(home, "backup", "--to", str(bundle),
                     "--manifest", str(manifest),
                     extra_env=good_env).returncode == 0
    # Re-point the backup env at the right passphrase for the tar-fail leg.
    env["BLACKWALL_CLONE_PASSPHRASE"] = "test"
    new_home = tmp_path / "newhome"
    new_home.mkdir()
    env2 = dict(env)
    env2["BLACKWALL_CLONE_PASSPHRASE"] = "wrong-passphrase"
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env2)
    assert r.returncode != 0
    assert "integrity" in (r.stdout + r.stderr).lower()
    assert list(new_home.iterdir()) == []
    # A tar failure also removes the partial output.
    env3 = dict(env)
    env3["BLACKWALL_CLONE_FORCE_TAR_FAIL"] = "1"
    fail_bundle = tmp_path / "fail.tar.gpg"
    r = run_clone(home, "backup", "--to", str(fail_bundle),
                  "--manifest", str(manifest), extra_env=env3)
    assert r.returncode != 0
    assert not fail_bundle.exists()
    assert not (tmp_path / (fail_bundle.name + ".tmp-clone")).exists()


def test_manifest_exclude_keeps_sock_out(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    gh = home / ".config" / "gh"
    gh.mkdir(parents=True)
    (gh / "hosts.yml").write_text("ok\n")
    (gh / "agent.sock").write_text("sock\n")
    env = _gpg_env(tmp_path)
    manifest = _fixture_manifest(tmp_path)
    bundle = tmp_path / "clone.tar.gpg"
    assert run_clone(home, "backup", "--to", str(bundle),
                     "--manifest", str(manifest),
                     extra_env=env).returncode == 0
    new_home = tmp_path / "newhome"
    new_home.mkdir()
    r = run_clone(new_home, "restore", str(bundle), "--yes",
                  "--skip-packages", "--skip-repos", extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (new_home / ".config" / "gh" / "hosts.yml").exists()
    assert not (new_home / ".config" / "gh" / "agent.sock").exists()


# ------------------------------------------------------------- plan builder

def _craft_evil_bundle(*, gnupghome: Path, passphrase: str,
                      out: Path) -> None:
    """Build a hostile tar (dotdot member, absolute member, escaping link)
    with python tarfile — GNU tar would sanitise these on extract — encrypt
    it with gpg, and hand back a bundle restore must refuse member by member.
    """
    import io
    import tarfile
    src = out.parent / "evilsrc"
    (src / "sub").mkdir(parents=True)
    (src / "good.txt").write_text("ok\n")
    os.symlink("/etc/passwd", src / "esc-link")
    tar_path = out.parent / "evil.tar"
    # Members live under the ~/.ssh entry prefix: GNU tar strips the
    # hostile parts on extract (the dotdot member is refused outright, the
    # absolute member loses its leading /), and pairing + copy must still
    # refuse every escape — while the good file restores.
    with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as tar:
        tar.add(str(src / "good.txt"), arcname=".ssh/good.txt")
        data = b"evil\n"
        dotdot = tarfile.TarInfo(".ssh/a/../evil")
        dotdot.size = len(data)
        tar.addfile(dotdot, io.BytesIO(data))
        absolute = tarfile.TarInfo("/abs-evil")
        absolute.size = len(data)
        tar.addfile(absolute, io.BytesIO(data))
        tar.add(str(src / "esc-link"), arcname=".ssh/esc-link")
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, passphrase.encode())
    finally:
        os.close(write_fd)
    env = {"PATH": os.environ["PATH"], "GNUPGHOME": str(gnupghome)}
    proc = subprocess.run(
        ["gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
         "--passphrase-fd", str(read_fd), "--symmetric",
         "--cipher-algo", "AES256", "-o", str(out), str(tar_path)],
        capture_output=True, timeout=120, pass_fds=(read_fd,), env=env,
    )
    os.close(read_fd)
    assert proc.returncode == 0, proc.stderr.decode()[:500]


def test_reject_dotdot_member(tmp_path):
    """A hostile tar's `a/../evil`, absolute member and escaping symlink all
    fail closed: decrypt+extract, then pairing skips each with a warning and
    restores nothing outside the manifest."""
    home = tmp_path / "home"
    home.mkdir()
    entries = [{"path": "~/.ssh", "why": "x", "root_path": home / ".ssh",
                "root": False, "exclude": []}]
    gnupghome = tmp_path / "gnupg"
    gnupghome.mkdir(mode=0o700)
    bundle = tmp_path / "evil.tar.gpg"
    _craft_evil_bundle(gnupghome=gnupghome, passphrase="test", out=bundle)
    stage = tmp_path / "stage"
    stage.mkdir()
    rc, _gpg_err, _tar_err, status = bw.decrypt_bundle(
        bundle, stage, "test")
    # GNU tar refuses the dotdot member (exit 2) AFTER extracting the good
    # members — the decrypt itself is intact (DECRYPTION_OKAY + GOODMDC),
    # which is exactly the split the restore path must handle: trusted
    # bytes, hostile names.
    assert bw.gpg_decrypt_ok(status) is True, _gpg_err + _tar_err
    _ = rc
    pairs, warnings = bw.pairs_from_bundle(stage, entries, home)
    joined = "\n".join(warnings)
    # The sanitised absolute member matches no entry; the dotdot member is
    # refused by tar itself (see tar_err below).
    assert any("abs-evil" in w and "no manifest entry" in w
               for w in warnings), warnings
    assert "evil" in joined and "abs-evil" in joined
    assert "Member name contains '..'" in _tar_err
    # The escaping nested link is refused at copy time, not pair time.
    assert [s.name for s, _, _, _ in pairs] == [".ssh"]
    failures: list[str] = []
    dest = home / ".ssh"
    dest.mkdir(parents=True)
    assert bw._copy_staged_tree(stage / ".ssh", dest, home / ".ssh",
                                False, failures, None) is False
    assert (dest / "good.txt").read_text() == "ok\n"
    assert not (dest / "esc-link").exists()
    assert any("esc-link" in f and "escapes" in f for f in failures)
    # ...and nothing outside the entry root is ever restored.
    assert all(str(d).startswith(str(home / ".ssh")) for _, d, _, _ in pairs)
    # Unit-level: the raw member names are unsafe on their face.
    assert bw._safe_member_parts("a/../evil") is None
    assert bw._safe_member_parts("/abs-evil") is None
    assert bw._safe_member_parts("..") is None


def test_reject_absolute_member():
    assert bw._safe_member_parts("/etc/passwd") is None
    assert bw._safe_member_parts("") is None


def test_unknown_member_skipped_with_warning(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    entries = [{"path": "~/.ssh", "why": "x",
                "root": False, "exclude": []}]
    tmp = tmp_path / "stage"
    (tmp / ".ssh").mkdir(parents=True)
    (tmp / "evil").write_text("nope")
    pairs, warnings = bw.pairs_from_bundle(tmp, entries, home)
    assert [s.name for s, _, _, _ in pairs] == [".ssh"]
    assert any("evil" in w and "no manifest entry" in w for w in warnings)


def test_symlink_escaping_home_rejected(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    entries = [{"path": "~/.ssh", "why": "x",
                "root": False, "exclude": []}]
    tmp = tmp_path / "stage"
    (tmp / ".ssh").mkdir(parents=True)
    (tmp / ".ssh" / "link-out").symlink_to("/etc/passwd")
    (tmp / ".ssh" / "link-ok").symlink_to("config")
    (tmp / ".ssh" / "config").write_text("a")
    (tmp / ".ssh" / "link-up").symlink_to("../../../../etc/passwd")
    pairs, warnings = bw.pairs_from_bundle(tmp, entries, home)
    # Top-level mapping keeps the tree; nested escapees are refused at copy
    # time by _copy_staged_tree, which the round-trip tests exercise.
    assert [s.name for s, _, _, _ in pairs] == [".ssh"]
    # Copy the staged tree into its real deploy parent (home / ".ssh")
    # and check the escapees never land.
    dest = home / ".ssh"
    dest.mkdir(parents=True)
    failures: list[str] = []
    assert bw._copy_staged_tree(tmp / ".ssh", dest, home / ".ssh",
                                False, failures) is False
    assert (dest / "config").exists()
    assert (dest / "link-ok").is_symlink()
    assert not (dest / "link-out").exists() and not (dest / "link-up").exists()
    assert any("link-out" in f and "escapes" in f for f in failures)
    assert any("link-up" in f and "escapes" in f for f in failures)


def test_repo_origin_must_be_url_and_target_inside_home(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    def plan_for(path, origin):
        return {"repos_clone": [{"path": path, "origin": origin}],
                "repos_no_origin": []}

    failures: list[str] = []
    bw.apply_repos(
        plan_for("dev/a", "-u malicious"), False, home, failures)
    assert any("unsafe origin" in f for f in failures)
    failures.clear()
    bw.apply_repos(
        plan_for("dev/b", "ext:sh -c evil"), False, home, failures)
    assert any("unsafe origin" in f for f in failures)
    failures.clear()
    bw.apply_repos(
        plan_for("../escape", "https://example.com/a.git"),
        False, home, failures)
    assert any("escapes" in f or "outside" in f for f in failures)


def test_gpg_status_gate():
    good = ("[GNUPG:] BEGIN_DECRYPTION\n"
            "[GNUPG:] DECRYPTION_INFO 2 9 0\n"
            "[GNUPG:] DECRYPTION_OKAY\n"
            "[GNUPG:] GOODMDC\n")
    assert bw.gpg_decrypt_ok(good) is True
    bad_pass = ("[GNUPG:] BEGIN_DECRYPTION\n"
                "[GNUPG:] ERROR symkey_decrypt.maybe_error 11\n"
                "[GNUPG:] DECRYPTION_FAILED\n"
                "[GNUPG:] FAILURE gpg-exit 33554433\n")
    assert bw.gpg_decrypt_ok(bad_pass) is False
    truncated = ("[GNUPG:] BEGIN_DECRYPTION\n"
                 "[GNUPG:] NODATA 2\n"
                 "[GNUPG:] DECRYPTION_FAILED\n")
    assert bw.gpg_decrypt_ok(truncated) is False
    assert bw.gpg_decrypt_ok("") is False


def test_plan_builder_only_counts_missing():
    inv = {
        "native": ["keep", "add-native"],
        "foreign": ["add-foreign"],
        "system": ["have.service", "want.service", "gone.service"],
        "user": ["u.service"],
        "tools": {"cargo": ["have-crate", "want-crate"],
                  "npm": [], "bun": ["x"], "pipx": [], "uv": []},
        "local_bin": [],
        "repos": [
            {"path": "dev/a", "origin": "https://example.com/a.git",
             "branch": "main", "dirty": 0, "ahead": 0},
            {"path": "dev/b", "origin": "", "branch": "main",
             "dirty": 1, "ahead": 0},
            {"path": "dev/c", "origin": "https://example.com/c.git",
             "branch": "main", "dirty": 0, "ahead": 0},
        ],
    }
    home = Path("/tmp/fake-home-plan")
    ctx = {
        "home": home,
        "file_ops": [],
        "installed_pkgs": {"keep", "yay-helper"},
        "aur_helper": "yay",
        "svc_enabled_sys": {"have.service"},
        "svc_existing_sys": {"have.service", "want.service"},
        "svc_enabled_user": set(),
        "svc_existing_user": {"u.service"},
        "tools_present": {"cargo": {"have-crate"}, "npm": set(),
                          "pipx": set(), "uv": set()},
        "tools_have": {"cargo": True, "npm": True, "bun": True,
                       "pipx": False, "uv": False},
    }
    plan = bw.build_restore_plan(inv, ctx)
    assert plan["pkgs_native"] == ["add-native"]
    assert plan["pkgs_foreign"] == ["add-foreign"]
    assert plan["sys_enable"] == ["want.service"]
    assert plan["sys_missing"] == ["gone.service"]
    assert plan["user_enable"] == ["u.service"]
    assert plan["tools_plan"] == {"cargo": ["want-crate"]}
    assert [r["path"] for r in plan["repos_clone"]] == ["dev/a", "dev/c"]
    assert plan["repos_no_origin"] == ["dev/b"]
    assert plan["repos_exist"] == []


def test_reauth_runs():
    r = subprocess.run([sys.executable, str(CLONE), "reauth"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert "whatsapp" in r.stdout.lower()
