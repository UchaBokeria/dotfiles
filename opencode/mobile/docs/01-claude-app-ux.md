# 01 — Claude mobile app UX autopsy

Source of truth: grand-plan.md. This doc is research input, not decisions.
Researched 2026-10-03 from primary Anthropic sources (code.claude.com, support.claude.com, Play listing).

## 1. App structure

- Single "Claude" app (Play `com.anthropic.claude`, 50M+, 4.6). No separate Code app.
- Bottom nav: chat home + **Code tab**. `claude.ai/code/new` starts a Code session.
- Code tab → session list, `code` → Projects → New project.

## 2. Session list

- Sessions found by name at Code tab / `claude.ai/code`.
- Remote Control sessions: computer icon + green online dot.
- Title precedence: explicit `--name` → `/rename` → last meaningful message → auto `host-adjective-noun`.
- Paid plans: RAG search over past chats (surfaced as tool calls, citations link back).
  - Scope: all non-project chats together; inside a project only that project's chats.
  - Incognito (ghost icon) excluded from search/memory.

## 3. Chat + input bar

- `+` menu: Add files/photos, Memory off-switch (must be set BEFORE first message, locked after).
- Mic = dictation (speech→text, text reply). Sound-wave = full-duplex voice mode.
- Model menu next to send: model + effort + thinking. Changeable anytime, applies from next response.
- Effort: Low/Medium/High/xHigh (Opus long agentic)/Max. Thinking toggle with timer + expandable section.
- Newer models force thinking on.

## 4. Attachments pipeline

- Types: PDF/DOCX/CSV/TXT/HTML/ODT/RTF/EPUB/JSON/XLSX (XLSX needs code exec). Images JPEG/PNG/GIF/WebP.
- Limits: 500MB/file, ≤20/chat, images ≤8000×8000, PDF ≤1000 pages (visual ≤100). Project files 30MB/file.
- Remote Control from phone: photos → visible to Claude + saved `~/.claude/uploads/`;
  other files → downloaded to host, passed as `@` refs; `@` autocompletes local project paths.
- Undownloadable → `[n of m attachments did not arrive]` note, message still delivered.

## 5. Voice

- Dictation: all plans, 12 languages (EN/FR/DE/HI/IT/JA/KO/PT/RU/ES/TR/UK, non-EN beta).
  Audio deleted after transcription, not used for training.
- Voice mode (beta, phone-first): hands-free (pause-detect) vs push-to-talk, voice+pace picker,
  model selector, mid-conversation code-switch, transcripts saved as text, connected tools usable.

## 6. Background / push / widget

- Phone never runs code. Cloud sessions survive phone close, persist across devices.
- Remote Control drives own machine (must stay awake, `tmux`/`screen`; sleep → auto-reconnect).
- Push triggers: Claude-initiated (task done, decision needed) or explicit ("notify me when…").
  Two `/config` toggles: `Push when Claude decides`, `Push when actions required`.
- Setup: same account/org, OS notify permission, open app once to refresh push token.
- Skipped while typing/focused; `CLAUDE_CLIENT_PRESENCE_FILE` extends presence suppression.
- Android battery optimization can delay push → app must guide exemption.
- Widget (Android 8.0+, resizable): spark = new chat, camera = new chat + camera,
  mic = new chat + dictation. All widget starts count toward usage.

## 7. Permission prompts

- Modes (dropdown by prompt box): cloud Accept-edits (default), Plan, Auto (org-gated).
  Self-started Remote Control: Manual, Accept edits, Plan — no Auto, no Bypass from app.
- Manual = approve edits/shell/network. acceptEdits = + file ops in scope.
  Plan = research only until plan approved. Auto = classifier reviews, ask-rules still prompt.
- Deny rules win everywhere. `rm` on critical paths, `AskUserQuestion`, org-`ask` connectors never auto-approved.
- Permission prompts + `AskUserQuestion` stay open until answered in-thread.
  Other dialogs expire after 5 min (`dialogExpiry`).
- Mobile command limits: `/plugin`, `/resume`, `/claude-api` are local-only.
  From app use arg-forms: `/model sonnet`, `/effort high`, `/compact`, `/context`, `/usage`, `/rename`, `/mcp`.

## 8. Projects vs chats

- Chats: single linear thread; optional incognito (unsaved) or memory-off (saved, unremembered).
- Classic Projects: workspace with own chats + knowledge + instructions + per-project memory.
  Paid RAG ~10× capacity. Search stays inside the project.
- New Projects beta (Code-first): coordinator conversation + parallel worker threads
  (own branch/PR each, auto-fix watching). Overview: Threads (Ready/Waiting/Working/Landing/Idle/Resolved),
  Library, Pull requests, Routines. `Work locally` runs one thread via Remote Control.
  Cap 200 new threads/day; idle costs nothing; Delete is permanent.
- Mobile creation: Code tab → Projects → New project (Name required, Goal + Context optional).

## 9. OS citizenship (why the bar is high)

- Android intents/share/clock/calendar/maps/Health Connect with native charts.
- Contextual least-privilege prompts with preview-before-send (Messages/Email need no perm via share+preview).
- Per-topic memory with edit/delete, per-chat kill switch, incognito, never-save IDs.
- Enterprise: SSO/SCIM, model allowlists, Trusted Devices (biometric/passkey step-up), audit logs.

## 10. Takeaways for opencode remote

- Copy: Code-tab session list with online dots, `+` attach menu, memory pre-first-message switch,
  model+effort picker by send button, presence-aware push, resizable 3-button widget,
  in-thread approvals that never silently expire, per-project memory scoping.
- Beat: opencode sessions run on OUR hardware (no cloud), so push needs our own bridge;
  permission model maps to opencode allow/ask/deny + remember — simpler, show it inline like Claude's cards.

## Sources

- https://code.claude.com/docs/en/mobile
- https://code.claude.com/docs/en/remote-control
- https://code.claude.com/docs/en/claude-projects
- https://code.claude.com/docs/en/permission-modes
- https://play.google.com/store/apps/details?id=com.anthropic.claude
- https://support.claude.com/en/articles/10534883-use-the-claude-widget-on-android
- https://support.claude.com/en/articles/11869629-use-claude-with-android-apps
- https://support.claude.com/en/articles/11101966-use-voice-mode
- https://support.claude.com/en/articles/10065434-use-dictation-on-claude-mobile
- https://support.claude.com/en/articles/8241126-upload-files-to-claude
- https://support.claude.com/en/articles/8664678-change-the-model-effort-and-thinking-settings
- https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context
- https://support.claude.com/en/articles/9517075-what-are-projects
