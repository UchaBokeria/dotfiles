---
name: browser-connect
description: Connect to a browser. Use BEFORE the first browser tool use in a session — runs the in-chat chooser once, then stays with the choice.
---

# Browser connect (once per session)

If a browser was already chosen earlier in THIS conversation, keep using it
silently — never re-ask in the same session.

The extension (`cdp_*` tools) is the DEFAULT driver. `chrome-direct_*` is
fallback ONLY on explicit user request — never switch silently.

## 1. Discover candidates (fast, parallel)- Read `~/.config/opencode/browser.json` (entries, `bridgeName` map).
- Extension path: `curl -s http://127.0.0.1:9225/hub-browsers` (online names).
- Port instances: `curl -s --max-time 5 http://127.0.0.1:<port>/json/version`
  (chrome-direct = explicit-request fallback only).
- NEVER probe `chrome-devtools_*` — that path is disabled (Allow dialog).

## 2. Ask in chat (question tool, single question, first browser task only)
Options:
- Extension browsers (one option per online bridge name).
- `chrome-direct` headless ONLY if the user named it — otherwise omit it.
- If no extension browser is online: ask whether to wait for the user to
  open the paired browser, or (explicitly) use `chrome-direct` headless.

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
  NEVER mix `chrome-direct_*` CDP tools on a tab the extension owns in the
  same task — Chrome allows one debugger per tab and will detach the other.
  Pick one driver per tab per task.
- `cdp_*` needs the extension live in that browser (reloaded with the
  `debugger` permission) and reachable hub (`/hub-browsers` shows it online).
- Failure protocol: if the extension path is unreachable, STOP and ask via
  the question tool (offer headless or waiting). NEVER fall back silently.

## 5. Remember
State the choice once ("Using Headless clone for this session.") and keep
using it. `/browser use <name>` overrides mid-session.

## 6. Tool-truth rule (never improvise the hub protocol)
- The ONLY browser-driving tools are the MCP functions: `cdp_tabs`,
  `cdp_navigate`, `cdp_snapshot`, `cdp_screenshot`, `cdp_evaluate`,
  `cdp_click`, `cdp_fill`, `cdp_type`, `cdp_press`, `cdp_console`,
  `cdp_network`, `cdp_close_tab`, `cdp_select_tab`, `cdp_upload`,
  `cdp_scroll`, `cdp_hover`, `cdp_select`, `cdp_dialog`, `cdp_wait`,
  `cdp_record`, `cdp_release_tab`.
- Bridge HTTP endpoints (`/tabsnapshot/`, `/a11y/`, `/pending`,
  `/session-tabs`, `/group`, `/mark`, `/netrules`, `/record`) are
  READ/annotate helpers only. They NEVER substitute for driving tools.
- If `cdp_*` functions are absent from your tool list: STOP, do NOT
  improvise with raw WebSocket/bridge calls, do NOT claim partial
  capability. Tell the user verbatim: "Browser driver tools (cdp_*) are
  not loaded in this session — restart opencode or switch to build agent."
- NEVER "activate by driving the hub protocol directly" — bin/cdp-mcp.ts
  is adapter source code, not a runtime you re-implement mid-session.
