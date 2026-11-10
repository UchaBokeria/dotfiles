1: ---
2: name: ralph-loop
3: description: Long iterative autonomous work loop. Use when a task must be retried until verifiably done (migrations, bulk refactors, fix-all-linters). Trigger phrases: ralph loop, loop until done, keep iterating.
4: ---
5: 
6: # Ralph Loop (opencode port)
7: 
8: Claude Code implements this with a Stop hook; opencode has no equivalent, so
9: the loop runs as an explicit in-session protocol:
10: 
11: ## Start (`/ralph-loop`)
12: 1. Write state to `.opencode/ralph-loop.local.md`:
13:    `active: true`, `iteration: 1`, `max_iterations: N` (default 10),
14:    `completion_promise: <single verifiable sentence>`, then the task prompt.
15: 2. Work the task. At the end of every iteration, re-read the state file,
16: [CREDENTIAL-RELATED LINE OMITTED]
17: 3. Stop only when: `iteration > max_iterations`, or the completion promise is
18:    **completely and unequivocally true** — then output
19:    `<promise>TEXT</promise>` and delete the state file.
20: 4. Never emit the promise to escape the loop. Monitor with
21:    `grep '^iteration:' .opencode/ralph-loop.local.md`.
22: 
23: ## Cancel (`/cancel-ralph`)
24: If `.opencode/ralph-loop.local.md` is missing: "No active Ralph loop found."
25: Otherwise read `iteration:`, delete the file, report
26: "Cancelled Ralph loop (was at iteration N)".
27: 
28: ## When to use / not use
29: - Use: verifiable end states (tests green, zero lint errors, N items migrated).
30: - Don't use: open-ended research, tasks needing user input mid-loop, or
31:   anything where each iteration costs money without bound — set a small max.
