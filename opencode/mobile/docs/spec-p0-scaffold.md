# SPEC — P0 scaffold (app boots, themes, servers connect)

Source of truth: `docs/grand-plan.md` §7. Implements: T1 (theme engine skeleton), T2 (neon default + light),
S1 (server profiles + switching), S2 (health/version pin), S3 (connection hardening), X1 (settings infra),
X5 (onboarding skeleton — full aggressive perms in P0b), doc 14 copy-checklist rows 1–3 + 6.

## 0. Toolchain (verified on this machine 2026-10-04)

- Android SDK `~/Android/Sdk`: platforms android-35 + android-36, build-tools 34/35/36.
- `local.properties`: `sdk.dir=/home/scriptkid/Android/Sdk` (generated, gitignored).
- AGP 8.13.x + Kotlin 2.2.x + JDK 17 (AGP requires 17; system java is 27 — set `org.gradle.java.home`
  to a JDK 17 path if present, else AGP toolchain; verify at scaffold).
- compileSdk 36, targetSdk 36 (verify Play requirement at build; 35 minimum), minSdk 26.
- No Kotlin/Flutter on PATH — Gradle downloads everything (wrapper pinned, hashes checked).

## 1. Module layout (doc 06)

```
mobile/
  app/                 (:app — Application, NavHost, DI wiring, onboarding)
  feature-servers/     (S1: profile list/add/edit/switch, health check UI)
  feature-settings/    (X1: DataStore settings + export/import screen skeleton)
  feature-theme/       (T1/T2: ThemeRepository, neon tokens doc 08 §2, light scheme)
  domain/              (pure Kotlin: ServerProfile, AppSettings, ThemeScheme models + repo interfaces)
  data/                (Retrofit OpenCodeApi per doc 14 §1 + JSON rules, EncryptedSharedPreferences
                        SettingsManager per doc 14 §4, network_security_config, S3 retry/backoff)
  gradle/libs.versions.toml (version catalog — ALL deps pinned here)
```

`:domain` has zero `androidx`/Android imports (unit-testable on JVM). Hilt across modules.

## 2. Deliverables (acceptance = all true)

1. `./gradlew :app:assembleDebug` green on this machine; APK installs on API-26 + API-36 emulators.
2. First-run onboarding (X5 skeleton): Welcome → Servers → Theme preview → Permissions (aggressive list
   incl. POST_NOTIFICATIONS rationale + battery-exemption settings intent D5) → Ready.
3. Server CRUD: add URL + user + password (encrypted, per-profile key), Test (`GET /global/health`
   → `healthy:true` + version shown), switch active server, delete. Tailscale URL works today;
   Tunnel URL field-ready.
4. Connection hardening (S3): preemptive Basic + 401 Authenticator; timeouts from settings;
   `?directory=` appended by interceptor (default server cwd); version pin stored per profile;
   `ignoreUnknownKeys/lenient/coerce`, `explicitNulls=false`, `encodeDefaults=true`.
5. Theme engine (T1/T2): `ThemeRepository` (DataStore) → CompositionLocal tokens → M3 Expressive;
   neon dark default (doc 08 §2 hexes verbatim) + light scheme + system-auto; no hardcoded colors in features.
6. Edge-to-edge from day one: `enableEdgeToEdge()` + per-screen insets; composer-less screens verified
   on gesture + 3-button nav (screenshot both).
7. Settings infra (X1): DataStore schema v1 (all doc-13 groups present even if few rows wired),
   export/import JSON working.
8. Tests: `:domain` unit tests; `:data` MockWebServer tests (health 200/401, `prompt_async` 204,
   Basic header assert — mirror grapeot `OpenCodeRepositoryTest.kt:298`); screenshot test of theme tokens.
9. Screenshots attached in-session: onboarding, server list, settings, neon chat-placeholder on API-26 + API-36.

## 3. Explicit non-goals (later phases)

Chat UI (P1), permissions/models/agents (P2), attachments/voice/projects/vim (P3), push/bridge/FGS/widget (P4),
browser/CDP (P5). No FGS, no UnifiedPush, no Room yet (profiles in EncryptedSharedPreferences per grapeot).

## 4. Risks

- AGP/Kotlin/JDK triad on Arch (JDK 27 default) — pin JDK 17 for Gradle, verify first build.
- M3 Expressive alpha API drift — pin version in catalog, isolate in `:feature-theme`.
- Emulator availability for API 26 — create AVDs now (`system-images;android-26;google_apis;x86_64`).

## 5. Review gate

ktlint/detekt clean · tests green · 2-emulator screenshots · grand-plan cross-check (§5: S1–S3, T1–T2, X1, X5-skeleton) · user review.
