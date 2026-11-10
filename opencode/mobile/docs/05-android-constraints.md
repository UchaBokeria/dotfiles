# 05 — Android constraints 2025–2026 (background, battery, insets, minSdk)

Source of truth: grand-plan.md. Verified 2026-10-03 against official Android docs.
Re-verify Play target-SDK deadline + FGS-notification-without-grant rendering at build time.

## 1. Headline: no perpetual background SSE

Five releases made indefinite background sockets impractical: bg FGS-start bans (12+),
mandatory FGS types (14+), `dataSync` 6h/24h cap (15+), job quotas alongside FGS (16),
Doze deferral, OEM killers. Supported architecture: **push-to-wake + short-lived connections**
(open SSE only while chat UI foreground or bounded sync). Our push = ntfy bridge (doc 09).

## 2. Foreground service types (mandatory API 34+)

- Every FGS declares `android:foregroundServiceType` + holds `FOREGROUND_SERVICE` + type permission.
- `dataSync`: uploads/downloads/fetch — closest fit for agent sync, subject to 6h cap.
- `remoteMessaging`: device-to-device SMS-style relay ONLY — claiming it for agent SSE risks Play rejection.
- `specialUse`: needs manifest justification + Play Console declaration + human review.
- `shortService` (34+): ~3-min timeout, no sticky — "finish send after backgrounding" only.
- What we use: `dataSync` FGS started from visible activity for live SSE while chatting;
  stop on backgrounding. UIDT jobs (34+, `RUN_USER_INITIATED_JOBS`) for attachment uploads;
  FGS-worker fallback below 34.
- Background start ban (31+): no `startForegroundService()` from background
  (`ForegroundServiceStartNotAllowedException`). Exemptions: high-priority FCM (n/a — no Firebase),
  user tap on notification/widget, battery-optimizations-off, visible overlay.
- Boot (targetSdk 35+): boot receiver CANNOT launch `dataSync`/camera/mic FGS — schedule WorkManager instead.
- `dataSync` 6h/24h cap: overrun → `onTimeout()` then crash if not stopped in seconds;
  exhausted quota at start → start exception. Honor via timeout + WorkManager handoff.
- Android 16: jobs running concurrently with an FGS count against JobScheduler quota.
  Monitor `WorkInfo.getStopReason()` / `JobParameters.getStopReason()`.

## 3. Doze / App Standby / battery exemption

- Doze (screen off, stationary, unplugged): network suspended, jobs/alarms deferred to
  shrinking maintenance windows. App Standby: untouched apps → network ~1×/day until charger.
- Official line: use push infra (FCM in docs; ntfy+UnifiedPush in our case), not own socket.
- Exemption flow: `PowerManager.isIgnoringBatteryOptimizations()` → settings intent
  (`ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS`) preferred; direct request
  (`ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) is Play-restricted for chat apps —
  USER CHOSE fully-aggressive anyway: we do the direct request, accept Play-review risk,
  sideload first / Play later. Recorded as decision D5.
- OEM killers (dontkillmyapp.com, re-verified 2026-06), worst→least:
  Huawei > Xiaomi > OnePlus > Samsung > rest; Pixel ≈ stock.
  - Samsung: sleeping/deep-sleeping lists + auto re-sleep (~3 days); needs Don't-optimize + Recents lock.
    One UI 6.0+: FGS of API-34-targeted apps "work as intended".
  - Xiaomi/MIUI: Autostart permission + Battery saver → No restrictions + Recents pin required by default.
    Detect autostart state via community MIUI-autostart API.
- Budget: in-app "background health" screen (P4) — exemption status, OEM deep-link instructions,
  ntfy registration diagnostics. No code path survives Xiaomi/Samsung defaults without user action.

## 4. Notifications

- `POST_NOTIFICATIONS` runtime permission since API 33 — request in aggressive onboarding with rationale.
- Channels (API 26+): create BEFORE posting; importance user-overridable → choose deliberately:
  agent-reply HIGH, approval-stall HIGH (separate channel), FGS-status LOW/MIN, no sound.
  Never delete/recreate channels (resets user prefs).
- FGS still needs a `Notification` object regardless of grant — honest "connection live" indicator.
- API 34+: full-screen intent needs `USE_FULL_SCREEN_INTENT` + user grant (reserve for calls, not messages).
  Don't rely on exact alarms for keepalive (`SCHEDULE_EXACT_ALARM` is user-granted).

## 5. Edge-to-edge (forced on targetSdk 35+ / Android 15)

- Status/nav transparent, offsets disabled; `setStatusBarColor`/`setDecorFitsSystemWindows` deprecated.
- Cutout modes coerced to ALWAYS — pad around `WindowInsets.displayCutout` yourself.
- Implementation: `enableEdgeToEdge()` + per-component insets (Views: `ViewCompat` listener;
  Compose: `statusBars`/`navigationBars`/`displayCutout`/`ime` insets, Scaffold `contentWindowInsets`).
- Material3 Compose handles insets mostly automatically; Material2 does NOT.
- Chat-critical: composer padding driven by ANIMATED IME inset, not `adjustResize` alone;
  test gesture nav + 3-button nav + cutout/foldable images. Audit onboarding/settings screens too.

## 6. minSdk / targetSdk — LOCKED: minSdk 26, targetSdk current

- minSdk 26 (Android 8.0, 2017): channels native, Autofill, adaptive icons, ShortcutManager,
  uniform background-limits baseline. Drops ~7.x (small, shrinking — confirm in Play Console stats).
- Desugaring (`coreLibraryDesugaringEnabled`) backports `java.time`/streams/concurrent to the 20s —
  language APIs are NOT a reason to raise minSdk; only framework behaviors are.
- Compose + M3 + Room + WorkManager + DataStore all support 21+ — no constraint from minSdk 26.
- targetSdk/compileSdk track current Play requirement independently (35 required Aug 2025;
  36 enforcement on August cadence — verify at build time).
- Device lab for P6 hardening: physical or imaged API 26 (channels/FGS-old), API 33 (notif perm),
  API 35 (edge-to-edge forced), Samsung + Xiaomi skins, foldable.

## Sources

- https://developer.android.com/develop/background-work/services/fgs/service-types
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- https://developer.android.com/develop/background-work/services/fgs/timeout
- https://developer.android.com/about/versions/15/behavior-changes-15
- https://developer.android.com/about/versions/16/behavior-changes-all
- https://developer.android.com/develop/background-work/background-tasks/data-transfer-options
- https://developer.android.com/develop/background-work/background-tasks/uidt
- https://developer.android.com/training/monitoring-device-state/doze-standby
- https://developer.android.com/develop/ui/views/notifications/notification-permission
- https://developer.android.com/develop/ui/compose/system/setup-e2e
- https://dontkillmyapp.com/ (+ /samsung, /xiaomi)
- https://github.com/XomaDev/MIUI-autostart
