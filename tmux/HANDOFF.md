## Goal
Persistent nested tmux workspaces and a shared Archive on Blackwall and Arch Linux, preserving the native session tree.

## State
2026-11-07, Codex: deployed to both hosts. Prefix s opens native sessions; s inside lists ALL workspaces with indented parent/child rows, active marker, live session counts and pagination. Select a workspace to return to native sessions. w / prefix W opens CRUD. Creating or opening an empty ordinary workspace creates a uniquely named <workspace>-default detached shell so it never falls back to the options menu. Empty Archive still uses its menu.

h/l now use native collapse/expand; the old root h binding is removed on reload. z toggles the selected session into shared Archive or back to its original workspace. Missing origins prompt for an existing/new workspace path; u remains a restore alias. C-r toggles Archive and return. H/L and Tab/BTab cycle siblings; [/] parent/first child; m moves sessions; ? shows keys. General and Archive remain protected. Workspace deletion requires child-by-child confirmation and archives sessions. x/X retain native session/window/pane confirmations. D confirms permanent Archive purge, protects attached/last sessions, and requests a fresh Resurrect save.

Metadata persists atomically in ~/.local/state/tmux/workspaces.json (other sockets have separate files), keyed by session names with rename tracking and archive origins. Existing Resurrect/Continuum hooks remain intact; additive tmux hooks use index 9271. Status-left retains the original theme outside the picker and displays workspace/key hints inside. Full isolated PTY suite passed on Blackwall tmux 3.4 and Arch tmux 3.7c, including the s parent/nested list selection, default sessions and native views, h/l folding, z archive/restore, previous CRUD/move/purge safeguards, unchanged original pane PIDs, and real Resurrect save/server restart/restore. Live deployment kept server PIDs 35471/3104 and all existing pane IDs/PIDs unchanged.

## Next
None.

## Gotchas
Blackwall is not a Git repository. Arch deployment is in ~/.config/.dotfiles/blackwall/tmux, branch nuc. Active configs: tmux.conf and tmux.conf.local; dot-prefixed copies are inactive. New default shells start in the caller pane directory, with the configured shell. Metadata is independent of Resurrect snapshots; new/renamed/restored sessions are reconciled by hooks. Native tree ignores empty filters, so ordinary empty views create a default session; Archive never does. Native menus/popups launch outside waiting locks; naming mutations run after the popup closes. send-keys -K targets the client for native ':' prompts. Tests disable the test socket's closure hook during cleanup to avoid replacing intentionally killed default sessions. Follow-up backups: /tmp/tmux-workspaces-followup-backup-20261107 and /tmp/arch-tmux-workspaces-followup-backup-20261107. Run python3 tests/workspaces.py; it only restarts its disposable socket.
