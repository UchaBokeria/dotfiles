Read ~/.agents/AGENTS.md first when available, then HANDOFF.md.

## Ucha's terminal UI preferences

These preferences were explicitly requested on 2026-11-07. Preserve them in future picker and terminal UI development:

- Use the live tmux theme, compact in-context overlays, symmetrical spacing and aligned dividers. Keep the parent view open behind dialogs, with smooth first-frame rendering.
- Prefer one centred separator/title, framed by ● dots, with only useful context. For session previews: `● session-name window-count active-window-name ●`; omit duplicate headers, window/pane indices and process labels.
- Main `r` renames; `J/K` reorder. Rename inputs prefill current values.
- `/` opens reactive fuzzy search in INSERT mode. Escape changes INSERT to NORMAL; another Escape closes. NORMAL uses j/k and i/a return to INSERT. List/action/workspace/destination/help popups start in NORMAL and support the same search modes. Plain name-entry forms remain INSERT with Escape cancelling.
- New workspaces stay empty. Keep session creation explicit. Tagged operations use the whole selection and retain collapsed/filtered tags.

- Give wrapped workspace pills one blank row between lines. Put transient notices at the bottom-right in reserved space, never over content.
- Use a short, centred ease-out reveal on both hosts. Arch alone uses rounded popup frames and capsule selection highlights, matching its pills.
- The status workspace pill shows only the current workspace; add `press ?` only while the session picker is open. Pane marking is removed; `.` moves windows to another session, including other workspaces.

## Safety and delivery

Do not restart live tmux servers, reload plugins or terminate ongoing work to deploy picker changes. Record live server and pane identities first; test destructive paths only on disposable sockets. Deploy matching helpers to Blackwall and Arch, then apply scripts/session-picker.conf only if bindings changed and run scripts/workspaces.py init. Keep unrelated tmux.conf.local/status edits out of commits. Update HANDOFF.md and commit/push owned changes in Arch's dotfiles repository.
