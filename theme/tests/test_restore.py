"""Tests for scripts/blackwall-restore, the one-command server rebuild.

The script wipes disks and reinstalls an OS, so none of it may run for real
here. Every external command is replaced by a stub on PATH that appends
"name args" to a log; the tests then assert WHICH commands ran and in WHAT
ORDER. The two things that must never happen are partitioning in --in-place
or --dry-run, and touching a disk that is mounted or booted from.

BLACKWALL_RESTORE_TEST=1 is the script's own seam: no root check, no
block-device check. BLACKWALL_RESTORE_PREFIX / _MNT point its files at tmp dirs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "blackwall-restore"

# Anything that changes a disk or lays down a new system.
DESTRUCTIVE = (
    "sgdisk", "parted", "fdisk", "wipefs", "mkfs.", "mkswap", "pacstrap",
    "genfstab", "grub-install", "partprobe", "dd ",
)

STUBBED = (
    "pacman", "systemctl", "restic", "ssh-keyscan", "useradd", "runuser",
    "chown", "chmod", "sgdisk", "partprobe", "udevadm", "mkfs.vfat",
    "mkfs.ext4", "mount", "umount", "pacstrap", "genfstab", "arch-chroot",
    "curl", "sync", "grub-install",
)

GENERIC = '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "$STUB_LOG"\nexit 0\n'

SPECIAL = {
    "restic": """#!/usr/bin/env bash
echo "restic $*" >> "$STUB_LOG"
if [[ " $* " == *" snapshots "* && " $* " == *" --json "* ]]; then
    echo '[{"short_id":"aaaa1111"},{"short_id":"bbbb2222"}]'
elif [[ " $* " == *" cat config "* ]]; then
    echo '{"version":2,"id":"bbbb2222"}'
fi
exit 0
""",
    "pacman": """#!/usr/bin/env bash
echo "pacman $*" >> "$STUB_LOG"
[[ $1 == -Qi ]] && exit 1
exit 0
""",
    "ssh-keyscan": """#!/usr/bin/env bash
echo "ssh-keyscan $*" >> "$STUB_LOG"
echo "host.example ssh-ed25519 AAAAfakehostkey"
""",
    "ssh-keygen": """#!/usr/bin/env bash
[[ $1 == -F ]] && exit 1
echo "256 SHA256:fakefingerprint host.example (ED25519)"
""",
    "id": """#!/usr/bin/env bash
[[ ${1:-} == scriptkid ]] && exit 1
exec /usr/bin/id "$@"
""",
    "lsblk": """#!/usr/bin/env bash
case "$*" in
    *TYPE*) echo "${STUB_LSBLK_TYPE-disk}" ;;
    *MOUNTPOINTS*) echo "${STUB_MOUNTS:-}" ;;
    *PKNAME*) echo "${STUB_PKNAME:-}" ;;
esac
""",
    "findmnt": """#!/usr/bin/env bash
[[ ${@: -1} == / ]] && echo "${STUB_ROOT_SRC:-}"
exit 0
""",
    "genfstab": """#!/usr/bin/env bash
echo "genfstab $*" >> "$STUB_LOG"
echo "UUID=0000-1111 / ext4 rw,relatime 0 1"
""",
}


@pytest.fixture
def box(tmp_path: Path):
    """A sandbox: stub commands, fake prefix and mnt, fake apply and rice."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name in STUBBED:
        (stubs / name).write_text(SPECIAL.get(name, GENERIC))
    for name in ("ssh-keygen", "id", "lsblk", "findmnt"):
        (stubs / name).write_text(SPECIAL[name])
    # pacstrap must leave a locale.gen behind, like the real thing.
    (stubs / "pacstrap").write_text(
        '#!/usr/bin/env bash\necho "pacstrap $*" >> "$STUB_LOG"\n'
        'mkdir -p "$2/etc"; echo "#en_US.UTF-8 UTF-8" > "$2/etc/locale.gen"\n'
    )
    for p in stubs.iterdir():
        p.chmod(0o755)

    log = tmp_path / "calls.log"
    log.write_text("")
    apply_ = tmp_path / "apply"
    apply_.write_text('#!/usr/bin/env bash\necho "server/apply" >> "$STUB_LOG"\n')
    apply_.chmod(0o755)
    rice = tmp_path / "rice"
    rice.mkdir()
    inst = rice / "install"
    inst.write_text('#!/usr/bin/env bash\n[[ ${1:-} == --help ]] && echo "  --profile NAME"\nexit 0\n')
    inst.chmod(0o755)
    pw = tmp_path / "pw"
    pw.write_text("correct horse battery\n")
    pw.chmod(0o600)

    env = {
        "PATH": f"{stubs}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "STUB_LOG": str(log),
        "BLACKWALL_RESTORE_TEST": "1",
        "BLACKWALL_RESTORE_PREFIX": str(tmp_path / "prefix"),
        "BLACKWALL_RESTORE_MNT": str(tmp_path / "mnt"),
        "BLACKWALL_APPLY": str(apply_),
        "BLACKWALL_RICE_DIR": str(rice),
        "BLACKWALL_STORAGEBOX_USER": "u123456",
        "BLACKWALL_RESTIC_PASSWORD_FILE": str(pw),
        # The fingerprint the ssh-keygen stub prints. Interactive tests
        # override it with "" to take the confirm-every-time path.
        "BLACKWALL_STORAGEBOX_FPR": "fakefingerprint",
    }

    class Box:
        path = tmp_path
        prefix = tmp_path / "prefix"
        mnt = tmp_path / "mnt"
        pwfile = pw
        install = inst

        @staticmethod
        def run(*args, stdin="", **extra):
            e = {**env, **extra}
            return subprocess.run(
                ["bash", str(SCRIPT), *args], env=e, input=stdin,
                capture_output=True, text=True, timeout=60,
            )

        @staticmethod
        def calls() -> list[str]:
            return [ln for ln in log.read_text().splitlines() if ln]

    return Box


def first(calls: list[str], *needles: str) -> int:
    for i, line in enumerate(calls):
        if all(n in line for n in needles):
            return i
    raise AssertionError(f"no call containing {needles}; calls were:\n" + "\n".join(calls))


def assert_order(calls: list[str], *steps: tuple[str, ...]) -> None:
    idx = [first(calls, *s) for s in steps]
    assert idx == sorted(idx) and len(set(idx)) == len(idx), (
        f"wrong order {list(zip(steps, idx))}\n" + "\n".join(calls)
    )


def destructive(calls: list[str]) -> list[str]:
    return [c for c in calls if any(c.startswith(d) for d in DESTRUCTIVE)]


# ------------------------------------------------------------------ static

def test_bash_syntax():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_shellcheck_clean():
    if not shutil.which("shellcheck"):
        pytest.skip("shellcheck not installed")
    r = subprocess.run(
        ["shellcheck", "-x", "-S", "warning", str(SCRIPT)], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout


def test_script_carries_no_secrets():
    text = SCRIPT.read_text()
    assert "sshpass" not in text
    assert "BEGIN" not in text or "PRIVATE KEY" not in text


# ------------------------------------------------------------------ dry run

def test_dry_run_in_place_runs_nothing(box):
    r = box.run("--in-place", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert box.calls() == [], "dry-run must not execute any external command"
    assert "[dry-run]" in r.stdout
    assert not (box.prefix / "etc" / "blackwall").exists(), "dry-run wrote files"


def test_dry_run_rescue_never_partitions(box):
    r = box.run("--from-rescue", "/dev/vdz", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert destructive(box.calls()) == []
    assert {c.split()[0] for c in box.calls()} <= {"lsblk", "findmnt"}


def test_dry_run_rescue_plan_is_in_order(box):
    out = box.run("--from-rescue", "/dev/vdz", "--dry-run").stdout
    needles = [
        "sgdisk --zap-all /dev/vdz",
        "mkfs.vfat",
        "mkfs.ext4",
        "mount /dev/vdz3",
        "pacstrap -K",
        "genfstab -U",
        "mkinitcpio -P",
        "grub-install --target=i386-pc /dev/vdz",
        "grub-install --target=x86_64-efi --efi-directory=/boot/efi --removable",
        "blackwall-restore-firstboot.service",
        "umount -R",
        "systemctl reboot",
    ]
    pos = [out.index(n) for n in needles]
    assert pos == sorted(pos), list(zip(needles, pos))


def test_nvme_partition_names(box):
    out = box.run("--from-rescue", "/dev/nvme0n1", "--dry-run").stdout
    assert "mkfs.ext4 -F -L blackwall-root /dev/nvme0n1p3" in out


# ------------------------------------------------------------------ in-place, for real (stubbed)

def test_in_place_restore_order(box):
    r = box.run("--in-place", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    calls = box.calls()
    assert destructive(calls) == [], "--in-place must never partition or reinstall"
    assert_order(
        calls,
        ("pacman", "restic", "openssh"),
        ("useradd", "scriptkid"),
        ("ssh-keyscan", "-p 23"),
        ("restic", "snapshots"),
        ("restic", "cat config"),
        ("restore bbbb2222", "--include /etc/ssh/ssh_host_ed25519_key"),
        ("restore bbbb2222", "--include /root/.ssh"),
        ("restore bbbb2222", "--include /var/lib/tailscale"),
        ("restore bbbb2222", "--include /etc/wireguard"),
        ("restore bbbb2222", "--include /home/scriptkid"),
        ("systemctl stop", "docker"),
        ("restore bbbb2222", "--include /var/lib/docker/volumes"),
        ("systemctl restart", "docker.service"),
        ("restore bbbb2222", "--include /etc/cloudflared"),
        ("chown", "1000:1000", "/home/scriptkid"),
        ("server/apply",),
        ("runuser", "-u scriptkid", "--profile server --apply --yes"),
        ("systemctl reboot",),
    )
    assert any("--overwrite if-changed" in c for c in calls), "restore must be idempotent"


def test_in_place_writes_env_and_private_password_file(box):
    box.run("--in-place", "--yes", "--no-reboot")
    env = (box.prefix / "etc/blackwall/backup.env").read_text().splitlines()
    assert "RESTIC_REPOSITORY=sftp:u123456@u123456.your-storagebox.de:/blackwall" in env
    assert "RESTIC_PASSWORD_FILE=/etc/blackwall/restic-password" in env
    assert "STORAGEBOX_HOST=u123456.your-storagebox.de" in env
    assert "STORAGEBOX_USER=u123456" in env
    pw = box.prefix / "etc/blackwall/restic-password"
    assert pw.read_text() == "correct horse battery"
    assert (pw.stat().st_mode & 0o777) == 0o600
    assert ((box.prefix / "etc/blackwall/backup.env").stat().st_mode & 0o777) == 0o600
    assert (box.prefix / "etc/blackwall/storagebox_known_hosts").is_file()
    assert "blackwall-restore start" in (box.prefix / "var/log/blackwall-restore.log").read_text()


def test_snapshot_flag_overrides_latest(box):
    box.run("--in-place", "--yes", "--no-reboot", "--snapshot", "deadbeef")
    calls = box.calls()
    assert any("restore deadbeef" in c for c in calls)
    assert not any("restore bbbb2222" in c for c in calls)


def test_no_reboot_flag(box):
    r = box.run("--in-place", "--yes", "--no-reboot")
    assert r.returncode == 0, r.stderr
    assert not any("systemctl reboot" in c for c in box.calls())


def test_fingerprint_is_shown_before_trust(box):
    r = box.run("--in-place", "--no-reboot", stdin="n\n", BLACKWALL_STORAGEBOX_FPR="")
    assert r.returncode != 0
    assert "SHA256:fakefingerprint" in r.stdout
    assert not any("restore" in c for c in box.calls() if c.startswith("restic"))
    assert not (box.prefix / "etc/blackwall/storagebox_known_hosts").exists()


def test_missing_apply_fails_loudly(box):
    r = box.run("--in-place", "--yes", "--no-reboot", BLACKWALL_APPLY=str(box.path / "nope"))
    assert r.returncode != 0
    assert "missing or not executable" in r.stdout + r.stderr
    assert not any(c.startswith("runuser") for c in box.calls())


def test_missing_server_profile_fails_loudly(box):
    box.install.write_text("#!/usr/bin/env bash\necho usage\n")
    r = box.run("--in-place", "--yes", "--no-reboot")
    assert r.returncode != 0
    assert "no --profile option" in r.stdout + r.stderr
    assert not any(c.startswith("runuser") for c in box.calls())


# ------------------------------------------------------------------ rescue, for real (stubbed)

def test_rescue_order_and_initramfs(box):
    r = box.run("--from-rescue", "/dev/vdz", "--yes", "--no-reboot")
    assert r.returncode == 0, r.stdout + r.stderr
    assert_order(
        box.calls(),
        ("sgdisk", "--zap-all"),
        ("sgdisk", "-t 1:ef02"),
        ("sgdisk", "-t 2:ef00"),
        ("mkfs.vfat",),
        ("mkfs.ext4",),
        ("mount", "/dev/vdz3"),
        ("pacstrap",),
        ("genfstab",),
        ("mkinitcpio -P",),
        ("grub-install", "i386-pc"),
        ("grub-install", "x86_64-efi", "--removable"),
        ("systemctl enable", "blackwall-restore-firstboot.service"),
        ("umount -R",),
    )
    conf = (box.mnt / "etc/mkinitcpio.conf.d/blackwall.conf").read_text()
    assert "autodetect" not in conf.replace("# No autodetect", "")
    for mod in ("virtio_blk", "virtio_pci", "virtio_net", "nvme", "ena", "xen-blkfront", "xen-netfront"):
        assert mod in conf
    assert "DHCP=yes" in (box.mnt / "etc/systemd/network/99-blackwall-bootstrap.network").read_text()
    unit = (box.mnt / "etc/systemd/system/blackwall-restore-firstboot.service").read_text()
    assert "blackwall-restore --in-place --yes" in unit
    assert "growpart" in (box.mnt / "usr/local/sbin/blackwall-growroot").read_text()
    assert ((box.mnt / "etc/blackwall/restic-password").stat().st_mode & 0o777) == 0o600
    assert (box.mnt / "var/lib/blackwall/restore-pending").exists()


def test_rescue_requires_typing_the_disk_name(box):
    r = box.run("--from-rescue", "/dev/vdz", "--no-reboot", stdin="wrong\n",
                BLACKWALL_STORAGEBOX_FPR="fakefingerprint")
    assert r.returncode != 0
    assert "did not match" in r.stdout + r.stderr
    assert destructive(box.calls()) == []


def test_rescue_accepts_the_typed_disk_name(box):
    r = box.run("--from-rescue", "/dev/vdz", "--no-reboot", stdin="vdz\n",
                BLACKWALL_STORAGEBOX_FPR="fakefingerprint")
    assert r.returncode == 0, r.stdout + r.stderr
    assert any(c.startswith("sgdisk") for c in box.calls())


@pytest.mark.parametrize("flags", [[], ["--dry-run"]])
def test_rescue_refuses_a_disk_with_mounted_partitions(box, flags):
    r = box.run("--from-rescue", "/dev/vdz", "--yes", *flags, STUB_MOUNTS="/mnt/data")
    assert r.returncode != 0
    assert "mounted partitions" in r.stdout + r.stderr
    assert destructive(box.calls()) == []


def test_rescue_refuses_the_disk_it_booted_from(box):
    r = box.run(
        "--from-rescue", "/dev/vda", "--yes",
        STUB_ROOT_SRC="/dev/vda2", STUB_PKNAME="vda",
    )
    assert r.returncode != 0
    assert "booted from" in r.stdout + r.stderr
    assert destructive(box.calls()) == []


def test_rescue_refuses_a_partition(box):
    r = box.run("--from-rescue", "/dev/vda1", "--yes", STUB_LSBLK_TYPE="part")
    assert r.returncode != 0
    assert "not a whole disk" in r.stdout + r.stderr
    assert destructive(box.calls()) == []


def test_rescue_checks_repo_before_wiping(box):
    # --from-rescue must prove the backup is readable BEFORE asking for the
    # wipe: snapshots + cat config run while the disk is still untouched, and
    # the confirm prompt comes after them. Here the fingerprint matches the
    # pin, so the run reaches pick_snapshot and then stops at the wipe
    # confirm — which is still before any partition command.
    r = box.run("--from-rescue", "/dev/vdz", "--no-reboot", stdin="wrong\n")
    assert r.returncode != 0
    assert "did not match" in r.stdout + r.stderr
    out = r.stdout + r.stderr
    assert out.index("Snapshot") < out.index("ALL DATA ON")
    calls = box.calls()
    assert any("snapshots" in c for c in calls if c.startswith("restic"))
    assert any("cat config" in c for c in calls if c.startswith("restic"))
    assert destructive(calls) == []


def test_rescue_writes_nothing_before_confirm(box):
    r = box.run("--from-rescue", "/dev/vdz", "--no-reboot", stdin="wrong\n",
                BLACKWALL_STORAGEBOX_FPR="fakefingerprint")
    assert r.returncode != 0
    assert "did not match" in r.stdout + r.stderr
    conf = box.prefix / "etc/blackwall"
    assert not conf.exists() or list(conf.iterdir()) == []
    assert not (box.mnt / "etc/mkinitcpio.conf.d/blackwall.conf").exists()


def test_yes_without_fingerprint_refuses_host_key(box):
    r = box.run("--in-place", "--no-reboot", "--yes", BLACKWALL_STORAGEBOX_FPR="")
    assert r.returncode != 0
    assert "NEVER" in r.stdout or "never trusted blindly" in r.stdout + r.stderr
    assert not (box.prefix / "etc/blackwall/storagebox_known_hosts").exists()
    assert not any("restore" in c for c in box.calls() if c.startswith("restic"))


def test_yes_with_pinned_fingerprint_trusts_silently(box):
    r = box.run("--in-place", "--no-reboot", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (box.prefix / "etc/blackwall/storagebox_known_hosts").is_file()
    assert "fingerprint matches BLACKWALL_STORAGEBOX_FPR" in r.stdout


def test_ssh_host_keys_are_enumerated_not_globbed(box):
    r = box.run("--in-place", "--yes", "--no-reboot")
    assert r.returncode == 0, r.stdout + r.stderr
    restores = [c for c in box.calls() if "ssh_host" in c]
    assert restores, "no ssh host key restore ran"
    assert not any("ssh_host_*" in c for c in restores)
    for key in ("ssh_host_ed25519_key", "ssh_host_ecdsa_key", "ssh_host_rsa_key"):
        assert any(key in c for c in restores), f"{key} not restored"
        assert any(f"chmod 0600 {key}" in c or f"chmod 0600 /etc/ssh/{key} " in c
                   or c.endswith(f"/etc/ssh/{key}") for c in box.calls()), f"{key} chmod missing"


def test_docker_restarts_after_volume_restore(box):
    r = box.run("--in-place", "--yes", "--no-reboot")
    assert r.returncode == 0, r.stdout + r.stderr
    calls = box.calls()
    stop = first(calls, "systemctl stop", "docker")
    vol = first(calls, "restore", "/var/lib/docker/volumes")
    start = first(calls, "systemctl restart", "docker.service")
    assert stop < vol < start


def test_growpart_rc_captured_in_if(box):
    r = box.run("--from-rescue", "/dev/vdz", "--yes", "--no-reboot")
    assert r.returncode == 0, r.stdout + r.stderr
    grow = (box.mnt / "usr/local/sbin/blackwall-growroot").read_text()
    assert 'if growpart "$disk" "$num"; then rc=0; else rc=$?; fi' in grow
    assert "|| [ $? -eq 1 ]" not in grow


def test_rice_url_whitelist(box):
    r = box.run("--in-place", "--yes", "--no-reboot",
                BLACKWALL_RICE_DIR=str(box.path / "missing-rice"),
                BLACKWALL_RICE_URL="https://evil.example/rice.git")
    assert r.returncode != 0
    assert "refusing to clone" in r.stdout + r.stderr
    assert not any(c.startswith("runuser") and "git clone" in c for c in box.calls())


def test_chmod_failure_is_fatal(box):
    r = box.run("--in-place", "--yes", "--no-reboot",
                PATH=f"{box.path}/stubs:/usr/bin:/bin")
    assert r.returncode == 0  # sanity: baseline passes before we poison chmod
    (box.path / "calls.log").write_text("")
    poison = box.path / "stubs" / "chmod"
    poison.write_text('#!/usr/bin/env bash\necho "chmod $*" >> "$STUB_LOG"\nexit 1\n')
    r = box.run("--in-place", "--yes", "--no-reboot")
    assert r.returncode != 0
    assert "chmod" in (r.stdout + r.stderr).lower()
    calls = box.calls()
    assert not any(c.startswith("server/apply") for c in calls)
    assert not any(c.startswith("runuser") for c in calls)


# ------------------------------------------------------------------ arguments

def test_a_mode_is_required():
    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode != 0
    assert "--from-rescue" in r.stdout + r.stderr and "--in-place" in r.stdout + r.stderr


def test_bad_storagebox_user_is_rejected(box):
    r = box.run("--in-place", "--yes", BLACKWALL_STORAGEBOX_USER="u1; rm -rf /")
    assert r.returncode != 0
    assert "Storage Box user" in r.stdout + r.stderr
    assert not any(c.startswith("restic") for c in box.calls())
