---
name: fish
description: Fish shell specifics. The user's primary interactive shell is fish 4.8.1 — use fish syntax in commands, not bashisms.
---

# Fish (primary shell; opencode `shell` is `/usr/bin/fish`)

```fish
set -gx NAME value      # export (not export NAME=value)
set -gx PATH $PATH ~/.local/bin
string match -q '*.ts' $f; and echo yes; or echo no
test -f file; and echo exists
command -v foo          # not which/foo
for f in *.ts; echo $f; end
begin; ...; end         # grouping (braces don't exist)
```

## Gotchas
- `$VAR` never word-splits (unlike bash) — safer by default.
- `&&`/`||` work but `; and` / `; or` is idiomatic.
- No `[[ ]]`, no `$(( ))` (use `math`), no `function` output capture via `$()`
  — use `()` command substitution: `set x (cmd)`.
- Scripts with `#!/usr/bin/env bash` shebang stay bash — don't "fix" them.
- Non-interactive shells skip `config.fish` abbreviations; use full commands.
