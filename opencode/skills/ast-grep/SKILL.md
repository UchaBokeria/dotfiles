---
name: ast-grep
description: Structural code search and rewriting. Use when grep is too dumb — find code by syntax shape (function calls, imports, patterns) across 25+ languages, or rewrite matches.
---

# ast-grep (`ast-grep` 0.45.3, on PATH; `sg` alias works but prints a deprecation notice)

Pattern syntax: `$VAR` matches any single AST node, `$$$ARGS` matches multiple.

```bash
ast-grep run -p 'console.log($$$ARGS)' --lang ts    # find calls
ast-grep run -p 'import $X from "lodash"' --lang ts -l      # list files
ast-grep run -p 'function $NAME($$$ARGS) { $$$BODY }' --lang js
ast-grep run -p 'requests.get($URL, $$$ARGS)' --lang py
ast-grep run -p 'fmt.Println($$$ARGS)' --lang go
ast-grep scan --config sgconfig.yml                         # project lint rules
```

Rewrite: `ast-grep run -p 'a' -r 'b' --lang ts --update-all` (dry-run first without
`--update-all`). Rules in `sgconfig.yml` double as custom lint.

## When to use / not use
- Use: refactors ("all callers of X"), framework migrations, finding patterns
  regex can't express (nested calls, specific imports), bulk renames.
- Don't use: plain text search (`rg` is faster), single-file edits (Read/Edit).
- Combine: `sg` to locate → `read` to inspect → `edit` to change.
