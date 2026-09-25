# ArchPilot — agent contributor guide

This file is the single working reference for changing code here. It folds
in everything from the earlier `handover.md` (now removed); where
`README.md` disagrees with this file, this file is right. `README.md` is
user documentation with several stale passages (see Stale list below) —
do not treat it as the spec.

## What this is

System-wide AI assistant for the blackwall Hyprland rice (`SUPER+grave`).
Four parts: `archpilotd` (asyncio daemon, systemd user unit), `archpilot-ui`
(GTK4 window), `archpilot` (CLI for keybinds/waybar/scripts),
`hooks/pretooluse.py` (safety gate on every tool call of the AI).

The model never runs inside ArchPilot. The daemon drives an external CLI
through a swappable engine: `claude` (default, `claude -p`, subscription
OAuth, long-lived child per conversation) or `codex` (`codex exec --json`,
ChatGPT sign-in, one process per turn resumed by thread id). Core rule:
**no vendor SDK is ever imported and no metered API is ever used.**
`pyproject.toml` has `dependencies = []` — stdlib only. See Engines below
for the interface a third engine (opencode) must implement.

## Run / reload / observe

```fish
cd ~/.config/.dotfiles/blackwall/archpilot
uv sync
systemctl --user enable --now archpilotd.service
systemctl --user enable --now archpilot-triage.timer
.venv/bin/pytest -q                       # 680 passed (2026-09-25), ~14s
/usr/bin/python3 tests/gtk/check_selection.py   # needs a display, run by hand
journalctl --user -u archpilotd -f        # daemon logs
archpilot state                           # state dump
ARCHPILOT_UI_DEBUG=/tmp/keys.log          # key trace: start UI with this set
```

After a change: daemon code or config → `systemctl --user restart
archpilotd` (config is read once at start). UI code → close window (`ZZ`)
and reopen (`SUPER+~` or `archpilot ui`). `hooks/*.py` → next tool call
(fresh process each time).

## Architecture (short)

`SUPER+~` → `archpilot ui --toggle` → `bin/archpilot-ui` (GTK, system
python, threaded subscribe client) → `$XDG_RUNTIME_DIR/archpilot.sock`
(0600, newline JSON; `/tmp/archpilot-<uid>/` fallback) → `archpilotd`
(asyncio). Daemon owns SessionManager, approval + password brokers,
context injectors, git auto-commit. `claude -p` child is registered via
`--settings` JSON with the PreToolUse hook on EVERY tool; hook sends
`OP_ASK_PERMISSION` and blocks; sudo goes `sudo -A` shim → `askpass.py` →
daemon → masked field in window.

A turn (`Daemon._on_prompt` → `run_turn`, `daemon.py:181`): split leading
directives (`:opus/:sonnet/:haiku/:fable` force claude engine; `:ask`/`:action`
pick mode; `:term/:sys/:sess/:clip/:sel/:win` pick context) → new tab if
mode/model/engine differ → `persist.save()` → append staged attachments →
prepend `<archpilot-context>` (window always when enabled; terminal on
failure-words or `:term`; sessions on session-words or `:sess`; system only
when `context.system=true` AND sys-words or `:sys`; clipboard/selection
only on `:clip`/`:sel`, capped 4000 chars) → action mode snapshots
`git status --porcelain -uall` → handle engine events (`delta` throttled
80ms; `tool` → activity line; `rate_limit` → reset times; `result` → usage,
failure classification, action split; `error` → crash classification) →
`finally` never leaves status thinking → disarm sudo → Codex persists thread
id → auto-commit only paths dirtied during the turn (`archpilot: <first
prompt line>`, `--no-verify --only`) → delivery per `ui.on_submit`
(`expand` reopens, `toggle` leaves, `dismiss` hid at submit; error always
reopens; notify only for action/error turns when window hidden or dismiss
mode). Turns are serialized by one `asyncio.Lock`.

Suggested actions: system prompt asks for at most one
```` ```archpilot-action ```` fence → parsed into button (`actions.py`) →
`run_action` sends "Run exactly this command..." through the engine in
action mode. Still goes through the gate; shortcut, not bypass. Addressed
by index, never re-parsed text.

Rewind (`u` on message): Claude Code cannot resume at a point, so fresh
session in the SAME tab slot, earlier turns kept locally, replayed as
"Earlier in this conversation: …" (`session.replay_text`), prompt back to
input unsent (`EV_RESTORE_INPUT`). Mode/model/effort change: per-process
flags, so engine stopped, session marked `restored`, next prompt
re-attaches with `--resume`. Engine switch (`ctrl+alt+tab`/chip/`:engine`):
tab + transcript stay, model resets (no shared names), new engine gets
replay of unseen turns (max 8 × 2000 chars), Claude resumes only if
transcript exists, Codex only if rollout exists; choice becomes default for
new tabs for daemon's life. Restart: `persist.load()` re-adopts last
session; missing transcript/rollout → blank, not failure.

## Engines in detail

Claude (`modes.build_argv`):
`claude -p --model <m> (--session-id <uuid> | --resume <uuid>)`
`--input-format/--output-format stream-json --include-partial-messages
--verbose --append-system-prompt <machine+SUFFIX> --settings
$RUNTIME/archpilot-settings/<mode>.json [--effort …] --setting-sources ''
--strict-mcp-config --mcp-config '{"mcpServers":{}}'` (or named servers).
Ask: `--permission-mode manual --disallowedTools Write Edit NotebookEdit`.
Action: `--permission-mode acceptEdits`. No `--bare` (metered),
no `--disable-slash-commands` (skills work). Session id is ours (uuid4);
transcripts in `~/.claude/projects/<slug>/<id>.jsonl` (slug: `/` and `.` →
`-`). Child held open (prompt-cache); 32MB line limit; stderr drained (40
kept); cancel = SIGTERM→0.7s→SIGKILL. Model cycle now
haiku→sonnet→opus→fable. Effort low…ultra.

Codex (`modes.codex_argv`, `engine/codex.py`): one `codex exec` per turn,
prompt on stdin (`-`); resume `codex exec resume -c sandbox_mode="…" …
<thread> -` (no --sandbox/-C on resume — verified in help). No
`--append-system-prompt` → instructions ride first message in
`<instructions>`. Sandbox IS the mode (read-only/workspace-write); never
`--dangerously-bypass-approvals-and-sandbox`. Thread adopted only on
completed turn. Models from `~/.codex/models_cache.json` (visibility list,
config `model` first) or `[codex] models`; cached for daemon life. Effort
clamped to `supported_reasoning_levels`. Usage forwards `input_tokens` +
`cached_input_tokens` (as cache_read) for the ctx meter.

Engine interface (third engine): `start/send/events/cancel/stop/running/
stderr_tail`; events delta/message/tool/result/rate_limit/error/system.
`result.raw.usage` + `modelUsage[*].contextWindow` feed the meter.

## Safety model (do not break)

Three layers in `hooks/pretooluse.py` → `policy.classify` (`policy.py`):

1. **DENY** every mode, no prompt: `policy.DENYLIST` regexes on
   whitespace-normalised command (rm -rf /, --no-preserve-root, mkfs*,
   dd of=/dev/sd|nvme|vd|mmcblk|disk, curl|wget|sh, fork bomb, shred,
   recursive chmod/chown on /, redirect onto block device, force-push
   main).
2. **ALLOW/ASK** reversibility: Read/Grep/Glob/WebSearch/WebFetch/TodoWrite
   allowed. Edit/Write/NotebookEdit allowed inside dotfiles repo
   (auto-committed, revertable), ASK outside. Unknown tools ASK. Bash:
   `$(`/backtick → ASK; redirect outside repo → ASK; sudo/doas/pkexec/run0
   → ASK (also arms password broker). Per-segment (split on `| || && ;`):
   strip leading sudo/env/VAR=, forbid `hyprctl dispatch exec|execr` and
   `keyword exec`, trap flags (find -delete/-exec…, sort -o, rg --pre,
   grep --devices), pacman/yay/paru pass -S/-Q/-F/-U, -R/-D ASK, sed -i
   ASKs, READ_ONLY_VERBS pass, SUBCOMMAND_ALLOW for git/systemctl/docker,
   hyprctl/eww/makoctl/wpctl/brightnessctl pass whole — **anything else
   ASKs (default-deny)**. Ask mode turns ASK into DENY (structurally
   read-only: `--permission-mode manual` + `--disallowedTools Write Edit
   NotebookEdit`).
3. **Auto-commit + `archpilot undo`**: repo is the undo stack (`git.py`;
   `undo` = `git revert` newest `^archpilot:` commit).

Hook contract (`docs/hook-contract.md`, probed on 2.1.237; machine runs
2.1.281 — re-probe after upgrades): harness-timeout kill RUNS the command;
`exit 1` + empty stdout RUNS it; only `permissionDecision: deny` or `exit 2`
blocks. So: every error path funnels to `exit 2` (incl. top-level `except
BaseException`), hook enforces own deadline
`safety.approval_deadline_s=240` inside harness `timeout=600`
(`settings.HARNESS_TIMEOUT_S`). **Keep 240 < 600. Never exit 1.**

Approval flow: hook `OP_ASK_PERMISSION` → daemon `awaiting_approval` +
window open + full command shown + `notify-send -A allow/deny` → answer
`y`/`x`, `archpilot approve [id] [--deny]`, or notification. Daemon down /
timeout / bad reply → refuse (fail closed).

sudo: `shim.py` puts `$XDG_RUNTIME_DIR/archpilot-bin/sudo`
(`exec /usr/bin/sudo -A`) first on child PATH, `SUDO_ASKPASS=hooks/askpass.py`
(700). Broker answers only while armed (approving an elevating command arms
for that turn, covering sudo's 3 retries; turn end disarms). Unarmed → empty
password → sudo fails (stops model self-phishing). Password in one Future,
one caller, never stored. Shim not hook-rewrite (rewrite makes transcript
lie; model reports tampering). Known leak: `archpilot password VALUE` in
`/proc/<pid>/cmdline`; prefer GTK field or stdin.

Codex gets NO gate/denylist/approval — only its sandbox (ask=read-only,
action=workspace-write; never `--dangerously-bypass-approvals-and-sandbox`).

## File map

- `daemon.py` (1182): socket server, turn runner, approval/password brokers,
  tabs, rewind, engine switch, rofi pickers, serve/shutdown.
- `session.py` (626): Session (turns, usage/limits, snapshot, rewind,
  turn_views) + SessionManager (tabs, ensure_started, shutdown).
- `modes.py` (204): claude/codex argv builders, MODEL/EFFORT/ENGINE cycles,
  `system_prompt`, sandbox map. NOTE: module docstring says `plan` for ask
  — stale; code uses `manual` + disallowedTools.
- `engine/claude_code.py` (213): long-lived child, stream-json, 32MB line
  limit, stderr drain, SIGTERM→SIGKILL cancel.
- `engine/codex.py` (439): per-turn process, thread adoption only on
  completed turn, catalogue from `~/.codex/`, effort clamping, activity
  lines in Claude's voice.
- `policy.py` (318): denylist + reversibility classifier.
- `hooks/pretooluse.py` (165): THE GATE, bare interpreter, fail closed.
- `hooks/askpass.py` (71): SUDO_ASKPASS, silent-empty failure.
- `settings.py` (61): renders `--settings` JSON per mode (hook registration).
- `shim.py` (48): sudo -A PATH shim.
- `git.py` (57): turn-scoped auto-commit (`-uall` load-bearing).
- `ipc.py` (75): protocol — ops prompt/subscribe/state/approve/password/
  toggle/cancel/new/tab/draft/rewind/picker/scroll/widget/set/run_action/
  attach/detach/open_session/rename/ask_permission/ask_password; events
  state/delta/turn_end/approval_request/password_request/error/restore_input.
- `client.py` (64): blocking socket client for CLI.
- `cli.py` (698): 22 subcommands (ui/toggle/send/state/subscribe/approve/
  password/set/new/cancel/run/copy/shot/history/sessions/scroll/triage/
  waybar/undo). `cmd_ui` close/focus + `_submap` route through
  `compositor` Lua helpers (fixed 2026-09-24); `--retry` validated
  positive; `history --print` / `sessions --print` print without rofi;
  `copy` uses fire-and-forget wl-copy (U31); `cmd_state` fails loudly on
  empty reply; shot names are `time.time_ns()` (no second-collision).
- `config.py` (174): DEFAULTS + `~/.config/archpilot/config.toml` merge;
  malformed file → silent defaults. `session.follow_terminal_cwd` is a
  **dead key** (declared, never read).
- `paths.py` (75): every location; `DOTFILES` hardcoded
  `~/.config/.dotfiles/blackwall` — decides revertable boundary +
  auto-commit repo.
- `persist.py` (73): last-session pointer (id/cwd/mode/model/effort/engine/
  codex_thread + ALL tabs; atomic write; validated load). Thread id is saved
  at adopt-time mid-turn, not just turn end.
- `problems.py` (140): failure classification (auth/limit/network/model/
  missing/crash) → fix command. Codex auth rule BEFORE Claude's (both match
  401). Opencode rules go before Claude's too.
- `auth.py` (59): pre-flight via `~/.claude/.credentials.json`
  (`refreshTokenExpiresAt` only; `expiresAt` lapse is normal). Claude-only;
  Codex/opencode need their own or skip.
- `activity.py` (75): tool call → "running rg" line.
- `actions.py` (50): ```archpilot-action fence parse/strip.
- `commands.py` (223): `:` line parse (aliases + unambiguous prefixes +
  Tab completion) + KEYBINDINGS table (`:help` source — update here, not in
  help text).
- `vim.py` (1110): VimBuffer, no GTK import, headless-tested. Motions,
  operators+counts, dd/cc/yy/D/C/Y, x/X/s/S/p/P/r/J/~, per-insert-session
  undo, visual/V/block (+block I/A/c/d), macros q/@, multicursor ctrl-n/
  ctrl-up/down, ctrl-a select all. NO text objects. Docstring "no macros"
  is stale — macros exist.
- `markup.py` (152): markdown → Pango + hard wrap (eww legacy, still used
  for snapshot fields).
- `titles.py` (71): chat names in state dir, never in transcripts.
- `triage.py` (231): pacnew/failed-units/disk/docker checks, 12h de-dup,
  ready prompts (`triage --ask KEY` filters from history).
- `rofi_theme.py` (205): picker theme from `eww/colors.scss` + repairs old
  `rofi/launchers/` shared/colors.rasi (harmless; rice now uses
  `rofi/blackwall/` — deletable).
- `compositor.py` (83): Hyprland socket discovery at call time; `lua()` +
  `focus_class()` / `close_class()` / `submap_reset()` emit Lua `hl.dsp.…`
  expressions (see Traps). `dispatch()` (legacy) remains for the `.conf`
  fallback only.
- `context/`: window (hyprctl activewindow) / terminal (kitty scrollback
  120 lines + /proc cwd) / sessions (tail-read index + Codex rollouts) /
  system (free/df/failed/checkupdates/pacnew; off by default) /
  clipboard+selection (directive-only, 4000 chars, errors=replace) /
  history (tail 96KB, mtime cache, noise filter + Codex rollouts) / rice
  (machine block for system prompt) / relevance (failure-word heuristics
  only — bare deictics never fire; `:term/:sys/:win/:sess/:clip/:sel`).
- `ui/gtk_app.py` (2380): the window. Label-rendered VimBuffer prompt (not
  Entry), CAPTURE-phase keys, no focusable buttons, Tab toggles input/chat,
  Tab-chords cycle (shift=mode, ctrl=model, alt=effort, ctrl+alt=engine),
  alt+1..9/gt/gT tabs, ctrl-t new, ctrl-w close, ctrl-s sessions, ctrl-c /
  Esc-Esc stop, super+enter run action, ctrl-h in-window history (Enter
  OPENS conversation via OP_OPEN_SESSION), `:` line, attachments (drop +
  ctrl-v paste → `$RUNTIME/archpilot-shots/`), per-message copy +
  drag-select→clipboard+primary (`wl-copy` fire-and-forget), approval/
  password/notice/error panels, ctx + 5h + weekly meters, theme from rice
  tokens with colors.scss fallback + live GFileMonitor re-theme, draft
  save/restore, self-resize via hyprctl Lua. NOTE: `_retry_turn`
  sends `{"cmd": "prompt"}` — daemon dispatches on `"op"` → "unknown op
  None"; fix to `{"op": ipc.OP_PROMPT, ...}`. TIPS["new"] says ctrl-n —
  key is ctrl-t.
- `ui/client.py` (92): threaded subscribe, auto-reconnect, GLib.idle_add
  marshalling.
- `ui/theme.py` (781): GTK CSS from `../theme/blackwall_theme` tokens
  (stdlib import via sys.path), fallback derivation; radius 22px must equal
  Hyprland rounding.
- `bin/archpilot-ui`: launches on `/usr/bin/python3` (NOT venv; PyGObject
  is system-built), PYTHONPATH=src.
- `bin/archpilot-snapshot`: pre-git safety net. Docstring "not git-tracked"
  is stale — tree IS tracked now; git replaces it.
- `systemd/`: `archpilotd.service` (After=default.target — Hyprland never
  activates graphical-session here; ANTHROPIC_API_KEY= emptied; explicit
  PATH; TimeoutStopSec=10; Restart=on-failure), triage service+timer
  (10min after login, every 6h).
- `tests/`: 28 modules, 680 tests + `tests/gtk/check_selection.py` (by
  hand; venv python 3.13 can't import PyGObject built for system 3.14).
  New: `test_dispatch_strings.py` (Lua strings, retry op, rice map),
  `test_fixes.py` (U23/H4/U33/D2/H8/U46). Fixed pins: shutdown `{"op"}`
  (T1), ask==manual (T2), sandbox-present (T3), cached tokens 2200 (T4).
  Policy regression tables (DENY/ASK/ALLOW, 50 cases). Vim linewise/count
  tests. Nothing tests the hook end-to-end vs real `claude` — that gap
  remains.
- `.snapshots/`: gitignored local scratch (untracked 2026-09-25; was 671
  tracked stale copies before). Exclude when grepping.
- `app/`, `settings/`: empty leftovers.
- `.remember/`: Claude Code session-notes tooling (gitignored contents);
  readable history, nothing depends on it.

## Config (`~/.config/archpilot/config.toml`, all optional)

| Key | Default | Meaning |
|---|---|---|
| `ui.on_submit` | `toggle` | toggle/expand/dismiss; error always reopens |
| `ui.notify_on_complete` | `true` | action/error + approval notifications |
| `model.default` | `haiku` | Claude model for new chats |
| `mode.default` | `ask` | ask/action |
| `engine.default` | `claude` | claude/codex; persisted on switch (U45) |
| `codex.models` | `[]` | empty = Codex catalogue |
| `codex.binary` | `codex` | |
| `codex.default_model` | (unset) | persisted on `:model` with no session (U45) |
| `effort.default` | `medium` | low…ultra |
| `session.follow_terminal_cwd` | `false` | new sessions start in focused terminal's cwd (impl. 2026-09-25; was dead) |
| `context.window/terminal/sessions` | `true` | window forcible via `:win` (U22) |
| `context.system` | `false` | |
| `safety.approval_deadline_s` | `240` | clamped under harness 600 in code (U1 fix) |
| `safety.auto_commit` | `true` | |
| `mcp.servers` | `[]` | names from `~/.claude.json` |
| `rofi.theme` | `""` | |
| `rofi.sync_launcher_colors` | `true` | |
| `screenshot.cmd` | `grim … {path}` | must contain `{path}` (validated now) |

`config.save()` writes back in-memory changes (new — U45). Bad VALUES raise
at first access (not silent-defaults); unknown keys kept silently. `Config`
deep-copies DEFAULTS now (was process-global alias).

## CLI + protocol

22 subcommands: ui/toggle/send/state/subscribe/approve/password/set/new/
cancel/run/copy/shot/history/sessions/scroll/triage/waybar/undo. Every
fire-and-forget op now acks `{ok:true}` (U18 — UI send no longer blocks
5s). `cancel` without `--session` cancels current (U14). Negative
run/copy indices rejected (U27). Daemon validates rewind/scroll ints,
attach paths, `msg["cwd"]` type. Socket: live-owner probe on start,
inode-checked unlink on shutdown (U20). Broadcast over snapshot list,
all exceptions pruned (U38).

## Runtime files

`$RUNTIME/archpilot.sock` (0600, live-probed) · `archpilot-settings/
{ask,action}.json` (hook registration, hook path quoted+checked) ·
`archpilot-bin/sudo` (0700 wrapper; source no longer chmodded) ·
`archpilot-shots/` (shot-+paste- pruned to 20) · `archpilot-rofi.rasi` ·
`~/.local/state/archpilot/last-session.json` (atomic, ALL tabs + current)
· `titles.json` (corrupt file never overwritten) · `triage-seen.json`
(12h) · `~/.config/archpilot/config.toml` ·
`~/.claude/projects/<slug>/<id>.jsonl` · `~/.claude/.credentials.json` ·
`~/.codex/{config.toml,models_cache.json,sessions/**/rollout-*.jsonl}`.

## Rice integration (parent repo)

- `hypr/lua/keybinds.lua`: SUPER+grave → `archpilot ui --toggle`,
  +SHIFT → `shot`, +CTRL → `sessions`, +ALT → `history` (via
  `.venv/bin/archpilot`).
- `hypr/lua/rules.lua`: float/center/900x176 for `dev.archpilot.ui`; dead
  `eww-archpilot` pin rule still present.
- `hypr/lua/glass.lua`: ArchPilot window tagged for hyprglass.
- `scripts/blackwall-shot --ask` / `blackwall-shots`: `archpilot shot
  --file`.
- `scripts/blackwall-watch` check `archpilot` tier 1: `archpilot waybar`;
  `awaiting_approval` → critical notification with `ui --toggle` action.
- `waybar/modules/archpilot.json`: `custom/archpilot` defined (toggle /
  history / mode-cycle clicks) but NOT placed in any bar layout — not
  shown.
- `theme/blackwall_theme`: imported by `ui/theme.py` for tokens.
- `eww/colors.scss`: read by `rofi_theme.py` + UI fallback; watched live.
- `installer/data/steps.toml`: `archpilot-venv`, `archpilot-units`,
  `archpilot-path`, `agent-clis` (`npm i -g @anthropic-ai/claude-code
  @openai/codex`).
- `kitty/kitty.conf`: `allow_remote_control yes` + `listen_on
  unix:@mykitty` (appends `-<pid>`) — required for terminal context.

## Traps (verified, not folklore)

- **Lua dispatch (FIXED 2026-09-24).** `hyprctl dispatch` takes a LUA
  expression under this rice (see cheatsheet "The Hyprland config, in
  Lua" + `strings /usr/bin/Hyprland | grep '^hl\.'`). Legacy
  `focuswindow class:…` / `closewindow …` / `submap reset` fail with Lua
  parse errors (verified live). Fix: `compositor.lua()` +
  `focus_class()` / `close_class()` / `submap_reset()` helpers emitting
  `hl.dsp.focus({window=…})` / `hl.dsp.window.close({window=…})` /
  `hl.dsp.submap("reset")` (all verified ok live). `daemon._ui_open` /
  `_ui_close` / picker and `cli.cmd_ui` / `_submap` route through them.
  `compositor.dispatch()` (legacy) remains for the `.conf` fallback only.
  Pinned by `tests/test_dispatch_strings.py` + `test_compositor.py`. The
  `archpilot` submap no longer exists in Lua config; `cli._submap`
  ignores non-`reset` names.
- **Retry dead (FIXED 2026-09-24).** Was: `gtk_app._retry_turn` sent
  `{"cmd": "prompt"}`; daemon dispatches on `"op"` → "unknown op None".
  Now sends `{"op": ipc.OP_PROMPT, ...}`. Pinned by test.
- **Active-window context from GTK.** `context/window.active()` reads
  `hyprctl activewindow`; when typing in ArchPilot, ArchPilot IS active —
  "why did that fail?" gets own class, no kitty scrollback. Eww-era
  leftover (layer surface never became active). Fix: record previously
  focused window on UI open (`hyprctl -j clients` by `focusHistoryID`).
- **Never `pkill -f archpilot` / `pgrep -f archpilot`** from an agent
  shell — matches own cmdline, kills self (exit 144). Use `systemctl
  --user restart archpilotd`, `pkill -x`, explicit PIDs.
- **GTK probe needs own `application_id`** (e.g. `dev.archpilot.probe.x`);
  reusing `dev.archpilot.ui` hands activation to running window, probe
  prints nothing. Load CSS via `theme.css()`.
- Never `--bare` on claude (forces metered ANTHROPIC_API_KEY).
  `--mcp-config '{}'` rejected; use `'{"mcpServers":{}}'`.
- `asyncio.start_unix_server` NOT as `async with` for shutdown:
  `wait_closed()` blocks on never-ending subscribe conns → SIGKILL after
  90s. `serve()` closes subscribers explicitly.
- GTK CSS: no `line-height`/`caret-color` (aborts parse). Icons need
  `"Symbols Nerd Font"`. Buttons `set_can_focus(False)` or Space/Enter
  activates them instead of reaching vim.
- `git status --porcelain -uall` whenever new-file detection matters
  (default collapses untracked dirs).
- Read Lua traps in `../docs/cheatsheet.md` before touching Hyprland
  config or loading a plugin.
- Parent repo is PUBLIC. Stage explicit paths, never `git add -A`
  (`~/.config/opencode` symlinks into repo; `-A` once committed an RSA
  key). Commit style: `fix: <what now holds>`. Never commit secrets
  (`.env`, `*.key`, tokens); theme/run-tests scans. Known untracked
  secret: `fish/functions/sparkcode.fish` holds a plaintext
  MODEL_API_KEY_* — never stage it; rotate if ever pushed.
- Changing a keybind/command: update README + `commands.KEYBINDINGS`
  (`:help` source) + `../docs/cheatsheet.md` ArchPilot section if
  user-facing.
- Live-machine prohibitions (parent handover §2.9): brightness, anything
  under `$XDG_RUNTIME_DIR/hypr/`, `pkill/pgrep -f` self-match,
  `:focusable true` on eww layer windows.
- `wl-copy` stays resident — fire and forget, never await.
- hook-contract probed on 2.1.237; machine runs 2.1.281 — re-probe after
  upgrades.

## Stale docs/comments (fix when touching the area)

- README mode table: ask uses `manual` + `--disallowedTools`, not `plan`.
  "Enters Hyprland submap on focus": no longer true. Eww-widget passages
  (status-bar chips, `eww reload` in Setup, layer-shell overlay). Vim table
  `ctrl-n new · ctrl-l/e/t cycle` superseded (ctrl-t new, Tab chords,
  ctrl-n multicursor). History enter "loads into prompt": opens
  conversation.
- `modes.py` docstring said `plan`, `vim.py` said "no macros";
  both fixed 2026-09-24. `bin/archpilot-snapshot` "not git-tracked"
  fixed. "mako" → swaync in config/daemon/gtk comments fixed.
- `gtk_app.TIPS["new"]` said ctrl-n; fixed to ctrl-t (2026-09-24).
- **`context/rice.py` map (FIXED 2026-09-24).** Now describes Lua
  (`hypr/lua/` + `hl.dsp.…` rule), `rofi/blackwall/`, token generator,
  swaync. Pinned by `test_dispatch_strings.py`. If the rice changes
  shape again, update this + the test together.
- `bin/archpilot-snapshot` "not git-tracked": tracked now.
- "mako" in `on_submit` comments/notify code: daemon is swaync now
  (`notify-send` works either way).
- `hook-contract.md` version gap (above).

## Opencode engine (probed 2026-09-24, opencode 1.18.32)

Event shapes recorded from live runs (not assumed):

- `opencode run --format json -m meta-lucky/muse-spark-1.3 "hi"` emits
  `step_start` → `text` (`part.text`) → `step_finish` (`reason: stop`,
  `part.tokens {total,input,output,reasoning,cache}`, `cost: 0`).
  `sessionID` (`ses_…`) is top-level on every event — adopt from first
  event; resume with `-s <id>` (verified: resumed turn returns same
  `sessionID`). Multi-step: repeated step_start/text/step_finish; tool
  calls arrive as `part.type: tool` (`tool`, `callID`, `state.status/
  input/output`); `step_finish` reason `tool-calls` between steps.
- `--variant max` accepted. `--agent plan` accepted (ask-mode candidate).
- `-f <file>` attaches files (prompt attachments). `--dir <cwd>` sets
  session dir. `--title` sets session title.
- Bad model: `{"type":"error", ... "UnknownError", "Unexpected server
  error..."}` but process EXIT=0 — detect via event, not exit code.
- Bad session id: `Error: Session not found` on stderr, EXIT=0 — same,
  parse output.
- No `--sandbox` equivalent; no PreToolUse hook. `--auto` auto-approves
  (equivalent of Codex's bypass flag) — NEVER pass it.

Build (template: `engine/codex.py` + `tests/test_codex.py`, both
one-process-per-turn, resume-by-id):

1. `engine/opencode.py`: `OpencodeEngine` with start/send/events/cancel/
   stop/running/stderr_tail. Map: `text`→delta/message, `tool`→tool
   (via `activity.describe`-style naming), `step_finish`→result (stash
   `tokens` as usage; no contextWindow reported — ctx meter needs a
   fallback, e.g. tokens-so-far vs configured limit, or hidden until
   known), `error`→error. Add `thread_exists()` equivalent (session
   lookup; `opencode` stores sessions server-side — check `opencode
   export`/session list or resume-probe).
2. `modes.py`: `OPENCODE="opencode"` in ENGINE_CYCLE + `opencode_argv()`
   builder + mode mapping (ask→`--agent plan`-style read-only agent;
   action→default agent with permission config).
3. `session.py`: `ensure_started` branch, `resume_hint`
   (`opencode -s <id>`… note: resume needs the message too), field like
   `codex_thread` for opencode session id.
4. `persist.py`: save/load that id (validate on load like Codex rollout
   check).
5. `daemon.py`: `_models_for`, `_default_model`, `_switch_engine`
   fresh/restored logic; auth pre-flight is Claude-only — add opencode
   check or skip.
6. `config.py`: `[opencode]` (binary, models, default_model, agent);
   `commands.py` ENGINES; `problems.py` Meta/opencode rules BEFORE generic
   Claude auth rule; `ui/theme.py` + `gtk_app.py` engine chip class +
   tooltip.
7. **Safety decision (required).** opencode tools bypass PreToolUse.
   Options: (a) ask-mode agent with edit/bash denied; (b) opencode plugin
   hooking tool execution → `policy.classify()` + daemon `ask_permission`
   op (reuses gate + widget UI — best); (c) opencode `permission` config.
   Current repo `opencode.json` has `"*": "allow"` — fail closed whatever
   is chosen.
8. **Billing decision (required).** Meta keys are metered
   (`MODEL_API_KEY*` fish universals) — departs from never-metered rule;
   strip nothing, document deliberately.
9. Tests: fake-binary pattern from `test_codex.py`/`test_engine.py`
   driving stub emitting recorded JSON lines above.

## Purpose / problem solved / philosophy

Purpose: a system-wide assistant embedded in the desktop — SUPER+~ from
anywhere, with the machine's context already attached (focused window,
terminal failure, other sessions) so the user never retypes it. Sessions
are real CLI sessions, resumable from a terminal; the window is a view,
not a silo.

Problem solved: chatbot-in-a-box friction (retyping context, losing
conversations across restarts, irreversible agent edits, password prompts
with no tty, notification noise). Answers: ambient injectors, persist +
`--resume`, reversibility-gated auto-commit undo stack, armed askpass
broker, notify-only-when-interesting.

Philosophy (hold these): subscription CLIs, never metered APIs; safety by
structure (mode flags, sandboxes) + explicit gate (fail closed) + undoable
writes, in that order; default-deny on unknown commands; silence by
default (triage de-dup, notify only actions/errors, no nagging); probes
over docs (hook contract, event shapes recorded from runs); every key
documented in the same change (`commands.KEYBINDINGS` + README +
cheatsheet); prove it works (state changes, not "accepted"/"config ok").
