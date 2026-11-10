1: ---
2: name: worktree
3: description: Isolated git worktree workflows. Use ONLY when asked for parallel streams, risky refactors, or reviewing a PR in isolation — never by default.
4: ---
5: 
6: # Worktrees (on-demand only)
7: 
8: The `opencode-worktree` TUI is installed globally. Prefer plain git unless
9: parallel isolation is genuinely needed.
10: 
11: ```bash
12: opencode-worktree                  # visual manager (needs a git repo)
13: git worktree add ../proj-<topic> -b <branch>   # manual, same result
14: git worktree list && git worktree remove --force ../proj-<topic>  # cleanup
15: ```
16: 
17: ## Rules
18: - One `COMPOSE_PROJECT_NAME` per worktree for compose projects; never stop
19:   shared services (see `docker` skill).
20: - Off the default branch from `dev` unless told otherwise; push branches,
21:   never commit directly to worktree checkouts of `dev`.
22: - Remove the worktree when merged. Stale worktrees rot fast — list and prune.
