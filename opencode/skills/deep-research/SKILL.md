---
name: deep-research
description: Thorough web research procedure. Use for deep dives, comparisons, library vetting, or anything needing cited, current sources.
---

# Deep research procedure

Built-in `websearch` is shallow single-shot. For depth, fan out:

1. **Rephrase** the question 3–5 ways (synonyms, version numbers, `site:github.com`, error text).
2. **Parallel sweep**: dispatch one `task` explore subagent per phrasing
   (they share nothing, run concurrently). Each returns: answer + URLs.
3. **Docs-first**: for libraries, prefer `context7` over blogs; for code
   usage, `gh_grep` over tutorials.
4. **Cite everything**: inline `[Title](URL)` per claim; distrust undated
   pages for fast-moving topics (check publish date).
5. **Synthesize**: dedupe, flag contradictions explicitly, recommend.
6. If a claim matters and sources conflict, `webfetch` the primary source
   (docs, repo, changelog) and trust it over aggregators.
