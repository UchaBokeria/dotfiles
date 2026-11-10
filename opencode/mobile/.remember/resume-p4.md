# RESUME — opencode remote (mobile), continued on blackwall

You are continuing the opencode-remote Android project after a PC→blackwall migration.
Read FIRST, in order:
1. `~/dev/opencode-mobile/AGENTS.md` (wiring + hard rules)
2. `~/dev/opencode-mobile/.remember/now.md` (full state: P0–P3 done, decisions, gaps)
3. `~/dev/opencode-mobile/docs/grand-plan.md` (SOURCE OF TRUTH — never rewrite wholesale;
   correct/add only, and record proposed grand-plan changes instead of applying them since
   the user can't approve mid-run)
4. `~/dev/opencode-mobile/docs/spec-p3-media.md` (last completed phase, for patterns)

Context of THIS session: full transcript at
`~/dev/opencode-mobile/.remember/transcript-ses_efcba9b8.json` (861 msgs — reference only,
now.md + grand-plan carry the state; don't re-read the whole thing unless details are missing).

Environment facts (verified 2026-10-06):
- This box (blackwall): opencode 1.18.31, serve :4096 healthy (user ucha, unit password),
  LLM keys in fish universal vars, Android SDK installing at ~/Android (check /tmp/sdk-install.log;
  NO KVM — emulator impossible here; unit tests + assembleDebug only).
- Project: ~/dev/opencode-mobile; symlinked at ~/.config/opencode/mobile.
- `local.properties` points at /home/scriptkid/Android/Sdk (create it or wait for SDK install).
- No `org.gradle.java.home` pin in android/gradle.properties (machine-local, by design); system java is 21.
- Server API matches frozen spec docs/assets/serve-spec-1.0.0-dev.json (v1 + v2 twins).

Your task:
1. Verify: files present, `~/.opencode/bin/opencode --version`, serve health, gradle.properties sane.
2. Write `docs/spec-p4-push.md` (P4: self-hosted ntfy + serve→ntfy bridge on THIS box, UnifiedPush
   in app, `dataSync` FGS live sync, extended widget 3+3+status, background health screen, Room for
   weekly stats + message cache + SessionPrefs persistence). Follow the spec conventions of spec-p3-media.md.
   Research input already exists: docs/05-android-constraints.md, docs/09-push-without-firebase.md.
3. Implement P4 in dependency order. Verify each step (unit tests via `./gradlew` in android/;
   NO emulator here — mark all UI verification as PENDING-FOR-PC). Do NOT attempt Cloudflare Tunnel
   setup (needs interactive auth) — spec it, don't execute.
4. Rules: no commits, no pushes (report only); never rewrite grand-plan.md wholesale; keep code
   hygiene per docs/11-code-hygiene.md; update `.remember/now.md` handoff + grand-plan changelog
   (append-only) as you finish each piece.
5. If blocked (billing 402s, missing creds, SDK failure): record the blocker in now.md and STOP
   that track cleanly — do not work around security or burn resources retrying.

Begin with step 1 verification and report a brief status line per item before implementing.
