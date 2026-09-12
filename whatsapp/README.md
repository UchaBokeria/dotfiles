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

It covers the chat list, the conversation, search, sending, replies, reactions,
forwarding, deletion, and media - images, video, audio and documents, drawn in
the terminal or handed to the desktop. Group administration, AI integration and
development hooks are separate sub-projects, listed in
`docs/superpowers/specs/2026-09-08-wa-core-design.md`.

## Requirements

- `wacli` 0.18 or newer, authenticated (`wacli auth`). The installer fetches it
  from its own releases if it is missing.
- Go 1.22 or newer to build.

Nothing else is required. Every dependency is pure Go, so `CGO_ENABLED=0`
produces a binary that runs on Arch and on a headless Ubuntu server alike, with
no X11, no desktop and no C toolchain.

Three optional programs each buy one thing, and their absence costs only that:

| Missing | What you lose |
|---|---|
| `ffmpeg` | a video's first frame, and a voice note's waveform |
| `wl-copy` / `xclip` | copying through a helper; wa falls back to OSC 52, which works over ssh |
| `xdg-open` | opening an attachment in a desktop application |

## Install

From a checkout:

```sh
./install.sh            # installs Go and wacli if missing, then wa
./install.sh --check    # report what is missing, change nothing
./install.sh --headless # a server: no clipboard or desktop helpers
make install            # just build and install, nothing else
```

With no checkout, on a machine that already has Go:

```sh
go install github.com/UchaBokeria/dotfiles/whatsapp/cmd/wa@latest
```

Or let the script do all of it, including wacli:

```sh
curl -fsSL https://raw.githubusercontent.com/UchaBokeria/dotfiles/nuc/whatsapp/install.sh | bash
```

`install.sh` covers the parts that otherwise go wrong: pacman, apt, dnf,
zypper, apk and brew are all handled; a Go older than 1.22 is upgraded, falling
back to the upstream tarball when the distribution's is still too old; wacli is
fetched from its published binaries — checksum verified — rather than built,
because its own module asks for a newer Go than any distribution ships; and
`~/.local/bin` is added to bash, zsh **and** fish, not only the shell you ran
it from. That last one is the whole reason it exists — otherwise the binary
installs fine and the shell reports `command not found`.

On a machine with no display it installs neither a clipboard helper nor
`xdg-utils`, which would drag in X11 for nothing: copying uses OSC 52, which
your terminal carries over ssh. Pass `--desktop` to ask for them anyway.

It never writes `~/.config/wa/config.toml`. The binary carries every default,
and a full copy on disk would shadow them permanently, so a later version could
never improve one. You get `config.toml.example` to copy lines out of.

To keep messages arriving while `wa` is closed, install the optional unit:

```sh
install -Dm644 systemd/wa-sync.service ~/.config/systemd/user/wa-sync.service
systemctl --user enable --now wa-sync.service
```

## Keys

`<Space>?` inside `wa` lists every binding. The shape of it:

| | |
|---|---|
| `Tab` | move between the conversation and the input box |
| `S-Tab` | cycle all three sections: list, conversation, input |
| `j` `k` `gg` `G` `<C-d>` `<C-u>` | move |
| `i` | type: the search box on the left, the message composer on the right |
| `<Esc>` | leave insert; again to leave the draft |
| `<CR>` | open a chat, or send a message |
| `/` `?` `n` `N` | search inside the open conversation |
| `:grep <text>` | search every conversation into the quickfix list |
| `<Space>i` `<Space>in` `<Space>iN` | toggle and walk the quickfix list |
| `<Space><Space>` | jump to a chat by name |
| `u` | undo the last archive, pin, mute or read |
| `Space` `.` | context menu for whatever has focus |
| `r` `Y` | reply to, or copy, the selected message |
| `Space` `e` `w` `d` `o` | react, forward, download, open in the desktop |
| `Space` `u` `U` | attach a file, take the last one back off |
| `<C-v>` | paste: a picture attaches, text types |
| `ZZ` or `:q` | quit |

## Media

Images, video and text documents are drawn in the conversation, under the
message they belong to.

Where the terminal speaks kitty's graphics protocol - kitty itself, ghostty and
wezterm - a photograph is drawn as pixels. Everywhere else it is drawn with
half-block characters and 24-bit colour, which is a fair likeness of a
screenshot and a poor one of a face. Inside tmux the pixel path also needs

```tmux
set -g allow-passthrough on
```

without which the escape never reaches the terminal and nothing appears at all.
`wa doctor` says which of the two is in use. `media.graphics = false` forces
half blocks.

Video shows its first frame and its duration; audio and voice notes show a
waveform drawn from the samples; a text document shows its opening lines.

Stickers work too, animated ones included.

Anything up to `media.auto_download` - 2MB by default - is fetched the moment
it is drawn, one at a time in the background, so a conversation of photographs
shows photographs rather than a column of filenames. Bigger files wait to be
asked for. `:set media.auto_download=0` turns it off, `=10MB` raises it.

`<Space>d` downloads the attachment on the selected message, `<Space>D` every
attachment in the chat, `<Space>o` opens it in the desktop, `<Space>M` reports
what the cache is holding and `<Space>P` turns previews off for the session.

Downloads go through `wacli media download --read-only --output`, which takes
no store lock. That is the only form that works while a sync process is
running, and it is why `wa` keeps its own cache under
`~/.cache/wa/media`: a read-only download is not recorded in the store, so
nothing else remembers where the file went.

Preview size, the row cap and the document line count are in `[media]`.
`ffmpeg` and `ffprobe` are optional - without them a video shows a chip rather
than a frame, a voice note shows a duration rather than a waveform, and an
animated sticker shows nothing. Still images, including both still webp
encodings, are decoded in pure Go and need neither.

## Sending files

```
:attach ~/photo.jpg     add a file to the next message
:detach                 take the last one back off
<Space>u                the same, at the prompt
<C-v>                   paste: a picture attaches, text types
```

The draft becomes the caption. Several files go one after another and only the
first carries it — repeating a caption under every picture is not what anybody
means by captioning a batch. What is attached is named above the prompt, because
an attachment is otherwise invisible and a picture sent to the wrong chat cannot
be taken back.

Pasting reads the picture off the system clipboard through `wl-paste` or
`xclip`; a session with neither can only paste text, and says so.

## The mouse

Left click selects a chat or a message, and clicks a row in the reaction and
forward lists. Right click opens the same context menu the phone app shows — pin, mute, archive, mark read, delete on a chat; reply,
react, forward, copy, download, message info, delete on a message. Dragging
selects text and copies it when you let go, and the wheel scrolls whichever
pane the pointer is over.

Selection is drawn by wa rather than by the terminal, because a program that
tracks the mouse takes that job over. Copying goes through `wl-copy`, `xclip`
or `xsel` when one exists, and falls back to OSC 52 — with the caveat that tmux
swallows OSC 52 unless `set -g allow-passthrough on`, which is why a helper is
preferred.

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

## Links

URLs in a message are clickable, using OSC 8. A URL too long for the bubble is
still one link: every line it wraps onto carries the same target, so either
half opens the whole address. A terminal that does not understand OSC 8 shows
the text unchanged, and tmux forwards it from version 3.4 onwards. Turn it off
with `ui.links = false`.

The bar above the prompt shows where the selected message's link goes, broken
into host and path the way a browser shows a link under the pointer. A long URL
is unreadable and unverifiable inline — the text says one thing and the target
may say another — and the breadcrumb answers "where does this actually go"
without opening it.

The message context menu lists every link in the message separately, to open or
to copy. `ui.opener` picks the program; empty means `xdg-open`.

## Two addresses for one person

WhatsApp is moving accounts from a phone number (`995…@s.whatsapp.net`) to an
opaque identifier (`487…@lid`), and both reach the same person. wacli's store
records whichever the server used, so a conversation can end up split across
two rows: the reply filed under the number, the reaction under the LID, and
neither showing the other. It is how a reaction sent from `wa` could look like
it had done nothing.

`wa` folds them. The pairing is in the whatsmeow session database beside the
store, which is read read-only like everything else; `wa doctor` says how many
addresses it resolved. An address with no pair is left alone rather than
hidden — it is somebody `wa` knows nothing else about, and hiding it would hide
a real conversation.

## Replies

wacli sends the quote — the other person sees the reply attached to the right
message — but the row it writes to its own store carries no reference to it,
and the phone never fills one in. So `wa` keeps its own note of what its sends
replied to, in `~/.local/state/wa/sent-quotes.json`. It is advisory: deleting
it costs the quote bars on your own replies and nothing else.

Quotes on everything else come from the store, and the words are looked up
rather than shown as an ellipsis.

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
