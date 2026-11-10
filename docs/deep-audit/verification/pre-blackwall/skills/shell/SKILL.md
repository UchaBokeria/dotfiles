1: ---
2: name: shell
3: description: Non-interactive shell discipline. Applies to EVERY bash call — no TTY exists, hangs are fatal. Prefer native Read/Edit over shell file ops.
4: ---
5: 
6: # Shell rules (no TTY, ever)
7: 
8: Every command must complete without human input. Default timeouts kill hangs.
9: 
10: | Instead of | Use |
11: |---|---|
12: | `npm init`, `apt install x` | `-y` flags (`npm init -y`) |
13: | `pip install x` | `pip install --no-input x` |
14: | `git commit`, `git merge X` | `-m "msg"`, `--no-edit` |
15: | `git add -p`, `rebase -i` | never — use `git add <paths>` |
16: | `ssh host` | `ssh -o BatchMode=yes host` |
17: | `rm x`, `unzip f.zip` | `rm -f x`, `unzip -o f.zip` |
18: | `vim/nano/less/man/python` (bare) | NEVER — use Read/Edit, `python3 -c` |
19: 
20: - Pagers off: prefer `--no-pager` (`git --no-pager`), pipe to `head`.
21: - Long runs: set explicit timeouts; background daemons via systemd, not `&`.
22: - Fish is the interactive shell, but opencode executes per-call — write
23:   POSIX-compatible snippets unless fish is guaranteed (see `fish` skill).
