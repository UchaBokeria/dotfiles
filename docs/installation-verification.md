# Installer verification — 2026-11-08

This records the new fresh-Arch installer path, not acceptance of this machine's existing rice.

## Results

Final isolated checks: **17 Rust tests, 26 Python tests and 15 catalogue tests passed.** Release build passed. The final actual-catalogue `./install --dry-run --apply` exited zero with no required failures or pending work and no execution of installation steps. Independent review found two substantive issues (per-interface network-manager detection and legacy generated GPU assignments); both received regression tests and fixes.

## Implemented checks

- Rust engine unit tests: dependency order, missing/cyclic/failed/skipped prerequisites, mandatory versus optional outcomes, prepared first-login staging, manual extras, skipped queue entries, missing catalogue, free-text keyboard behavior and inert dry-run probes.
- Isolated Python tests: wrapper help/preview/archive handling, argument and exit preservation, canonical clone alias/conflict protection; machine Lua validation/preservation; sandboxed SDDM theme/session/fonts/auth preservation; selected GPU package mapping; competing network-manager protection; first-login selection, dependency ordering, secret exclusion, retries, idempotence, postconditions and process-group timeout cleanup.
- Catalogue tests: sources, dependency declarations and question/required package consistency.

These checks use temporary homes and fake subprocesses or harmless isolated shell commands. They do not install packages on the working host, reload its compositor or run broad desktop suites.

## Commands

```sh
cargo test --locked --manifest-path installer/Cargo.toml
python3 -m unittest discover -s installer/tests -v
archpilot/.venv/bin/pytest -q theme/tests/test_installer_catalogue.py
bash -n install
```

The pytest command uses the existing project environment; a clean test host needs pytest installed separately. That environment is not required by the Bash doorway itself.

## Package and upstream checks

Read-only package metadata resolved all 101 current unique required official package names and their dependency closure; official AUR RPC confirmed the required AUR names. Versioned packages and AUR builds can change independently of this source.

Primary references: [Hyprland configuration and explicit config startup](https://wiki.hypr.land/configuring/core/), [Hyprland startup guidance](https://wiki.hypr.land/getting-started/master-tutorial/), [Arch SDDM](https://wiki.archlinux.org/title/SDDM), and the [official Arch image mirror](https://geo.mirror.pkgbuild.com/images/latest/).

## Disposable VM

An official Arch cloud image, SHA256-verified against its published checksum, was booted with KVM/OVMF in a private VM: two vCPUs, 2GiB RAM, user-mode networking, loopback-only SSH and a Unix VNC socket. The guest uses a different ordinary username and a clone path containing spaces. Owner configuration and credentials were not copied.

A full core install resolves roughly 4.7GiB of installed official packages, before AUR builds, compiler caches and source assets. Available host storage cannot safely accommodate a complete graphical acceptance VM plus those peaks. Validation therefore uses a reduced test catalogue to exercise the real bootstrap and installer engine; compositor readiness and session marker jobs are simulated explicitly. The reduced catalogue does not establish complete rendered rice, physical GPU compatibility or a full core-package installation.

### Actual graphical reboot and login

After the bounded installer flow, the guest received the minimal real Hyprland/SDDM/Qt dependency set and the actual Lua tree and Astronaut theme. It was rebooted. QMP screenshots confirmed the themed SDDM greeter; the dedicated Blackwall session was selected and a temporary guest-only account password entered through the VM's virtual keyboard. SDDM launched the installed session wrapper into Hyprland 0.57.1. The real `hyprctl` reported a 1280×800 Virtual-1 output and empty config errors. The machine Lua hook automatically completed the reduced fixture's queued session job once after login. Its earlier fake compositor helper was removed before this real login.

This verifies the SDDM → session wrapper → explicit Lua → compositor → automatic first-login hook chain. It does **not** verify every real core session job: the fixture marker job is distinct from the full panel, wallpaper, plugin and ArchPilot job set.

The working host was not used as an installation target. Remaining acceptance is a full core-package install on adequately provisioned hardware or a larger disposable VM, including actual panel, wallpaper, notification, audio, input and physical GPU behavior. The disposable VM and its private test credentials are removed after public evidence is saved.

## Saved graphical evidence

[VM receipt and source hashes](verification/installer/README.md), [themed SDDM greeter](verification/installer/sddm-greeter.png), [actual compositor session](verification/installer/hyprland-session.png), and the logs alongside them are retained. The parent visually inspected both images. The compositor screenshot intentionally has its default wallpaper and no rice panels because that guest only installed the minimal graphical subset. This must not be shown as full-rice visual acceptance.

The final isolated tests also cover stale preview binaries, read-only snapshot planning, no sudo refresh during preview, and rejection of restore/preview flag combinations. Later code fixes are covered by the final tests; the VM source hash list identifies its earlier tested snapshot rather than implying it exercised every later change.
