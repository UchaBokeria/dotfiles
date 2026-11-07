## Goal
2026-11-08, Codex: track both graphical Chrome-in-tmux modes in this rice repo for Arch, mirroring the existing Blackwall Xvfb Chrome.

## State
Portable browser/pane installer/launchers/renderer are added, plus README link. chrome defaults to full native Chrome UI, chrome --page retains a page-only mode. On Arch both connect through private SSH tunnels to the same Blackwall profile. No credentials committed. Blackwall full/page integration and a clean client installation passed. Detailed scoped handoff: browser/HANDOFF.md.

## Next
Arch was offline on Tailscale and unreachable by SSH. Once reachable, pull nuc in ~/.config/.dotfiles/blackwall, run browser/pane/install.sh, confirm SSH identity/config, and test chrome plus chrome --page from Kitty/tmux. Live Arch installation has not been performed or verified.

## Gotchas
Do not overwrite unrelated dirty rice settings. No Chrome/tmux restart needed. Full view shares the exact Xvfb desktop with Remmina; controls affect the same window. Requires Kitty graphics; all nested tmux layers need passthrough.
