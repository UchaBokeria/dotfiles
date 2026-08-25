#!/usr/bin/env sh
# Apply the active status-line variant, once oh-my-tmux has finished.
#
# oh-my-tmux runs `_apply_theme&` - backgrounded - so it finishes at an
# unpredictable moment and a fixed `sleep` before applying the variant is a
# race. Waiting for a *marker* in status-left does not work either: on a
# re-source the marker is already there from the previous load, so the wait
# returns immediately and the variant is applied before oh-my-tmux overwrites
# it. Wait for the value to CHANGE instead - that is the event we actually
# care about - bounded so nothing can hang the config load.
#
# This lives in a file rather than inline in tmux.conf.local because the
# escaping needed to nest sh inside `run -b "..."` inside `if -b '...'` was
# four levels deep and broke the tmux parser.
set -u

before=$(tmux show-options -gv status-left 2>/dev/null)

i=0
while [ "$i" -lt 60 ]; do
    now=$(tmux show-options -gv status-left 2>/dev/null)
    [ "$now" != "$before" ] && break
    i=$((i + 1))
    sleep 0.1
done

# A moment more: oh-my-tmux sets status-left, status-right and the window
# formats in sequence, and we want to land after the last of them.
sleep 0.3
tmux source-file "${HOME}/.config/tmux/status/active.conf"
