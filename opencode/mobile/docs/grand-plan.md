# opencode remote — GRAND PLAN (source of truth)

> NEVER drift, regress, compact, or rewrite this file wholesale. Correct/add only, with user approval.
> All phases, specs, and reviews argue from this file. Cross-check list: §11.
> App name: "opencode remote"; launcher label: "opencode".

## 1. Vision & goals

- G1: Match then beat Claude mobile app quality for remote opencode sessions (doc 01).
- G2: Android-first, minSdk 26 support, easy + intuitive (docs 05, 08).
- G3: Work from anywhere without PC — full PC-setup replacement: background tasks (P2),
  notifications (P1), extended widget (P3), background health (P4).
- Quality over speed; no token/resource economy; research newest Android constraints always (Q1).
- No Firebase/paid; on-prem only; blackwall + `uchabokeria.space`; no Tailscale (T4).

## 2. Locked decisions

- D-Stack: 100% native Kotlin + Compose + M3 Expressive; minSdk 26; modules
  `:app/:feature/:domain/:data` (doc 06). Locked 2026-10-04.
- D-Push: self-hosted ntfy + `serve→ntfy` bridge on blackwall + UnifiedPush in app + FGS fallback (doc 09).
- D-Perms: fully aggressive first-run onboarding (direct battery-exemption request; Play risk accepted;
  sideload first). Decision D5 (docs 05, 13).
- D-Temp (D2): temporary mode HIDES sessions locally (no server auto-delete) + purge action/setting.
- D-Widget: extended — Claude 3 buttons + 3 recent shortcuts + status (locked round 3; no version cuts; phases = build order).
- D-Vim: MAXIMAL emulation as own workstream (normal/insert/visual, motions+text objects, registers 0-9,
  macros, marks/jumps, :s, counts; library-first, expect custom InputConnection), non-blocking.
- D-Push-T: per-device unguessable ntfy topics (locked round 3).
- D1: Projects = client-side Room entity (memory/instructions per project) mapped to dirs,
  injected as system context. Server Project = directory only.
- D3: websearch toggle = per-message tools gating; memory toggle = simple-memory injection on/off;
  permission default = PATCH /config rules; browser switch = /mcp + tools gating (verify live /doc).
- D4: `/rc` + Tailscale flow keeps working until Tunnel cutover; then migrate.

## 3. Topology (no Tailscale)

- `opencode.uchabokeria.space` → blackwall `serve :4096` via cloudflared Tunnel, per-server Basic auth.
- `ntfy.uchabokeria.space` → self-hosted ntfy, native auth + unguessable topics, NO Cloudflare Access on machine endpoints.
- `pc.uchabokeria.space` → reserved for PC tunnel later (post-v1 scope, design keeps the slot).
- `adb-emu` tunnel (PC→Cloudflare, `tcp://localhost:5037`) → lets blackwall drive the PC emulator
  over remote ADB for verification screenshots/taps (doc remote-adb.md). NO Access policy yet —
  tunnel registered but unreachable until the user adds DNS + Access; ADB has no auth so Access
  is mandatory before any use.
- Secrets in EncryptedSharedPreferences + Keystore. `network_security_config.xml` dev allowlist only.

## 4. Research index (mobile/docs/)

01-claude-app-ux · 02-ai-app-patterns · 03-third-party-clients (R11: alvarolorentedev UX + grapeot native;
grinev bot for state machines; doza62 QR pairing) · 04-mobile-principles · 05-android-constraints
· 06-stack-decision · 07-serve-api-contract · 08-ui-theming · 09-push-without-firebase
· 10-browser-embed · 11-code-hygiene · 12-app-optimization · 13-settings-catalog (APPROVED round 3)
· 14-r11-teardown (file-level, verified) · 15-permission-allowlist (DRAFT, needs approval).

## 5. Master feature list

- S1 multi-server profiles + switching · S2 health/version pin · S3 retry/backoff/keepalive/resurrection + `?directory=` always
- C1 list/search/open incl. PC-created · C2 new + temp mode (D2) + default-temp · C3 rename/fork/share/abort/revert/summarize/diff/todo/children
- H1 Claude-like chat + streaming deltas · H2 attach files/images/camera (blocked: doc 07 gap #1 probe first)
  · H3 websearch default-on · H4 dictation + voice mode · H5 memory toggle · H6 connectors view
  · H7 permission cards Once/Always/Reject, unrestricted-default (allowlist doc 15 DRAFT) · H8 agent plan/ask/build
  · H9 model+effort server-driven picker · H10 stats tokens/$/context per-session + weekly
  · H11 projects (D1) · H12 slash commands native+custom · H13 vim full emulation (own workstream)
- B1 browser per-chat enable · B2 playwright↔extension switch · B3 CDP screencast observe/control
  · B4 password handoff (Custom Tab + CredentialManager, FLAG_SECURE, revoke)
- P1 ntfy push (reply-ready, approval stalls inline) · P2 FGS live sync · P3 extended widget
  · P4 background health screen
- T1 theme engine day one · T2 dark/light/auto, default dark-cyberpunk neon (doc 08 tokens)
  · T3 user schemes import/export
- X1 settings import/export · X2 biometric lock · X3 offline cache + resync · X4 QR pairing · X5 aggressive onboarding

## 6. Settings

Catalog proposed in doc 13 — APPROVAL PENDING (consult round 3). DataStore-backed, JSON import/export.

## 7. Build order (phases, NOT version cuts — everything ships)

- P0: scaffold (modules, DI, theme engine, settings infra, server profiles, health/version, S1–S3) + Tunnel plan
- P1: sessions + chat + streaming (C1–C3, H1, S3 hardened) + upload probe (doc 07 gap #1)
- P2: permissions/models/agents/commands/stats (H6–H10, H12) + connectors view
- P3: attachments/voice/projects (H2–H5, H11) + H13 vim workstream (parallel, non-blocking)
- P4: ntfy bridge + UnifiedPush + FGS + widget + health screen (P1–P4) + blackwall deploy
- P5: browser/CDP/handoff (B1–B4)
- P6: hardening — Doze/OEM matrix, API-26 + current lab, foldable, perf pass (doc 12), full regression
- Each phase: implement → smoke-test on emulators (screenshots in-session) → cross-check vs this file
  → user review → real-device fix loop.

## 8. Hygiene & rules (docs 04, 11)

MVVM+UDF, `:domain` pure, repos behind interfaces, Hilt, no GlobalScope, `prompt_async` sends,
defensive parse, GET-then-merge config, tokens-only styling (lint), ktlint/detekt clean,
tests (VM/repo unit + MockWebServer fake-serve + theme screenshots), no secrets in logs,
FLAG_SECURE on sensitive surfaces. Never: perpetual bg SSE, polling loops, blind schema trust,
plan rewrites.

## 9. Knowledge persistence

`mobile/.remember/` handoff notes + memory entities (`opencode-remote-*`) + simple-memory.
This repo's own `.remember` stays separate.

## 10. Open questions (spec phase, with user)

ntfy topic/auth naming · default permission allowlist · browser-switch mechanism after /doc probe ·
H2 upload path after probe · vim scope details · widget shortcut count · settings catalog approval (doc 13).

## 11. First-message cross-check (nothing dropped)

G1/G2/G3 ✓ · R1–R10 → docs 01/02/03/04+12/05/05/08/08+06/12/07+11 ✓ · R11 → doc 03 + spec-phase teardown ✓
· F1→S1 · F2→C1 · F3→C2 · F4→H1–H10 · F5→doc13+X1 · F6→B1–B4 · F7→H12+H13+T1–T3 · F8→§5 ✓
· T1→doc04/11 · T2→S3+doc11 · T3→D-Stack+§10 · T4→§3+D-Push ✓
· P1 flow→§7 · P2 root-clean (only .md/AGENTS.md at root) · P3 theme→T1–T3+doc08 · P4 name/perms→X5+D-Perms ✓
· P5 persistence→§9 ✓. Root rule: project root holds only markdown/AGENTS/config; all code under feature modules.

## 12. Changelog (append-only)

- 2026-10-04: created from consult rounds 1–2 + 6 research tracks + gap analysis (9 gaps fixed: dual teardown,
  temp-purge, D1 projects, D3 toggle mappings, H2 probe gate, vim workstream, extended widget, 13-doc index,
  Tailscale cutover). Pending: settings approval, spec phase.
- 2026-10-04 (round 3): settings APPROVED all groups; per-device ntfy topics; widget = 3 buttons + 3 recents + status;
  vim = maximal; allowlist drafted (doc 15, needs approval). R11 teardown verified (doc 14 + copy checklist).
  H2 UNBLOCKED: live probe proved `data:<mime>;base64` file parts round-trip (doc 07). Frozen live spec
  `docs/assets/serve-spec-1.0.0-dev.json` (v1 162 paths + v2 twins on binary). Global permission/question
  endpoints corrected (`POST /permission/{id}/reply {reply}`, `POST /question/{id}/reply {answers}`). Next: P0 spec.
- 2026-10-04 (P0 DONE): scaffold builds (`:app/:domain/:data/:feature-theme/:feature-servers/:feature-settings`),
  APK installs on API-26 + API-35 emulators, 4 MockWebServer wire tests green, onboarding/servers/settings
  verified by screenshot, LIVE `serve` health check passes from API-26 emulator
  (`connected · v0.0.0-dev-202609282029` via 10.0.2.2). Screenshots in `docs/assets/p0-*.png`.
  P0b debt: ktlint/detekt wiring, full aggressive permission onboarding flow, release/R8 build. Next: P1 spec.
- 2026-10-04 (P1 DONE): sessions + chat + streaming infra. `:feature-chat` (Sessions/Chat VMs + screens),
  SSEClient (backoff+jitter), ChatRepositoryImpl (shared SSE, password-safe holder, reconcile),
  DtoMap lenient mappers. Verified live on API-26 emulator: session list w/ real PC sessions,
  temp create + TEMP badge, thread render w/ tool cards + cost footers, send→optimistic→204→reconcile,
  error cards (clean billing message + inline per-turn errors). Bugs fixed from live evidence:
  init-order NPE (passwordCache), password cache race (single passwordHolder flow), SSE GlobalEvent
  `payload` wrapper unwrap, `properties`-nested IDs, nested error.message extraction.
  12 unit tests green (incl. real 584KB payload + wrapper shapes). Screenshots `docs/assets/p1-*.png`.
  Test session deleted from server. Known gaps: live token streaming not visually captured (model 402s
  before streaming; delta path unit-tested), rename/delete/abort not executed live, no API-35 P1 shots.
- 2026-10-04 (P2 DONE): approvals + pickers + commands + stats + markdown + connectors. Permission/
  Question repos (global endpoints, grinev settle rules, SSE-wired), Catalog repo (providers/agents/
  commands/MCP/tool-ids), inline cards (Once/Always/Reject + terminal lines; single/multi/custom/cancel),
  model sheet (live providers + effort), agent chips (live), `/` autocomplete + execute, websearch tools
  gating, stats sheet (session totals; weekly deferred to P4/Room), connectors tab,
  mikepenz markdown 0.41.0 (last line for Kotlin 2.2) + BOM 2025.12.00 (Compose UI 1.10.0, method
  verified in AAR). Bugs fixed from live evidence: boolean-as-string parsing, SSE requestID extraction,
  empty-bubble errors, markdown/Compose NoSuchMethodError. 18 unit tests green. Screenshots `docs/assets/p2-*.png`.
  Known gaps: live permission/question ROUND-TRIP unverified (model 402s before asking; cards render from
  unit-shaped data only), rename/delete/abort still not executed live. Next: P3 spec.
- 2026-10-05 (P3 DONE): attachments + dictation + projects + vim spike. `+` sheet (camera/Photo Picker/SAF),
  staged chips, client JPEG compression (PNG→JPEG verified), data-URL round-trip, thread image thumbs +
  zoom/share viewer, mic dictation (SpeechRecognizer partials, graceful denial), projects CRUD + filter
  chips + link-on-create + system injection (verified live: systemLen=61), mem chip, no-autocorrect/no-caps
  input types on URL/username/path fields (found by live testing), vim spike (docs/vim-spike.md: no lib
  exists, custom InputConnection architecture, ~12–16d phased, Gboard key-event risk flagged).
  Bugs fixed from live evidence: Base64→java.util (JVM tests), compress try/catch, File.url kept,
  MapSerializer→SessionLink rows, SessionsViewModel combine/brace repairs. 23 unit tests green
  (OpenCodeApi 8, DtoMap 11, Attachments 4). Screenshots `docs/assets/p3-*.png`. Test sessions cleaned.
  Known gaps: camera capture untested (emulator), dictation transcription untested (no mic; denial path
  verified), project edit/delete executed only via create path (edit dialog same pattern), viewer share
  untested. Next: P4 spec (push bridge + FGS + widget + Room weekly stats).
