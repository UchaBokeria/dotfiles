---
name: shell
description: Non-interactive shell discipline. Applies to EVERY bash call — no TTY exists, hangs are fatal. Prefer native Read/Edit over shell file ops.
---

# Shell rules (no TTY, ever)

Every command must complete without human input. Default timeouts kill hangs.

| Instead of | Use |
|---|---|
| `npm init`, `apt install x` | `-y` flags (`npm init -y`) |
| `pip install x` | `pip install --no-input x` |
| `git commit`, `git merge X` | `-m "msg"`, `--no-edit` |
| `git add -p`, `rebase -i` | never — use `git add <paths>` |
| `ssh host` | `ssh -o BatchMode=yes host` |
| `rm x`, `unzip f.zip` | `rm -f x`, `unzip -o f.zip` |
| `vim/nano/less/man/python` (bare) | NEVER — use Read/Edit, `python3 -c` |

- Pagers off: prefer `--no-pager` (`git --no-pager`), pipe to `head`.
- Long runs: set explicit timeouts; background daemons via systemd, not `&`.
- Fish is the interactive shell, but opencode executes per-call — write
  POSIX-compatible snippets unless fish is guaranteed (see `fish` skill).
