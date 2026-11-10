1: ---
2: description: Start a Ralph Loop in the current session — iterate until done.
3: ---
4: 
5: # Ralph Loop
6: 
7: Initialize `.opencode/ralph-loop.local.md` with frontmatter
8: (`active: true`, `iteration: 1`, `max_iterations` default 10,
9: `completion_promise` from the arguments, `started_at`) followed by the task:
10: 
11: $ARGUMENTS
12: 
13: Then follow the `ralph-loop` skill protocol: work the task, and at the end of
14: each iteration re-read the state file, increment `iteration`, and continue
15: with the same prompt. Stop only at max iterations or on a truthful
16: `<promise>` completion. Never emit a false promise to escape.
