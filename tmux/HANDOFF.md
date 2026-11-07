## Goal
Persistent nested tmux workspaces on Blackwall and Arch, preserving all live work.

## State
2026-11-07, Codex: the custom picker has one centred preview separator (`● session-name window-count active-window-name ●`), with captured active window panes and application colours. Lowercase r renames; J/K reorder. Search is reactive and Vim-modal: / starts INSERT, Esc switches to NORMAL, another Esc closes, i/a resume input. Workspace, action, destination and help overlays start NORMAL and remain inside the parent picker; rename forms prefill names.

Opening uses a short centre-origin ease-out reveal, retaining buffered curses initialization. Arch alone has rounded overlay frames and capsule selections. Wrapped workspace pills have a blank row between lines. Transient notices occupy a reserved bottom-right row and expire. The status pill contains only the current workspace outside the picker; `press ?` appears only while the picker is open; inline shortcuts remain removed and ? opens help. These preferences are recorded in project AGENTS.md and shared ~/.agents/AGENTS.md source.

Ctrl+Space pane marking and its clear action are removed from the picker. Dot moves selected windows to any session, including another workspace. A session row selects its active window; pane rows select their containing window; tags deduplicate windows. The backend validates the entire selection first and resolves source indices after each move, supporting renumber-windows. If all source windows move, a detached shell window keeps that source session alive. Existing pane processes and destination active windows are preserved.

Previous nested workspace/order/history/focus, bulk tagged session actions, empty workspace creation, Archive origin restore and protected workspaces remain. Resurrect/Continuum integration retains metadata, preview preference and exact session/window/pane focus.

All six isolated suites passed on both hosts: modal window moves/layout, opening/resize, full picker controls, bulk tags, resume, and native CRUD plus actual Resurrect restart. Deployed matching script hashes on both; live server PIDs 35471/3104, all 13/6 original pane PIDs and all plugin hooks retained. Only status-left and the normal uptime counter changed among global options. Blackwall attached focus stayed unchanged; Arch remained in the same session/window while the active pane changed during verification. No live server/session restart or termination.

## Next
None. Close/reopen an already-open picker to load the new Python code. For Sonata background assignment, prior handoff noted ~/opt/cloud/sonata/src/tmux.ts forces -L sonata; switching future runs to the shared socket needs a separate Sonata change with socket-aware cleanup. No Sonata source edited.

## Gotchas
Blackwall tmux directory is not Git. Commit only owned tmux files in Arch ~/.config/.dotfiles/blackwall on nuc; leave unrelated dotfiles/tmux.conf.local/status edits untouched. Install picker_startup.py and picker_theme.py before picker imports; source only scripts/session-picker.conf and run workspaces.py init. Existing open pickers need reopening. Tests use disposable sockets: picker_modal.py, picker_opening.py, picker_layout.py, picker_bulk.py, session_resume.py and workspaces.py. Arch staging /tmp/tmux-modal-ui-check; live safety snapshots /tmp/tmux-modal-verify. FirstPaint requires popup PTY stdout/stderr and preserves dimensions. Native fallback remains available via layout --kind native. Shared preferences source is ~/opt/cloud/omnigent/AGENTS.hub.md (separate repo).
