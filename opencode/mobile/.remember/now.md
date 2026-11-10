# Handoff — opencode remote (mobile/)

## MIGRATION (2026-10-06): this project now lives on blackwall too

- Blackwall copy: `~/dev/opencode-mobile/` (rsync of this dir, excl. build outputs + .hprof).
- Blackwall link: `~/.config/opencode/mobile` → `~/dev/opencode-mobile` (symlink).
- This PC's opencode config delta synced to blackwall `~/.config/opencode` (extension, opencode.json,
  bin, AGENTS.md, skills; excl. node_modules, service.json).
- Full session transcript: `.remember/transcript-ses_efcba9b8.json` (861 msgs, same session resumed).
- Memory: `~/.config/memories/local.db` copied to blackwall (memories MCP store).
- Continue on blackwall: tmux `mobile-continue`, resume prompt `.remember/resume-p4.md`.
- Blackwall run (1.18.34, zen free model): P4 in progress there. PC keeps emulator verification.
- Post-migration updates: binary 1.18.31→1.18.34, ext repacked 1.0.13→1.0.38 served, 5 LLM keys set,
  Android SDK installed (no KVM → no emulator, unit tests + assemble only).

## State (2026-10-05, P3 DONE)

P0 + P1 + P2 + P3 complete and live-verified. `mobile/docs/`: 01–15 research + grand-plan.md (source of
truth) + spec-p0/p1/p2/p3 + vim-spike.md + `assets/` (serve spec + P0/P1/P2/P3 screenshots).
`mobile/android/`: `:app/:domain/:data/:feature-theme/:feature-servers/:feature-settings/:feature-chat`.

P3 verified on API-26 emulator vs live `serve`: attach sheet (camera/Photo Picker/SAF), staged chips,
PNG→JPEG compression, data-URL round-trip, VISION MODEL SAW THE IMAGE and described it correctly,
mic permission flow + graceful denial, projects CRUD + filter chips + link-on-create + system injection
(systemLen=61 live), mem/web chips. 23 unit tests green (8+11+4). Test sessions cleaned from server.

Locked decisions stand: native Kotlin minSdk 26 · ntfy+UnifiedPush per-device · aggressive onboarding (D5) ·
temp=hide+purge · extended widget (3+3+status) · maximal vim (spike done, ~12–16d, Gboard risk flagged) ·
client-side Projects (D1, DataStore; Room in P4) · allowlist approved · Tailscale until Tunnel cutover.
Kotlin 2.2.20 (no KSP 2.4); markdown 0.41.0; BOM 2025.12.00.

Known gaps: live permission/question ROUND-TRIP unverified (model 402s before asking) ·
rename/delete/abort not executed live · live token streaming not visually captured ·
weekly stats needs Room (P4) · camera capture untested (emulator) · dictation transcription untested
(no mic) · P0b debt (ktlint/detekt, full perm flow, R8).

## Next

1. P4 spec: ntfy self-host + serve→ntfy bridge (blackwall, needs SSH — CF Access gate was blocking),
   UnifiedPush in app, FGS live sync, extended widget (3 buttons + 3 recents + status), background health
   screen, Room (weekly stats + message cache + SessionPrefs persistence).
2. Then P4 implementation. Phases = build order, everything ships.

## Context

- Live `serve :4096` (user ucha, unit creds) = dev backend; emulator at 10.0.2.2:4096.
- Meta billing fixed itself mid-P3 (vision turn worked) — 402s come and go; reconcile paths cover both.
- Emulator api26 (5554); Quest 3 (2G0YC5ZF7X03LP) sometimes on adb — NEVER install to it.
- Bottom nav 4 tabs; tab tap coords shift with tab count — always use uiautomator bounds.
- adb `input text` + Gboard: verify every field via dump; URL/username/path fields now autocorrect-free.
- No stray test sessions on server ("Probe retry request" not ours — left alone).
- Root rule: `mobile/` root holds only md/AGENTS; code under `android/`; docs under `docs/`.
