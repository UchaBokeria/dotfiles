# wa

A terminal WhatsApp client, driven by vim keys, built on
[wacli](https://wacli.sh).

```
all                        107 │  2                              ╭────────────────────────────╮
▪ Nika                     Tue │                                 │ ▎ did you push the nuc      │
  Team Blackwall         5 Tue │                                 │ yeah, just now             │
  aka                   14 Mon │                           14:03 ╰────────────────────────────╯ ✓✓
  Lexo                     Sun │
  ...                          │  1  ╭──────────────────────╮
                               │     │ did you push the nuc │
                               │     ╰──────────────────────╯ 14:02
                               │› write a message
 NORMAL  Team Blackwall                                          chat  running
```

## What it is

`wa` reads and sends WhatsApp messages from a terminal. It does not talk to
WhatsApp itself: wacli does that, and `wa` is the interface in front of it.

This is the **core**. It covers the chat list, the conversation, search, and
sending text. Media rendering, reactions, replies, group administration, AI
integration and development hooks are separate sub-projects, listed in
`docs/superpowers/specs/2026-09-08-wa-core-design.md`.

## Requirements

- `wacli` 0.18 or newer, authenticated (`wacli auth`).
- Go 1.22 or newer to build.

Nothing else. Every dependency is pure Go, so `CGO_ENABLED=0` produces a
binary that runs on Arch and Ubuntu alike.

## Install

```sh
make install                 # builds and installs to ~/.local/bin/wa
```

On Ubuntu, if the packaged Go is older than 1.22:

```sh
sudo add-apt-repository ppa:longsleep/golang-backports && sudo apt install golang-go
```

To keep messages arriving while `wa` is closed, install the optional unit:

```sh
install -Dm644 systemd/wa-sync.service ~/.config/systemd/user/wa-sync.service
systemctl --user enable --now wa-sync.service
```

## Keys

`<Space>?` inside `wa` lists every binding. The shape of it:

| | |
|---|---|
| `Tab` | switch between the chat list and the conversation |
| `j` `k` `gg` `G` `<C-d>` `<C-u>` | move |
| `i` | type: the search box on the left, the message composer on the right |
| `<Esc>` | leave insert; again to leave the draft |
| `<CR>` | open a chat, or send a message |
| `/` `?` `n` `N` | search inside the open conversation |
| `:grep <text>` | search every conversation into the quickfix list |
| `<Space>i` `<Space>in` `<Space>iN` | toggle and walk the quickfix list |
| `<Space><Space>` | jump to a chat by name |
| `u` | undo the last archive, pin, mute or read |
| `ZZ` or `:q` | quit |

Drafts are per chat, and each has its own undo history, so `d`, `ciw`, `daw`,
`u` and macros all work in the composer.

**`u` never unsends.** Only `:revoke` retracts a message, and only your own.

## Configuration

`~/.config/wa/config.toml`. Every default is in there with a comment; the file
shipped in this directory is the same one embedded in the binary.

```toml
[ui]
list_width = 34
scrolloff   = 10
timeoutlen  = 300

[keys.normal]
"<C-p>" = "picker.chats"
```

Change a setting for the session with `:set ui.list_width=40`, or permanently
with `:set!`, which writes to `~/.config/wa/overrides.toml` rather than editing
your hand-written file. `:map n <C-p> picker.chats` rebinds at runtime.
`:actions` lists everything bindable.

The file is watched: saving it re-applies the settings without a restart.

## The lock screen

```sh
wa lock set        # set a password
wa lock clear      # remove it
```

Then turn it on with `[lock] enabled = true`.

**What it does and does not do.** It gates `wa`'s interface. It does *not*
encrypt anything: `~/.local/state/wacli/wacli.db` stays readable on disk by any
process running as you, password or no password. It stops someone sitting down
at an unlocked terminal from reading your conversation; it is not protection
against someone with access to the filesystem.

## How it works

Reads go straight to wacli's SQLite database, opened read-only. A warm
`wacli --json` call costs 11–15 ms, and the interface issues a query per
keystroke while searching, so the direct path is what makes search feel
immediate. A schema probe at startup checks the migration version and every
column the queries name; if either is unrecognised, `wa` falls back to reading
through the wacli CLI and says so in the status line.

Writes always go through wacli, which owns the store lock. While a
`sync --follow` process is running it accepts delegated sends over a Unix
socket in the store directory, and that handover costs about 2.7 seconds — far
too slow to block on, which is why the composer draws the message immediately
and reconciles it when the real id comes back. The measurements behind these
choices are in `docs/delegation-probe.md`.

`wa` starts a sync process if none is running and reaps it on exit. If one is
already running that `wa` did not start, its webhook goes somewhere `wa` cannot
listen, so updates arrive by polling the store instead; the status line says
`polling` when that happens.

## Development

```sh
./run-tests          # gofmt, vet, tests, build
go test ./... -run TestGolden -update    # refresh the render golden files
```

Golden files under `internal/ui/render/testdata` pin the bubble layout at
several widths. Read a regenerated one before committing it: a golden nobody
looked at is a snapshot of a bug.
