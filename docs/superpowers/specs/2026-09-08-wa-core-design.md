# wa — WhatsApp TUI, core sub-project

Date: 2026-09-08
Status: approved, ready for implementation planning
Scope: sub-project 1 of 6 (see "Sub-project map")

## Summary

`wa` is a terminal WhatsApp client written in Go, layered on the `wacli`
command-line tool. It presents a chat list on the left and a conversation on the
right, driven by vim modal editing that matches the author's Neovim
configuration. Everything is configurable, and configuration can be changed at
runtime.

This document specifies **core** only: configuration, theming, the transport to
wacli, the store, the vim engine, and a chat list plus conversation pane that can
read and send text. Media rendering, rich message operations, account
management, AI integration, and development hooks are separate sub-projects,
each with its own spec. Core defines the interfaces they plug into.

## Sub-project map

| # | Name | Contents |
|---|------|----------|
| 1 | core | config, keymaps, theme, transport, store, vim engine, chat list, message pane, send text |
| 2 | media | image/video/audio/document rendering, clickable links, open-in-OS |
| 3 | richmsg | reply, react, edit, delete, forward, star, polls, location |
| 4 | mgmt | groups, contacts, channels, profile, history backfill, store administration |
| 5 | ai | Claude and Codex integration: summarize, draft, translate, ask-about-chat |
| 6 | hooks | development environment integrations, event scripts, notifications |

Each sub-project gets its own spec, plan, and implementation cycle.

## Context and constraints

Established by inspection of the running system on 2026-09-08:

- `wacli` 0.18.1 at `/usr/bin/wacli`, authenticated as `995568669331@s.whatsapp.net`.
- Store at `~/.local/state/wacli`: `wacli.db` (5.2 MB), `session.db`, `LOCK`.
- Store contents: 109 chats, 5987 messages, 101 contacts, 19 groups. FTS5 enabled.
- `wacli.db` uses **WAL** journal mode, so concurrent readers are safe while the
  sync process writes.
- `LOCK` is an advisory pidfile (`pid=`, `acquired_at=`). `wacli doctor --json`
  reports `lock_held` and validates pid liveness.
- Warm `wacli ... --json` invocation costs **11–15 ms**.
- Schema is versioned in `schema_migrations`; highest applied version is **26**.
- Only one process may hold the store lock. `wacli sync --follow` holds it, and
  its `--send-spacing` flag ("pace delegated sends in follow mode") indicates
  that sends issued while it runs are delegated to it. **This is an assumption
  and is verified as implementation task 1.**
- Live updates are available two ways: `sync --webhook <url>` (events `message`,
  `receipt`, `chat_presence`, HMAC-SHA256 signed) and a global `--events` NDJSON
  stream on stderr. Core uses the webhook.
- Target terminals: kitty inside tmux (the author's setup) and any
  xterm-256color terminal. Target distributions: Arch and Ubuntu.
- The blackwall rice derives every surface's colours from
  `theme/blackwall_theme/tokens.py` through the `blackwall-theme` generator.
  No colour literal may appear in this project's source.

## Decisions

| Decision | Choice |
|----------|--------|
| Home | `blackwall/whatsapp/`, Go module `github.com/UchaBokeria/blackwall/whatsapp` |
| Binary | `wa` |
| Sync ownership | Hybrid: adopt a running sync, otherwise spawn and reap one |
| Config | TOML, hot-reloaded, with runtime `:set` and `:map` |
| Lock screen | Argon2id hash in a state file outside the dotfiles repo |
| Vim fidelity | Full: motions, counts, operators, text objects, registers, macros, dot-repeat, jumplist, quickfix |
| Message rendering | WhatsApp-style bubbles |
| Architecture | Direct read-only SQLite reads with CLI fallback; all writes through the wacli CLI; Bubble Tea UI |

## Architecture

```
blackwall/whatsapp/
  go.mod                    module github.com/UchaBokeria/blackwall/whatsapp
  cmd/wa/main.go            flags, subcommands, TUI launch
  internal/
    domain/                 pure types: JID, Chat, Message, Media, Contact, Event
    config/                 TOML load, defaults, validation, hot reload, dotted-path access
    theme/                  Palette -> lipgloss styles; theme.toml + embedded fallback
    store/                  Reader interface; sqlite (read-only) and cli implementations
    wacli/                  Client; the only package that executes a subprocess
    daemon/                 sync lifecycle: adopt-or-spawn, state file, reap-if-owned
    live/                   webhook listener, HMAC verification, poll fallback
    vim/                    modal engine; no WhatsApp knowledge; own test suite
    action/                 registry mapping action names to handlers
    lock/                   argon2id credential file, verification, idle timer
    ui/                     bubbletea root and panes
      render/               bubble layout, wrapping, day separators, delivery ticks
    xdgpath/                config, state, cache, media paths
```

### Boundaries

Three boundaries carry the design.

**`vim` knows nothing about WhatsApp.** It consumes keystrokes and produces
`Resolved{Action, Count, Register, Motion, Range}`. Macros, registers, counts,
operators, dot-repeat, the undo stack, and the `:` parser live there and are
tested against a fake buffer with no network, database, or terminal. Given the
full-fidelity requirement this is the package most likely to grow; isolating it
keeps that growth contained.

**`action` is the only thing `vim` and `ui` share.** Configuration binds
`"<C-d>" = "scroll.half_down"`, and the registry resolves that string. This makes
"everything is configurable" true by construction: the registry is exactly what
`:map`, the keymap picker, and `:actions` enumerate.

**`wacli` is the only package that spawns a process.** Every mutation funnels
through it, so lock handling, timeouts, JSON envelope decoding, and error
translation exist in one place. `store` never writes.

### Data flow

- Reads: `ui` -> `store.Reader` -> SQLite (or CLI fallback) -> `domain`.
- Writes: `ui` -> `action` -> `wacli.Client` -> `wacli` -> sync process.
- Live: sync -> HTTP POST -> `live` -> `domain.Event` -> `tea.Msg` -> `ui`
  invalidates the affected chat and re-reads it from the store.

## Components

### domain

Pure value types with no I/O and no dependencies on other internal packages:
`JID`, `ChatKind`, `Chat`, `Message`, `MediaRef`, `Contact`, `Event`,
`DeliveryState`. Every other package speaks these types.

`JID` parses and normalizes the WhatsApp forms (`<user>@s.whatsapp.net`,
`<id>@g.us`, `<id>@newsletter`, `<id>@broadcast`) and exposes `Kind()` and a
display form.

### config

Loaded from `$XDG_CONFIG_HOME/wa/config.toml`, which is symlinked out of
`blackwall/whatsapp/config.toml`. Embedded defaults are overlaid by the user
file.

- Unknown *keys* produce a startup warning that lists them, and loading
  continues.
- An unknown *action name* in a keymap is a fatal startup error naming the
  offending file and line. A binding that silently does nothing is worse than a
  refusal to start.
- Hot reload watches the file with fsnotify and a 150 ms debounce. A parse error
  keeps the previous configuration in effect and surfaces the error; it never
  silently reverts to defaults.
- `Get(path string)` and `Set(path, value string)` provide dotted-path access for
  `:set ui.list_width=40`.
- `:set!` persists by rewriting a trailing marked block:

  ```
  # --- written by :set! --- do not edit inside this block
  ...
  # --- end :set! ---
  ```

  Hand-written TOML above the block, including comments, is left untouched. This
  is the same splice idiom `blackwall-theme` uses for `tmux.conf.local`.

Default settings mirror the author's Neovim configuration where an analogue
exists: `leader = "<Space>"`, `timeoutlen = 300`, `scrolloff = 10`,
`ignorecase = true`, `smartcase = true`, `clipboard = "unnamedplus"`,
`gutter = "hybrid"` (absolute number on the cursor line, relative elsewhere).

### theme

A new `blackwall-theme` target named `wa` writes `blackwall/whatsapp/theme.toml`
from the existing token set (`bg`, `fg`, `accent`, `on_accent`, `link`, `muted`,
`faint`, `cursor`, `raised`, `raised_hi`, `sunken`, `edge`, `selection`, `warn`,
`bad`, `good`, and the sixteen ANSI entries). `scripts/setwall` therefore
re-themes the TUI in the same pass as every other surface.

`theme.Load` reads that file when present and otherwise uses a palette embedded
in the binary, so a machine without the dotfiles still renders correctly.
`[theme] file = "..."` overrides the path. The package exposes named lipgloss
styles; no Go source contains a colour literal.

Border style is configurable (`rounded`, `thick`, `double`, `ascii`, `none`) with
`rounded` as the default.

### store

```go
type Reader interface {
    Chats(ctx context.Context, f ChatFilter) ([]domain.Chat, error)
    Chat(ctx context.Context, jid domain.JID) (domain.Chat, error)
    Messages(ctx context.Context, f MessageFilter) ([]domain.Message, error)
    Message(ctx context.Context, chat domain.JID, id string) (domain.Message, error)
    Search(ctx context.Context, q Query) ([]domain.Message, error)
    Contact(ctx context.Context, jid domain.JID) (domain.Contact, error)
    Stats(ctx context.Context) (Stats, error)
    Close() error
}
```

Two implementations.

`sqliteReader` opens `file:<store>/wacli.db?mode=ro&_pragma=busy_timeout(5000)`
using `modernc.org/sqlite` (pure Go, so no cgo). WAL permits reading while the
sync process writes. Read-only mode is enforced by the DSN, not by convention.

`cliReader` shells out to `wacli ... --json` through the `wacli` package.

Selection happens once at startup: `select max(version) from schema_migrations`
must be a version this build understands (26 at time of writing), and
`PRAGMA table_info` must show every column actually read. Either check failing
selects `cliReader` and emits one warning. This makes a wacli upgrade degrade
rather than misread.

Paging is keyset on `(ts, rowid)`; `OFFSET` is never used.

Columns read from `messages`: `rowid, chat_jid, chat_name, msg_id, sender_jid,
sender_name, ts, from_me, text, display_text, quoted_msg_id, quoted_sender_jid,
is_forwarded, reaction_to_id, reaction_emoji, media_type, media_caption,
filename, mime_type, file_length, local_path, downloaded_at, revoked,
deleted_for_me, edited, edited_ts`. From `chats`: `jid, kind, name,
last_message_ts, archived, pinned, muted_until, unread, unread_count`.

### wacli

```go
type Client interface {
    Doctor(ctx context.Context) (Doctor, error)
    SendText(ctx context.Context, req SendTextRequest) (SentMessage, error)
    MarkRead(ctx context.Context, jid domain.JID) error
    MarkUnread(ctx context.Context, jid domain.JID) error
    Archive(ctx context.Context, jid domain.JID, on bool) error
    Pin(ctx context.Context, jid domain.JID, on bool) error
    Mute(ctx context.Context, jid domain.JID, on bool) error
    Typing(ctx context.Context, jid domain.JID, on bool) error
    Raw(ctx context.Context, args ...string) ([]byte, error)
}
```

Every call uses `exec.CommandContext` with the configured timeout, always passes
`--json`, and decodes the `{success, data, error}` envelope. Configured
`--account` and `--store` flags are injected centrally.

Errors are translated into typed values: `ErrStoreLocked` (retried once with
`--lock-wait`), `ErrUnauthenticated`, `ErrAmbiguousRecipient` carrying the
candidate list, `ErrTimeout`. A non-zero exit with unparseable output becomes
`ErrWacli` carrying the trimmed stderr.

Sends are serialized through a single worker goroutine so that rapid `Enter`
presses cannot interleave.

### daemon

Startup calls `wacli doctor --json` and branches:

1. Lock free: spawn

   ```
   wacli sync --follow \
     --webhook http://127.0.0.1:<port>/e \
     --webhook-allow-private \
     --webhook-secret <32 random bytes, hex> \
     --webhook-events message,receipt,chat_presence
   ```

   with `--download-media` added when `[media] auto_download` is set. Write
   `~/.local/state/wa/daemon.json` (mode 0600) containing `pid`, `port`,
   `secret`, `owned: true`.

2. Lock held and `daemon.json` names a live pid: attach, reusing its port and
   secret.

3. Lock held with no usable state file — the case where `wacli sync` was started
   by hand in a shell: webhooks cannot be received, so `live` uses its polling
   source. The status line shows `sync: polling`, making the degradation visible.

Exit reaps the sync process only when `owned` is true: `SIGTERM`, then `SIGKILL`
after a grace period, then remove the state file. A stale state file whose pid is
dead is cleaned up on startup. Unexpected death triggers a backoff restart with
`sync: reconnecting` in the status line.

A systemd user unit for always-on background sync is provided but not required.

### live

An HTTP server bound to `127.0.0.1:0`, so the kernel assigns the port and it is
read back after `Listen`. Each request must come from a loopback address and
carry a valid `X-Wacli-Signature` HMAC-SHA256 over the body; anything else is
rejected with 401 and logged.

**Events are invalidation hints, not data.** A decoded event marks a chat dirty;
the UI then re-reads the authoritative rows from the store. The event channel is
bounded and drops oldest under burst, incrementing a counter. Because payloads
are never trusted as the source of truth, a dropped event costs latency and
nothing else.

`Source` is an interface with two implementations, `WebhookSource` and
`PollSource`. The poll source compares `max(rowid)` and `last_message_ts` on a
configurable interval (default 2 s), which is cheap given sub-millisecond reads.

### vim

The input pipeline is single-path so that macro replay and live typing cannot
diverge:

```
tea.KeyMsg -> Key{mods, rune|special} -> macro recorder (tee)
           -> count accumulator -> register prefix
           -> keymap trie walk (per mode)
           -> Resolved{Action, Count, Register, Motion, Range}
           -> action registry -> handler
```

Macros record *keys*, not actions, so `@a` traverses the identical pipeline.

**Modes**: normal, insert, visual, visual-line, operator-pending (a sub-state of
normal), cmdline, search. Trie ambiguity resolves after `timeoutlen`
milliseconds, default 300.

**Focus versus modes.** The composer and the search box are not focus targets;
they are the insert surface of their pane. `Tab` and `<S-Tab>` toggle the pane;
`<C-h>`, `<C-l>`, `<C-j>`, `<C-k>` also move focus. `i` on the left begins search
typing, `i` on the right opens the composer, and `Esc` returns to normal mode in
that pane. `<Esc>` in normal mode clears search highlighting.

**Motions, message pane**: `j`, `k`, `{`, `}` (sender or day block), `gg`, `G`,
`<C-d>`, `<C-u>`, `<C-f>`, `<C-b>`, `zz`, `zt`, `zb`, `H`, `M`, `L`,
`f{char}` (next message from a sender whose name starts with the character),
`/`, `?`, `n`, `N`, marks `m{a-z}` local and `m{A-Z}` global, recalled with
`` ` `` and `'`.

**Motions, composer**: `h`, `j`, `k`, `l`, `0`, `^`, `$`, `w`, `W`, `b`, `B`,
`e`, `E`, `ge`, `f`, `F`, `t`, `T`, `;`, `,`, `%`, `(`, `)`.

**Operators and text objects** (composer): `d`, `c`, `y`, `gu`, `gU`, `g~`, with
`iw`, `aw`, `i"`, `a"`, `i'`, `a'`, `i(`, `a(`, `i[`, `a[`, `i{`, `a{`, `ip`,
`ap`, `is`, `as`; plus `A`, `I`, `o`, `O`, `p`, `P`, `x`, `s`, `S`, `D`, `C`.

**Registers**: unnamed `"`, named `a`–`z` with `A`–`Z` appending, yank `"0`,
blackhole `"_`, and system `"+` / `"*` bridged to the terminal clipboard through
OSC 52, which works through kitty and tmux. With `clipboard = "unnamedplus"` the
unnamed register aliases the system register.

**Dot-repeat**: actions declare `Repeatable`; `.` replays the last repeatable
action with its count and register.

**Jumplist**: entries are `{chat, anchor, cursor}`, pushed on chat switch, search
jump, `gg`, `G`, and quickfix jumps. `<C-o>` and `<C-i>` traverse across chats.

**Quickfix**: `:grep <pattern>` runs an FTS search across every chat into the
list. `<leader>i` toggles it, `<leader>in` and `<leader>iN` move, `<leader>io`
opens, `<leader>ip` opens it in the picker — the same bindings as the author's
Neovim quickfix section.

**Undo is two independent stacks.**

- *Composer*: a linear undo stack per draft, `u` and `<C-r>`, one stack per chat,
  retained for the session. A branching undo tree is deliberately not built: it
  earns its keep in a file that is revisited, not in a draft written once and
  sent.
- *Actions*: a ring of reversible actions, each carrying a declared inverse —
  archive, mute, pin, star, mark-read. `u` in the message pane reverses the most
  recent one.

**Sends and deletions are never enrolled on the undo ring.** `u` after a send
refuses and directs the user to `:revoke`; `u` after a delete refuses and reports
that the message is gone. An undo key that sometimes retracts a message sent to
another person is a trap, so it never does; retraction stays an explicit typed
command.

### action

A registry of named actions:

```go
type Action struct {
    Name       string
    Summary    string
    Modes      []vim.Mode
    Repeatable bool
    Run        func(ctx Context) error
}
```

Namespaced names: `pane.*`, `list.*`, `chat.*`, `scroll.*`, `msg.*`,
`composer.*`, `search.*`, `qf.*`, `picker.*`, `app.*`. `:actions` lists the
registry; the keymap picker is generated from it; configuration validation checks
against it.

### lock

`wa lock set` prompts twice and writes `~/.local/state/wa/lock.json` (mode 0600):

```json
{"algo":"argon2id","salt":"...","hash":"...","t":3,"m":65536,"p":4}
```

This lives in the state directory, never in `config.toml`, so nothing secret is
ever committed to the dotfiles repository. `wa lock clear` removes it.

When `[lock] enabled` is true the TUI draws a lock screen before any data is
loaded and accepts input only there. `idle_timeout` re-locks after inactivity and
`on_suspend` re-locks on resume. `:lock` locks immediately.

**Documented limitation.** The lock gates the interface only. It does not protect
data at rest: `~/.local/state/wacli/wacli.db` remains readable by any process
running as the same user. This is stated in the README and in `:help lock` so the
protection is not overestimated.

### ui

A Bubble Tea root model owning: chat list pane, message pane, composer, command
line, status line, picker overlay, lock overlay, and the `:log` buffer.

Layout is a left column of configurable width (default 34) and a right column
taking the remainder, with a one-line status bar and a one-line command line.
Below `[ui] min_width` (default 80) the layout collapses to a single pane that
`Tab` switches between.

Chat list rows show pin and mute indicators, chat name, unread badge, relative
timestamp, and a snippet of the last message. Filters are `all`, `unread`,
`pinned`, `archived`, `muted`, `groups`, `dms`, cycled with `<Tab>`-adjacent
bindings and set directly with `:filter <name>`. Search filters the list
incrementally as it is typed.

The message pane renders bubbles: messages from the account right-aligned inside
a bordered box, others left-aligned with a sender label above in group chats. Day
separators divide the stream. Delivery state renders as `⧗` pending, `✓` sent,
`✓✓` delivered, and `✓✓` in the accent colour for read. Quoted replies render as
an indented bar inside the bubble. Edited messages carry an `(edited)` marker,
revoked messages a placeholder.

Rendering is width-bucketed and memoized: a message's rendered lines are cached
per `(id, width, theme generation)`, so scrolling 6000 messages does not re-wrap
text repeatedly.

Optimistic send: the composer inserts a pending bubble immediately, the returned
message id reconciles it against the real row, and a failure marks the bubble
with the error while leaving the draft intact.

## Error handling

No failure is silent. Every wacli error reaches both the status line and the
`:log` buffer. Each degradation announces itself exactly once per session:
schema fallback to the CLI reader, poll fallback for live updates, and any
missing optional tool.

Preflight runs before the first frame: `wacli` present and at least version
0.18, authentication confirmed (otherwise the screen explains `wacli auth`), and
the store readable. A failed preflight prints a diagnosis and exits non-zero
rather than opening an empty interface.

## Testing

| Package | Approach |
|---------|----------|
| `vim` | Table-driven key-to-`Resolved` tests, plus a keyscript runner that feeds a string of keys and asserts buffer, undo, and register state |
| `domain` | Property-style tests over JID parsing and normalization |
| `config` | Round-trip load, overlay, validation errors, `:set!` splice preservation |
| `store` | Fixture database built from checked-in DDL under `testdata`; never touches the live store |
| `wacli` | A fake `wacli` binary injected on `PATH`, built by the test; no network and no real account |
| `live` | HMAC acceptance and rejection, drop-oldest behaviour under burst |
| `render` | Golden snapshots of bubble layout at widths 40, 80, and 120 with ANSI stripped |
| `ui` | `teatest` end-to-end from key press to rendered frame |

`whatsapp/run-tests` mirrors `theme/run-tests` and additionally runs `gofmt -l`
and `go vet`. Development follows test-first discipline: a failing test precedes
each behaviour.

## Packaging

Pure Go with `CGO_ENABLED=0`; dependencies are `modernc.org/sqlite`,
`github.com/charmbracelet/bubbletea`, `github.com/charmbracelet/lipgloss`,
`github.com/BurntSushi/toml`, `github.com/fsnotify/fsnotify`, and
`golang.org/x/crypto`. The `go.mod` language version is kept low enough for the
toolchain packaged by current Ubuntu.

`wa` is added to `SCRIPTS` in `scripts/link-bin`, and `docs/cheatsheet.md` gains
a section in the same change, per the repository rule that a documented command
must also be on `PATH`.

## Risks

**Send delegation is unproven.** The design assumes `wacli send` succeeds while
`sync --follow` holds the lock, delegating through it. `--send-spacing` is strong
evidence but not proof. Implementation task 1 verifies this against a chat the
author nominates, before any interface work. If sends instead require exclusive
lock ownership, the daemon must stop, send, and restart, and that change comes
back for review rather than being absorbed silently.

**Schema coupling.** Direct reads couple to wacli's internal schema. Mitigated by
the migration-version probe, the column guard, and the CLI fallback reader.

**Graphics through tmux.** Not a core concern — media rendering is sub-project 2
— but kitty's graphics protocol requires tmux passthrough, and `chafa` is not
installed. Core only needs to keep the renderer interface free of assumptions
about how a message body is drawn.

## Out of scope for core

Media rendering and playback, reactions, replies, edits, deletions, forwarding,
starring, polls, locations, group and channel administration, contact
management, profile editing, history backfill, AI features, development hooks,
and notifications. Core provides the interfaces these attach to and nothing more.
