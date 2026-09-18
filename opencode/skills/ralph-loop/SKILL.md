---
name: ralph-loop
description: Long iterative autonomous work loop. Use when a task must be retried until verifiably done (migrations, bulk refactors, fix-all-linters). Trigger phrases: ralph loop, loop until done, keep iterating.
---

# Ralph Loop (opencode port)

Claude Code implements this with a Stop hook; opencode has no equivalent, so
the loop runs as an explicit in-session protocol:

## Start (`/ralph-loop`)
1. Write state to `.opencode/ralph-loop.local.md`:
   `active: true`, `iteration: 1`, `max_iterations: N` (default 10),
   `completion_promise: <single verifiable sentence>`, then the task prompt.
2. Work the task. At the end of every iteration, re-read the state file,
   increment `iteration`, and start the next pass with the SAME prompt.
3. Stop only when: `iteration > max_iterations`, or the completion promise is
   **completely and unequivocally true** — then output
   `<promise>TEXT</promise>` and delete the state file.
4. Never emit the promise to escape the loop. Monitor with
   `grep '^iteration:' .opencode/ralph-loop.local.md`.

## Cancel (`/cancel-ralph`)
If `.opencode/ralph-loop.local.md` is missing: "No active Ralph loop found."
Otherwise read `iteration:`, delete the file, report
"Cancelled Ralph loop (was at iteration N)".

## When to use / not use
- Use: verifiable end states (tests green, zero lint errors, N items migrated).
- Don't use: open-ended research, tasks needing user input mid-loop, or
  anything where each iteration costs money without bound — set a small max.
