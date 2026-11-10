# Install Blackwall on fresh Arch

Blackwall installs the desktop on an **already installed Arch Linux x86_64 system**. It does not partition disks or install a bootloader. The intended path is TTY → `./install` → reboot → SDDM → Blackwall Hyprland. Compositor-dependent setup finishes automatically after the first login.

## Before starting

Install Arch with a kernel, firmware and working networking. Create your normal user and configure its sudo access. If using archinstall, choose NetworkManager for networking and leave the desktop profile unset; Blackwall installs SDDM and Hyprland. The installer refuses to silently replace an existing network manager or display manager. An existing systemd-networkd/ConnMan/dhcpcd setup needs an explicit migration to NetworkManager before all network panels can work.

As root during base setup, install the prerequisites:

```sh
pacman -Syu --needed sudo git base-devel
```

Log into a TTY **as your normal user** and verify `sudo -v` works. Do not run the installer as root. The installer adds Rust and GPU-detection tools if missing before building itself. Allow several gigabytes for the desktop, caches and AUR builds; an Internet connection is required throughout installation and optional first-login plugin builds.

Intel/AMD/Mesa machines use the normal Arch graphics stack. The installer detects the GPU and offers a VA-API userspace driver choice. NVIDIA kernel drivers and hardware-specific kernel configuration must already be appropriate for your GPU; selecting a video-decoding driver is not a proprietary kernel-driver installer. No existing machine's monitor names, keys or credentials are copied.

## Clone and install

Use a Git clone, not a ZIP. Submodules supply the SDDM theme and tmux plugins.

```sh
git clone --branch nuc --recurse-submodules https://github.com/UchaBokeria/dotfiles.git blackwall
cd blackwall
./install
```

These instructions require the installer changes in this working version; an older remote revision does not contain them until they are committed and pushed.

The TUI lets you review optional application groups, modifier/GPU choices, wallpaper, existing files that will be backed up and the final plan. Core desktop, fonts and theming groups are required. Developer tools, extra browsers, messaging, media and other application bundles remain choices; the installer does not assume you want the entire original machine's software catalogue.

You can clone anywhere. A checked alias at `~/.config/.dotfiles/blackwall` supplies the path existing rice consumers expect. A different checkout already at that location is preserved and reported as a conflict. Keep the installed checkout: many live configurations link to it.

For a noninteractive install of the required desktop:

```sh
./install --apply
# Add optional groups explicitly, for example:
./install --apply --group shell-tools --group browsers
```

Headless runs use detected/default machine answers; explicit `BLACKWALL_MOD` and `BLACKWALL_LIBVA` environment values override detection. AUR builds can take time. Required package, configuration or theme failures return nonzero and prevent a successful reboot-ready result. Optional failures are reported separately. Fix the reported cause and rerun; existing satisfied work is skipped.

## Reboot and first login

After the TTY phase reports success, reboot yourself:

```sh
systemctl reboot
```

SDDM starts at graphical boot with the Japanese aesthetic Astronaut theme. Select **Blackwall (Hyprland)** if the greeter has another session selected, then log in with your normal account. No autologin is configured.

The session explicitly launches the Lua configuration. The generated machine configuration starts automatic completion: desktop daemons, wallpaper/theme reload and the ArchPilot user services. The compatible glass plugin is attempted separately; when no plugin release supports the installed Hyprland, the desktop keeps its normal blur and records the optional warning. No manual second installer pass is required.

The first-login job records each result, checks required postconditions, and retries unfinished work. Completed steps are not repeated. Optional failures have a three-attempt limit. A manual pointer-click desktop self-test and interactive account setup are deliberately not run by the unattended job.

To inspect first-login setup:

```sh
python3 ~/.config/.dotfiles/blackwall/installer/helpers/session-finalize.py status
cat ~/.local/state/blackwall-installer/session.log
systemctl --user status blackwall-first-login.timer
```

If `XDG_STATE_HOME` is set, status and logs live beneath `$XDG_STATE_HOME/blackwall-installer` instead. Retry normally happens automatically. From a live Hyprland terminal, an explicit retry is:

```sh
python3 ~/.config/.dotfiles/blackwall/installer/helpers/session-finalize.py run
```

## Personal and optional integrations

Your WhatsApp pairing, SSH keys, VPN credentials, agent-provider logins, browser accounts and saved sessions belong to the new machine. They cannot be recreated from rice configuration. Personal source-machine links are skipped by default. Optional application groups may require their own account setup; their presence is not part of the core desktop's readiness claim.

Hyprland monitor settings start at preferred resolution and automatic positioning. Per-machine overrides are in `hypr/lua/machine.lua`; the installer updates its marked block and preserves custom settings outside that block.

## Preview and recovery

```sh
./install --help
./install --dry-run --apply
```

Help does not need sudo, a build or network. A dry run never installs build prerequisites, builds the installer or refreshes sudo; it needs an existing installer binary. If none exists, it exits with instructions to build one explicitly. It skips arbitrary catalogue check/detection commands rather than claiming those shell commands are universally inert, so it can propose already-satisfied setup work conservatively.

The installer backs up conflicting linked/copied configurations beneath `~/.local/state/blackwall/backups`. The completion screen shows the restore command:

```sh
./install --restore /path/shown/by/installer
```

Configuration restore is not a package-manager or complete system rollback. System service selection and installed packages are not undone by that command. SDDM's pre-existing main configuration is preserved except a conflicting theme selection; that file gets a `.blackwall-backup` before its theme key changes.

If a graphical login fails, return to a TTY, inspect `journalctl -b -u sddm`, `~/.local/share/sddm/wayland-session.log`, and the first-login log. Do not rerun unrelated repairs blindly. `blackwall-selftest` remains a manual diagnostic that can interact with the desktop.

## Verification boundary

See [installation verification](installation-verification.md) for the exact tested version and acceptance limits. Isolated installer checks do not prove every physical GPU or a real fresh-machine graphical login. Current setup follows [Hyprland's Lua/startup documentation](https://wiki.hypr.land/configuring/core/) and [Arch's SDDM guidance](https://wiki.archlinux.org/title/SDDM).
