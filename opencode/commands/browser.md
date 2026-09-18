---
description: Browser picker with popup. Usage: /browser (choose) or /browser use <name> (switch directly).
---

# Browser picker

Source of truth: `~/.config/opencode/browser.json` (`active` + entries).

Arguments: $ARGUMENTS

## `use <name>` (direct switch, no popup)
1. Validate `<name>` exists in `browser.json`.
2. Probe it (port → curl `/json/version`; autoConnect → `<name>_list_pages`;
   `configured: false` → refuse). Unreachable → explain, do NOT switch.
3. Read `browser.json` first, Write it back with new `active`, confirm.

## No arguments → POPUP (required behavior)
Do NOT just print a table and stop. You MUST use the **question tool** so the
user gets the selectable popup:
1. Read `browser.json`. Probe each entry quickly (same probes as above;
   keep it fast, 5s timeouts).
2. Call question with one question ("Pick a browser"), options = each
   reachable browser (label + status detail, e.g. "Headless clone — Chrome/150,
   5 tabs"), plus "Accept in Chrome" (bridge pending flow per
   `browser-connect` skill).
3. Apply the answer: direct switch (write `browser.json`), or run the accept
   flow. Confirm what was chosen and which tool prefix is now active.
