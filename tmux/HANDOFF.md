## Goal
Persistent nested tmux workspaces on Blackwall and Arch with the requested picker layout and familiar session-tree controls, without interrupting live work.

## State
2026-11-07, Codex: custom curses picker remains primary. Header now wraps ordered workspace pills, including nested paths, with the active pill coloured; pills are clickable. Session j/k, arrows and Ctrl+N/P wrap. Bare 0–9 and Alt+a–z open native numbered rows 0–35; prefix digits/F-keys select root workspaces, Alt+digits/F-keys select nested workspaces. Alt shortcuts enter children from a parent and select siblings from a nested leaf. Empty slots report a notice and succeed instead of returning shell errors. External shortcut requests update an open picker in place.

Session d/u and Ctrl+D/U scroll half-pages; PgDn/PgUp and Ctrl+F/B full pages (the configured prefix takes precedence), g/G first/last. Native controls include collapse/expand/all, search/repeat, tmux format filter, tags, sort/reverse, confirmed deletion, marked pane (Ctrl+Space, M clears), starting pane (Alt+H), command on tagged/current items (:), preview browsing (< >), mouse and context menu. Existing custom overrides remain m move, H/L workspace navigation, ? help. b shows a balanced two-column guide; ? shows all keys as an overlay without closing the picker. s workspace list and m destination chooser are bounded overlays. s-list J/K reorders, x confirms leaf deletion and archives running sessions. Input Ctrl+U clears; Escape cancels. Empty filter clears it; empty create/rename still cancels.

Preview uses capture-pane -e and cursor-aware cropping matching tmux screen_write_preview. It retains alternate-screen content, colours/attributes, and the session's active window with its pane splits. < > browse windows or panes without changing the actual active window/pane. It never resizes applications or sends input to them. b/v remain persistent and the guide stays above preview, or at the bottom when preview is hidden.

Existing CRUD, protected General/Background/Archive, archive origin restoration, per-workspace versus global histories, ordered numeric shortcuts, exact focus restoration, and Resurrect/Continuum integration remain. Tests use disposable sockets: picker_layout.py covers wrapping, row accelerators including Alt+a, nested Alt shortcuts in/out of picker, overlays, move/archive/delete guards, half-page scrolling, coloured fullscreen alternate screen across split panes, preview browsing without focus changes, filters/tags/marks/commands, saved b/v, detach cleanup and original process/server preservation. workspaces.py covers native fallback plus real Resurrect restart; session_resume.py covers reconnect and safely emptying current sessions.

Final suites passed on tmux 3.4 and 3.7c. Deployed identical helpers to both hosts. Live verification preserved server PIDs 35471/3104, every original pane process, exact client session/window/pane targets, plugin hooks and Resurrect/Continuum settings. No live restart or session termination.

## Next
None.

## Gotchas
Blackwall is not Git. Commit only owned tmux files in Arch ~/.config/.dotfiles/blackwall on nuc; leave unrelated tmux.conf.local theme edits and other changes untouched. Live PIDs 35471 (Blackwall), 3104 (Arch). Apply helpers/hooks via scripts/workspaces.py init; source scripts/session-picker.conf only if bindings change. Never reload plugins or restart live servers. Native fallback: scripts/workspaces.py layout --kind native; primary --kind custom. New dependency picker_preview.py is stdlib-only. Raw curses mode is necessary for Ctrl+S and Ctrl+Space; confirmation waits must block despite refresh timeouts. Backups/baselines /tmp/tmux-workspaces-picker-v2-20261107; Arch isolated staging /tmp/tmux-workspaces-picker-v2-check.
