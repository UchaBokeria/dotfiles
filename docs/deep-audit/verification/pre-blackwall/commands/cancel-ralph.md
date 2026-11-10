1: ---
2: description: Cancel the active Ralph Loop, if any.
3: ---
4: 
5: # Cancel Ralph Loop
6: 
7: Check for `.opencode/ralph-loop.local.md`. If missing, report "No active
8: Ralph loop found." Otherwise read its `iteration:` value, delete the file,
9: and report "Cancelled Ralph loop (was at iteration N)".
