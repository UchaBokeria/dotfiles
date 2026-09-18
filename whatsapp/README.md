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

`make install` puts `wa` in `~/.local/bin`. If the shell then says
`wa: command not found`, that directory is not on `PATH` yet — Ubuntu only adds
it at login, and only if it already existed — and `make install` prints the
exact line to add. Until then `~/.local/bin/wa` runs it directly.

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

## The top bar

One line across the top: the linked account on the left, over the chat list,
and the open conversation on the right, over the conversation — name, whether
it is a group and how many people are in it, unread count, and whether it is
pinned, muted or archived. How many people can read what you are about to type
is worth knowing before you type it. The clock sits at the far right, because a
full-screen terminal usually hides the desktop's.

## Keys

`<Space>?` inside `wa` lists every binding. The shape of it:

| | |
|---|---|
| `Tab` | move between the conversation and the input box |
| `S-Tab` | cycle all three sections: list, conversation, input |
| `j` `k` `gg` `G` `<C-d>` `<C-u>` | move |
| `i` | type: the search box on the left, the message composer on the right |
| `<Esc>` | leave insert; again to leave the draft |
| `<CR>` | a chat: open it. A message: follow its link, open its attachment, or copy its text |
| `/` `?` `n` `N` | search inside the open conversation |
| `:grep <text>` | search every conversation into the quickfix list |
| `<Space>i` `<Space>in` `<Space>iN` | toggle and walk the quickfix list |
| `<Space><Space>` | jump to a chat by name |
| `u` | undo the last archive, pin, mute or read |
| `Space` `.` | context menu for whatever has focus |
| `r` `Y` | reply to, or copy, the selected message |
| `Space` `e` `w` `d` `o` | react, forward, download, open in the desktop |
| `Space` `u` `U` | browse for a file to attach, take the last one back off |
| `<C-^>` | back to the last chat, as `<C-^>` is the alternate file in vim |
| `<C-v>` | mark this chat or message; every action then works on all the marks |
| `Space` `f` … | the finder: messages, attachments, pictures, video, audio, documents, links, starred |
| `Space` `F` … | the same, inside the open chat |
| `Space` `C` | the profile: how much of this conversation there is, and of what |
| `Space` `g` … | the chat drawer: favourite, export, clear, read, archive, mute, pin, delete |
| `Space` `n` … | contacts: the address book, rename, tag, add, forget |
| `Space` `A` | attach a file by typing its path |
| `<C-v>` while typing | paste: a picture attaches, text types |
| — | press the leader and pause: what may follow appears, with what each does |
| `<BS>` `<Esc>` | mid-sequence: step back out of a group, or abandon it |
| `ZZ` or `:q` | quit |

In the input box, `<C-v>` is a column selection, `<C-n>` puts a cursor on every
occurrence of the word under the cursor, and `<C-Down>` / `<C-Up>` add one on
the line below or above — the bindings `mg979/vim-visual-multi` uses. `I` and
`A` then type down the left or right edge of the block, `d` cuts it, `c`
changes it, `y` copies it; with cursors, `i` `a` `c` `d` do the same at every
one of them, and `<Esc>` leaves.

The input box has its own keys, and only the input box answers them. With the
draft focused, `w` `b` `e` `0` `^` `$` move the cursor through what you are
writing, and `d` `c` `y` take those motions the way they do in vim; with the
conversation focused the same keys do nothing to the draft, so `Tab` is the
whole of the difference. While typing, `<C-a>` and `<C-e>` go to the ends of
the line, `<M-b>` and `<M-f>` a word at a time, `<C-w>` and `<M-BS>` rub out
the word behind the cursor, `<C-u>` and `<C-k>` the line either side of it.

### Attachments over 100MB

wacli will not download one. `MaxMediaDownloadSize` in its `internal/wa/media.go`
is a compiled-in constant - no flag, no environment variable - so a 180MB zip
sitting in your own chat cannot be fetched by any wacli installed from the
published binaries. wa says so before starting the transfer rather than after.

The only way past it is a wacli built with a bigger number, which is one
script:

```
./scripts/wacli-big-media 2GB        # newest release, 2GB cap
./scripts/wacli-big-media 500MB v0.18.2
```

It clones the release, rewrites that one constant, builds, and installs over
`~/.local/bin/wacli`. wacli links go-sqlite3, so unlike wa it needs cgo and a C
compiler (`apt install build-essential`, `pacman -S base-devel`). Then tell wa
the new limit so it stops refusing early, and restart `wacli sync --follow`:

```toml
[media]
max_download = "2GB"
```

wa looks for wacli on `PATH` first, then in `~/.local/bin`, `$GOBIN`,
`$GOPATH/bin`, `~/go/bin` and `/usr/local/bin`, so a wacli from `go install`
works even where `~/go/bin` is not on `PATH`. `wa doctor` prints the one it
found, or every place it looked when it found none; `[wacli] bin` takes an
explicit path when it lives somewhere else.

## Finding things

`/` searches the open conversation and marks every match; the one you are on is
a different colour from the rest. `:grep` fills the quickfix list, for results
that are a work list to walk through.

The finder is the third way, and the one for "it was in some chat, months ago":

```
<Space>ff    every chat, by text          :find
<Space>fa    attachments                  :find media
<Space>fi    pictures                     :find images
<Space>fv    video                        :find video
<Space>fo    audio and voice notes        :find audio
<Space>fd    documents                    :find docs
<Space>fl    links                        :find links
<Space>fs    starred                      :find starred
<Space>F…    the same, in this chat only  :find! …
```

It queries the store on every keystroke rather than filtering a list in memory,
so it searches the whole history rather than the part that happens to be
loaded. Enter opens the chat and lands on the message.

`<Space>C` (`:stats`) is the profile page: how many messages each way, how many
links, how many pictures, videos, voice notes and documents — and of the
documents, how many are archives — how much they weigh, and how far back the
conversation goes.

## Doing several at once

`<C-v>` marks the chat or the message under the cursor and moves on, so a run
of them is one key each; ctrl-click does the same with the mouse. Everything
that can sensibly work on many then does: for chats, mark read, archive, mute,
pin, favourite, export, clear, delete; for messages, copy (as a transcript,
with a blank line between each), forward, download, delete. With nothing marked they act on what is under
the cursor, so there is nothing new to learn. `<Esc>` drops the marks.

Contacts mark the same way, inside the address book. Enter on a single contact
opens the conversation; enter on a marked set hands them to the chat list as a
selection, because opening five conversations at once is not a thing anybody
wants and every bulk action already lives there. A contact with no conversation
yet is left out, and the status line says how many.

## The chat drawer

What the phone app puts behind a long press:

```
<Space>gf  favourite        <Space>ga / gA  archive / unarchive
<Space>ge  export to JSON   <Space>gm / gM  mute / unmute
<Space>gc  clear locally    <Space>gp / gP  pin / unpin
<Space>gr  mark read        <Space>gu       mark unread
<Space>gx  delete locally   <Space>gb       block · <Space>gd disappearing
```

Two of those wa cannot do, and says so rather than pretending: wacli has no
block command and no disappearing-messages timer, so both belong to the phone.
Favourites are wacli's own local contact tag, because WhatsApp's favourites
never reach a linked device; the chat list has a `favourites` filter and marks
them with a star.

Contacts live under `<Space>n`: `nn` opens the address book (every contact,
including the ones you have never written to), `nr` renames one locally, `nt`
tags one, `na` checks a number is on WhatsApp and opens the chat, `nf` forgets
the local name and tags. The address book is wacli's; a linked device cannot
write the phone's.

## Locking

`:lock set` chooses a password from inside wa — there is no need to leave for a
shell — and `<Space>l` locks the screen after that. `:lock clear` removes it,
`:lock status` says where things stand, and `wa lock set|clear|status` does the
same from a shell. The screen shows nothing of the conversation, and the wave
under the mark keeps moving so a locked session cannot be mistaken for a hung
one.

```toml
[lock]
enabled = true
idle_timeout = "15m"
```

## Ticks

One tick means WhatsApp took it, two mean the other device has it, and two in
the accent colour mean it was read — the phone app's own vocabulary.

wacli's store records only "sent": receipts arrive as live events over the sync
webhook and are not written anywhere. wa keeps its own small record of them in
`~/.local/state/wa/receipts.json`, so the second tick survives a restart. A
session with no `wacli sync --follow` behind it sees one tick and nothing more,
because nothing is delivering the receipts.

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

WhatsApp keeps a file on its servers for a few weeks and then drops it. After
that only the phones that already downloaded it still have the bytes, and the
chip says `· expired`. `:retry` asks your phone to upload it again — it works
only while that phone is online and still holds the file.

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

## Finding the keys

A half-typed sequence is invisible: the prompt shows what you pressed and
nothing says what may follow. Press the leader, wait `ui.whichkey_delay`, and
the continuations appear with what each one does — groups first, marked
`+name`, then single keys. `<BS>` steps back out of a group, `<Esc>` abandons
the sequence, and it closes on its own once the sequence resolves.

Group names come from `[ui.groups]`, keyed by prefix. A prefix with no name
there is labelled from the actions underneath it, which share a namespace often
enough that most of them name themselves. `ui.whichkey = false` turns it off;
`<Space>?` still lists every binding at once.

## Sending files

```
<Space>u                browse for a file, starting where you left off
:attach ~/photo.jpg     add a file to the next message
<Space>A                the same, at the prompt
:detach                 take the last one back off
<Space>U                the same, at the prompt
<C-v>                   paste: a picture attaches, text types
```

The paperclip in front of the prompt opens the same browser with a click. A
directory opens, a file attaches, `..` goes up, and typing filters the listing
the way every other picker in `wa` does.

An `.ogg`, `.opus` or `.oga` file is sent as a voice note rather than as an
audio file: WhatsApp draws the first as a waveform you press play on and the
second as a document, and a recording sent as a document is the wrong one every
time.

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

## The look

wa draws in the rice's shape language: the Nerd Font half circles (U+E0B6 and
U+E0B4) that round tmux's status segments and waybar's capsules round every
chip, badge, field and message here too. Nothing is square unless you ask for
it, and nothing is outlined: the section with the keyboard shows it by coming
forward - its chip and its selection take the accent - rather than by a border.

Every part of it is configuration:

```toml
[ui]
shape = "pill"          # "pill", "rounded" (any font) or "square"
icon_set = "nerd"       # "nerd", "unicode" or "ascii"
bubble_edges = "half"   # how a message of several lines is rounded
gutter = "none"         # "hybrid" brings back the line numbers

[ui.layout]
margin = 1              # empty cells at the screen edges
gap = 2                 # between the chat list and the conversation
list_rows = 2           # 2 shows the last message under each chat's name
bubble_gap = 1          # blank rows between messages
padding = 1             # inside bubbles, fields and popups

[icons]                 # replace any single icon by name
pin = ""

[theme.colors]          # replace any single palette role
accent = "#AA9B75"
```

A one-line message is a capsule; a longer one is a rounded card, its first and
last rows capped and the rows between given half-block sides that meet the caps.
`bubble_edges = "ends"` and `"all"` are the two alternatives that were compared
by eye and lost: the first steps at every corner, the second scallops.

The time and the delivery ticks sit inside the bubble. A selected message lifts
toward the accent and its rounded ends take the accent itself.

**Colours** come from the rice's own design tokens. `blackwall-theme` writes
`whatsapp/theme.toml`, which the installer links to `~/.config/wa/theme.toml`,
so wa wears the same accent as tmux, waybar and rofi. Without it wa falls back
to wallust's or pywal's colours, then to its built-in palette; `wa doctor`
says which. `:reload` applies a change to the shape, the icons, the layout or
`[theme.colors]` without restarting.

**Fonts.** The shapes and icons need a Nerd Font in the terminal. `install.sh`
installs JetBrainsMono Nerd Font when none is present (`ttf-jetbrains-mono-nerd`
on Arch, the release archive elsewhere). On a headless server the font belongs
on the machine you connect from; set `shape = "rounded"` and
`icon_set = "unicode"` for a terminal without one.

## Colours and glass

With no `theme.file` of your own, wa takes the colours wallust or pywal pulled
out of the wallpaper — `~/.cache/blackwall/palette.json` first, then
`~/.cache/wallust/colors.json`, then `~/.cache/wal/colors.json`. Only a
background, a foreground and sixteen ANSI colours are read; the raised
surfaces, edges and bubbles are mixed from those towards the background, so a
surface reads as raised whatever the wallpaper happened to be.
`theme.follow_wallpaper = false` keeps the built-in palette.

A terminal cannot blur what is behind it — that belongs to the compositor —
but it can stop painting over it. Under Hyprland, `ui.glass = "auto"` leaves
the bars and the key popup unpainted so the blur shows through, and says in
`wa doctor` whether plain Hyprland blur or hyprglass is doing the work. Bubbles
and badges keep their fill: those are content, and a transparent bubble is just
text. Your terminal needs its own transparency for any of it to show —
`background_opacity` in kitty.

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

```
:lock set          # choose a password, from inside wa
:lock              # lock now, or <Space>l
:lock clear        # remove the password
:lock status       # is there one?
```

The same four exist as `wa lock set|clear|status` in a shell, for the machine
where `wa` has not been started yet. Turn the idle lock on with
`[lock] enabled = true`.

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
