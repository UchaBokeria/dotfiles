# SPEC — P2 permissions / models / agents / commands / stats

Source of truth: `docs/grand-plan.md` §7. Implements: H6 (connectors view), H7 (permission cards +
allowlist doc 15 APPROVED), H8 (agent switch), H9 (model+effort picker), H10 (stats per-session;
weekly deferred — see §5), H12 (slash commands), questions (AskUserQuestion cards), markdown renderer.

## 1. Data (`:data` + `:domain`)

- `PermissionRepository` (+ domain interface): `pending: Flow<List<PermissionItem>>`,
  `refresh()` (GET /permission), `reply(id, once|always|reject)` (POST /permission/{id}/reply {reply}).
  SSE `permission.asked` → refresh; `permission.replied` → drop by requestID + refresh
  (grinev rules: failed reply stays answerable; vanished = answered elsewhere).
  `PermissionItem{id, sessionID, permission, patterns[], metadata{}, always[], tool{messageID,callID}}`
  (spec schema PermissionRequest verbatim).
- `QuestionRepository`: `pending: Flow<List<QuestionItem>>`, `refresh()` (GET /question),
  `reply(id, answers: List<List<String>>)` (labels in question order),
  `reject(id)`. SSE `question.asked/replied/rejected` same pattern.
  `QuestionItem{id, sessionID, questions[{header, question, options[{label,description}], multiple, custom}], tool?}`
  (QuestionInfo verbatim; V2 shapes parsed leniently into the same model).
- `CatalogRepository`: `providers()` (GET /provider → all[].{id,name,models{id,name,limits,modalities,cost}};
  fallback GET /config/providers), `agents()` (GET /agent, filter hidden, primary/all modes),
  `commands()` (GET /command), `mcpStatus()` (GET /mcp), `toolIds()` (GET /experimental/tool/ids, for H3 gating).
  Cache per profile in memory; refresh on profile switch + manual.
- Prompt additions: `PromptRequest` gains `model: ModelInput?`, `variant: String?`, `tools: Map<String,Boolean>?`
  (D3: H3 websearch toggle = `tools["webfetch"]=false` when off — verify tool id against /experimental/tool/ids
  at runtime, fall back to excluding nothing + note; memory toggle H5 = system-prompt injection skip, client-side).
- Stats: extend `DtoMap.message` callers — per-session totals computed in ChatViewModel from loaded
  messages (`step-finish` tokens/cost sums) + session.cost/tokens if server provides; context % =
  last assistant tokens vs selected model limit (provider map).

## 2. Thread UI (`:feature-chat`)

- Permission cards inline at the requesting turn (position: end of list while pending, like Claude):
  title/type/pattern chips + metadata filepath + Once / Always / Reject (doc 15 defaults preselected
  note: "auto-allow list would allow this" hint when applicable). After reply: card collapses to
  "allowed once ✓ / always / rejected" terminal line (grinev rule). Cross-session: cards show for the
  session open; other sessions' pending count surfaces as a badge on the sessions list (attention ids).
- Question cards: header + question + options (single → tap answers immediately; multi → toggle + Done;
  custom → text field when allowed; Cancel → reject). FIFO: newest replaces display, others queued count.
- Model+effort: top-bar chip (current model/variant) → bottom sheet: providers → models (search) →
  effort (none/low/medium/high/xhigh/max, static list per opencode config schema) → applies to next send
  + per-session memory (grapeot pattern). Favorites + recent (grinev pattern, local).
- Agent switch: chips row above composer (plan/ask/build + custom agents from /agent, hidden filtered).
  Sends `agent` per message.
- Commands: `/` in composer → autocomplete sheet (name + description) → tap appends `name + " "` or
  executes immediately if no args needed (spec: execute via POST /session/{id}/command {command, arguments};
  result renders as assistant turn). Custom + native listed together with source tag.
- Connectors (H6): overflow menu → Connectors screen: MCP server list + status (GET /mcp), toggle = P5 scope
  (view-only in P2 + note). Websearch/memory toggles as above-composer status row chips (doc 08 §7).
- Stats (H10 P2): chat header tap → sheet: session totals (in/out/reasoning, cache r/w, cost, context % bar),
  per-turn footers already present. Weekly → DEFERRED (§5).

## 3. Markdown renderer

- mikepenz `multiplatform-markdown-renderer` (`-m3` + `-code` modules): replaces MonoText; streaming via
  `rememberStreamingMarkdownState` + append (doc 08). Code blocks: language header + copy button.
  Tables, lists, links as tappable spans. Version pinned in catalog after resolve check.

## 4. Acceptance

1. Permission asked (live or simulated via unit-event) → card renders → Once/Always/Reject → terminal line;
   `permission.replied` from elsewhere removes the card.
2. Question asked → single-tap answers; multi-select + Done; custom text; cancel rejects.
3. Model sheet lists live server providers/models; pick + effort applies to next send (verify via OkHttp body).
4. Agent chips switch `agent` per send. `/` sheet lists commands; execute runs a turn.
5. Stats sheet shows session totals + context %; numbers match server cost/tokens.
6. Markdown: code fence → highlighted block + copy; table renders; links tappable.
7. Tests: DtoMap (permission/question parse), VM tests (reply/remove, model apply), MockWebServer
   (permission/question/command/provider paths + bodies). Screenshots: cards, sheets, markdown, stats.

## 5. Explicit non-goals / deferrals

- Weekly stats (H10-weekly): needs local persistence (Room) → P4 with push bridge store. DECISION recorded.
- MCP toggles, browser backend switch (P5). Voice (P3). Vim (H13 workstream). Widget (P4).
- `tools` gating exact webfetch id: runtime-resolved; if absent, H3 toggle injects "answer from chat only"
  system hint instead (fallback documented in code).

## 6. Review gate

Tests green · emulator screenshots (cards + sheets + markdown + stats) · live permission/question round-trip
if reproducible (else event-replay test) · grand-plan cross-check (H6–H10, H12, questions) · user review.
