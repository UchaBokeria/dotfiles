# ArchPilot

System-wide AI assistant for the blackwall Hyprland rice, bound to `SUPER + ~`.

Driven by the **Claude Code CLI**, using your existing OAuth subscription
credentials. It never imports an Anthropic SDK and never touches the metered
API — the daemon spawns `claude` and talks to it over stdio.

## What it is

An eww widget with a prompt input and a status bar, backed by a daemon that
holds a long-lived `claude` process per conversation. Two modes:

| Mode | Enforced by | Can it change the machine? |
|---|---|---|
| **ask** | `--permission-mode plan` + `--disallowedTools` | No — structurally |
| **action** | `--permission-mode acceptEdits` + PreToolUse gate | Yes, after policy review |

Sessions are real Claude Code sessions. Anything started in the widget can be
picked up in a terminal:

```fish
cd ~/.config/.dotfiles/blackwall/archpilot
claude --resume <session-id>      # archpilot state | jq -r .resume
```

The current conversation survives a daemon restart or a reboot: the pointer is
kept in `~/.local/state/archpilot/last-session.json` and re-attached with
`--resume`. Claude Code already stores the transcript; only the pointer was
missing.

## The window

`SUPER + ~` opens it (`archpilot ui`). It is a plain GTK4 window, not a layer
surface, and that is the whole point: it takes keyboard focus by itself, every
keystroke is ours so vim editing is real, and its scroll position can be driven
so the transcript follows an answer.

The eww widget it replaced has been removed. It could not hold focus, could not
handle keys, and the daemon opening it behind the GTK window is what produced
the second, unclosable window when a command asked for permission.

### `:` commands

`:new`, `:model opus`, `:effort max`, `:mode action`, `:history`, `:sessions`,
`:tabnew`, `:tabclose`, `:export ~/chat.md`, `:copy`, `:mcp chrome on`, `:q`.
Aliases and unambiguous prefixes work as in vim (`:q`, `:tn`, `:expo`), and
`tab` completes. Parsing lives in `commands.py` with no GTK import, so it is
tested headless.

### Tabs

Several conversations at once: `:tabnew`, `gt` / `gT` to cycle, `alt+1..9` to
jump, `:tabclose`. Each tab is a separate Claude Code session with its own
transcript, so every one stays resumable from a terminal - tabs are a view over
sessions, not a new concept. The bar hides itself when only one is open.

### Regions

`Tab` moves the keyboard between the input and the conversation; `shift+tab`
cycles mode, `ctrl+tab` model, `alt+tab` effort. In the conversation the keys
are vim-ish: `j`/`k` select, `gg`/`G` jump, `y` copies, `u` continues from that
message, `ctrl-d`/`ctrl-u` scroll, `super+enter` runs whatever that message
proposed. The selected message is lifted and rail-marked.

`ctrl-h` opens history in a panel at the top: type to filter, `tab` moves into
the results, `j`/`k` move, `enter` loads it into the prompt.

### Vim

Real modal editing, implemented in `src/archpilot/vim.py` with no GTK import so
it is testable headless (58 tests).

| | |
|---|---|
| motions | `h j k l 0 ^ $ w W b B e E f F t T gg G` |
| operators | `d c y` + any motion, `dd cc yy`, `D C Y`; counts either side (`d2w` == `2dw`) |
| edits | `x X s S p P`, `u` / `ctrl-r` |
| insert | `i I a A o O`, `ctrl-w`, `ctrl-u`, backspace |
| lines | `o O` open a line, `dd cc yy` are line-wise, `D C` stop at end of line |
| visual | `v` charwise, `V` linewise; `d y c` apply to the selection |
| edits | `r{char}` replace, `J` join lines, `~` toggle case |
| scroll | `ctrl-d` / `ctrl-u` half a page, in normal mode |
| app | `ctrl-n` new · `ctrl-h` history · `ctrl-s` sessions · `ctrl-l/e/t` cycle model/effort/mode · `ctrl-enter` run action · `q` close |

The prompt is multi-line: **shift+enter** inserts a line break and the box
grows with it, up to a cap - past that it scrolls, so a long paste can never
push the conversation off the top. `Enter` submits; **super+enter** runs the
command the last answer proposed, and does nothing when there isn't one.

`Tab` cycles mode, `ctrl+tab` model, `alt+tab` effort. Defaults are ask / haiku
/ medium. Every button carries a tooltip naming its key.

Each message has its own copy button, and drag-selecting any text copies it to
both the clipboard and the primary selection - so middle-click paste works too.
A command that has been run stops being a button and stays in the conversation
as a record of what happened.

History search lives **inside the window** (`ctrl-h`): type to filter, `up`/`down`
to pick, `enter` to load it into the prompt. It replaced rofi, which had to be
handed both the screen and the keyboard and could never show useful context.

The window starts compact and grows with the answer up to a cap, then scrolls.
It also enters a Hyprland submap whenever it has focus, so the rest of your
SUPER keymap is inert while you are typing at it and returns the moment you
focus something else.

`Esc` in normal mode does nothing, as in vim. Application commands live on
`ctrl-` so they never shadow a motion - `n`, `p`, `d` and `y` all mean something
in normal mode already.

Set `ARCHPILOT_UI_DEBUG=/tmp/keys.log` to trace every keystroke with the
resulting mode and buffer; it is how the two subtlest bugs here were found.

## Keybinds

| Key | Action |
|---|---|
| `SUPER + ~` | toggle the widget (session keeps running while hidden) |
| `SUPER + SHIFT + ~` | region screenshot, staged for the next prompt |
| `SUPER + CTRL + ~` | browse Claude Code sessions (rofi) |
| `SUPER + ALT + ~` | browse and re-ask past prompts (rofi) |
| `SUPER + CTRL + Return` | run the first suggested action |

## Status bar

The chips are buttons. Clicking one cycles it:

| Chip | Cycles through |
|---|---|
| mode | ask → action |
| model | opus → sonnet → haiku |
| effort | low → medium → high → xhigh → max |

All three are per-process flags on the `claude` child, so changing one stops the
engine and re-attaches with `--resume`. The conversation survives the switch —
verified by having sonnet memorise a word and haiku recall it.

Alongside them: a context-occupancy chip (`ctx 42%`, which turns amber past
75% — a session quietly filling its window is what makes later turns
expensive), a history button, a stop button while a turn is running, and
copy buttons on the answer and on each suggested command. GTK3 labels are not
selectable and eww exposes no `:selectable`, so copy buttons are the only way
to get text out of the widget.

## Prompt directives

Typed at the start of a prompt:

| Directive | Effect |
|---|---|
| `:opus` `:sonnet` `:haiku` `:fable` | model for this turn |
| `:ask` `:action` | mode for this turn |
| `:term` | force-attach terminal scrollback |
| `:sys` | force-attach system state |
| `:sess` | force-attach other Claude sessions |
| `:clip` | attach the clipboard |
| `:sel` | attach the primary selection (whatever is highlighted) |

`:clip` and `:sel` are the only injectors with no heuristic behind them. A
clipboard routinely holds passwords and tokens, and attaching it to any prompt
that happens to say "this" would write them into a transcript that lives on
disk — so they are reached by directive only.

Context is otherwise attached only when the prompt calls for it — "why did that
fail?" pulls scrollback, "how do I write a for loop" pulls nothing.

## Ambient triage

The one part that speaks first. A timer scans for conditions that are
actionable, unambiguous, and would otherwise be found at a bad time:

| Check | Fires when |
|---|---|
| `pacnew` | `.pacnew` / `.pacsave` files are waiting to be merged |
| `failed-units` | any system or user unit is failed |
| `disk` | a filesystem is ≥90% full (urgent at 95%) |
| `docker` | ≥5 GB is reclaimable |

Each finding carries the prompt that would deal with it, so acting is one
command: `archpilot triage --ask docker` seeds a session and opens the widget.

Silence is the default. An unchanged finding is not repeated for 12 hours —
a notification that reappears hourly trains you to ignore the channel.

```fish
systemctl --user enable --now archpilot-triage.timer
archpilot triage          # just list what it sees
```

## Waybar

`waybar/modules/archpilot.json` adds a `custom/archpilot` module. It streams
rather than polls, so the bar reflects the daemon instantly. Left click toggles
the widget, right click opens history, middle click cycles mode. It turns amber
when something needs you.

## Safety

Three layers, in order:

1. **Denylist** — `rm -rf /`, `mkfs`, `dd of=/dev/*`, `curl | sh`, fork bombs.
   Refused in every mode, never offered as a prompt.
2. **Reversibility** — reads and revertable edits run freely; anything
   irreversible pauses and shows you the exact command (`src/archpilot/policy.py`).
3. **Auto-commit** — changes under the dotfiles repo are committed as
   `archpilot: …`, scoped to only what the turn touched. `archpilot undo`
   reverts. Your unrelated work in progress is never swept in.

The gate **fails closed**: if the daemon is unreachable or the hook crashes, the
command is refused. See `docs/hook-contract.md` — that behaviour is not the
default and had to be built deliberately.

### Commands that need a password

A `sudo` command would otherwise hang forever: the Bash tool has no tty, so sudo
has nothing to prompt on. ArchPilot puts a `sudo` shim early in the child's PATH
that adds `-A`, and points `SUDO_ASKPASS` at `hooks/askpass.py`:

```
sudo  ->  askpass helper  ->  daemon  ->  masked field in the widget
```

Claude never sees the password — sudo invokes the helper directly, so it never
enters the model's context. Three rules make that hold:

1. **Elevation always asks.** `sudo anything` goes to the approval gate first,
   so you see the exact command before a password field appears.
2. **The broker is armed, not open.** It answers only while an approved elevated
   command is running. Otherwise the model could invoke the helper itself
   (`SUDO_ASKPASS` is in its environment) and make you type a password for a
   command nobody approved. Arming lasts for that command's turn, so sudo's
   normal three retries work.
3. **Nothing is stored.** The password is held in one Future, handed to one
   caller, and dropped. sudo's own timestamp cache covers repeats.

One honest caveat: eww can only invoke shell commands, so the typed value
arrives as an argument and is briefly visible in `/proc/<pid>/cmdline`. On a
single-user desktop that window is narrow, but it is real.

## A note on your rofi themes

ArchPilot generates its own picker theme from `eww/colors.scss`, and — unless
you set `rofi.sync_launcher_colors = false` — also writes the
`shared/colors.rasi` that every launcher theme in this rice imports. That file
is wallust's job and was missing, which is why the launchers rendered unstyled.
Both are regenerated on daemon start, so they follow the wallpaper.

## Setup

```fish
cd ~/.config/.dotfiles/blackwall/archpilot
uv sync
systemctl --user enable --now archpilotd.service
eww reload
hyprctl reload

# optional: makes `archpilot` available in your shell.
# eww and hyprland call the venv binary by absolute path and do not need this.
ln -sf ~/.config/.dotfiles/blackwall/archpilot/.venv/bin/archpilot ~/.local/bin/archpilot
```

Config lives at `~/.config/archpilot/config.toml`; every key has a default, so
the file is optional. See `DEFAULTS` in `src/archpilot/config.py`.

## Layout

```
src/archpilot/
  daemon.py      socket server, turn runner, approval broker
  engine/        spawns `claude`, parses stream-json  (swappable seam)
  policy.py      denylist + reversibility classifier
  session.py     one conversation = one Claude Code session
  markup.py      markdown -> Pango, plus the wrapping eww cannot do
  context/       window, terminal, system, sessions, relevance
hooks/pretooluse.py   the gate. read docs/hook-contract.md first.
```

The daemon speaks newline-JSON over `$XDG_RUNTIME_DIR/archpilot.sock`, so the
frontend is swappable — eww is a client, not a dependency.

## Things that cost a probe to learn

Recorded so they are not rediscovered the hard way:

- `--bare` forces `ANTHROPIC_API_KEY` auth. Using it would silently move
  ArchPilot onto metered billing. Never use it.
- `--mcp-config '{}'` is rejected; the empty value is `'{"mcpServers":{}}'`.
  Without `--strict-mcp-config`, all ~20 configured MCP servers load their tool
  schemas into every turn.
- A PreToolUse hook killed by timeout, or exiting non-zero with no stdout,
  **lets the command run**. Only `permissionDecision: "deny"` and `exit 2` block.
- eww's `deflisten` does not interpolate `defvar`s into its command string —
  it needs a literal path.
- The eww daemon's PATH (from Hyprland `exec-once`) does not include
  `~/.local/bin`, so the widget calls the venv binary by absolute path.
- eww 0.5.0 labels ignore `:wrap`, `:limit_width` and `:show_truncated`;
  all four combinations ellipsise. Wrapping happens in `markup.py` instead.
- GTK3 CSS has no `line-height` or `caret-color`; either one aborts the rest of
  the stylesheet parse.
- kitty's `listen_on unix:@mykitty` actually listens on `@mykitty-<pid>`.
- GTK activates the *focused widget* on Space and Enter. With a focusable button
  in the header, typing a space pressed it - the keystroke never reached the
  editor and the buffer was cleared. Every button here is `set_can_focus(False)`.
- A key controller added to a window runs in the bubble phase, so children see
  keys first and something was eating Return. `PropagationPhase.CAPTURE` makes
  the window authoritative, which is what vim needs.
- A command launched from an eww button is a child of eww: closing the window
  can reap it, and calling back into eww from it can deadlock. The rofi pickers
  therefore run in the daemon, and the button only writes one line to a socket.
- `windowrules.conf` ends with `match:class ^(.*)$, size 1000 750`, so *every*
  window is forced to that size and nothing can size itself to its content.
  `configs/archpilot.conf` is sourced later and overrides it.
- `noborder` is not a valid windowrule field in Hyprland 0.56 - nor is
  `border`, `no_border` or any spelling of it. `hyprctl reload` still prints
  `ok`; the error only shows in `hyprctl configerrors`.
- A window's own preferred size is bounded by the size the compositor already
  forced on it, so asking it echoes that back and nothing ever grows. Measure
  the child, and resize with `hyprctl dispatch resizewindowpixel`.
- A `ScrolledWindow` reports almost no natural height unless
  `set_propagate_natural_height(True)` is set, so a window sized from its
  content never grows with the transcript.
- Ask mode does **not** use `--permission-mode plan`. Its system prompt made
  every answer open with "this is not a planning task", and no appended
  instruction overrode it. The write tools are removed outright instead and the
  hook refuses mutations in ask mode, so it still cannot change anything.
- `noborder` / `bordersize` are not valid windowrule fields in Hyprland 0.56;
  the working ones are `border_size 0` and `rounding N`.
- `wl-copy` forks and stays resident to serve the selection, so waiting for it
  to exit blocks until something else takes ownership - it froze the UI.
- Reading whole transcripts to build history cost ~3s. Tail-reading the last
  96KB with an mtime-keyed cache brings it to ~60ms cold, ~3ms warm.
- PyGObject is built for the system interpreter, so `bin/archpilot-ui` runs on
  `/usr/bin/python3` rather than the uv venv. ArchPilot has no third-party
  dependencies, so `PYTHONPATH` is all that is needed.
- The widget is on the layer-shell **overlay** layer, which draws above ordinary
  windows - so rofi opened *behind* it and a click looked like it did nothing.
  The pickers hide the widget first and restore it afterwards; `shot` does the
  same so the overlay is not baked into the capture.
- rofi's `config.rasi` holds settings but no theme, so a bare `rofi -dmenu` is
  unstyled. The launcher themes in this rice cannot be borrowed either: they
  `@import "shared/colors.rasi"`, which does not exist here (wallust never
  generated it) - which also means the SUPER+R / SUPER+F launchers are
  currently unthemed. ArchPilot generates its own self-contained theme from
  `eww/colors.scss` instead, so it re-themes with the wallpaper.
- In yuck, `"{var}"` inside a string is literal text; interpolation is `"${var}"`.
  The wrong one renders the expression to the user verbatim.
- A PreToolUse hook *can* rewrite a command via `updatedInput` — but then the
  transcript records something the user never approved, and the model notices
  and reports it as tampering. Hence the PATH shim for sudo.
- asyncio's `StreamReader` caps a line at 64KB, but stream-json puts a whole
  message on one line. A screenshot comes back as base64 and blows past it,
  raising "Separator is not found" and wedging the turn. Hence
  `limit=STREAM_LIMIT` on the subprocess.
- `git status --porcelain` collapses an untracked *directory* into one entry, so
  a file created inside an already-untracked tree is invisible to a
  before/after diff. Auto-commit needs `-uall`.
