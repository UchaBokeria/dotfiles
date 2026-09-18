---
name: browser-connect
description: Connect to a browser. Use BEFORE the first browser tool use in a session — runs the in-chat chooser once, then stays with the choice.
---

# Browser connect (once per session)

If a browser was already chosen earlier in THIS conversation, keep using it
silently — never re-ask in the same session.

## 1. Discover candidates (fast, parallel)- Read `~/.config/opencode/browser.json` (entries, `bridgeName` map).
- Port instances: `curl -s --max-time 5 http://127.0.0.1:<port>/json/version`.
- Live Chrome: `<name>_list_pages` (works = reachable; timeout = needs Allow).
- Bridge registrations: `curl -s http://127.0.0.1:9225/browsers` (friendly
  names extensions reported).
- Windows per port instance: `bun ~/.config/opencode/bin/chrome-windows.ts
  http://127.0.0.1:<port>` (groups tabs by window). Live autoConnect
  instance: tabs only, no window grouping (MCP limitation — say so).

## 2. Ask in chat (question tool, single question, first browser task only)
Options:
- Each reachable browser: label + tab count (e.g. "Headless clone — 5 tabs").
- Each extra window (same profile, 2+ windows): "Live Chrome — Window 2 (3 tabs)".
- "Accept in Chrome" (browser-side choice).

## 3a. Window chosen
`select_page` on one of that window's tabs first (focuses it for subsequent
`new_page` calls), then proceed. Note the window choice alongside the browser.

## 3b. "Accept in Chrome" chosen
1. `curl -X POST http://127.0.0.1:9225/pending -d '{"session":"<short-label>"}'`
   (label = date + topic, e.g. `sep17-github-triage`).
2. Tell the user: "Click the opencode-connect extension icon in the browser
   you want, then Accept." (No extension yet? → install steps:
   `chrome://extensions` → Developer mode → Load unpacked →
   `~/.config/opencode/browser-extension`; set the friendly name in its popup.)
3. Poll `GET /pending/<session>` every ~5s, up to 120s. On `accepted`:
   map the bridge name via `browser.json` `bridgeName`; if unmapped, ask once
   and store it. On timeout/expiry: fall back to step 2 options.
4. Blackwall browsers register on blackwall's own bridge; query it over
   Tailscale (`http://<blackwall-ip>:9225/...`) the same way when relevant.

## 4. During work (Claude parity)
- After opening tabs for a task: `POST /session-tabs
  {session, browser, tabs:[{url,title}]}` AND `POST /group
  {browser, session, requestId, urls, title, color}` — the extension groups
  them per session (blue = default), so parallel sessions don't collide.
- Working badge: `POST /mark {browser, session, requestId, urls}` stamps an
  "opencode: <session>" pill on matching tabs (empty urls = all tabs).
- Full tab list incl. `chrome://` pages (which MCP tools can't see):
  `GET /tabsnapshot/<bridgeName>` (extensions upload on their poll tick,
  ~30s stale max).
- Instant a11y for any page: `GET /a11y/<bridgeName>` (content-script
  snapshot of the active tab, ~30s stale max; MCP `take_snapshot` stays the
  live path).
- Gmail + OTP: the clone inherits the Google login with full Gmail access.
  Read verification codes yourself — open `https://mail.google.com`, search
  newest (`in:inbox newer_than:1h`), extract the code, type it where needed.
  Never ask the user for codes.
- Speed + stealth: `POST /netrules {browser, block:["images","media",
  "fonts"], stealth:true}` — extension applies declarativeNetRequest session
  rules (3–5x faster loads, normalized bot-facing headers). Clear with
  `{block:[],stealth:false}` when done. Side panel (`panel.html`) exposes
  the same toggles + pending accepts per browser.
- Profile picker: `GET /profiles` lists local Chrome profiles. When
  (re)cloning the `chrome-direct` profile, ask which source profile to copy
  (default: the main one).

## 5. Driver discipline (CDP conflict rule)
- The extension is the SOLE debugger on tabs it drives (`cdp_*` tools).
  NEVER mix `chrome-devtools_*`/`chrome-direct_*` CDP tools on a tab the
  extension owns in the same task — Chrome allows one debugger per tab and
  will detach the other. Pick one driver per tab per task.
- `cdp_*` needs the extension live in that browser (reloaded with the
  `debugger` permission) and reachable hub (`/hub-browsers` shows it online).

## 5. Remember
State the choice once ("Using Headless clone for this session.") and keep
using it. `/browser use <name>` overrides mid-session.
