## Goal
2026-11-10, Codex: restore normal window-number shortcuts outside the picker, add direct workspace shortcuts and a previous-workspace session toggle on Blackwall and Arch.

## State
Implemented and loaded on both live servers. Ctrl+A 0–9 selects windows outside the picker; inside Ctrl+A s, Prefix+0–9 selects root workspaces (0 = workspace 10). Bare numbers inside the custom picker still open numbered rows. Alt+Shift+0–9 jumps directly to root workspaces without a prefix, accepting both shifted punctuation and extended modifier encodings. Existing function-key and nested Alt-number mappings remain.

Inside Ctrl+A s, ^ (Shift+6) switches to the last-used session in the previous workspace; reopening and pressing ^ returns. Separate per-client previous-workspace history survives same-workspace session/window/pane changes and is persisted alongside existing history. The destination's saved window/pane is restored. Browsing workspace pills does not overwrite the attached session's history. Deleted/empty previous workspaces fall back to another live workspace; old state migrates lazily. Bare ^ outside the picker passes through. Updated ? help lists the keys.

Verified on disposable sockets: actual digit/window dispatch, Alt+Shift workspace jumps, custom/native picker scope, repeated ^ round trips after same-workspace changes, saved window/pane, native exit and outside ^ pass-through. Resume tests passed on both hosts. Full native CRUD/Resurrect regression passed on both hosts; opening/status-edge/resize checks also passed on Blackwall. Repeated installed shortcut tests passed on both hosts.

Only scripts/session-picker.conf was sourced, then workspaces.py init warmed the changed helper. Original status-left strings were restored after the deferred init. Live server PIDs remain 35471/3104, with original panes, hooks and status verified; no live session/server restart or termination.

The previous bounded warm-helper optimization remains active: see PICKER_SERVICE.md. Caches are memory-only, metadata capped at 2 MiB/1024 rows, per-popup previews at eight panes/100,000 cells, workers capped at four. Source fingerprints replace the helper gracefully; open pickers load new UI code after reopening.

## Next
No pending implementation. Changes are committed/pushed in Arch's rice repository. Reopen any already-open picker to load the new controls.

## Gotchas
Blackwall ~/.config/tmux is not Git; canonical copy is Arch ~/.config/.dotfiles/blackwall/tmux on nuc. Leave unrelated rice edits, tmux.conf.local and status/opencode files untouched. Tests use disposable sockets; TMUX_TEST_KEY_DELAY=1 helps native keyboard tests on busy Arch. Native filter header updates precede dismissal of its prompt; tests synchronize on the backend transaction before typing the next key. tmux 3.7c list-keys positional filtering differs: inspect the entire table when verifying a binding. Safety snapshots and apply/verify scripts are in /tmp/tmux-shortcuts-verify on both hosts.
