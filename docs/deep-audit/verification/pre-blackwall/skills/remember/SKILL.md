1: ---
2: name: remember
3: description: Save session state for clean continuation next session.
4: allowed-tools: Read, Write
5: ---
6: 
7: Write a handoff note so the next session can continue cleanly. Use your knowledge of the current session — you were here. Write in first person ("I").
8: 
9: **Path:** Use the path from the most recent `=== HANDOFF ===` block in this session's context (e.g., `Write next handoff to: /home/user/.remember/myproject-slug/remember.md`). If no `=== HANDOFF ===` block is present, fall back to `{project_root}/.remember/remember.md`. This is at the PROJECT ROOT, NOT relative to this skill file.
10: 
11: **If the file already exists, Read it first before Writing.** The Write tool enforces a read-before-write check on existing files; without a prior Read, the first Write call will fail with "File has not been read yet." A 1-line Read is enough to satisfy the check.
12: 
13: Format:
14: 
15: ```
16: # Handoff
17: 
18: ## State
19: {What's done, what's not. Files, MRs, decisions. 2-4 lines max.}
20: 
21: ## Next
22: {What to pick up. Priority order. 1-3 items.}
23: 
24: ## Context
25: {Non-obvious gotchas, blockers, preferences from this session. Skip if nothing.}
26: ```
27: 
28: Rules:
29: 
30: - Under 20 lines total
31: - Specific: file paths, MR numbers, branch names
32: - Forward-looking — the next session doesn't care about the journey
33: - If nothing meaningful to hand off, write: "No active work."
34: 
35: Say "Saved." when done — nothing else.
