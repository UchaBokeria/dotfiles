1: ---
2: name: pickup
3: description: Resume work started in Claude Code. Use when the user says "continue from Claude", "pick up where I left off", or opens a project with Claude history but no .remember handoff.
4: ---
5: 
6: # Picking up from Claude Code
7: 
8: Gather state in this order, cheapest first. Stop as soon as the picture is
9: clear — don't read everything.
10: 
11: 1. **Git**: `git status`, `git log --oneline -10`, `git branch --show-current`.
12:    Uncommitted changes + recent commits usually tell 80% of the story.
13: 2. **Project memory**: `{project}/.remember/` (`remember.md` or `now.md`),
14:    then `AGENTS.md` / `CLAUDE.md` in the project root.
15: 3. **Claude sessions** (only if 1–2 leave gaps): dir
16:    `~/.claude/projects/<slug>/` where slug is the project path with leading
17:    `-` and `/` → `-` (e.g. `-home-scriptkid-dev-cloud`). Take the newest
18:    `*.jsonl` (`ls -t`), read the tail: `user` lines are prompts, `assistant`
19:    text + tool uses show what was tried. Session files can be ~MBs — tail,
20:    don't dump.
21: 4. **Prompt history**: `~/.claude/history.jsonl` (global, newest last) only
22:    if the project dir has no sessions.
23: 
24: Then report: what was being done, what's done vs pending, blockers/gotchas,
25: and propose the next step. If a `.remember` handoff exists, switch to the
26: `remember` skill workflow from here on.
