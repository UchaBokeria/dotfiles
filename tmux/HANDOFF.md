## Goal
Persistent nested tmux workspaces on Blackwall and Arch, with a unified themed picker, safe session management and no interruption of live work.

## State
2026-11-07, Codex: latest layout removes b and the inline shortcuts panel entirely; ? is the help overlay. Preview is enabled by default, uses about two thirds of the available area and preserves the last v setting in workspaces.json. Equal side-by-side previews align to the same centre column as help, including odd widths and tmux's extra-cell splits. Preview still reads colour/alternate-screen content around the cursor, composes the active window's panes and browses with < > without switching/resizing applications.

Prefix s now opens the actual current session's workspace and selects that session, regardless of stale picker-view options. J/K move the selected session block down/up, keep it selected and persist order by workspace/session name in session_order. Creation order seeds new lists consistently; assignment and rename tracking maintain the saved lists. JSON metadata survives real Resurrect restore.

w is now an in-process actions overlay. Its CRUD, child/sibling creation, shortcut editing, session actions, move, empty/purge and guarded workspace deletion retain the picker and existing confirmation protections. Input, actions, workspaces, move, search and help use the same frame/style. Session R, w R/r, workspace-list r and standalone rename prompts prefill the current value; Ctrl+U clears and Escape/empty names cancel. Dialog Escape never eats the next key as an Alt sequence. / or Ctrl+S opens a reactive fuzzy overlay searching workspaces, sessions, windows and panes (including collapsed groups); Enter highlights/expands the match, then the normal Enter opens it. Esc cancels. Existing native controls, numeric row shortcuts, nested Alt shortcuts, local/global histories, archive origin restore, protected folders, mouse and saved focus remain.

picker_theme.py reads live @bw_* colours and standard message/status/mode styles, resolving tmux formats. Changes refresh in open views, without hardcoded accent/raised colours. Main status hint is now only ?:help. picker_preview.py and picker_theme.py use only stdlib.

Both tmux 3.4/3.7c isolated PTY suites passed: current session/workspace, non-alphabetic J/K ordering and reselection after reopen, reactive fuzzy matching, w CRUD/Enter/empty/delete confirmation, rename prefills in all routes, unchanged picker PID, live palette changes, large colour split previews, v persistence, native controls, archive/delete guards, detach/reconnect, and real Resurrect restart retaining session order plus exact session/window/pane. Geometry tests cover even/odd divider placement. Deployed on both hosts. Verified unchanged live server PIDs 35471/3104, attached session/window/pane IDs and attached pane processes, plus existing plugin hooks/options. Arch retained all original pane processes. No live server restart or session termination was issued.

## Next
None.

## Gotchas
Blackwall is not Git. Commit only owned tmux files in Arch ~/.config/.dotfiles/blackwall on nuc; unrelated tmux.conf.local and other dirty files must remain untouched. Install new dependencies before session_picker.py. Apply scripts/session-picker.conf (removes old b binding) and workspaces.py init; never reload plugins or restart live servers. Existing open picker processes need closing/reopening for new code. Native fallback: workspaces.py layout --kind native; primary --kind custom. Tests: python3 tests/picker_layout.py, tests/session_resume.py, tests/workspaces.py; disposable sockets only. Backups/baselines /tmp/tmux-picker-v3-20261107; Arch staging /tmp/tmux-picker-v3-check.
