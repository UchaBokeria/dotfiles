# Fresh Arch rice installation implementation plan

**Goal:** A regular sudo-enabled user clones Blackwall on an installed, networked Arch x86_64 machine, runs `./install` in a TTY, then reboots into SDDM and the configured Hyprland desktop without manually rerunning setup.

**Architecture:** Retain the Bash doorway, Rust TUI/planner/executor and TOML catalogue. Bootstrap compilation prerequisites before Rust/AUR work; preserve a canonical repo alias for existing consumers. Stage compositor-only work for automatic first login with durable status. Required failure prevents a successful completion claim; optional integrations remain distinct.

**Constraints:** Preserve this machine's dirty source and live session. No host installation, service changes, compositor reloads or personal account copying. Test with isolated fixtures and a disposable Arch guest. Disk/bootloader/Arch base installation remains the owner's preceding step. No automatic reboot.

- [x] Bootstrap: pure help and nonmutating dry-run; install compilation prerequisites safely; reject root/non-Git archive usage with actionable messages; clean sudo keepalive on exit.
- [x] Portability: canonical repo alias that preserves conflicting checkouts, machine-specific modifier/GPU config, source-complete package/config/theme inventory.
- [x] Engine: dependency order and failed prerequisite gating; required/optional outcomes; accurate TUI/headless exit and reboot messaging; free-text interaction.
- [x] Login: SDDM enablement, correct session entry and theme, graphical target, conflict-aware networking, automatic first-login session setup and status.
- [x] Verification: isolated bootstrap/helper/engine tests, catalogue checks, clean guest install where resources permit, explicit reboot/graphics acceptance limits.
- [x] User guide: fresh Arch prerequisites, clone/run/reboot instructions, selected optional groups, recovery and logs.

**Review focus:** arbitrary clone paths (including spaces), missing compiler/AUR helper, skipped or failed required steps, mismatched GPU/compositor versions, required session work staged but not completed. Account-dependent services require the new machine's own login; no credentials or sessions are cloned.

## Verification outcome

17 Rust,26 Python and15 catalogue tests passed. Actual fresh Arch compiler/bootstrap and reduced catalogue execution passed in a disposable VM, including spaced clone paths, pending queue/idempotence and required failure status. Minimal real SDDM/Hyprland packages then passed a guest reboot, themed greeter login, explicit Lua startup (Hyprland0.57.1, no config errors) and automatic fixture queue completion. Full669-package desktop/panels/audio/notifications and physical GPUs remain acceptance limits documented in docs/installation-verification.md. Existing dirty changes were preserved; nothing was committed/pushed or installed on the owner host.
