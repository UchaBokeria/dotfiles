## Goal
Persistent nested tmux workspaces on Blackwall and Arch, with safe session management and the requested session-picker layout.

## State
2026-11-07, Codex: custom curses session picker is the primary layout (explicitly chosen by the user). Centered workspace title and gap above the session tree; b toggles a two-column guide between the list and live pane preview; v hides preview and anchors the guide at the bottom. Both preferences persist. Session/window/pane tree supports j/k, h/l, Enter, search, tags, mouse, confirmed x/X deletion, archive/restore and moving sessions. Workspace navigation and s workspace list stay in the same picker process. List x confirms leaf-workspace deletion, archives running sessions, protects General/Background/Archive, and waits for the user's answer. Existing themed status/pills stay intact with b/? hints.

Previous functionality remains: workspace CRUD/default sessions, empty folders, protected Background, shared Archive with original-folder restoration, root/nested numeric/F-key shortcuts, J/K workspace ordering, local prefix BTab versus global prefix M-Tab histories, exact session/window/pane focus restoration and Resurrect/Continuum integration. Deleting all current sessions safely relocates attached clients and retains the workspace/server. Deleted-session snapshots trigger Resurrect save. Additive hooks use index 9271; detached focus uses hook_client and saved client pane context.

Isolated PTY suites on tmux 3.4 and 3.7c cover layout geometry, real custom interactions, positive/cancelled pane/window/session deletions, current-session rescue, workspace-list x protection/archive, restoring missing origins, persisted b/v, stable picker process, detach cleanup, native fallback, histories, shortcuts, CRUD, and real Resurrect restart. Deployed and enabled on both hosts. Live verification preserved server PIDs 35471/3104, all original pane processes, exact client session/window/pane targets and existing plugin hooks/options. Continuum advanced its save timestamp normally; no server/session restart.

## Next
None after deployment and final checks.

## Gotchas
Blackwall is not Git. Commit/push only owned tmux files in Arch ~/.config/.dotfiles/blackwall on branch nuc; unrelated changes (including tmux.conf.local theme edits) must remain untouched. Live server PIDs: Blackwall 35471, Arch 3104. Source scripts/session-picker.conf and run scripts/workspaces.py init for bindings/hooks; do not reload plugins or restart live servers. Native fallback: scripts/workspaces.py layout --kind native; primary: --kind custom. Run python3 tests/picker_layout.py, tests/session_resume.py and tests/workspaces.py (all use disposable sockets). Ctrl+S requires curses raw mode. List confirmation must temporarily block despite the picker refresh timeout. Backups/baselines: /tmp/tmux-workspaces-layout-20261107 and Arch staging /tmp/tmux-workspaces-layout-check-20261107.
