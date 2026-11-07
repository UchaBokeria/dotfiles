## Goal
Persistent nested tmux workspaces on Blackwall and Arch, with smooth opening, correct bulk actions and no disruption of live work.

## State
2026-11-07, Codex: opening now batches pane/header/owner options with the popup in one tmux command queue. Dimensions and old border metadata are read in batches. picker_startup.py buffers curses initialization and its first complete screen in an anonymous RAM-backed fd, publishes one paint, restores stdout/environment, and disables the startup scrolling wipe. Repeated-opening terminal traces reduced setup redraws from five to one and removed intermediate blank curses paints. The ready PID marker follows the first paint; resize and subsequent live output remain functional.

Tagging is a batch selection, independent of tmux's single marked pane. Tags survive collapsed groups and format filters; actual vanished items are pruned. m, z, x/X, w move/archive/restore/delete/rename, R, command (:), and J/K operate on the tagged selection. Parent/child tagging excludes overlapping targets. Workspace actions on tagged windows/panes deduplicate their owning sessions, because workspaces contain sessions. Delete preserves exact tagged session/window/pane scope, validates snapshots and confirms/cancels the entire selection. Rename collects and validates all names before applying; Escape cancels the batch. Restore remembers each session's origin, asking for a replacement path only for missing origins. Selected counts appear in the picker/actions. New assign-many/restore-many/rename-many helper actions validate all sessions first.

Creating sibling, parent/top-level or nested workspaces now creates metadata only, with no default session. Existing sessions are retained. Empty folders remain openable and c/n explicitly create sessions. ensure_session is used only to create a rescue session when confirmed deletion would otherwise strand clients or stop the server.

Prior behaviour remains: actual current workspace/session on prefix s; persistent name-based session order with J/K; large v preview, no b panel, ? help; in-process w/input/search/list overlays; rename prefills; reactive fuzzy search across workspaces/sessions/windows/panes; live tmux theme colours; archive and special-folder guards; independent local/global history and exact focus persistence with Resurrect/Continuum.

Both tmux 3.4/3.7c isolated suites passed opening/resize, full picker interactions, empty workspace creation, multi-tag move/actions/rename/command/archive/restore, collapsed child deletion and cancellation, stale selection rejection, unchanged unselected work/server, and actual Resurrect restart with saved order/focus/preferences. tests/picker_layout.py and tests/workspaces.py explicitly create any fixture sessions they need; their names ending -default are test fixtures, not automatic workspace creation.

Deployed to both hosts. Live verification retained server PIDs 35471/3104, all pre-deployment pane PIDs, attached work and existing plugin hooks/settings; no live restart or session termination.

## Next
None. User requested a copyable Claude instruction for Sonata: ~/opt/cloud/sonata/src/tmux.ts currently forces -L sonata. Future runs need configurable shared-default routing and helper assignment to background, while old runs retain their original socket, tests stay isolated and cleanup remains Sonata-only. No Sonata source was edited.

## Gotchas
Blackwall is not Git. Commit only owned tmux files in Arch ~/.config/.dotfiles/blackwall on nuc; leave unrelated tmux.conf.local/status edits untouched. Install picker_startup.py before session_picker.py, then workspaces.py init; do not reload plugins/restart live servers. Existing open pickers need closing/reopening. FirstPaint is for tmux popup PTYs (stdout/stderr terminal); it preserves dimensions and restores LINES/COLUMNS. Native fallback: workspaces.py layout --kind native; primary --kind custom. Tests: picker_opening.py, picker_bulk.py, picker_layout.py, session_resume.py, workspaces.py. All use disposable sockets. Baselines/backups /tmp/tmux-opening-fix-20261107 and /tmp/arch-tmux-opening-fix-20261107; Arch staging /tmp/tmux-opening-fix-check.
