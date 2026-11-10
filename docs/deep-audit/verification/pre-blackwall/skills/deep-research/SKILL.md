1: ---
2: name: deep-research
3: description: Thorough web research procedure. Use for deep dives, comparisons, library vetting, or anything needing cited, current sources.
4: ---
5: 
6: # Deep research procedure
7: 
8: Built-in `websearch` is shallow single-shot. For depth, fan out:
9: 
10: 1. **Rephrase** the question 3–5 ways (synonyms, version numbers, `site:github.com`, error text).
11: 2. **Parallel sweep**: dispatch one `task` explore subagent per phrasing
12:    (they share nothing, run concurrently). Each returns: answer + URLs.
13: 3. **Docs-first**: for libraries, prefer `context7` over blogs; for code
14:    usage, `gh_grep` over tutorials.
15: 4. **Cite everything**: inline `[Title](URL)` per claim; distrust undated
16:    pages for fast-moving topics (check publish date).
17: 5. **Synthesize**: dedupe, flag contradictions explicitly, recommend.
18: 6. If a claim matters and sources conflict, `webfetch` the primary source
19:    (docs, repo, changelog) and trust it over aggregators.
