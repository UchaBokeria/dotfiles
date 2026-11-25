# Spec: `scripts/blackwall-clone` — 1:1 machine clone layer

Repo: /home/scriptkid/.config/.dotfiles/blackwall (branch nuc). Read first:
docs/installation.md, installer/data/README.md, installer/data/packages.toml (format of groups),
scripts/link-bin, docs/cheatsheet.md (style), theme/run-tests (what the suite enforces about scripts).

The installer (`./install`) reproduces the PUBLIC rice. This script carries everything else so a
fresh machine ends up identical: extra packages, private state, repos, and a list of what must be
re-authenticated by hand. Single Python 3 file, stdlib only, executable, `#!/usr/bin/env python3`.
Encryption: `gpg --symmetric --cipher-algo AES256` (gpg is already on every Arch install; no `age`).

## Subcommands

### `blackwall-clone inventory [--out FILE]`
Writes TOML (hand-written emitter, stdlib has no TOML writer) describing this machine:
- `[packages] native` = `pacman -Qqen`, `foreign` = `pacman -Qqem`, each MINUS every name already in
  installer/data/packages.toml (parse with tomllib; groups -> packages -> name). These are the extras.
- `[services] system` = `systemctl list-unit-files --state=enabled --no-legend` names (type
  service/timer/socket/path), `user` = same with `--user`.
- `[tools]`: `cargo install --list` crate names; `npm ls -g --depth=0 --parseable` basenames;
  `bun pm ls -g` names if bun exists; `pipx list --short`; `uv tool list` names. Each probe is
  skipped silently if the tool is absent; a failing probe records an empty list plus a
  `# <tool>: <first stderr line>` comment.
- `[local_bin]`: files in ~/.local/bin that are NOT symlinks into the repo (record name + whether
  it is a symlink and its target, or a regular file).
- `[repos]`: every git repo under ~/dev, ~/.config, ~/opt (maxdepth 4, skip the blackwall repo,
  skip node_modules/.cache/target): path relative to $HOME, `origin` URL (or ""), current branch,
  `dirty` count (`git status --porcelain | wc -l`), `ahead` count vs upstream (0 if none).
Default --out: stdout.

### `blackwall-clone backup --to FILE.tar.gpg [--manifest FILE] [--dry-run]`
1. Runs inventory and stores it inside the bundle as `inventory.toml`.
2. Reads a manifest (default: `clone/manifest.toml` in the repo — you create it) listing paths:
   ```toml
   [[path]]
   path = "~/.ssh"          # ~ expanded; absolute paths outside $HOME need root
   why  = "ssh keys and known_hosts"
   root = false             # true -> read with sudo tar
   exclude = ["*.sock"]     # optional fnmatch patterns
   ```
   Seed the manifest with (skip silently when absent on a machine): ~/.ssh, ~/.gnupg,
   ~/.local/share/keyrings, ~/.config/gh, ~/.config/sonata/keys.json, ~/.claude (exclude
   projects/*/*.jsonl older than nothing — keep all; exclude `cache`, `statsig`, `shell-snapshots`),
   ~/.claude.json, ~/.codex (exclude `log`, `sessions` is kept), ~/.config/opencode (exclude
   node_modules), ~/.local/share/opencode, ~/.config/agent-tools, ~/notes, ~/.local/bin files that
   inventory marked as regular files (c2a lives there and must never enter the repo),
   /etc/NetworkManager/system-connections (root), /etc/wireguard (root).
   Never put secrets in the manifest itself; it is public.
3. Builds a tar (pax format, preserving mode/owner/mtime, `--numeric-owner`) to a pipe straight into
   `gpg --symmetric --cipher-algo AES256 --pinentry-mode loopback` with the passphrase read from
   `BLACKWALL_CLONE_PASSPHRASE` env if set, else gpg prompts. No unencrypted tar ever touches disk.
   Root paths: run `sudo tar` for those into a second member, or one `sudo tar` over everything —
   your choice, but non-root paths must not require sudo when the manifest has no root entries.
4. `--dry-run` prints each path, size (du -sh), and whether it exists; writes nothing.
5. Prints, before writing, a warning list of repos with dirty>0 or ahead>0 or empty origin
   ("not in the bundle; push before wiping the old machine").
Exit non-zero if gpg/tar fails; remove the partial output file on failure.

### `blackwall-clone restore FILE.tar.gpg [--yes] [--skip-packages] [--skip-repos]`
Run on the new machine AFTER ./install. Steps, each printed as `==> step`:
1. Decrypt to a pipe, list members, and for each existing target that differs, move it to
   `<target>.pre-clone-<YYYYmmdd-HHMMSS>` before extracting (never silently overwrite).
   Extract user paths as the user, root paths via sudo. Afterwards fix perms: ~/.ssh 700, private
   keys 600, ~/.gnupg 700.
2. Packages: install `native` extras with `sudo pacman -S --needed --noconfirm`, `foreign` with the
   AUR helper (yay/paru, first found) `--needed --noconfirm`. Install one by one on failure so one
   bad package does not abort the rest; collect failures and print them at the end.
3. Services: `systemctl enable` system units missing/disabled (sudo), `systemctl --user enable` user
   units. Skip units whose unit file does not exist; report them.
4. Tools: cargo/npm -g/pipx/uv tool installs for missing ones, only if the tool manager exists.
5. Repos: `git clone <origin> ~/<path>` for repos with an origin that do not exist yet; skip and
   report repos without origin.
6. Print the reauth checklist (below).
Without `--yes`, print the plan (what each step would do, counts) and ask `Proceed? [y/N]` once.
Idempotent: a second run proposes nothing new and backs up nothing whose content is identical.

### `blackwall-clone reauth`
Prints the checklist of things a bundle cannot carry, from `clone/reauth.toml` (you create it):
each entry `name`, `why`, `how` (one shell line or one sentence). Seed it with: browser sign-ins
(Chrome profiles are not carried), GitHub CLI if `gh auth status` fails, readb device pairing
(`~/.config/agent-tools/readb.md`), WhatsApp (wa) session re-link, Spotify/spicetify login,
Tailscale/VPN if present, Claude Code `/login` if `claude` reports logged-out, Codex login,
any hardware-bound keys (TPM/FIDO). `restore` runs live checks where a check exists
(`gh auth status`, `claude --version` etc. are fine; do NOT start interactive logins).

## Repo integration
- `scripts/link-bin`: add blackwall-clone the way the other scripts are added.
- `docs/cheatsheet.md`: new section "## Clone this machine" (3-6 lines, same style as neighbours):
  old machine `blackwall-clone backup --to /path/clone.tar.gpg`; new machine `./install`, reboot,
  `blackwall-clone restore /path/clone.tar.gpg`, then `blackwall-clone reauth`.
- Add `clone/manifest.toml` and `clone/reauth.toml` with comments explaining each entry's why.
- Tests: `theme/tests/test_clone.py` (pytest, run with
  `archpilot/.venv/bin/pytest theme/tests/test_clone.py`; NOT theme/run-tests which runs everything).
  Cover with tmp dirs and a fake HOME: manifest parsing + ~ expansion + excludes; inventory
  extras subtraction against a small fixture packages.toml; backup->restore round trip with
  BLACKWALL_CLONE_PASSPHRASE=test using real gpg (GNUPGHOME in tmp) and a fake HOME, checking a
  pre-existing different file gets a .pre-clone- backup and identical files do not; dry-run writes
  nothing; partial file removed when gpg fails (bad GNUPGHOME). Package/service/repo steps are
  exercised with `--skip-packages --skip-repos` plus a unit test of the plan builder only — tests
  must never call pacman -S, sudo, or systemctl enable.
- Then run the whole suite once: `theme/run-tests`; report pass/fail counts. Two failures are
  known and pre-existing (blackwall-repo-link classification; secret scanner on
  archpilot/tests/test_redact.py and docs/deep-audit) — do not fix those, do not add new ones.

## Constraints
- Do not touch anything outside: scripts/blackwall-clone, scripts/link-bin, clone/, docs/cheatsheet.md,
  theme/tests/test_clone.py. Do not commit. Do not run backup/restore against the real $HOME.
- Never `git add`. Never print a passphrase. Never use `pkill -f`.
- Report: files changed, test output tail, any spec point you could not meet and why.
