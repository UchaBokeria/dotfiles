1: ---
2: name: ast-grep
3: description: Structural code search and rewriting. Use when grep is too dumb — find code by syntax shape (function calls, imports, patterns) across 25+ languages, or rewrite matches.
4: ---
5: 
6: # ast-grep (`ast-grep` 0.45.3, on PATH; `sg` alias works but prints a deprecation notice)
7: 
8: Pattern syntax: `$VAR` matches any single AST node, `$$$ARGS` matches multiple.
9: 
10: ```bash
11: ast-grep run -p 'console.log($$$ARGS)' --lang ts    # find calls
12: ast-grep run -p 'import $X from "lodash"' --lang ts -l      # list files
13: ast-grep run -p 'function $NAME($$$ARGS) { $$$BODY }' --lang js
14: ast-grep run -p 'requests.get($URL, $$$ARGS)' --lang py
15: ast-grep run -p 'fmt.Println($$$ARGS)' --lang go
16: ast-grep scan --config sgconfig.yml                         # project lint rules
17: ```
18: 
19: Rewrite: `ast-grep run -p 'a' -r 'b' --lang ts --update-all` (dry-run first without
20: `--update-all`). Rules in `sgconfig.yml` double as custom lint.
21: 
22: ## When to use / not use
23: - Use: refactors ("all callers of X"), framework migrations, finding patterns
24:   regex can't express (nested calls, specific imports), bulk renames.
25: - Don't use: plain text search (`rg` is faster), single-file edits (Read/Edit).
26: - Combine: `sg` to locate → `read` to inspect → `edit` to change.
