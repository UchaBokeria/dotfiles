# CLAUDE.md — this repo is the live opencode config (dotfiles: `blackwall/opencode/`)

Full rules live in `AGENTS.md` — read it first, it applies here too.

## Claude-specific notes
- Resuming prior Claude Code work here: use the `pickup` skill
  (git → `.remember/` → Claude session history). Check
  `{project}/.remember/` (`remember.md` / `now.md`) at session start.
- Same non-negotiables as `AGENTS.md`: git identity is
  **UchaBokeria <ucha1bokeria@gmail.com>**, no attribution trailers, never
  commit secrets, review diffs before push/PR.
- Editing `opencode.json`: upstream-v1 schema only (`provider` singular +
  `npm` + `options`); always pre-flight with `timeout 60 opencode models`.
  Details in `AGENTS.md` → "This repo = live opencode config".
