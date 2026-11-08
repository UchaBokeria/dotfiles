## Goal
2026-11-08, Codex: maintain both graphical Chrome-in-tmux views in this rice repo for Arch, mirroring Blackwall's existing Xvfb Chrome.

## State
Installed and verified on Arch and Blackwall. chrome defaults to full native Chrome UI; chrome --page keeps a page-only view. Pane closure stops owned viewers/tunnels and removes graphics. Resizing and moving panes rescale the view. Browser keys work by default; Ctrl+A Esc toggles tmux/browser controls. Mouse is temporarily enabled only in browser windows. Existing prefix/mouse/passthrough settings restore after exit. Full/page actual SSH integration and real Kitty visual lifetime tests passed on both hosts. See browser/HANDOFF.md and browser/pane/README.md.

## Next
No pending feature work. Reopen a chrome view to use updated code. Rerun browser/pane/install.sh after changing the Casty patch/data/lock.

## Gotchas
Preserve unrelated dirty rice files. Never restart live Chrome/tmux for deployment. Full view shares the exact desktop with Remmina. Kitty Unicode placeholders and synchronized frame updates are required; nested tmux needs passthrough in each layer. Credentials stay in existing private files, never Git.
