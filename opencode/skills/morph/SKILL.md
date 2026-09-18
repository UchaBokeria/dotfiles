---
name: morph
description: Morph Fast Apply and WarpGrep search. Use for fast large edits (morph_edit), agentic codebase search, or public-repo context without cloning. Needs MORPH_API_KEY.
---

# Morph (plugin tools)

Requires `MORPH_API_KEY` in the environment (`morphllm.com`). Without it,
these tools fail — fall back to native edit/grep.

- `morph_edit` — 10k+ tok/s edits. Prefer for large rewrites; use native
  `edit` for small precise changes.
- `warpgrep_codebase_search` — agentic multi-turn search (sub-6s). Use when
  `grep`/`ast-grep` need too many rounds.
- `warpgrep_github_search` — public repo context by `owner/repo`, no clone.
- Compaction runs automatically in the background (fast compressor); a toast
  announces it. It coexists with DCP — if summaries ever look double-
  compressed, prefer DCP's `/dcp compress` and say so in chat.
