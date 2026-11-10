# 06 — Stack decision (LOCKED: native Kotlin)

Source of truth: grand-plan.md. Decision locked 2026-10-04 with user. Revisit only with user approval.

## Decision

**100% native Kotlin + Jetpack Compose + Material3 Expressive**, OkHttp SSE,
Room, DataStore, WorkManager, Hilt, kotlinx.serialization, Coil 3, CameraX.
minSdk 26, targetSdk/compileSdk current. Modules `:app / :feature:* / :domain / :data`.

Only (A)/(B) give full Android-framework access for our hardest constraints
(old devices + background SSE + self-hosted push + WebRTC/VNC). iOS is future/possible,
so cross-platform UI buys nothing now and costs quality daily.

## Comparison (researched 2026-10-03, relative rankings, no invented benchmarks)

| Criterion | (A) Native Kotlin ✅ | (B) KMP shared | (C) Flutter | (D) RN/Expo |
|---|---|---|---|---|
| Old-Android compat | Best (Compose minSdk 21+) | Same on Android | Plugin-gated (e.g. webrtc→23) | Worst (RN 0.73+ → 23–24) |
| Background services | Full FGS/WorkManager/Doze control | Same Android, zero iOS share | Isolates plumbing, second-class | Deprecated bg-fetch → bg-task, weakest |
| Startup | Fastest (baseline profiles, R8) | Same | Engine-init cost | Slowest (Hermes helps, still bundle parse) |
| APK size | Smallest (R8, bundles, ABI splits) | Slightly larger | Largest (libflutter.so per ABI) | Mid-large |
| Chat/SSE/markdown | OkHttp EventSource + streaming markdown, full control | Transport shared, UI per-platform anyway | Streaming jank + highlight gaps | Polyfill SSE, thinnest VNC |
| VNC + WebRTC | Google WebRTC SDK + JVM VNC, direct interop | Same Android, doubled iOS work | flutter-webrtc 701 open issues, VNC DIY | Community only, heavy bridging |
| Offline | Reference path (Room+DataStore+WM) | Feasible (KMP samples) | Two failure domains | Weakest scheduling |
| Theming | M3 dynamic color, CompositionLocal tokens | Same Android, iOS separate anyway | M3 fidelity lags | Native views escape system |
| No-Firebase push | Best UnifiedPush host (Tusky/Element/Nextcloud Talk pattern) | Same Android | Needs native bridge | Same + worse scheduling |
| Staffing | Any Android hire productive | Needs Kotlin+Swift senior | Easy Dart hire, escapes need Kotlin anyway | Largest pool, heaviest churn |

- (B) only if iOS committed within ~12mo WITH iOS capacity. Otherwise dual-platform build/DI cost, zero shipped benefit.
- (C)/(D) rejected: lose exactly where requirements are hardest.

## Keep-the-door-open structure

- `:domain` pure Kotlin, no Android imports; DTOs kotlinx.serialization from day one → drop into `commonMain` later.
- `PushGateway` interface (UnifiedPush / FGS-fallback); theme behind `ThemeRepository`.
- KMP status note: shared-logic KMP production-stable; Compose Multiplatform stable Android+iOS, web Beta —
  stable ≠ cheap to staff. Revisit when iOS is real.

## Key libraries (initial pin, verify at scaffold)

- UI: `androidx.compose.material3:material3` (Expressive), `material3-adaptive` (ListDetailPaneScaffold),
  `androidx.window` (foldables), `androidx.activity` (enableEdgeToEdge), `androidx.browser` (Custom Tabs)
- Chat: mikepenz `multiplatform-markdown-renderer` (`-m3` + `-code` + `-coil3`), Coil 3, CameraX,
  platform SpeechRecognizer, Media3 for voice playback, `LocalHapticFeedback`
- Net/persist: OkHttp (+SSE), Retrofit, kotlinx.serialization, Room, DataStore, WorkManager, Hilt
- Push: UnifiedPush `android-connector` (+ ntfy distributor app), CredentialManager (passkeys/autofill)
- CDP: OkHttp WebSocket + kotlinx.serialization; optional kklisura/chrome-devtools-java-client
- Widget: Glance (preferred) or RemoteViews; CameraX + Photo Picker (no storage perm)

## Sources

- https://developer.android.com/develop/ui/compose/setup
- https://kotlinlang.org/docs/multiplatform/kotlin-multiplatform-react-native.html
- https://kotlinlang.org/docs/multiplatform/multiplatform-ktor-sqldelight.html
- https://github.com/android/kotlin-multiplatform-samples
- https://docs.flutter.dev/perf/app-size · https://docs.flutter.dev/deployment/android.md
- https://docs.flutter.dev/perf/isolates.md · https://docs.flutter.dev/platform-integration/platform-channels.md
- https://github.com/flutter-webrtc/flutter-webrtc
- https://docs.expo.dev/versions/latest/sdk/background-fetch/ · https://docs.expo.dev/versions/latest/sdk/background-task/
- https://github.com/expo/expo
- https://unifiedpush.org/
