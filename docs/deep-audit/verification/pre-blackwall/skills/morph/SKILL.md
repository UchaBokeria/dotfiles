1: ---
2: name: morph
3: [CREDENTIAL-RELATED LINE OMITTED]
4: ---
5: 
6: # Morph (plugin tools)
7: 
8: [CREDENTIAL-RELATED LINE OMITTED]
9: these tools fail — fall back to native edit/grep.
10: 
11: - `morph_edit` — 10k+ tok/s edits. Prefer for large rewrites; use native
12:   `edit` for small precise changes.
13: - `warpgrep_codebase_search` — agentic multi-turn search (sub-6s). Use when
14:   `grep`/`ast-grep` need too many rounds.
15: - `warpgrep_github_search` — public repo context by `owner/repo`, no clone.
16: - Compaction runs automatically in the background (fast compressor); a toast
17:   announces it. It coexists with DCP — if summaries ever look double-
18:   compressed, prefer DCP's `/dcp compress` and say so in chat.
