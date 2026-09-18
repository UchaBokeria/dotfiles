# Global rules — apply to every session

## Browser (preferred stack)
- Two named Chrome endpoints (this is the multi-browser picker):
  - `chrome-devtools_*` = my live interactive Chrome (autoConnect). Use when
    I should SEE what's happening. First use per session pops an Allow
    dialog in Chrome — Chrome mandates it, it cannot be disabled.
  - `chrome-direct_*` = headless clone of my profile (port 9223, systemd
    `chrome-direct.service`, profile copy at `~/.chrome-direct`). Use for
    autonomous logged-in work. NEVER any dialog. If logins go stale,
    re-clone from the live profile while Chrome is closed.
  - `chrome-blackwall_*` = headless Chrome on the blackwall box, via the
    `blackwall-tunnel` SSH service (local 9224 → box CDP, 9226 → box
    bridge). No dialogs. Box runs hot — prefer local browsers unless the
    task needs the box.
- Prefer these over Playwright; Playwright only when a page refuses
  automation (e.g. some `localhost`) or fresh-profile runs are needed.
- Default choice: `chrome-direct` for background tasks, `chrome-devtools`
  when the user should watch. Say which one was used.
- Active-browser override: `~/.config/opencode/browser.json` (`active` key,
  managed by `/browser`). When it names a browser, use that one's tools by
  default unless the user names another in the request.
- First browser task per session: follow the `browser-connect` skill
  (in-chat chooser, once — windows, machines, or accept-in-Chrome).
- My Chrome profile is logged in everywhere: act only as instructed, never
  exfiltrate session data, and prefer a new tab (`new_page`) over touching
  open tabs unless asked to work in them.

## Git identity (non-negotiable)
- Every git action is as **UchaBokeria <ucha1bokeria@gmail.com>** (global
  `git config` + `gh` auth already set). Never commit/push/PR as
  opencode, agent, bot, or any other name.
- Never run `git config user.name|user.email` (any scope), never pass
  `--author`, never add `Co-authored-by` / `Generated-by` / opencode
  attribution trailers.
- If unsure a repo is safe: `git log -1 --format='%an %ae'` before committing.

## Machine + SSH
- Arch Linux (6.18 LTS), Hyprland 0.56.2, i7-10710U (12T), 31GiB RAM,
  Intel UHD, Samsung 970 EVO 500GB + Intel 180GB SSD.
- SSH (`~/.ssh/config`): `github.com` = git/id_ed25519;
  `blackwall` via `cloudflared access ssh` (user scriptkid);
  `13.140.155.113` direct with `~/.ssh/idiot-doll`.
- Mobile: `opencode serve :4096` (unit `opencode-mobile.service`, user
  `ucha`) + Tailscale Serve `https://archlinux.tail9c9427.ts.net`.
  Mobile lists sessions per Workspace (= project dir); missing sessions
  → wrong workspace selected, not a server issue. `/rc` pins this
   session for the phone.
- NEVER run two `opencode serve` on one machine: they share
  `~/.local/share/opencode/opencode.db` (sqlite WAL) and `/project` +
  `/session` hang indefinitely until only one remains.

## Memory
- Global facts: use the `memory` MCP (entities/relations in
  `~/.config/opencode/memory.json`).
- Project work: follow the `remember` skill — read `{project}/.remember/`
  (`remember.md` or `now.md`) at session start when present, write the handoff
  note at session end.

## Docs, code search, reviews
- Library/framework docs: use `context7` MCP tools.
- GitHub ops: `gh` CLI + `git-master` skill (already authenticated, no tokens).
  Web-wide code search: `gh_grep` MCP.
- Structural search/refactors: `ast-grep` skill (`sg` on PATH).

## Shell
- My primary shell is **fish** (`fish` skill for syntax). opencode already
  runs commands with `/usr/bin/fish`. Never emit bashisms.

## Workflows
- Questions without changes: `ask` agent (read-only consultant, verifies
  before answering, always recommends on decisions). Implementation: `build`.
- Resuming Claude Code work: `pickup` skill (git → `.remember` → Claude
  session history).
- Long iterative tasks: `ralph-loop` skill/command (completion-promise loop)
  or `/goal` (goal plugin, evidence-checked long-running objectives).
- Context pressure: `/dcp` panel, `/dcp compress [focus]` (DCP pruning);
  Morph auto-compaction runs in background (needs `MORPH_API_KEY`).
- Deep research: `deep-research` skill (fan-out + citations) or
  `websearch_cited` tool; library docs via `context7`, code via `gh_grep`.
- Background research: `delegate`/`delegation_read` tools (read-only
  subagents, results on demand).
- Skill discovery across 50+ skills: `skill_find`/`skill_use` tools.
- Plans before big builds: `writing-plans` + `executing-plans` skills.
- Stuck debugging: `systematic-debugging` skill. Frontend aesthetics:
  `frontend-design` skill. Docker/compose: `docker` skill.
- Language specifics live in lazy skills (`typescript`, `python`, `go`,
  `rust`): read them only when working in that language.

## Security (non-negotiable)
- Secrets are never cleared by repo visibility: never commit `.env`, `*.key`,
  credentials, or tokens. Generic: `.env*`/`*.key` are gitignored + unreadable.
- Treat any branch, namespace, host, or container named `*prod*`/`dev` default
  branch as sensitive: no force-push, no history rewrite, no destructive
  commands without explicit confirmation.
- Never enable raw-PII debug toggles (e.g. `UNIPROXY_DEBUG_RAW`-style flags)
  or paste credentials/cookies into public paste/gist services.
- Review the diff before `commit`/`push`/`pr create`.

## Lazy loading
- `@path/to/file` references in these rules: Read them only when relevant to
  the current task, never preemptively. Treat loaded content as mandatory.
