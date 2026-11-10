# opencode remote — agent wiring

> Project: native Android client for opencode (`serve` HTTP+SSE). Source of truth: `docs/grand-plan.md`.
> Never rewrite grand-plan wholesale — correct/add only, with user approval.

## Where things live

- `docs/grand-plan.md` — vision, decisions, features, phases. Read before any task.
- `docs/01–13-*.md` — research. Consult, don't re-derive.
- Code (once scaffolded): `:app / :feature:* / :domain (pure Kotlin) / :data` (doc 06).

## Stack (locked)

Kotlin + Compose + M3 Expressive, OkHttp SSE, Room, DataStore, WorkManager, Hilt,
kotlinx.serialization. minSdk 26, targetSdk current. No Firebase, no paid, no Tailscale.
Topology: `opencode.` + `ntfy.uchabokeria.space` via Cloudflare Tunnel; `pc.` reserved.

## Hard rules

- Sends via `POST /session/{id}/prompt_async` (204) + SSE `/event`; never block on sync POST for long turns.
- Always send `?directory=`; version-pin via `/global/health`; defensive-parse unknown fields.
- `GET /config` then merge — never blind `PATCH`. Never call `/instance/dispose`.
- No perpetual background SSE (Doze/6h-cap/OEM — doc 05). Push = ntfy bridge + UnifiedPush + FGS fallback.
- Styling via theme tokens only (doc 08); default dark-cyberpunk neon; edge-to-edge + animated IME insets.
- Secrets → EncryptedSharedPreferences + Keystore. `FLAG_SECURE` on browser observation.
- H2 attachments BLOCKED until live-`/doc` upload probe resolves (doc 07 gap #1).

## Workflow

- Phases P0–P6 = build order (§7 grand-plan). Each phase: implement → emulator smoke test
  (screenshots in-session) → cross-check vs grand-plan → user review → fix loop.
- Quality over speed; research newest Android constraints; never compress plans.
- Persist state: `mobile/.remember/` + `opencode-remote-*` memory entities.
