---
name: pickup
description: Resume work started in Claude Code. Use when the user says "continue from Claude", "pick up where I left off", or opens a project with Claude history but no .remember handoff.
---

# Picking up from Claude Code

Gather state in this order, cheapest first. Stop as soon as the picture is
clear — don't read everything.

1. **Git**: `git status`, `git log --oneline -10`, `git branch --show-current`.
   Uncommitted changes + recent commits usually tell 80% of the story.
2. **Project memory**: `{project}/.remember/` (`remember.md` or `now.md`),
   then `AGENTS.md` / `CLAUDE.md` in the project root.
3. **Claude sessions** (only if 1–2 leave gaps): dir
   `~/.claude/projects/<slug>/` where slug is the project path with leading
   `-` and `/` → `-` (e.g. `-home-scriptkid-dev-cloud`). Take the newest
   `*.jsonl` (`ls -t`), read the tail: `user` lines are prompts, `assistant`
   text + tool uses show what was tried. Session files can be ~MBs — tail,
   don't dump.
4. **Prompt history**: `~/.claude/history.jsonl` (global, newest last) only
   if the project dir has no sessions.

Then report: what was being done, what's done vs pending, blockers/gotchas,
and propose the next step. If a `.remember` handoff exists, switch to the
`remember` skill workflow from here on.
