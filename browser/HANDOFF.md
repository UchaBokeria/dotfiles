## Goal
2026-11-08, Codex: real graphical Chrome inside a tmux pane on Blackwall and Arch, with both full-window and single-page modes. Track the portable setup in the rice repo at ~/.config/.dotfiles/blackwall/browser/pane.

## State
chrome (or --full) mirrors the exact existing Blackwall Xvfb desktop via shared VNC: Chrome tabs, toolbar, extensions, menus and side panels. chrome --page retains the Casty content-only view in the same profile. Both support mouse/keyboard and Ctrl+Q back to shell. Full mode uses native Ctrl+L/Ctrl+T/Ctrl+W. No Chrome or tmux restart; no new browser/profile/public port.

Installer, launchers, RFB client, Kitty renderer, pinned upstream patch/lock/license and both integration tests are tracked here. Arch setup defaults to SSH scriptkid@13.140.155.113 using ~/.ssh/idiot-doll, configurable without storing passwords. It creates temporary loopback-only tunnels to VNC/CDP and preserves existing chrome launchers via backups. Blackwall deployed source is ~/opt/cloud/browser/pane.

Local Blackwall integration tests passed actual PNGs through tmux, full native tab and URL controls, mouse/typing, resize, return-to-shell and original tabs/browser/server preservation. The full extracted image was inspected and contains actual Chrome tabs and toolbar. Existing single-page integration also passed. Arch peer 100.67.214.119 was offline; installation there remains pending until SSH is reachable.

## Next
Bring Arch online, pull nuc in ~/.config/.dotfiles/blackwall and run browser/pane/install.sh. Verify the private SSH identity/config and test both chrome and chrome --page in Kitty/tmux.

## Gotchas
Kitty graphics required on the local terminal; nested tmux needs passthrough at each layer. Full view is the same shared desktop as Remmina, so actions affect the same Chrome. No credentials are checked into this repo. Never restart existing tmux/Chrome to install. Do not overwrite unrelated dirty rice settings when deploying.
