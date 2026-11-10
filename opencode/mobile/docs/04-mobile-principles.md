# 04 — Mobile development principles & philosophy (good / bad practices)

Source of truth: grand-plan.md. Applies to all implementation phases.

## 1. Guiding principles

- Server is source of truth; phone is a smart cache. Every screen must survive process death
  (ViewModel + SavedStateHandle + Room), because Android WILL kill the process.
- Async-first: no blocking network on main thread, no synchronous send-then-spinner.
  Every request has timeout + retry + visible state (sending/sent/failed-retry).
- Offline is a state, not an error: cached sessions/threads render read-only with a banner;
  queued sends flush on reconnect. Design empty/offline/error states before happy path.
- Least privilege, most clarity: each permission requested with a sentence saying WHY;
  aggressive onboarding (per user decision) lists all, but each row still explains itself.
- Battery is a feature: no polling loops; SSE only while foreground (or bounded FGS);
  WorkManager for deferred work; respect Doze instead of fighting it (see doc 05).

## 2. Architecture hygiene (Android)

- MVVM + UDF: `ViewModel` holds `StateFlow<UiState>`; Composables render, never fetch.
- Layering: `:app` (wiring) → `:feature:*` (screens+VMs) → `:domain` (pure Kotlin use-cases, no Android imports)
  → `:data` (Retrofit/Room/DataStore/WorkManager behind interfaces). KMP-extractable later.
- Repository interfaces in `:domain`, implementations in `:data`. Push behind `PushGateway`
  interface (UnifiedPush / FGS-fallback). Theme behind `ThemeRepository` (JSON tokens → M3 scheme).
- One source of truth per datum: sessions list from one Flow; thread from one Flow;
  never two caches of the same session diverging.
- Dependency injection with Hilt; no service locators, no static singletons holding Context.

## 3. Networking discipline (the S3 connection contract in code)

- OkHttp single client: preemptive Basic auth + 401 Authenticator, TLS (no cleartext off-device),
  `network_security_config.xml` allowlist (localhost/`10.0.2.2` only for dev).
- `prompt_async` for sends (204, no long-lived HTTP). Sync `POST message` only for short turns w/ timeout.
- SSE: one EventSource to `/event` (fallback `/global/event`), 1s→30s exp backoff + jitter,
  `since=`/status-poll resync after reconnect. `?directory=` on every request.
- Version pin: `GET /global/health` at connect; gate behavior per server version; defensive-parse
  unknown event/part fields (log + skip, never crash).
- Structured concurrency: `viewModelScope` + `SupervisorJob`; cancel streams on `onCleared`;
  no `GlobalScope`, no leaked callbacks.

## 4. Compose rules

- State hoisting: screens stateless, state lives in VM. `collectAsStateWithLifecycle()`.
- Lazy lists with stable keys; `key(session.id)` everywhere; avoid re-composition storms
  during streaming (buffer deltas ~100–200ms before recompose of markdown tail).
- Streaming markdown: `rememberStreamingMarkdownState` + append; re-parse tail only.
- Insets per-component (`imePadding`, `navigationBarsPadding`, `statusBarsPadding`);
  never root-level `safeDrawingPadding`. IME-animated composer (see doc 08).
- Test at 200% font scale + German-length strings; no hardcoded dp heights on text containers.

## 5. Good practices checklist

- Baseline Profiles + R8 + App Bundle from P0; measure startup (TTID) on an API-26 device.
- EncryptedSharedPreferences + Keystore for passwords/tokens; `FLAG_SECURE` on sensitive surfaces;
  no secrets in logs, no PII in crash reports.
- Notification channels from day one (HIGH replies, LOW status); never reuse/delete channels.
- Feature flags / settings for every behavior (F5 catalog, doc 13) — but flags need owners + defaults.
- Tests: ViewModel + repository unit tests; fake `serve` (see alvarolorentedev `tests/*.test.mjs` pattern,
  port to MockWebServer); screenshot tests for theme tokens; manual Doze/OEM matrix (doc 05 §6).

## 6. Bad practices (banned)

- Blocking REST for agent turns; perpetual background SSE; polling the server on a timer.
- `GlobalScope`, static Context, leaking EventSources across config changes.
- Hardcoded colors/sp/dp (all through theme tokens, doc 08/13).
- Blind `PATCH /config` (GET-then-merge only); blind schema assumptions (defensive parse).
- WebView-wrapped site as "app"; Expo-style JS push infra (we are on-prem, doc 09).
- Compressing plans, skipping verification, drifting from grand-plan (project rule, not just code).
