# 07 — opencode `serve` API contract (mobile client mapping)

Source of truth: grand-plan.md. Verify EVERY endpoint against the LIVE `/doc`
of the exact server version at implementation time. Known drift already exists.

## 0. Transport

- Verified live 2026-10-04 against `serve 0.0.0-dev-202609282029` on this machine
  (frozen spec: `docs/assets/serve-spec-1.0.0-dev.json`, OpenAPI 3.1, 162 paths, 472 schemas).
  Re-verify per server version; never hardcode schemas.
  `serve` is plain HTTP (`--port` default 4096, `--hostname` default 127.0.0.1); TLS ends at Cloudflare.
- Spec: `GET {BASE}/doc` = OpenAPI 3.1. Generate/verify client against live `/doc`; never hardcode schemas.
- Auth: HTTP Basic on EVERY request when `OPENCODE_SERVER_PASSWORD` set
  (user `opencode` default, `OPENCODE_SERVER_USERNAME` override).
  OkHttp: preemptive `Authorization: Basic base64(user:pass)` + 401 `Authenticator`. Never off-device plain HTTP.
- `?directory=` on ~all endpoints routes multi-project servers — ALWAYS send project worktree.
- Boot pin: `GET /global/health → {healthy, version}`; gate behavior per version.
- Concurrency: ONE `serve` per machine (shared sqlite WAL) — client connects only, never spawns.

## 1. Endpoint tables

### Global / health / events

| Method | URL | Mobile use |
|---|---|---|
| GET | `/global/health` | Boot check + version pin |
| GET | `/event` (SSE) | PRIMARY stream (`server.connected` then `Event`s) |
| GET | `/global/event` (SSE) | Legacy duplicate; prefer `/event`, support both |

### Project / path

| Method | URL | Mobile use |
|---|---|---|
| GET | `/project?directory=` | Workspace picker |
| GET | `/project/current?directory=` | Current cwd context |
| GET | `/path` | Show cwd |
| GET | `/vcs` | Branch chip |

### Sessions

| Method | Body | Resp | Notes |
|---|---|---|---|
| GET `/session?directory=` | — | `Session[]` | List |
| POST `/session?directory=` | `{parentID?, title?}` | `Session` | Create |
| GET `/session/status` | — | `{[id]: idle\|busy\|retry}` | Poll fallback when SSE drops |
| GET `/session/{id}` | — | `Session` | Details |
| DELETE `/session/{id}` | — | bool | Delete + data |
| PATCH `/session/{id}` | `{title?}` | `Session` | Rename |
| GET `/session/{id}/children` | — | `Session[]` | Fork tree |
| GET `/session/{id}/todo` | — | `Todo[]` | Agent todos |
| POST `/session/{id}/init` | `{messageID, providerID, modelID}` | bool | → AGENTS.md |
| POST `/session/{id}/fork` | `{messageID?}` | `Session` | Branch at message |
| POST `/session/{id}/abort` | — | bool | Stop turn (`MessageAbortedError` may surface) |
| POST `/session/{id}/share` | — | `Session` w/ `share.url` (opncd.ai) | PUBLIC — explicit confirm + unshare affordance |
| DELETE `/session/{id}/share` | — | `Session` | Unshare |
| GET `/session/{id}/diff?messageID=` | — | `FileDiff[]` | Review changes |
| POST `/session/{id}/summarize` | `{providerID, modelID}` | bool | Summarize |
| POST `/session/{id}/revert` | `{messageID, partID?}` | ⚠️ `Session` (types.gen) vs `boolean` (docs) — check live `/doc` | Undo |
| POST `/session/{id}/unrevert` | — | ⚠️ same mismatch | Restore |
| POST `/session/{id}/permissions/{permID}` | `{response: once\|always\|reject}` | bool — types.gen has ONLY `response`; docs claim extra `remember?` — send `response` only on v1 | Approval reply (session-scoped; prefer global below) |
| GET `/permission` | — | `PermissionRequest[]` | Global pending-approval poll (grapeot pattern) |
| POST `/permission/{requestID}/reply` | `{reply: once\|always\|reject, message?}` — NOTE field is `reply`, not `response` | bool | Global approval reply (preferred: no session id needed) |
| GET `/question` | — | `QuestionRequest[]` | Global pending-question poll |
| POST `/question/{requestID}/reply` | `{answers: string[][]}` (selected labels in question order) | bool | Question reply (grinev state machine) |
| POST `/question/{requestID}/reject` | — | bool | Question cancel |

`Session`: `id, projectID, directory, parentID?, summary?, share?, title, version, time{created,updated}, revert?`.

### Messages (core: async send + SSE render)

| Method | Body | Resp |
|---|---|---|
| GET `/session/{id}/message?limit=` | — | `{info: Message, parts: Part[]}[]` |
| GET `/session/{id}/message/{msgID}` | — | `{info, parts}` |
| POST `/session/{id}/message` | `{messageID?, model?{providerID,modelID}, agent?, noReply?, system?, tools?, parts}` | `{info, parts}` — BLOCKS full turn |
| POST `/session/{id}/prompt_async` | same | 204 — result via SSE ✅ mobile send path |
| POST `/session/{id}/command` | `{messageID?, agent?, model?: string, command, arguments}` — `model` is plain string here | `{info, parts}` |
| POST `/session/{id}/shell` | `{agent, model?, command}` | `AssistantMessage` |

Rule: sends via `prompt_async`; render `session.status` + `message.part.updated` deltas;
`GET message` to reconcile; `session.idle` → confirm via detail GET.
`noReply:true` injects context without triggering the model.

### Part model

- Sendable inputs: `text {text}`, `file {mime, filename?, url, source?}`,
  `agent {name}`, `subtask {prompt, description, agent}`. No reasoning/tool inputs.
- Renderable outputs: `text`, `reasoning`, `file`, `tool {callID, tool, state: pending|running|completed|error}`,
  `step-start`, `step-finish {reason, cost, tokens}`, `snapshot`, `patch {hash, files}`,
  `agent`, `retry {attempt, error}`, `compaction`, `subtask`.
- Streaming: `message.part.updated {part, delta?}` — APPEND `delta` to text/reasoning/tool state.
- Assistant `Message` carries `tokens{input,output,reasoning,cache}`, `cost`, `finish?`, `error?`
  (`ProviderAuthError|UnknownError|MessageOutputLengthError|MessageAbortedError|APIError`) —
  model failures arrive INSIDE 200 responses, not HTTP errors. Render inline with retry.

### SSE catalog (`/event`)

`server.connected`, `message.updated`, `message.part.updated`, `message.part.removed`, `message.removed`,
`permission.updated (Permission)`, `permission.replied`, `session.status`, `session.idle`,
`session.compacted`, `session.created|updated|deleted|diff|error`, `todo.updated`,
`command.executed`, `file.edited`, `file.watcher.updated`, `vcs.branch.updated`,
`tui.*`, `pty.*`, `lsp.*`, `installation.*`. Full union in types.gen `Event`.

### Permissions flow

1. SSE `permission.updated` → `Permission {id, type, pattern?, sessionID, messageID, callID?, title, metadata}`.
2. Card: title/type/pattern; buttons Once / Always / Reject.
3. `POST …/permissions/{id} {response}` → true; `permission.replied` confirms.
4. Types: `edit, bash, webfetch, doom_loop, external_directory, read, glob, grep, task, skill, …`
   → allow/ask/deny. Server `--auto` bypasses asks (denys enforced) — surface server mode in UI.

### Providers / agents / commands

| Method | Mobile use |
|---|---|
| GET `/provider` | Rich model picker (`all[].models` + limits/modalities/cost, `default`, `connected`) |
| GET `/config/providers` | Lighter picker |
| GET `/provider/auth` | Auth state |
| POST `/provider/{id}/oauth/authorize` → `{url, method, instructions}` | OAuth start (browser handoff; awkward on mobile — flag) |
| POST `/provider/{id}/oauth/callback` | OAuth finish |
| PUT `/auth/{id}` | API-key auth path (preferred on mobile) |
| GET `/agent` | Agent picker (plan/ask/build + custom) |
| GET `/command` | `Command[] {name, description?, agent?, model?, template, subtask?}` → execute via `POST …/command` |

### Files

| Method | Resp |
|---|---|
| GET `/find?pattern=` | matches `{path, lines, line_number, absolute_offset, submatches}[]` |
| GET `/find/file?query=&type=&directory=&limit=` | `string[]` |
| GET `/find/symbol?query=` | `Symbol[]` |
| GET `/file?path=` | `FileNode[]` |
| GET `/file/content?path=` | `FileContent {type: text\|binary, content, diff?, patch?, encoding?: base64, mimeType?}` |
| GET `/file/status` | `File[] {path, added, removed, status}` |

### Config / misc

- `GET /config`, `PATCH /config` (GET-then-merge, never blind overwrite).
- `GET /experimental/tool/ids`, `GET /experimental/tool?provider=&model=`;
  `GET /lsp|/formatter|/mcp`, `POST /mcp`; `POST /log`; `GET /doc`.
- Skip: `POST /instance/dispose` (kills server), `/tui/*` (desktop TUI),
  undocumented `/pty/*`, `/tui/publish`, `/tui/control/*`.

## 2. Gaps / risks

1. **Attachment upload RESOLVED (verified live 2026-10-04).** `FilePartInput{type:"file", mime, filename?, url}`
   with `url` = **`data:<mime>;base64,<bytes>`** stages correctly on the user message
   (verified: 1×1 PNG round-trips, `GET message` returns the file part with full data URL).
   No multipart endpoint; no `FilePartSource` needed for images. Client compresses/resizes
   BEFORE base64 (setting). Watch payload size on metered connections. `H2 UNBLOCKED`.
2. **No SSE resumption.** No Last-Event-ID/cursor/replay → resync via `/session/status` + `GET message?limit=`
   (`limit` is the only paging; large sessions may truncate).
3. **Schema drift v1 vs v2-fork.** Live binary serves v1 (`162 paths`) PLUS v2 twins
   (`/api/session/*` prompt/wait/history/context/agent/model, `/api/permission/*`, `/sync/*`,
   `/experimental/*`) absent from the v1 spec. Frozen reference: `docs/assets/serve-spec-1.0.0-dev.json`.
   Revert/unrevert type, permission `remember?` vs `reply`, structured-output `format` already diverge →
   verify each against live `/doc`, gate on `/global/health` version, defensive-parse.
4. **Sync POST hangs.** Long-turn blocking call — mobile treats sync as optional/short-turn only.
5. **OAuth on device.** Browser-redirect-to-server flow → prefer API-key `PUT /auth/{id}`; deep-link plan B.
6. **Share = public** (opncd.ai) — confirm dialog + unshare required.
7. **`?directory=` omission** silently targets wrong cwd — always send.

## 3. Minimal flows

- Boot: health → `/project` → `/provider` + `/agent` + `/command` → open `/event` SSE.
- Chat: create/pick session → `GET message?limit=` → `prompt_async` → render deltas → `session.idle` → confirm GET.
- Approval: `permission.updated`/`EventPermissionAsked` → card → `POST /permission/{id}/reply {reply}`
  (preferred global; session-scoped `POST …/permissions/{id} {response}` fallback). Questions: `GET /question`
  poll + `question.replied/rejected` reconcile (grinev FIFO state machine, doc 03 §B).
- Interrupt/undo/branch/publish: abort / revert / fork / share (+unshare).

## Sources

- https://opencode.ai/docs/server/ · https://opencode.ai/docs/sdk/
- https://opencode.ai/docs/permissions/ · https://opencode.ai/docs/share/ · https://opencode.ai/docs/commands/
- https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts
