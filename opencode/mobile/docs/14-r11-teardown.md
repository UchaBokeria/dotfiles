# 14 — R11 teardown (file-level, verified 2026-10-04)

Source of truth: grand-plan.md. Teardown of the three reference implementations.
Read the repos directly for code; this doc captures what to copy and what to avoid.

## 1. grapeot/opencode_android_client (NATIVE BLUEPRINT — copy patterns)

Repo: https://github.com/grapeot/opencode_android_client (branch `master`, MIT, 97★)

### Files to study first

| File | Why |
|---|---|
| `app/.../data/api/OpenCodeApi.kt` | Full Retrofit interface (table below) |
| `app/.../data/api/SSEClient.kt` | OkHttp EventSource + infinite 1s→30s backoff + resync hooks |
| `app/.../data/repository/OpenCodeRepository.kt` | Dual-client (REST 60s / SSE infinite), Basic auth, `configure()` rebuild, optimistic send + `session.error` recovery |
| `app/.../ui/MainViewModel.kt` + `MainViewModelSyncActions.kt` | Single `StateFlow<AppState>`, `streamingPartTexts["msg:part"]` anti-flash, 20s SSE watchdog → REST reconcile |
| `app/.../data/model/SSE.kt`, `Permission.kt`, `Question.kt` | Event/part/permission/question models |
| `app/.../util/SettingsManager.kt` | EncryptedSharedPreferences + per-profile passwords + backup exclusion |
| `app/src/main/res/xml/network_security_config.xml` | `cleartext=false`, HTTP allowlist localhost/`10.0.2.2`/ts.net |
| `app/src/test/.../OpenCodeRepositoryTest.kt:298` | Test contract: `prompt_async` + Basic header + body shape |

### Endpoint table (verified against our live `/doc` — all exist on v1)

`GET global/health` · `GET session?limit=` · `POST session {title?,parentID?}` ·
`GET/PATCH/DELETE session/{id}` · `GET session/status` · `GET session/{id}/message?limit=` ·
`POST session/{id}/prompt_async {messageID?,parts[],agent="build",model?}` → 204 ·
`POST …/abort` · `POST …/fork {messageID?}` · `POST …/revert {messageID,partID?}` ·
`POST session/{id}/permissions/{pid} {response: once|always|reject}` ·
`GET /permission` + `POST /permission/{id}/reply {reply}` (PREFER — no session id; field is `reply`) ·
`GET /question` + `POST /question/{id}/reply {answers: string[][]}` + `POST …/reject` ·
`GET config/providers` (+ `GET /provider` fallback) · `GET /agent` · `GET …/diff` · `GET …/todo` ·
`GET /file?path=` · `GET /file/content?path=` (base64 images) · `GET /file/status` ·
`GET /find/file?query&limit=50`.

### JSON rules (copy verbatim)

`ignoreUnknownKeys + lenient + coerceInputValues`, `explicitNulls=false` (server rejects `model:null`),
`encodeDefaults=true` (keeps part `type` discriminator).

### SSE recipe (copy, then extend with FGS + ntfy)

- `GET {base}/global/event`, `Accept: text/event-stream`, manual Basic header.
- `retryWhen`: `delay((1000*2^attempt).coerceAtMost(30000))`, infinite.
- Skip blank/`[DONE]`; malformed frames skipped silently; `onClosed/onFailure` feed retry.
- Watchdog: server 10s heartbeat; no frame >20s → one REST reconcile (messages only if not busy).
- `message.part.delta` → append to `streamingPartTexts["$msg:$part"]` seeded from existing part text.
- `session.error` → drop optimistic rows, return text to composer, inline error.

### State model (adapt, don't clone)

Single `AppState` + derived slices; `visibleMessages` filters post-revert;
`attentionSessionIds = permission.sessionIds + question.sessionIds`;
per-session draft + model/agent memory; `contextUsage` from last assistant tokens vs provider limit;
`sessionStats` rolls up `parentID` subtree. Permission card: 3-button REJECT/ONCE/ALWAYS.
Deep links `opencode://session/<id>` (copy). NFC quick-prompt (skip).

### Explicit gaps THEY document (WE fill)

No background SSE, no FGS, no push — background disconnects, foreground full-syncs.
`question`/permission stalls with no push = "async idle" gap → our P4 (doc 09) exists because of this.
Voice needs external AI Builder → we use platform SpeechRecognizer (doc 08).

## 2. alvarolorentedev/opencode-mobile (UX + ONBOARDING — inspiration only, no code)

Repo: https://github.com/alvarolorentedev/opencode-mobile (Apache-2.0, 232★) · Docs: https://getopencode.app/docs/

- Onboarding: Welcome → Connect → Workspace → Preferences → Permissions → Ready;
  `CURRENT_ONBOARDING_VERSION` migration; fail-safe to completed. Copy the SEQUENCE, rewrite natively.
- Connection profiles: `{id, name, serverUrl, username, modelPreferences{…}}`;
  password NEVER in app storage — per-profile SecureStore key. Copy the MODEL (EncryptedSharedPreferences equivalent).
- Tunnel docs worth mirroring in our setup guide: LAN vs Tailscale vs Cloudflare Tunnel (named, auth mandatory,
  SSE/WebSocket must pass) vs reverse-proxy `/api` prefix vs SSH. Troubleshooting table
  (HTML/404 → wrong base; 401/403 → creds; SSE stall → proxy dropped streaming) → adapt to Tunnel-only.
- Permission cards: operation + pattern/path, Allow once / Always / Deny; prefer Allow-once guidance for
  destructive/network. Question cards: single/multi/custom, in-order, Reject ends turn.
- Usage sheet: context %, in/out/reasoning tokens, cache r/w, steps, cost ONLY with server pricing;
  "Pricing unavailable" ≠ free. Copy the copy.
- No QR in self-host path (manual URL + `curl -u … /global/health` check) → our X4 QR pairing is our own design.

## 3. grinev/opencode-telegram-bot (STATE MACHINES — read before P2 ViewModels)

Repo: https://github.com/grinev/opencode-telegram-bot (MIT, 1.2k★)

- Permissions (`permission-callback-handler.ts`): guards (manager→message→non-empty IDs);
  `PermissionNotFoundError` = settled elsewhere; failed → stays answerable + warning, re-tap resends;
  success → buttons stripped + terminal line records outcome; reconnect re-shows one prompt per pending request.
- Questions (`question-callback-handler.ts`): single-select answers+advances; multi toggles + Done;
  custom only when allowed; cancel → `question.reject` ends turn; last question stays until consumed;
  one slot FIFO; same-session replaces, subagent-from-other-session waits.
- Queue-vs-steer (`prompt-queue-dispatch.ts`): Steer (mid-turn pickup) vs Queue (own run after), cap 5;
  V2 busy → session inbox, bot holds nothing; restart/reconnect reconciliation rules.
- Revert/fork (`message-history-callback-handler.ts`): user-message list newest-first paginated;
  revert rolls back + discards later; fork branches + sets current + applies agent/model/variant.
- Model picker (`model-selection-callback-handler.ts`): favorites → recents deduped, current ✅,
  stale tap redraws, variant picker iff >1 variant, agent pick applies its model silently.

## 4. Copy checklist (into P0–P2 specs)

- [ ] Retrofit table + JSON rules + dual-client + `configure()` rebuild (P0)
- [ ] SSEClient backoff + watchdog + delta-append + error-recovery (P0/P1)
- [ ] EncryptedSharedPreferences keys + backup exclusion + network_security_config (P0)
- [ ] AppState slices + attention ids + drafts + model/agent memory (P1)
- [ ] Permission/question reply endpoints + grinev guards (P2)
- [ ] Onboarding sequence + tunnel troubleshooting (P0/X5)
- [ ] Usage-sheet copy + cost-honesty rules (P2/H10)
