1: ---
2: description: Browser picker with popup. Usage: /browser (choose) or /browser use <name> (switch directly).
3: ---
4: 
5: # Browser picker
6: 
7: Source of truth: `~/.config/opencode/browser.json` (`active` + entries).
8: 
9: Arguments: $ARGUMENTS
10: 
11: ## `use <name>` (direct switch, no popup)
12: 1. Validate `<name>` exists in `browser.json`.
13: 2. Probe it (port → curl `/json/version`; autoConnect → `<name>_list_pages`;
14:    `configured: false` → refuse). Unreachable → explain, do NOT switch.
15: 3. Read `browser.json` first, Write it back with new `active`, confirm.
16: 
17: ## No arguments → POPUP (required behavior)
18: Do NOT just print a table and stop. You MUST use the **question tool** so the
19: user gets the selectable popup:
20: 1. Read `browser.json`. Probe each entry quickly (same probes as above;
21:    keep it fast, 5s timeouts).
22: 2. Call question with one question ("Pick a browser"), options = each
23:    reachable browser (label + status detail, e.g. "Headless clone — Chrome/150,
24:    5 tabs"), plus "Accept in Chrome" (bridge pending flow per
25:    `browser-connect` skill).
26: 3. Apply the answer: direct switch (write `browser.json`), or run the accept
27:    flow. Confirm what was chosen and which tool prefix is now active.
