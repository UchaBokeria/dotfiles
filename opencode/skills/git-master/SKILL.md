---
name: git-master
description: Git and GitHub operations. MUST USE for any git work — commits, branches, rebases, PRs, history search. Authenticated via gh CLI (UchaBokeria), no tokens needed.
---

# Git + `gh` (no MCP, no PAT)

`gh` is logged in. Never ask for credentials; never invent a token flow.

## Identity: ALWAYS UchaBokeria <ucha1bokeria@gmail.com>. NEVER opencode/agent/bot.
- Never `git config user.name|user.email`, never `--author`, never
  `Co-authored-by`/`Generated-by` trailers. Global config is already correct.

## Commits (atomic, always)
- One logical change per commit. Split unrelated hunks (`git add -p`).
- Message: `type: short imperative summary` (feat/fix/refactor/docs/chore).
- Always `git status` + `git diff --stat` before committing; review the full
  diff before `push` / `pr create`.

## Everyday
```bash
gh pr create --fill --assignee @me        # open PR from branch
gh pr status && gh pr checks              # CI state
gh pr view --comments                     # review feedback
gh issue list --assignee @me              # my issues
gh repo clone owner/repo ~/dev/<name>
git log --oneline -15                     # recent history
git log -S'pattern' --oneline -- file     # history search (pickaxe)
git bisect start <bad> <good>             # find breaking commit
```

## Branches & surgery
- Feature branches off `dev` (this user's default branch, often NOT main).
- `dev` and any `*prod*` ref: no force-push, no rebase, no history rewrite.
- Parallel streams: git worktrees (see `using-git-worktrees`), one
  `COMPOSE_PROJECT_NAME` per stream for compose projects.
- Deep PR review: `greptile` MCP. Bulk GitHub code search: `gh_grep` MCP.
