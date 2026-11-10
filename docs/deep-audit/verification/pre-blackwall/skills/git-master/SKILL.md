1: ---
2: name: git-master
3: [CREDENTIAL-RELATED LINE OMITTED]
4: ---
5: 
6: # Git + `gh` (no MCP, no PAT)
7: 
8: [CREDENTIAL-RELATED LINE OMITTED]
9: 
10: ## Identity: ALWAYS UchaBokeria <ucha1bokeria@gmail.com>. NEVER opencode/agent/bot.
11: - Never `git config user.name|user.email`, never `--author`, never
12:   `Co-authored-by`/`Generated-by` trailers. Global config is already correct.
13: 
14: ## Commits (atomic, always)
15: - One logical change per commit. Split unrelated hunks (`git add -p`).
16: - Message: `type: short imperative summary` (feat/fix/refactor/docs/chore).
17: - Always `git status` + `git diff --stat` before committing; review the full
18:   diff before `push` / `pr create`.
19: 
20: ## Everyday
21: ```bash
22: gh pr create --fill --assignee @me        # open PR from branch
23: gh pr status && gh pr checks              # CI state
24: gh pr view --comments                     # review feedback
25: gh issue list --assignee @me              # my issues
26: gh repo clone owner/repo ~/dev/<name>
27: git log --oneline -15                     # recent history
28: git log -S'pattern' --oneline -- file     # history search (pickaxe)
29: git bisect start <bad> <good>             # find breaking commit
30: ```
31: 
32: ## Branches & surgery
33: - Feature branches off `dev` (this user's default branch, often NOT main).
34: - `dev` and any `*prod*` ref: no force-push, no rebase, no history rewrite.
35: - Parallel streams: git worktrees (see `using-git-worktrees`), one
36:   `COMPOSE_PROJECT_NAME` per stream for compose projects.
37: - Deep PR review: `greptile` MCP. Bulk GitHub code search: `gh_grep` MCP.
