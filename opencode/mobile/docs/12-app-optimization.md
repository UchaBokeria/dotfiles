# 12 — App optimization & techniques

Source of truth: grand-plan.md.

## 1. Startup

- Baseline Profiles (compose + navigation paths) from P0; measure TTID on API-26 device.
- Lazy-init: don't open SSE, don't load providers/agents/commands until server connected.
- Hilt + R8 + App Bundle + per-ABI splits; keep `:app` wiring thin.

## 2. List + render perf

- LazyColumn stable `key(id)`; streaming buffer ~100–200ms; tail-only markdown re-parse
  (`rememberStreamingMarkdownState`); Coil async images with size bounds; diff/patch collapsed default.
- Avoid recomposition storms: hoist streaming state, use `derivedStateOf` for scroll-derived UI
  (jump-to-latest FAB, date dividers).

## 3. Network efficiency

- `prompt_async` + SSE deltas (no polling loops); status-poll ONLY as SSE-drop fallback with backoff.
- `GET message?limit=` paging; don't refetch full threads on every foreground (ETag/reconcile by `time.updated`).
- Image attach compressed client-side before staging (setting); camera capture resolution capped (setting).

## 4. Battery

- SSE socket lifetime = chat screen visible (+ bounded FGS). Nothing periodic under 15 min;
  WorkManager unique periodic ≥15min for widget status + health checks.
- ntfy keepalives as health signal; `since=` backfill instead of re-pull storms.
- Respect Doze: schedule, don't fight. Exemption is user-granted (D5), never assumed.

## 5. Size

- R8 full mode, resource shrinking, no unused deps; WebRTC/CDP libs loaded per-feature module
  (dynamic-feature or on-demand) so base APK stays lean for non-browser users.
- Prefer platform APIs (SpeechRecognizer, Photo Picker, CredentialManager) over SDK deps.

## 6. Measurement

- Per-phase: startup TTID (API 26 + current), APK size, SSE reconnect success rate,
  scroll jank (frame timing) on streaming thread, battery Historian spot-checks on P4/P6.
