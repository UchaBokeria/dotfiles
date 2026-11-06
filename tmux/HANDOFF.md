## Goal
Match Blackwall's native session picker with reversible hiding and vi navigation.

## State
2026-11-07, Codex via SSH: installed scripts/session-picker.conf and sourced it from active tmux.conf.local. Ctrl+A,s opens original choose-tree; j/k navigate; h hides; Ctrl+R reveals hidden sessions; u restores and returns to the filtered tree with confirmation. Native previews, mouse and kill confirmations retained. Applied only helper bindings live. Server PID 3104 and all session/window/pane IDs and pane PIDs unchanged. Isolated PTY test on Arch tmux 3.7c verified restoring a noncurrent session while another remained hidden, filtering, switching and preserved processes. Unrelated working-tree edits preserved.

## Next
None.

## Gotchas
Hidden flags live in the running server. Native tree ignores a filter that would hide every entry. x/X retain native destructive behavior with confirmation. send-keys -K types into native prompts; run-shell -C captures caller pane for restore. Backup: /tmp/arch-tmux.conf.local.before-session-picker-20261107. Active directory is symlinked to ~/.config/.dotfiles/blackwall/tmux; dot-prefixed config copies are inactive.
