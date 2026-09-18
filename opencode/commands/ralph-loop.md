---
description: Start a Ralph Loop in the current session — iterate until done.
---

# Ralph Loop

Initialize `.opencode/ralph-loop.local.md` with frontmatter
(`active: true`, `iteration: 1`, `max_iterations` default 10,
`completion_promise` from the arguments, `started_at`) followed by the task:

$ARGUMENTS

Then follow the `ralph-loop` skill protocol: work the task, and at the end of
each iteration re-read the state file, increment `iteration`, and continue
with the same prompt. Stop only at max iterations or on a truthful
`<promise>` completion. Never emit a false promise to escape.
