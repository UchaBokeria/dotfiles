---
description: Cancel the active Ralph Loop, if any.
---

# Cancel Ralph Loop

Check for `.opencode/ralph-loop.local.md`. If missing, report "No active
Ralph loop found." Otherwise read its `iteration:` value, delete the file,
and report "Cancelled Ralph loop (was at iteration N)".
