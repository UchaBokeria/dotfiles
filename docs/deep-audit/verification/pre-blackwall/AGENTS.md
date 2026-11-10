1: # Global rules — apply to every session
2: 
3: ## Browser (preferred stack)
4: - Two named Chrome endpoints (this is the multi-browser picker):
5:   - `chrome-devtools_*` = my live interactive Chrome (autoConnect). Use when
6:     I should SEE what's happening. First use per session pops an Allow
7:     dialog in Chrome — Chrome mandates it, it cannot be disabled.
8:   - `chrome-direct_*` = headless clone of my profile (port 9223, systemd
9:     `chrome-direct.service`, profile copy at `~/.chrome-direct`). Use for
10:     autonomous logged-in work. NEVER any dialog. If logins go stale,
11:     re-clone from the live profile while Chrome is closed.
12:   - `chrome-blackwall_*` = headless Chrome on the blackwall box, via the
13:     `blackwall-tunnel` SSH service (local 9224 → box CDP, 9226 → box
14:     bridge). No dialogs. Box runs hot — prefer local browsers unless the
15:     task needs the box.
16: - Prefer these over Playwright; Playwright only when a page refuses
17:   automation (e.g. some `localhost`) or fresh-profile runs are needed.
18: - Default choice: `chrome-direct` for background tasks, `chrome-devtools`
19:   when the user should watch. Say which one was used.
20: - Active-browser override: `~/.config/opencode/browser.json` (`active` key,
21:   managed by `/browser`). When it names a browser, use that one's tools by
22:   default unless the user names another in the request.
23: - First browser task per session: follow the `browser-connect` skill
24:   (in-chat chooser, once — windows, machines, or accept-in-Chrome).
25: - My Chrome profile is logged in everywhere: act only as instructed, never
26:   exfiltrate session data, and prefer a new tab (`new_page`) over touching
27:   open tabs unless asked to work in them.
28: 
29: ## Git identity (non-negotiable)
30: - Every git action is as **UchaBokeria <ucha1bokeria@gmail.com>** (global
31:   `git config` + `gh` auth already set). Never commit/push/PR as
32:   opencode, agent, bot, or any other name.
33: [CREDENTIAL-RELATED LINE OMITTED]
34:   `--author`, never add `Co-authored-by` / `Generated-by` / opencode
35:   attribution trailers.
36: - If unsure a repo is safe: `git log -1 --format='%an %ae'` before committing.
37: 
38: ## Machine + SSH
39: - Arch Linux (6.18 LTS), Hyprland 0.56.2, i7-10710U (12T), 31GiB RAM,
40:   Intel UHD, Samsung 970 EVO 500GB + Intel 180GB SSD.
41: - SSH (`~/.ssh/config`): `github.com` = git/id_ed25519;
42:   `blackwall` via `cloudflared access ssh` (user scriptkid);
43:   `13.140.155.113` direct with `~/.ssh/idiot-doll`.
44: - Mobile: `opencode serve :4096` (unit `opencode-mobile.service`, user
45:   `ucha`) + Tailscale Serve `https://archlinux.tail9c9427.ts.net`.
46:   Mobile lists sessions per Workspace (= project dir); missing sessions
47:   → wrong workspace selected, not a server issue. `/rc` pins this
48:    session for the phone.
49: - NEVER run two `opencode serve` on one machine: they share
50:   `~/.local/share/opencode/opencode.db` (sqlite WAL) and `/project` +
51:   `/session` hang indefinitely until only one remains.
52: 
53: ## Memory
54: - Global facts: use the `memory` MCP (entities/relations in
55:   `~/.config/opencode/memory.json`).
56: - Project work: follow the `remember` skill — read `{project}/.remember/`
57:   (`remember.md` or `now.md`) at session start when present, write the handoff
58:   note at session end.
59: 
60: ## Docs, code search, reviews
61: - Library/framework docs: use `context7` MCP tools.
62: [CREDENTIAL-RELATED LINE OMITTED]
63:   Web-wide code search: `gh_grep` MCP.
64: - Structural search/refactors: `ast-grep` skill (`sg` on PATH).
65: 
66: ## Shell
67: - My primary shell is **fish** (`fish` skill for syntax). opencode already
68:   runs commands with `/usr/bin/fish`. Never emit bashisms.
69: 
70: ## Workflows
71: - Questions without changes: `ask` agent (read-only consultant, verifies
72:   before answering, always recommends on decisions). Implementation: `build`.
73: - Resuming Claude Code work: `pickup` skill (git → `.remember` → Claude
74:   session history).
75: - Long iterative tasks: `ralph-loop` skill/command (completion-promise loop)
76:   or `/goal` (goal plugin, evidence-checked long-running objectives).
77: - Context pressure: `/dcp` panel, `/dcp compress [focus]` (DCP pruning);
78: [CREDENTIAL-RELATED LINE OMITTED]
79: - Deep research: `deep-research` skill (fan-out + citations) or
80:   `websearch_cited` tool; library docs via `context7`, code via `gh_grep`.
81: - Background research: `delegate`/`delegation_read` tools (read-only
82:   subagents, results on demand).
83: - Skill discovery across 50+ skills: `skill_find`/`skill_use` tools.
84: - Plans before big builds: `writing-plans` + `executing-plans` skills.
85: - Stuck debugging: `systematic-debugging` skill. Frontend aesthetics:
86:   `frontend-design` skill. Docker/compose: `docker` skill.
87: - Language specifics live in lazy skills (`typescript`, `python`, `go`,
88:   `rust`): read them only when working in that language.
89: 
90: ## Security (non-negotiable)
91: [CREDENTIAL-RELATED LINE OMITTED]
92: [CREDENTIAL-RELATED LINE OMITTED]
93: - Treat any branch, namespace, host, or container named `*prod*`/`dev` default
94:   branch as sensitive: no force-push, no history rewrite, no destructive
95:   commands without explicit confirmation.
96: - Never enable raw-PII debug toggles (e.g. `UNIPROXY_DEBUG_RAW`-style flags)
97:   or paste credentials/cookies into public paste/gist services.
98: - Review the diff before `commit`/`push`/`pr create`.
99: 
100: ## Lazy loading
101: - `@path/to/file` references in these rules: Read them only when relevant to
102:   the current task, never preemptively. Treat loaded content as mandatory.
