# 02 — AI mobile app patterns (ChatGPT / Gemini / generic)

Source of truth: grand-plan.md. Research input, not decisions.
Covers the "ai mobile app" brief item: what good AI apps share, beyond Claude specifics.

## 1. Universal chat-app skeleton

- Three-pane information architecture: sidebar/session drawer → thread → composer.
  Mobile collapses to one pane with bottom-sheet drawer + back-stack navigation.
- Session list rows: title + timestamp + status dot (idle/working/error). Search field pinned at top.
- Composer anatomy (left→right): `+` attach → text field (multiline, grows to ~5 lines) →
  mic → send/stop morphing button. Model/ratio chip above or beside send.
- Streaming: tokens append in place; stop button replaces send while busy; auto-scroll
  with "jump to latest" FAB when user scrolls up (see grapeot PRD: 60% of time is reading).

## 2. Message rendering rules

- Markdown first-class: headings, lists, tables, code fences with language header + copy button,
  inline code chips, links as tappable spans. Render incrementally (streaming tail re-parse only).
- Tool/activity cards: collapsible rows per tool call (pending → running → done/error),
  expandable diff/patch views, todo checklists with live check-off.
- Reasoning blocks: collapsed by default with timer ("thought for 12s"), expandable.
- Cost/token footer per turn: small muted line (input/output/cached tokens + $) — matches H10 stats.
- Error states render INLINE (model failure inside 200 response): red card with retry button,
  never a toast-only failure.

## 3. Sessions lifecycle patterns

- New chat is instant (no modal); title backfills from first exchange. Explicit rename via long-press.
- Fork/branch: long-press a message → "branch from here". Archive vs delete separated
  (archive hides, delete destroys + confirms).
- Cross-device continuity: server is source of truth; client reconciles on foreground
  (status poll + message fetch). Optimistic send with rollback on failure.
- Temporary/incognito: one toggle at creation; temp chats excluded from search/history/export.

## 4. Input modalities

- Dictation (speech→text into composer) vs voice mode (full duplex conversation) — offer both,
  like Claude. Dictation is cheap (platform SpeechRecognizer); voice mode is a workstream.
- Attach: photo picker (no storage perm), camera (CameraX), file picker (SAF, scoped).
  Show staged attachments as chips above composer with remove ×; compress images by setting.
- Slash commands: `/` in composer opens autocomplete sheet over keyboard; custom commands listed with descriptions.

## 5. Notifications done right

- Reply notifications: HIGH channel, direct-reply action + mark-read action.
- Approval stalls: separate channel, approve/deny inline actions on the notification itself.
- Quiet hours setting + per-session mute. Never badge the launcher for agent-typing noise.
- Presence-awareness: suppress push for the session currently open on screen.

## 6. Anti-patterns seen in wrapper apps

- Fire-and-forget bubbles with no tool visibility (user can't see what agent did).
- Blocking HTTP send with spinner (dies on radio drop; use async + SSE).
- Hidden history / no export / no delete (trust killer).
- Blanket permission grabs at install (storage+contacts for a chat app).
- WebView-wrapped website shipped as "app" (no offline, no push, no widget, slow).
- No empty states, no offline states, no retry affordance — just spinners.

## 7. Takeaways for opencode remote

- Skeleton: drawer list + thread + composer is non-negotiable; add agent/model chips (opencode-specific).
- Inline tool cards + reasoning collapse + per-turn cost footer = the quality bar.
- Async send + reconcile is the ONLY send path for long turns (matches S3/H1).
- Temp mode, per-session mute, quiet hours all ship (F5 settings).
