# Blackwall

An Arch Linux / Hyprland rice with shared wallpaper-driven theming, SDDM, panels, notifications and terminal configuration.

## Fresh machine

On an installed Arch system with networking and a normal sudo-enabled user:

```sh
git clone --branch nuc --recurse-submodules https://github.com/UchaBokeria/dotfiles.git blackwall
cd blackwall
./install
```

Review the plan in the TTY. After successful setup, reboot and choose **Blackwall (Hyprland)** in SDDM. First-login setup completes automatically.

Read [installation and recovery](docs/installation.md) before running. The current installer changes must be present in the revision you clone; they remain local until committed and pushed.


Graphical Chrome inside tmux: see [browser/pane](browser/pane/README.md). Both the full shared Xvfb Chrome window and a compact single-page view are supported.
