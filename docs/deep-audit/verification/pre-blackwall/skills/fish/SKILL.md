1: ---
2: name: fish
3: description: Fish shell specifics. The user's primary interactive shell is fish 4.8.1 — use fish syntax in commands, not bashisms.
4: ---
5: 
6: # Fish (primary shell; opencode `shell` is `/usr/bin/fish`)
7: 
8: ```fish
9: set -gx NAME value      # export (not export NAME=value)
10: set -gx PATH $PATH ~/.local/bin
11: string match -q '*.ts' $f; and echo yes; or echo no
12: test -f file; and echo exists
13: command -v foo          # not which/foo
14: for f in *.ts; echo $f; end
15: begin; ...; end         # grouping (braces don't exist)
16: ```
17: 
18: ## Gotchas
19: - `$VAR` never word-splits (unlike bash) — safer by default.
20: - `&&`/`||` work but `; and` / `; or` is idiomatic.
21: - No `[[ ]]`, no `$(( ))` (use `math`), no `function` output capture via `$()`
22:   — use `()` command substitution: `set x (cmd)`.
23: - Scripts with `#!/usr/bin/env bash` shebang stay bash — don't "fix" them.
24: - Non-interactive shells skip `config.fish` abbreviations; use full commands.
