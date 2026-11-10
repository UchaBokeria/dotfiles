# Handover: blackwall

Written 2026-09-24 for the team taking this project over. The team works in
**opencode** with Meta's **muse-spark-1.3** model (the Meta API at
`https://api.meta.ai/v1`). Read this file first. It says what the project is,
how the parts connect, what state the work is in, and which traps have already
cost someone a day.

Two other documents carry most of the detail. This file links to them rather
than copying them:

| Document | What it is |
|---|---|
| `docs/cheatsheet.md` | The living user and operator manual: every keybind, every script, every trap found so far. **It is updated in the same change as the feature, never afterwards.** |
| `archpilot/README.md` | ArchPilot, the AI assistant window, including a long "things that cost a probe to learn" list. |
| `whatsapp/README.md` | `wa`, the terminal WhatsApp client. |
| `installer/data/README.md` | The rules the installer's TOML catalogue follows. |
| `opencode/AGENTS.md` | The global opencode rules. **Rewrite the personal parts before you use it; see "opencode" below.** |

---

## 1. What this is

`blackwall` is a complete Arch Linux + Hyprland desktop (a "rice"), kept as
code in one git repository and reproducible on a new machine with one command.
It has four parts:

1. **The rice itself.** Configs for Hyprland (in Lua), eww panels, waybar,
   rofi, swaync, kitty, tmux, nvim, fish, GTK/Qt, sddm and more. They are
   themed from one token generator, so a wallpaper change re-themes all of
   them.
2. **`scripts/`.** About 35 bash and Python helpers (`blackwall-*`, `setwall`,
   …). They back the panels and keybinds: network, audio, VPN, screenshots,
   OCR, clipboard, notifications, calendar, the glass plugin, self-tests.
3. **Three real programs inside the repo:**
   - `archpilot/`: a system-wide AI assistant (Python, GTK4 window + daemon).
     It drives the `claude` or `codex` CLI.
   - `whatsapp/`: `wa`, a vim-driven terminal WhatsApp client (Go, on top of
     `wacli`).
   - `installer/`: a Rust TUI (ratatui) that installs the whole rice on a bare
     Arch box from a data catalogue.
4. **`opencode/`.** The live opencode configuration: providers, plugins, MCP
   servers, skills, and a browser extension with a CDP bridge.

| | |
|---|---|
| Repo | `github.com/UchaBokeria/dotfiles` (**public**). Everything committed is world-readable. |
| Working branch | `nuc`. Every current commit is here. |
| Other branch | `dev` is stale: 143 commits behind, last touched 2026-01-19. Ignore it. `README.md` at the root says "This branch for msi laptop"; that line is stale too. |
| Clone location | Must be `~/.config/.dotfiles/blackwall`. Scripts, the installer preflight and several configs assume that path. |
| Target machine | Arch Linux, kernel 6.18 LTS, **Hyprland 0.56.2**, Intel iGPU, a single-user desktop. |
| Languages | bash, Python 3.13+ (stdlib only in `theme/` and `scripts/`), Go 1.22+ (`wa`), Rust (installer), Lua (Hyprland), yuck/SCSS (eww), TOML. |

---

## 2. Rules for the opencode agent (read before you change anything)

These are the project's working rules. Most of them exist because breaking
them already caused an incident.

1. **Never hardcode a colour, radius, gap or font in a surface's config.**
   Edit `theme/blackwall_theme/tokens.py` and run `theme/blackwall-theme`.
   Generated files (for example `waybar/tokens.css`, `eww/tokens.scss`,
   `hypr/lua/colors.lua` and `kitty/colors.conf`) are output; hand edits to
   them are overwritten.
2. **Update `docs/cheatsheet.md` in the same change** as any new or changed
   keybind, script, subcommand or variant switcher.
3. **Put every new script on PATH.** Add it to `SCRIPTS` in `scripts/link-bin`,
   or to `NOT_ON_PATH` in `theme/tests/test_scripts.py` if it is a backend that
   eww, waybar or hypr call by full path. `theme/run-tests` fails otherwise.
4. **Give every new package, config file, service or build step an entry** in
   `installer/data/*.toml`. Without one, the next machine silently lacks it.
   `theme/tests/test_installer_catalogue.py` enforces part of this.
5. **Commit before you clone anywhere else.** A file that works here but was
   never committed is missing on every other machine. The installer's
   preflight screen lists such files.
6. **Stage explicit paths. Never `git add -A`.** `~/.config/opencode` is a
   symlink into this repo, so whatever opencode writes there lands in the
   working tree. `git add -A` once committed an RSA private key that way.
7. **Never commit secrets.** The repo is public. `theme/run-tests` scans every
   tracked file for key material and tokens. Keep it passing.
8. **Prove a change works; do not assume it.** "`config ok`", "`eww reload`
   succeeded" and "the hover test passed" have each been false positives (see
   section 7). Click tests use `tools/bwclick`. Hyprland changes are checked by
   booting the config nested.
9. **Do not touch these on the live machine:**
   - screen brightness (`blackwall-dim`, `ddcutil setvcp`). Read it, never set
     it.
   - anything under `$XDG_RUNTIME_DIR/hypr/`. Deleting the live socket breaks
     `hyprctl` until Hyprland restarts, and nothing else can recover it.
   - `pkill -f` / `pgrep -f` with a pattern that also appears in your own
     command line. They match and kill the agent's own shell (exit 144). Use
     `pkill -x <name>` or explicit PIDs.
   - `:focusable true` on an eww layer window. It freezes the whole session.
10. **WhatsApp writes go only to the owner's own number (with `--allow-self`)
    or to `0@s.whatsapp.net`.** The store holds real conversations, and a test
    send, react, forward, revoke or delete reaches a real person.
11. **The shell is fish.** opencode's bash tool really runs bash, so wrap fish
    builtins: `fish -c 'set -Ux NAME value'`.
12. **Commit style:** conventional prefix plus a sentence that says what was
    wrong or what now holds, for example `fix: glass survives a library update,
    and heals itself when it does not`. Bodies explain *why*. Documentation
    uses the same plain, causal prose; match it.

---

## 3. Repository map

```
blackwall/
├── install                 entry point: ./install (builds installer/, runs the TUI)
├── installer/              Rust TUI installer
│   ├── src/                main, probe, plan, exec, ui, data, theme, banner
│   └── data/               THE CATALOGUE: packages.toml, links.toml, steps.toml, questions.toml
├── theme/                  design-token generator (stdlib Python)
│   ├── blackwall-theme     CLI: regenerate every surface's tokens
│   ├── blackwall_theme/    tokens.py (source of truth), palette.py, color.py, emit/
│   ├── run-tests           THE repo-wide test suite (tokens, scripts, installer catalogue, tmux guard, secret scan)
│   └── tests/
├── scripts/                blackwall-* helpers, setwall, link-bin, rofi-paper, …
├── tools/bwclick/          C wlr-virtual-pointer client: real clicks for tests
├── hypr/
│   ├── hyprland.lua        symlink -> lua/hyprland.lua  (THIS is what loads)
│   ├── lua/                the live config: hyprland, keybinds, rules, glass, env, settings, animations
│   │   ├── colors.lua      generated, gitignored
│   │   ├── machine.lua     per-machine overrides, gitignored (template: machine.lua.example)
│   │   └── tests/          dispatch-selftest.lua
│   ├── hyprland.conf, configs/   the old .conf tree, kept only as a fallback
│   └── hyprmod/            saved profiles for HyprMod (the settings app vendored at hyprmod/)
├── hyprmod/                HyprMod: upstream GTK4 Hyprland settings app, vendored as a plain directory
├── eww/                    panels: control centre, network, audio, calendar, clocks, notifications, …
├── waybar/                 bar; variants in variants/, switched by waybar/variant
├── rofi/                   launchers; shared/blackwall.rasi generated
├── swaync/                 notification daemon config (mako is masked)
├── kitty/ tmux/ nvim/ fish/ cava/ mako/ wlogout/ gsimplecal/ imv/ flameshot/ Thunar/ wallust/ .themes/
├── home/                   configs adopted from ~/.config that had no repo home before
├── wallpapers/             67 images; the palette is derived from the active one
├── archpilot/              AI assistant (Python), see §5.6
├── whatsapp/               wa (Go), see §5.7
├── opencode/               live opencode config, see §5.8
├── docs/
│   ├── cheatsheet.md       the manual
│   └── superpowers/        wa design spec + implementation plan
├── sddm-astronaut-theme/   git submodule (login screen)
├── tmux/plugins/*          git submodules (tpm, resurrect, continuum, …)
├── .remember/, .claude/    Claude Code session tooling; see §9
└── .snapshots/             blackwall-snapshot checkpoints
```

---

## 4. How the repo becomes a desktop

- **Symlinks.** `~/.config/<app>` is a symlink into the repo for hypr, eww,
  waybar, rofi, kitty, fish, nvim, tmux, opencode, wallust and others. Editing
  the repo edits the live system, and Hyprland reloads its config whenever a
  file is saved.
- **Scripts on PATH.** `sudo scripts/link-bin` links the user-facing scripts
  into `/usr/local/bin`.
- **Theming.** `setwall <image>` sets the wallpaper, runs `wallust` (palette),
  then `theme/blackwall-theme` (tokens for every surface), then reloads the
  surfaces. `blackwall-theme --list` shows every target and where it is
  written. **The generated token files are tracked**, so every wallpaper change
  dirties about 15 files. Commit them deliberately or discard them with
  `git checkout`; do not mix them into an unrelated commit.
- **Session start.** `hypr/lua/env.lua` calls `scripts/blackwall-autostart`.
  It is idempotent: it starts only what is missing (waybar, eww, swaync,
  notifyd, watchers, cliphist) and self-heals the glass plugin.
  `blackwall-autostart --status` shows what is up.
- **Per-machine settings.** `hypr/lua/machine.lua` (gitignored) is written by
  the installer. `hyprland.lua` defines a `BLACKWALL` defaults table, then runs
  `pcall(require, "machine")`, so the file can override the modifier key,
  terminal, monitors and `extra_binds`.

### Installing on a new machine

```fish
git clone --recurse-submodules -b nuc https://github.com/UchaBokeria/dotfiles ~/.config/.dotfiles/blackwall
cd ~/.config/.dotfiles/blackwall
./install              # probe → choose groups → questions → wallpaper → plan → run
./install --dry-run    # same screens, changes nothing
./install --restore    # undo the last run
```

The install runs in two passes. Steps that need a live Hyprland session (the
glass plugin, setwall, spicetify, the selftest) are deferred: log in once, then
run `./install` again. Headless or CI use: `--apply` (no TUI, answers come from
`BLACKWALL_*` env vars, optional groups via repeated `--group <name>`), and
`--snapshot <screen>` prints one screen as text. The full procedure, including
the container test, is in `docs/cheatsheet.md` → "Installing on a new machine".

---

## 5. Components

### 5.1 Design tokens (`theme/`)

- `tokens.py` is the single source of truth. It holds the radius scale
  (22 windows / 18 panels / 12 rows / 8 marks / pill), spacing, the type scale
  (Inter), glass tint and alpha, and the motion curve `bw_ease`, which is
  shared with Hyprland animations.
- The generator exists because wallust templates cannot do colour arithmetic.
  Anything derived, such as alpha, mixes or contrast correction, happens in
  Python.
- Traps:
  - Formats with no alpha channel (kitty, cava, tmux, nvim) need
    `Colour.over(bg)`. `.hex6` silently drops the alpha. kitty also rejects
    `#RRGGBBAA`.
  - GTK CSS cannot store a length in `@define-color`, so waybar and wlogout
    spell radii literally. `blackwall-theme --check` audits them.
- `setwall` guards against colourless palettes: it lowers wallust's threshold
  step by step, and a grey accent is replaced or brightened.

### 5.2 Hyprland (Lua config)

- The Lua config has been live since 2026-08-26 (`hypr/hyprland.lua` →
  `lua/hyprland.lua`). **`hypr/lua/README.md` is stale:** it still says "It is
  not live". The cheatsheet section "The Hyprland config, in Lua" is correct.
- Layout is Hyprland's built-in **scrolling** layout (niri-style), not a
  plugin.
- `hyprctl dispatch` takes a **Lua expression** under this config, for example
  `hyprctl dispatch 'hl.dsp.window.tag({ tag = "x" })'`. The legacy
  `tagwindow x` syntax fails with a Lua parse error.
  `strings /usr/bin/Hyprland | grep '^hl\.'` lists the real API spellings.
- Dispatchers are typed. `hl.dsp.exec_raw` runs a **shell command**; it is not
  a dispatcher. `exec_raw("workspace 3")` once silently broke 22 binds.
- Top-level `hl.exec_cmd` re-runs on **every reload**, and a reload happens on
  every save. Autostart therefore goes through `blackwall-autostart`.
- **`hl.plugin.load(path)` must be called on every pass.** It is declarative,
  not imperative. Guarding it with `if not hl.plugin.X` caused an endless
  reload loop, about 200 waybars, and a compositor abort.
- **Tags are identity, not state.** A window rule that adds a tag on a
  transient condition (fullscreen) never removes it. That is what slowly
  killed the glass. A rule-applied tag survives `hyprctl reload` and cannot be
  removed with `-tag`; the window has to be re-opened.
- **Verify** with `Hyprland --config hypr/lua/hyprland.lua --verify-config`.
  It only proves the file parses, and it *executes* `exec_cmd`. To prove
  behaviour, boot the config nested: with `WAYLAND_DISPLAY` set,
  `Hyprland --config …` opens as a window. `hl.timer` crashes
  `--verify-config`, so never put a timer in the real config.
- **Revert** to the `.conf` tree with `rm ~/.config/hypr/hyprland.lua`, then
  log in again (from a TTY with Ctrl+Alt+F2 if the session is broken).

### 5.3 Liquid glass (hyprglass plugin)

- A compositor plugin, built per machine into
  `~/.local/share/blackwall/hyprglass/`. It is managed by
  `blackwall-glass status|install|on|off`, configured in `hypr/lua/glass.lua`,
  and uses the presets `blackwall` and `blackwall_panel`.
- Glass applies to the rofi, notification, control-centre, calendar and wifi
  layers, and to kitty, Thunar and ArchPilot windows. It does **not** apply to
  waybar, which uses plain blur.
- It **breaks whenever pacman rebuilds Hyprland against new libraries**, even
  when the version string does not change. `blackwall-autostart` runs `ldd` on
  the plugin at login and rebuilds it in the background. Rebuild by hand with
  `blackwall-glass install`, which starts from `make clean`. Diagnose with
  `hyprctl plugin load <so>`, which prints the real error.
- Without the plugin the rice still works, with plain blur.
- Panel glass also needs `layerrule`s (blur, `xray off`, `ignore_alpha`) plus
  CSS alpha on the *background*. Any one of these alone looks broken.

### 5.4 eww panels, waybar, rofi, swaync

- **eww** (0.5.0) draws the control centre, network/bluetooth/VPN, audio,
  calendar, clocks, notification history and stickers. Its scripts live in
  `eww/scripts/` and `scripts/`.
- Known eww traps (full list in the cheatsheet):
  - `:onclick` goes on the **button**, not a wrapping eventbox.
  - A script an eww handler launches must detach itself (the `BW_DETACHED`
    re-exec) before it calls `eww update`, or the two deadlock.
  - `(input)` cannot work in these panels, so text entry goes through rofi
    prompts.
  - A `defpoll` cannot read variables.
  - `eww reload` keeps serving the last config that parsed. The real symptom of
    a broken file is `eww open x` → "No window named…".
  - A button's text needs its own `label` selector.
  - Icons need `$font_icon` = `"Symbols Nerd Font"`, and only that family
    works.
- **waybar** has switchable variants: `waybar/variant capsule|pill|dock`.
  Workspace pills are custom modules driven by
  `scripts/blackwall-bar-workspaces`, because the native module dispatches in
  `.conf` syntax, which the Lua config rejects.
- **rofi**: all launchers share the generated `rofi/shared/blackwall.rasi`. The
  layouts in `rofi/blackwall/` hold geometry only.
- **swaync** is the notification daemon, and mako is masked.
  `blackwall-notifyd` passively logs every notification to
  `~/.local/share/blackwall/notifications.jsonl`. Notification actions are
  named `default`. `swaync-client -dn` turns DND **on** and `-df` turns it off,
  the reverse of how they read.
- **`blackwall-watch`**: background checks (disk, failed units, pacnew, updates
  and more), each raising a notification with an action. It never upgrades
  anything by itself.

### 5.5 Scripts (`scripts/`)

User-facing examples: `setwall`, `blackwall-shot` / `-shots` (capture, OCR,
translate, ask ArchPilot), `blackwall-clip`, `blackwall-net`, `blackwall-vpn`,
`blackwall-audio`, `blackwall-quiet`, `blackwall-cal`, `blackwall-clean`,
`blackwall-snapshot`, `blackwall-undo`, `blackwall-glass`,
`blackwall-selftest`. Each is documented in the cheatsheet.

Security-sensitive: **`blackwall-setkey`** runs as root to edit VPN
credentials. It whitelists keys per file and permanently refuses `PostUp`,
`PreUp`, `PostDown` and `pppd-plugin`, because a writable `PostUp` would be a
root shell. Keep it that strict.

### 5.6 ArchPilot (`archpilot/`)

**Full reference: `archpilot/AGENTS.md`.** It covers the architecture, the
safety gate, every key, config, protocol and CLI command, a plan for adding
an opencode engine, and the traps found by audit. The summary below is the
short version.

- A GTK4 window (`SUPER+~`) plus a daemon (`archpilotd`, a systemd user unit)
  that speaks newline-JSON over `$XDG_RUNTIME_DIR/archpilot.sock`.
- It has two modes. **ask** is read-only, enforced structurally. **action** can
  change the machine, behind a PreToolUse approval gate
  (`hooks/pretooluse.py`, which fails closed; see `docs/hook-contract.md`).
  Three safety layers apply, in order: a denylist, a reversibility classifier
  (`policy.py`), and auto-commit of dotfile changes (`archpilot undo`).
- `sudo` goes through a PATH shim and an askpass broker, so the model never
  sees the password.
- **Engines:** `engine/claude_code.py` drives the `claude` CLI on a Claude
  subscription. `engine/codex.py` drives `codex exec` on a ChatGPT sign-in. The
  package deliberately imports no vendor SDK, to avoid metered billing.
- **Note for this team:** ArchPilot does not talk to opencode or the Meta API
  today. To drive it with muse-spark, add a third engine behind the same
  interface (`start / send / events / cancel / stop`, emitting `EngineEvent`s)
  that shells out to opencode. `engine/codex.py` is the closest template,
  because it also runs one process per turn and resumes by id. Codex has no
  PreToolUse hook, so its modes map onto its sandbox. An opencode engine would
  need an equivalent answer for the approval gate.
- Run with `uv sync`, then `systemctl --user enable --now archpilotd.service`.
  Config is in `~/.config/archpilot/config.toml`, and every key defaults
  (`DEFAULTS` in `src/archpilot/config.py`).
- The UI runs on `/usr/bin/python3`, not on the venv, because PyGObject is
  built for the system interpreter.
- Tests: `cd archpilot && .venv/bin/pytest -q`. vim.py, commands.py and
  policy.py have no GTK import, so they are tested headless.

### 5.7 wa, the WhatsApp TUI (`whatsapp/`)

- Go, pure (`CGO_ENABLED=0`). Reads go straight to wacli's SQLite, read-only,
  with a schema probe and a CLI fallback. Writes go through `wacli`, delegated
  to a running `sync --follow` over its Unix socket (about 2.7 s, so the UI is
  optimistic). The measurements are in `whatsapp/docs/delegation-probe.md`.
- Install with `cd whatsapp && ./install.sh` or `make install` (to
  `~/.local/bin`). It needs wacli 0.18+, authenticated. `wa doctor` reports
  what it can see.
- Config is in `~/.config/wa/config.toml` (watched), plus `overrides.toml`
  for `:set!`. The palette comes from the generated `whatsapp/theme.toml`.
- **Roadmap** (`docs/superpowers/specs/2026-09-08-wa-core-design.md`), six
  sub-projects:
  1. core: done.
  2. media: done.
  3. rich messages: reply, react, forward, revoke and star are done; polls,
     location and edit are not.
  4. management: contacts and the chat drawer are done; groups, channels and
     backfill are open.
  5. ai: **not started**.
  6. hooks: **not started**.
- Visual design decisions (pill caps, "half" bubble edges, SelectedFill,
  `theme.Readable` contrast) were chosen by screenshot. Do not relitigate them
  without looking. To see real pixels, use Xvfb + kitty (x11) + a private tmux
  server + a screenshot; `tmux capture-pane` cannot show images.
- Golden render tests are in `internal/ui/render/testdata`. Refresh them with
  `go test ./... -run TestGolden -update`, and read the diff before you commit.
- The `wa lock` password hides the interface only. It does not encrypt
  wacli's store.

### 5.8 opencode (`opencode/`)

- `~/.config/opencode` is a **directory symlink** to `blackwall/opencode`.
  `AGENTS.md` still describes hardlinks, which predates the symlink.
- **Model setup already matches this team.** The default model is
  `meta-lucky/muse-spark-1.3-contributor`. Four providers
  (`meta-lucky`, `meta-ucha1bokeria`, `meta-uchaprimary`, `meta-buprimarydev`)
  all point at `https://api.meta.ai/v1` through `@ai-sdk/openai-compatible`,
  one per account. Each reads its key from an env var: `MODEL_API_KEY`,
  `MODEL_API_KEY_UCHA1BOKERIA`, `MODEL_API_KEY_UCHAPRIMARY`,
  `MODEL_API_KEY_BUPRIMARYDEV`. Each `muse-spark-1.3*` entry declares a
  1,048,576-token context and 65,536 output.
  - **Replace these providers with your own account(s).** Keep the pattern:
    one provider ID and one env var per account, `apiKey: "{env:VAR}"`.
  - There is no automatic failover between accounts. Switching is manual in
    `/models`.
- Keys live in **fish universal variables**
  (`fish -c 'set -Ux MODEL_API_KEY …'`), stored in the untracked
  `~/.config/fish/fish_variables`. Never in `opencode.json`. After you add a
  variable, restart opencode from a fresh fish shell. The installer asks for
  `MODEL_API_KEY` as a masked secret.
- The schema is **upstream v1**: `provider` (singular) + `npm` + `options`.
  v2-style keys are silently dropped. After every edit, run
  `timeout 60 opencode models`. `limit` needs both `context` and `output`.
- The Meta endpoint served exactly 8 models as of 2026-09-20: `muse-spark-1.1`,
  `-1.2`, `-1.2-contributor`, `-1.3`, `-1.3-contributor`,
  `muse-voice-transcribe-1.0`, `muse-image-1.0` and `sam-3.1`. Re-list them
  with `curl -s -H "Authorization: Bearer $MODEL_API_KEY" https://api.meta.ai/v1/models`.
- `permission` is `"*": "allow"` with a few `bash` denies. The agent runs
  commands without asking. Tighten that if your team wants approval prompts.
- Plugins: DCP (context pruning), background agents, cited web search,
  skillful (skills from `~/.config/opencode/skills` and the Claude skill
  dirs), goal, codex auth, simple-memory, opencode-mem.
- MCP servers: chrome-devtools, context7, gh_grep, memory, chrome-direct,
  chrome-blackwall, cdp, playwright, memories.
- Custom parts: `bin/bridge.ts` (a bun hub for the browser extension, on
  127.0.0.1:9225), `bin/cdp-mcp.ts`, `/rc` and `/browser` commands, the `ask`
  agent, and `browser-extension/`. The extension's signing key
  `opencode/ext-key.pem` is **gitignored and must stay so**.
- **`opencode/AGENTS.md` is personal and global.** It tells the agent to commit
  as the previous owner, never to add attribution trailers, and it names that
  owner's machines, SSH hosts and tailnet. **Rewrite the "Git identity",
  "Machine + SSH" and browser-profile sections for your team before you use
  this config**, or your agent will follow the previous owner's rules.
- Never run two `opencode serve` on one machine. They share one sqlite DB and
  hang.

### 5.9 tmux, nvim, fish

- **tmux**: prefix `C-a`. Status variants are switched with `tmux/variant`.
  `tmux/resurrect-guard` stops an empty save (one taken while the server was
  going down) from becoming `last`, which once wiped every session. Plugins
  are submodules.
- **nvim**: the palette is generated into
  `nvim/lua/custom/blackwall_palette.lua`.
- **fish**: plugins are vendored in `fish/`. The installer seeds fisher's
  records instead of running `fisher update`.

---

## 6. Testing and verification

| Suite | Command | Result on 2026-09-24 |
|---|---|---|
| Repo-wide (tokens, scripts ↔ link-bin ↔ cheatsheet, installer catalogue, tmux guard, secret scan) | `theme/run-tests` | 134 passed, 1 skipped |
| ArchPilot | `cd archpilot && .venv/bin/pytest -q` | 618 passed |
| wa | `cd whatsapp && ./run-tests` (gofmt, vet, test, build, docs) | **FAILS on one docs check.** gofmt, vet, every Go test and the build pass. `whatsapp/config.toml` is missing one line that `internal/config/default.toml` has: `"<leader>gi" = "chat.group_members"`. Add that line to `config.toml` to make it pass. |
| Installer | `cd installer && cargo test` | 0 Rust tests. The installer is tested through `theme/tests/test_installer_catalogue.py` and the container run below. |
| Live desktop | `blackwall-selftest` (30 checks, real clicks via `tools/bwclick`) | needs a running session |
| Hyprland dispatchers | `WAYLAND_DISPLAY=wayland-1 Hyprland --config hypr/lua/tests/dispatch-selftest.lua`, then read `/tmp/bw-dispatch-selftest.txt` | needs a session; lines saying `accepted` prove nothing, only state changes do |
| Fresh install | `docker run --rm archlinux:latest`, a NOPASSWD sudo user, `dbus-uuidgen --ensure`, clone, then `./install --apply` with `BLACKWALL_*` env vars | last full run passed on 2026-09-21 |

`theme/run-tests` borrows ArchPilot's venv pytest, so run `uv sync` in
`archpilot/` first on a new machine.

**Proving a click works:** `hyprctl layers` gives the panel geometry,
`bwclick X Y` clicks, and `eww get <var>` confirms the state changed. A hover
test is not evidence. GTK delivers hover to the eventbox but the click to the
button, which is how 52 handlers were once "fixed" the wrong way.

---

## 7. Traps, in one list

Each one has cost real time. Details are in the cheatsheet or the component
READMEs.

- `config ok` from Hyprland ≠ the config works.
- `eww reload` success ≠ the new config loaded.
- `gsettings set` with no session bus exits 0 and writes nothing, so wrap it in
  `dbus-run-session`. The same applies to reading and writing xfconf.
- The AUR is not reliable. `wallust` stopped building (upstream checksum), so
  there is a `cargo install --locked wallust` fallback step. AUR packages are
  installed one at a time, so one failure cannot take the others down. Do not
  use `wallust-git`: it is v4-alpha and rejects the v3 config.
- Installer steps run in **file order**. `after` is checked by a test, not
  topologically sorted. An empty `check` always counts as "to do".
- `pacman -Qqe` is not the install list. About 30 needed packages are
  installed only as dependencies.
- `wl-copy` stays resident, so never wait for it to exit.
- The first click after an eww panel maps can miss. The selftest warms up.
- A capture's clipboard write racing with an OCR text write is why OCR copies
  text only.
- The rule that floats every window at 1200x800 also catches overlay tools
  like flameshot. Exclude them.
- Tailscale's operator grant is per profile.
- Old copies of `setwall`, `rofi-paper` and `find_internal_audio` still sit in
  `/usr/bin`. `/usr/local/bin` shadows them, so `link-bin` must stay run.

---

## 8. Current state and open work

**Working tree at handover.** These are uncommitted:

- regenerated theme tokens from a wallpaper change: thunar.css, cava,
  eww/tokens.scss, hypr colors.conf, kitty, mako, nvim palette, rofi, tmux,
  waybar, whatsapp/theme.toml, wlogout. Commit them or discard them, as a
  separate commit.
- opencode edits in progress:
  - `opencode.json`: two memory plugins, a `memories` MCP server, and
    reasoning variants changed from `none` to `minimal` plus `max`.
  - `dcp.jsonc`.
  - browser extension `panel.html` / `panel.js`.
  - untracked `opencode/.agents/` and `opencode/opencode-mem.jsonc`.

  Review them, run `timeout 60 opencode models`, then commit them or drop
  them.

**Unfinished work (from the last session notes):**

- `whatsapp/run-tests` fails its config-drift check (§6). This is a one-line
  fix.

- swaync notification **card styling** and the **DND state** display were in
  progress. WiFi detection, rofi opacity and BT pairing were fixed, and the
  mpris widget was removed from swaync.
- wa sub-projects 5 (AI: summarise, draft, translate, ask-about-chat) and
  6 (hooks), plus the rest of 3 (polls, location, edit) and 4 (groups,
  channels, backfill).
- An opencode engine for ArchPilot, if this team wants it on Meta models
  (§5.6).
- Two SUPER keymaps cannot be tested nested (focus-by-direction, SUPER+drag).
  Check them by hand after any keybind change.
- The `packages.toml` re-inventory (every binary the configs call, mapped to a
  package group) is due before any "release".

**Stale documentation to fix:**

- `README.md` at the root ("msi laptop").
- `hypr/lua/README.md` ("It is not live").
- the hardlink wording in `opencode/AGENTS.md`.
- the cheatsheet section "Going back to floating", which refers to
  `windowrules.conf` and `hyprland.conf` from the `.conf` era.

---

## 9. Security

- **Outstanding:** a script (`c2a`) containing plaintext SSH passwords for
  internal hosts was committed to this public repo from 2026-04-30 until
  2026-09-19. History was rewritten and the GitHub repo recreated, but **those
  credentials must be treated as leaked and rotated**. That had not been
  confirmed at handover. A pre-rewrite git bundle that still contains the
  secret sits in the previous owner's home directory. Delete it once rotation
  is done. `c2a` now lives outside the repo, and a test fails if it comes
  back.
- The secret scan in `theme/run-tests` checks tracked filenames (`*.pem`,
  `*.key`, `.env`, `id_rsa`, `auth.json`, …) and contents (private-key
  headers, `sk-` / `ghp_` / `AKIA` / `xox` tokens, `sshpass -p`).
- Installer secrets: a `secret = true` question is masked, kept out of every
  step's environment, and passed to its `apply` on **stdin**, never in argv or
  the log.
- ArchPilot's approval gate fails closed. Keep it that way. A PreToolUse hook
  that times out or exits non-zero with no output *allows* the command, so
  only an explicit deny or exit 2 blocks.

---

## 10. Claude-specific leftovers, and what to do with them

The previous work was done with Claude Code. Under opencode:

| Item | What it is | Under opencode |
|---|---|---|
| `.remember/` (root and `archpilot/`) | Claude Code session-memory hook output: daily notes, `now.md` handoff | Readable history. The opencode `remember` skill in `AGENTS.md` uses the same layout. Keep it or delete it; nothing depends on it. |
| `.claude/settings.local.json`, `opencode/CLAUDE.md` | Claude Code settings / instructions | Harmless. `CLAUDE.md` only points to `AGENTS.md`. |
| `docs/superpowers/` | spec + plan written with the superpowers skills | Still the authoritative wa design. |
| ArchPilot engines | need the `claude` / `codex` CLIs and their subscriptions | See §5.6. The installer step `agent-clis` installs both. |
| The previous owner's saved gotchas | Claude's private memory | Everything in it that matters is in §2, §5 and §7 above. |

Recommendation: create a root `AGENTS.md` for this repo that says "read
`handover.md` and `docs/cheatsheet.md` first" and restates the rules in §2.
opencode loads `AGENTS.md` automatically; it does not load this file.
