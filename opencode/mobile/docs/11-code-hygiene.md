# 11 — Code hygiene (opencode sessions, backend connection, Android)

Source of truth: grand-plan.md. Lint- and review-enforced.

## 1. Connection code (S3 contract)

- Single OkHttpClient (timeouts from settings); preemptive Basic + 401 Authenticator;
  TLS only off-device; `network_security_config.xml` dev allowlist.
- Repository per aggregate (`SessionRepository`, `MessageRepository`, …) behind `:domain` interfaces.
- SSE manager: one EventSource lifecycle owner; backoff 1s→30s + jitter; resync via
  `/session/status` + `GET message?limit=`; `?directory=` always; version pin from `/global/health`.
- Defensive parsing: unknown event/part fields → log + skip, never crash. Contract tests against
  recorded `/doc` fixtures per server version.
- No `GlobalScope`; `viewModelScope`/`SupervisorJob`; cancel on `onCleared`.
- Never spawn `serve` from the app; never call `/instance/dispose`; never blind `PATCH /config`.

## 2. Session/message handling

- `prompt_async` sends; reconcile on `session.idle`; optimistic message with rollback.
- Deltas appended, never replaced; buffer ~100–200ms before recompose.
- Model errors inside 200s render inline with retry (never toast-only).
- Temp sessions filtered client-side (D2: hide locally); purge action + auto-purge setting.
- Client-side Projects entity (D1) → dirs; memory/instructions injected as system context on send.

## 3. Android hygiene

- Hilt DI; no statics holding Context; `SavedStateHandle` for process-death survival.
- Secrets: EncryptedSharedPreferences + Keystore; no secrets in logs/crash reports.
- `FLAG_SECURE` on browser-observation + optional whole-app (setting).
- Channels created once at install; WorkManager unique work names; FGS started only from visible activity.
- Tests: VM + repo unit tests, MockWebServer fake-serve, theme screenshot tests,
  manual Doze/OEM/device-lab matrix (doc 05 §6).

## 4. Review gates (per phase, before user review)

- `ktlint`/`detekt` clean; no hardcoded colors/strings/dimens in `:feature` (tokens only).
- Smoke test on API-26 emulator + current-API emulator; screenshots attached in-session.
- Cross-check touched IDs against grand-plan; fix deviations before handoff.
