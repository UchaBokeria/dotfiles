# 15 — Permission allowlist proposal (DRAFT for approval)

Source of truth: grand-plan.md. Status: APPROVED 2026-10-04 (round 3 follow-up, as-is).
Unrestricted-default per brief; deny rules always win (server-enforced).

## Proposed defaults (opencode permission types → default action)

| Type | Default | Rationale |
|---|---|---|
| `edit` (in-scope files) | ALLOW (remember) | Core agent loop; Claude parity (acceptEdits) |
| `read`, `glob`, `grep` | ALLOW (remember) | Read-only, zero risk |
| `bash` (safe read-only: ls, git status/diff/log, cat…) | ALLOW (remember) | Triage speed; still logged |
| `bash` (mutating: rm -rf, chmod, curl \| sh, sudo…) | ASK always | Destructive / exfiltration surface |
| `webfetch` | ALLOW (remember, websearch default-on H3) | Matches H3 default |
| `task`, `skill` (non-destructive) | ALLOW (remember) | Subagent delegation is normal work |
| `external_directory` (outside session dir) | ASK always | Sandbox escape |
| `doom_loop` | ASK always | Runaway-loop guard |
| `question` (AskUserQuestion) | ASK always (cards, never auto) | Needs human judgment by definition |
| `skill` (destructive/unknown) | ASK always | Unknown side effects |

## Rules

- Deny rules (server config) override everything, always.
- "Remember" (`always`) scoped per session by default; global-always requires explicit toggle (setting).
- Critical paths (`rm` on home/root, credential files) → ASK regardless of allowlist.
- Server `--auto` mode surfaced in UI banner (asks bypassed server-side except denys).
- Failed reply (e.g. `PermissionNotFoundError` = settled elsewhere) → card refreshes, stays answerable (grinev rule).

## Approval needed

User: approve table as-is, or adjust rows. Then it becomes the P2 permissions spec input.
