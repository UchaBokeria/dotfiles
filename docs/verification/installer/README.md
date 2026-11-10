# Disposable Arch installer verification - 2026-11-08

This is a bounded VM result. It does not certify the full rice package catalogue or every desktop panel.

## Environment

Official Arch cloud image `Arch-Linux-x86_64-cloudimg-20261101.620452.qcow2`, downloaded from https://geo.mirror.pkgbuild.com/images/latest/ and verified against its published SHA256: `794eb4889b39e1f0ed7d5ae998b2a1ed2137db8cf8c3476cf2962c7437ecb003`. QEMU/KVM used two CPUs, 2048 MiB RAM, a 6 GiB virtual disk, OVMF, virtio VGA, headless display and Unix VNC. SSH forwarding bound only localhost. The normal guest user was `ricecheck`, with sudo. No host installation, mount, service or desktop changes occurred.

The cloud image's time-wait-sync service blocked initial provisioning under QEMU user networking. It was stopped inside the guest; its clock was already correct. This is an image fixture condition, not installer acceptance.

## Results

- Real Git prerequisite setup, followed by the actual root `./install --apply`, installed missing Rust/base-devel through a full Arch upgrade and built the installer with `cargo build --locked --release`. The guest began without Git, Rust or a C compiler. Durable package evidence is in `vm-pacman.log`; initial temporary build logs were cleared by guest reboot.
- The Rust engine executed the reduced catalogue in `vm-fixture-data` from `/home/ricecheck/clone with spaces`. Required packages in this fixture are empty. Actual repo-link, machine configuration and session-register helpers were retained. Canonical checkout alias, config symlink, machine block and pending session queue were checked.
- The actual session helper completed the mocked required session marker with a simulated compositor, and a repeated invocation did not repeat the marker. Appending a required failing command returned exit 1 with explicit failure and no completion claim. `vm-smoke-checks.log` records the latest successful check. The script is retained for inspection.
- Minimal real Hyprland, SDDM and Qt theme packages were subsequently installed: 203 additional package dependencies, approximately 210 MiB downloads and 769 MiB installed. These were separate from the mocked catalogue and do not establish full-catalogue installation.
- The actual SDDM helper installed the selected Japanese aesthetic theme and dedicated Blackwall session. After a guest reboot, the theme rendered in SDDM. A private temporary guest password was entered through QEMU's keyboard; the greeter authenticated and launched the selected Blackwall session, through `/usr/local/bin/blackwall-session` and `start-hyprland`.
- Actual Hyprland **0.57.1**, commit `acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9`, ran the repository Lua configuration. Live `/usr/bin/hyprctl monitors -j` reported a 1280x800 DRM output, and `configerrors` returned exit 0 with empty output. Lua `--verify-config` also reported `config ok`. That flag executes `hl.exec_cmd` hooks, so it must not be treated as a read-only owner-desktop check.
- During the actual graphical login, the machine hook automatically completed the mocked session job at 13:19:42 UTC, with state `complete`, attempts 1. This proves the first-login dispatch path with a fixture job. It does not prove every real session job.

## Evidence and limits

`vm-source-sha256.txt` identifies the wrapper, Rust and helper source copied for the latest fixture run. Later workspace changes are not implicitly covered. The full Lua tree and an existing generated palette were copied for actual compositor checks; this is not a fresh theme-generation test. Required real AUR names eww, wlogout and wallust resolved through the official AUR RPC. All 99 required repo names resolved in a clean local sync-database resolver; the full 669-package dependency closure was estimated at 934 MiB compressed and 4715 MiB installed, before AUR/build/source overhead, and was not installed.

The images show the actual themed greeter and actual Hyprland session. The session has the compositor's default wallpaper because full rice packages/autostart scripts were deliberately absent. No full-rice appearance, panels, glass plugin, physical hardware, NVIDIA driver or owner-machine reboot acceptance is claimed.

Before cleanup, the VM used approximately 2.9 GiB guest filesystem space and 2.7 GiB actual host scratch, with 6.6 GiB host free. Public artifacts only are retained here. The temporary VM, disk, seed and login credentials are removed after evidence capture.
