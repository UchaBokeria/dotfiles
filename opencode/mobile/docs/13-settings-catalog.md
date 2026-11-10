# 13 — Settings catalog (consult + approve)

Source of truth: grand-plan.md. Status: PROPOSED — user approves/cuts/adds in consult round 3.
Everything dynamically configurable; DataStore-backed; import/export JSON (X1).

## Connection

- connect timeout, read timeout (async), SSE backoff base/max, keepalive interval,
  transport mode (SSE-live / poll-fallback / auto), default directory per server,
  server list add/edit/delete, per-server nickname + password (encrypted), quick-switch order.

## Sessions

- default-temporary (bool), temp auto-purge days + manual purge action, auto-title,
  delete-confirm, archive vs delete default, session search scope (all/dirs).

## Chat

- websearch default-on (H3), memory default (H5), streaming render (on/off + buffer ms),
  code-block theme, font size override, haptics on/off, enter-to-send, confirm-before-send-on-metered,
  date dividers, per-turn cost footer on/off.

## Agent

- default agent (plan/ask/build/custom), permission mode default (unrestricted/auto/manual),
  auto-approve rules editor, remember-choice default, default model+effort per server + per session,
  server `--auto` mode indicator.

## Attachments (H2)

- image compression (off/light/medium), max dimension, camera resolution, staged-upload staging note
  (blocked on doc 07 gap #1 probe), allowed mime display.

## Voice (H4)

- engine (platform), dictation language, push-to-talk vs hands-free, voice-mode voice+pace,
  transcript save on/off.

## Notifications (P1)

- master switch, reply channel importance, approval channel importance, status channel,
  quiet hours, per-session mute list, vibration/LED, lock-screen visibility, direct-reply on/off.

## Widget (P3)

- buttons enabled (new/Camera/mic per Claude parity + recents + status per user choice),
  recent count, tap behavior, refresh interval note (≥15min).

## Browser (B1–B4)

- per-chat default enabled, backend default (playwright/chrome-extension), CDP URL override,
  screencast quality/fps, control-mode confirm, password-handoff mode (custom-tab/credential-sheet),
  FLAG_SECURE on observation (always-on recommended), audit log view.

## Theme (T1–T3)

- scheme (neon default + user schemes), mode (dark/light/auto), font family, font-size scale,
  glow intensity on/off, shape roundness scale, motion (expressive/standard/reduced).

## Privacy & lock (X2 + rules)

- biometric/app lock (on/background-timeout), FLAG_SECURE whole-app, clear cache/downloaded data,
  share-link confirm (always), analytics off (no analytics — statement, not toggle).

## Background (P2/P4)

- FGS live-sync on/off, auto-start FGS on chat open, battery-exemption prompts (D5 aggressive),
  OEM instruction deep-links, ntfy topic + auth (encrypted), distributor check, health-check interval.

## Projects (H11, D1)

- project list (client entity → dirs), per-project instructions + memory files, default project for new sessions.

## Advanced

- log level, export/import settings JSON, export logs, reset to defaults, server version display,
  `/doc` viewer (debug), fake-serve mode (debug builds).
