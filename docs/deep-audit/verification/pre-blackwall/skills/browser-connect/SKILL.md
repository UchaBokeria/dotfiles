1: ---
2: name: browser-connect
3: description: Connect to a browser. Use BEFORE the first browser tool use in a session — runs the in-chat chooser once, then stays with the choice.
4: ---
5: 
6: # Browser connect (once per session)
7: 
8: If a browser was already chosen earlier in THIS conversation, keep using it
9: silently — never re-ask in the same session.
10: 
11: ## 1. Discover candidates (fast, parallel)- Read `~/.config/opencode/browser.json` (entries, `bridgeName` map).
12: - Port instances: `curl -s --max-time 5 http://127.0.0.1:<port>/json/version`.
13: - Live Chrome: `<name>_list_pages` (works = reachable; timeout = needs Allow).
14: - Bridge registrations: `curl -s http://127.0.0.1:9225/browsers` (friendly
15:   names extensions reported).
16: - Windows per port instance: `bun ~/.config/opencode/bin/chrome-windows.ts
17:   http://127.0.0.1:<port>` (groups tabs by window). Live autoConnect
18:   instance: tabs only, no window grouping (MCP limitation — say so).
19: 
20: ## 2. Ask in chat (question tool, single question, first browser task only)
21: Options:
22: - Each reachable browser: label + tab count (e.g. "Headless clone — 5 tabs").
23: - Each extra window (same profile, 2+ windows): "Live Chrome — Window 2 (3 tabs)".
24: - "Accept in Chrome" (browser-side choice).
25: 
26: ## 3a. Window chosen
27: `select_page` on one of that window's tabs first (focuses it for subsequent
28: `new_page` calls), then proceed. Note the window choice alongside the browser.
29: 
30: ## 3b. "Accept in Chrome" chosen
31: 1. `curl -X POST http://127.0.0.1:9225/pending -d '{"session":"<short-label>"}'`
32:    (label = date + topic, e.g. `sep17-github-triage`).
33: 2. Tell the user: "Click the opencode-connect extension icon in the browser
34:    you want, then Accept." (No extension yet? → install steps:
35:    `chrome://extensions` → Developer mode → Load unpacked →
36:    `~/.config/opencode/browser-extension`; set the friendly name in its popup.)
37: 3. Poll `GET /pending/<session>` every ~5s, up to 120s. On `accepted`:
38:    map the bridge name via `browser.json` `bridgeName`; if unmapped, ask once
39:    and store it. On timeout/expiry: fall back to step 2 options.
40: 4. Blackwall browsers register on blackwall's own bridge; query it over
41:    Tailscale (`http://<blackwall-ip>:9225/...`) the same way when relevant.
42: 
43: ## 4. During work (Claude parity)
44: - After opening tabs for a task: `POST /session-tabs
45:   {session, browser, tabs:[{url,title}]}` AND `POST /group
46:   {browser, session, requestId, urls, title, color}` — the extension groups
47:   them per session (blue = default), so parallel sessions don't collide.
48: - Working badge: `POST /mark {browser, session, requestId, urls}` stamps an
49:   "opencode: <session>" pill on matching tabs (empty urls = all tabs).
50: - Full tab list incl. `chrome://` pages (which MCP tools can't see):
51:   `GET /tabsnapshot/<bridgeName>` (extensions upload on their poll tick,
52:   ~30s stale max).
53: - Instant a11y for any page: `GET /a11y/<bridgeName>` (content-script
54:   snapshot of the active tab, ~30s stale max; MCP `take_snapshot` stays the
55:   live path).
56: - Gmail + OTP: the clone inherits the Google login with full Gmail access.
57:   Read verification codes yourself — open `https://mail.google.com`, search
58:   newest (`in:inbox newer_than:1h`), extract the code, type it where needed.
59:   Never ask the user for codes.
60: - Speed + stealth: `POST /netrules {browser, block:["images","media",
61:   "fonts"], stealth:true}` — extension applies declarativeNetRequest session
62:   rules (3–5x faster loads, normalized bot-facing headers). Clear with
63:   `{block:[],stealth:false}` when done. Side panel (`panel.html`) exposes
64:   the same toggles + pending accepts per browser.
65: - Profile picker: `GET /profiles` lists local Chrome profiles. When
66:   (re)cloning the `chrome-direct` profile, ask which source profile to copy
67:   (default: the main one).
68: 
69: ## 5. Driver discipline (CDP conflict rule)
70: - The extension is the SOLE debugger on tabs it drives (`cdp_*` tools).
71:   NEVER mix `chrome-devtools_*`/`chrome-direct_*` CDP tools on a tab the
72:   extension owns in the same task — Chrome allows one debugger per tab and
73:   will detach the other. Pick one driver per tab per task.
74: - `cdp_*` needs the extension live in that browser (reloaded with the
75:   `debugger` permission) and reachable hub (`/hub-browsers` shows it online).
76: 
77: ## 5. Remember
78: State the choice once ("Using Headless clone for this session.") and keep
79: using it. `/browser use <name>` overrides mid-session.
