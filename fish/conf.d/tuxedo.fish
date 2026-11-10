# Explicit per-session overrides win. The launcher also covers other shells.
if not set -q TODO_FILE; and not set -q TODO_DIR
    set -gx TODO_DIR "$HOME/notes"
    set -gx TODO_FILE "$HOME/notes/default"
end
if not set -q NOTES_DIR
    set -gx NOTES_DIR "$HOME/notes"
end
