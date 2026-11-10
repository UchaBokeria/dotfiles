# SPEC — P1 sessions + chat + streaming

Source of truth: `docs/grand-plan.md` §7. Implements: C1 (list/search/open incl. PC-created),
C2 (new + temp D2 + default-temp), C3 subset (rename/delete/abort; fork/revert/share/summarize/diff/todo
UI in P2, endpoints already declared), H1 (chat + streaming deltas), S3 hardened (SSE per doc 14 §1).

## 1. New module: `:feature-chat` (sessions list + thread + composer)

```
feature-chat/
  SessionsViewModel  (list/search/active, new+temp, rename/delete, status map)
  SessionsScreen     (search field, rows: title/time/status-dot/temp-badge, FAB new, long-press menu)
  ChatViewModel      (thread Flow, streamingPartTexts, send via prompt_async, abort, reconcile)
  ChatScreen         (MessageList + Composer; tool cards + reasoning collapse PLAIN in P1,
                      markdown lib lands in P2 — render text/code fences monospace for now)
  ChatNav            (route "chat/{sessionId}")
```

AppNav gains: Sessions tab (list) + `chat/{id}` route. Bottom nav: Servers / Sessions / Settings.

## 2. Data layer additions (`:data`, doc 14 copy-checklist)

- `SSEClient`: OkHttp EventSource → `{base}/global/event`, Basic header, infinite 1s→30s backoff+jitter,
  skip blank/`[DONE]`, `ignoreUnknownKeys` decode to `SSEEvent(directory?, type, payload)`,
  `server.heartbeat` noop. Lifecycle: `connect(profile)` returns `Flow<Result<SSEEvent>>`; cancel on scope end.
- `SessionRepository` (+ `:domain` interface): sessions Flow per active profile,
  `refresh()`, `create(title?, temp)`, `rename`, `delete`, `abort`, `statusMap`,
  `messages(id, limit)`, `sendPrompt(id, parts, agent, model, noReply)`.
- Temp (D2): `tempSessionIds` in DataStore (per profile); temp badge; list filter toggle
  "show temp"; purge action (delete all temp). NO server auto-delete.
- Reconcile: `session.status` event → if current && !busy: clear streaming overlays + refresh messages;
  `message.part.delta` → append `streamingPartTexts["msg:part"]`; `session.error` → drop optimistic,
  return text to composer, inline error card; 20s watchdog → one REST reconcile (grapeot rules).
- Models: `MessageWithParts(info, parts)`, `Part` sealed (text/reasoning/tool/step-start/step-finish/
  file/patch/agent/retry/compaction/subtask/unknown), `SessionStatusDto` extended
  (`type: idle|busy|retry`, retry{attempt,message}?) — defensive: unknown → `unknown` object, never crash.

## 3. UI rules (docs 02, 08)

- Rows: title + relative time + status dot (idle grey/working cyan/error red) + temp badge (magenta).
- Thread: user right / agent left; per-turn cost footer (from `step-finish{cost,tokens}`, muted small);
  error cards inline with Retry; "jump to latest" FAB; pull-to-refresh → status-poll resync.
- Composer: text field (grows ≤5 lines) + send/stop morph; staged text only in P1
  (attachments H2 in P3); optimistic user bubble; Enter-to-send per setting; haptic on send/error.
- Permission/question cards: NOT P1 (P2) — but thread must render `tool` parts in `awaiting` state
  as "waiting for approval (P2)" placeholder so P1 never misleads.
- Insets: composer `imePadding()` + animated IME (doc 08 §4); list behind nav bar.

## 4. Acceptance

1. Sessions list shows live server sessions incl. PC-created; search filters; status dots update via SSE.
2. New session (normal + temp w/ badge + default-temp setting honored); rename; delete (confirm per setting).
3. Chat: send → optimistic bubble → streaming agent text appends → completes with cost footer.
4. Abort mid-turn stops rendering + status returns idle. Kill-and-reopen app: thread reloads from server.
5. Airplane-mode: cached thread renders read-only + banner; send disabled with reason (X3 skeleton).
6. Tests: VM tests (send/reconcile/error with Turbine), SSE parse tests (heartbeat/delta/unknown-skip),
   MockWebServer (sessions list, prompt_async, abort). Screenshots: list, thread mid-stream, composer, temp badge.

## 5. Non-goals (P2+)

Markdown lib, permission/question cards, model/agent pickers (send uses defaults), fork/revert/share UI,
voice, attachments, widget, FGS. Optimistic send rollback only for transport errors (model errors render inline).

## 6. Review gate

Tests green · 2-emulator screenshots (incl. mid-stream) · live-serve chat round-trip from emulator
(send "ping" → agent reply renders) · grand-plan cross-check (C1–C3-subset, H1, S3) · user review.
