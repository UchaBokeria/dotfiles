## Goal
2026-11-10, Codex: refine picker-only workspace browsing and direct session shortcuts on Blackwall and Arch.

## State
Ctrl+A 0–9 still selects windows outside the picker and workspaces inside it. Outside the picker, Alt+0–9 now jumps to the chosen root workspace's saved session/window/pane (0 = workspace 10). The former Alt+Shift+number bindings are removed. Alt+Shift+6 (Alt+^) alone toggles the previous workspace's last-used session, accepting punctuation and extended modifier encodings. Existing function keys and prefix+Alt nested shortcuts remain.

Inside Ctrl+A s, bare ^ browses the previous workspace without opening a session or closing the picker; repeating returns. The custom picker remembers previous displayed workspaces; its first target is the attached client's previous session workspace. Native fallback also supports browsing/toggling ^. Alt+numbers inside the picker still selects nested workspaces. Updated ? help distinguishes browsing and session-opening shortcuts.

Previous-workspace session history remains separate from same-workspace session history and persists with workspace JSON. Direct toggles restore saved window/pane. The bounded warm helper remains active; see PICKER_SERVICE.md for cache limits and operation. Reopen an already-open picker for new UI code.

Revised real-key integration tests pass on both hosts: window numbering, direct Alt numbers, custom/native ^ browsing without session switches, nested navigation, repeated Alt+Shift+6 toggles including extended encoding, exact saved focus and retained fixture server/panes. Revised bindings are active on both live servers; original server/pane identities, hooks and status strings were verified unchanged. No live sessions or servers restarted. Previous revision's full native CRUD/Resurrect, resume and opening regression checks passed on both hosts as documented in Git history.

## Next
No pending implementation. Changes committed/pushed to the rice repo. Reopen existing pickers to load the revised controls.

## Gotchas
Blackwall ~/.config/tmux is not Git; canonical copy is Arch ~/.config/.dotfiles/blackwall/tmux on nuc. Leave unrelated rice edits, tmux.conf.local and status/opencode files untouched. Apply scripts/session-picker.conf only, then workspaces.py init; preserve status-left across its delayed initialization. Never restart live tmux or reload plugins. Safety snapshots/apply script: /tmp/tmux-shortcuts-revised on both hosts.

Tests use disposable sockets. Native header changes precede completion of its filter transaction; synchronize through the backend before the next test key. Popup flags clear before its tty finishes closing; wait before injecting a physical Alt key. tmux 3.7c list-keys positional filtering differs: inspect the whole key table. TMUX_TEST_KEY_DELAY=1 helps broad native keyboard tests on busy Arch.
