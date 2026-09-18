# blackwall — how to use it

Living reference. Anything added to the rice gets an entry here, so this file
is the answer to "what was that keybind again".

Prefix is **C-a** (tmux). `SUPER` is the Windows/Meta key.

---

## Screen capture

Every capture goes to **the clipboard and to disk**, so you can paste it
immediately and still find it a week later. Saved to `~/Pictures/Screenshots/`
as `YYYY-MM-DD_HH-MM-SS.png`.

| Keys | Does |
|---|---|
| `SUPER+N` | select a region |
| `SUPER+Print` | **flameshot**, plain — its own selector and toolbar, nothing of ours in front |
| `SUPER+SHIFT+Print` | select a region, then open it in flameshot to annotate |
| `SUPER+O` | select a region, put **its text** on the clipboard (OCR) |
| `SUPER+SHIFT+O` | select a region, OCR it, then **translate** it |
| `SUPER+SHIFT+N` | select a region and **ask ArchPilot** about it |
| `SUPER+CTRL+V` | **browse past captures** — pick one, then pick an action |

An OCR capture puts the *text* on the clipboard and nothing else. It used to
put the image there too, and because `wl-copy` takes ownership a moment after
it returns, the image could land after the text and replace it — which is why
`SUPER+O` seemed to extract nothing while `SUPER+SHIFT+O` worked (its
translation round trip let the image settle first). The text is also read
several ways now — as captured, enlarged and normalised, and inverted — and
the best result wins, because pale text on a translucent panel is the case
tesseract is worst at.

The history browser offers every action above on an old capture: copy, edit,
extract text, translate, ask ArchPilot, open the folder, delete.

**flameshot needs three things to be true on Hyprland**, and none of them was:

* `~/.config/flameshot/flameshot.ini` has to exist with `useGrimAdapter=true`,
  or flameshot asks the xdg Screenshot portal instead of shelling out to grim.
  The repo carried the file but nothing installed it, and the copy it carried
  saved to `/home/bu/Pictures` — the other machine. Step `flameshot-config`
  renders it per machine now.
* a portal preference file has to name **hyprland** for Screenshot, or
  xdg-desktop-portal answers with whichever backend is already running, which
  is the GTK one, which cannot grab a Hyprland screen. That is what "Screenshot
  aborted" meant. It lives in `~/.config/xdg-desktop-portal/hyprland-portals.conf`.
* the overlay has to be the whole screen. The blanket "every window floats at
  1200x800" rule in `hypr/lua/rules.lua` was catching flameshot too, so the
  region you drew was a region of a floating box.

Screen **recording** is `SUPER+CTRL+ALT+F9` (region) and `SUPER+CTRL+SHIFT+F9`
(everything), or the record button in the control centre. Both pass
`--audio="$(find_internal_audio)"`, which prints one PulseAudio source name —
the `internal_monitor` loopback if pipewire's drop-in made it, otherwise the
default sink's own monitor.

### From a terminal

```
blackwall-shot region --ocr          # any mode + any modifiers
blackwall-shot --file shot.png --ask # act on an image already on disk
blackwall-shots                      # the history browser
```

Modes: `region` `output` `window`.
Modifiers: `--edit --ocr --translate --ask --no-copy --no-save`.

**Languages.** OCR uses `eng` by default. For another language install its data
and set the variable:

```fish
sudo pacman -S tesseract-data-kat        # Georgian, or -rus, -deu, ...
set -x OCR_LANGS eng+kat                 # both at once is fine
set -x TRANS_TARGET ka                   # what --translate translates *into*
```

Translation tries Google, then Bing, then Apertium — Google rate-limits
translate-shell hard, so the fallback is doing real work, not being defensive.

---

### Sending a capture to the cloud session

`c2c` ships files to the session on the server and hands back a remote path.

| Command | Does |
|---|---|
| `c2c` | whatever is on the clipboard (image, or a copied file) |
| `c2c FILE [FILE...]` | specific files, any type |
| `c2c --shot` | select a region and upload it |
| `c2c --clip-path …` | put the remote path on the clipboard instead |

The path lands on the **primary selection** — middle-click (or shift+insert)
pastes it into the remote session. The clipboard keeps the image itself, so
the same capture can still be pasted into a *local* chat, and `--shot` saves a
copy into the screenshot history as well. Putting the path on the clipboard is
what used to destroy the image.

---

## Clipboard

| Keys | Does |
|---|---|
| `SUPER+ALT+V` | clipboard history — pick an entry to copy it back |

Backed by `cliphist`, recording text **and** images. The two watchers are
started by `blackwall-autostart`; without them history stays empty, which is
how it sat until 2026-08-25.

```
blackwall-clip            # the picker
blackwall-clip --delete   # remove one entry
blackwall-clip --wipe     # clear everything
```

---

## Launchers

| Keys | Does |
|---|---|
| `SUPER+R` | app grid, full screen |
| `SUPER+F` | file browser, centred list |
| `SUPER+U` | wallpaper picker — 3×3 previews, applies and re-themes the rice |

All of them share one generated theme (`rofi/shared/blackwall.rasi`); the
layouts in `rofi/blackwall/` hold nothing but geometry. Since 2026-09-12 that
shell is glass: the frosted fill, a 1px rim that follows the corner, the
spacing scale, and 13px Inter like every other panel. hyprglass frosts it (see
**Liquid glass**). The three tile launchers (app grid, wallpapers, screenshots)
show the selected tile the same way: an accent tint with an accent rim.

---

## The bar

```
waybar/variant              # which variant is active
waybar/variant capsule      # one glass pill per module group  (current)
waybar/variant pill         # workspaces + media + ONE right-hand pill
waybar/variant dock         # a single full-width sheet
```

Switching is a symlink swap plus a restart — no diff to revert.

### The workspace pills

They are ten custom modules (`custom/ws1` … `custom/ws10`), not waybar's own
`hyprland/workspaces`. That module renders perfectly but sends a click into
Hyprland's socket as `dispatch workspace 3`, and the Lua config parses a
dispatch as Lua — so every click was a silent syntax error and the bar did
nothing at all. `scripts/blackwall-bar-workspaces` renders each pill and
dispatches the click in Lua instead; its `listen` daemon refreshes the bar
(signal 9) whenever a workspace changes. The look is unchanged: the same rules
apply to `.ws` that applied to `button`.

---

## tmux

Prefix **C-a**. `C-b` on its own toggles the status bar.

| Keys | Does |
|---|---|
| `prefix` `/` | search the scrollback |
| `prefix` `C-u` | jump to the last URL on screen |
| `Escape` or `q` | leave copy mode |

**tmux-copycat is removed.** It rebound every cancel and copy key in
copy-mode-vi through an async `run-shell`, so `Escape` stopped cancelling a
mouse selection. It is unmaintained and tmux has had its search built in since
3.1 — the two binds above are the useful half of it, on native search.

```
tmux/variant                # which status variant is active
tmux/variant segment        # joined segments, rounded joins  (current)
tmux/variant dots           # page-indicator dots, only the current window named
tmux/variant pill           # rounded capsules
tmux/variant minimal        # no fills at all
```

### Sessions survive a reboot

tmux-continuum saves the layout every **5 minutes** and restores it when the
server starts. A save identical to the previous one is thrown away, so an idle
machine costs nothing. Saves live in `~/.local/share/tmux/resurrect/`, and
`last` points at the one that gets restored.

| Keys | Does |
|---|---|
| `prefix` `C-s` | save now |
| `prefix` `C-r` | restore from `last` |

`tmux/resurrect-guard` keeps `last` honest. A save taken while the server is
going down comes out **empty**. resurrect linked that empty file as `last`, and
the next boot restored nothing. That is how every session vanished on
2026-09-12. The guard runs after every save, before every restore and at config
load. It moves empty saves to `~/.local/share/tmux/resurrect-empty/` (they are
never deleted) and relinks `last` to the newest save that has panes in it.

If sessions are ever missing, check `readlink ~/.local/share/tmux/resurrect/last`
and the timestamps beside it, then `prefix` `C-r`.

---

## WhatsApp

`wa` is a terminal WhatsApp client in `whatsapp/`, driven by vim keys. It is a
compiled Go binary rather than a script, so it goes on PATH through its own
Makefile rather than through `scripts/link-bin`:

```
cd whatsapp && ./install.sh       # installs Go and wacli if missing, then wa
cd whatsapp && ./install.sh --check   # report what is missing, change nothing
cd whatsapp && ./install.sh --headless  # a server: skip clipboard and xdg-utils
cd whatsapp && make install       # just build and install, nothing else
```

On another machine, with no checkout:

```
go install github.com/UchaBokeria/dotfiles/whatsapp/cmd/wa@latest
curl -fsSL https://raw.githubusercontent.com/UchaBokeria/dotfiles/nuc/whatsapp/install.sh | bash
```

`install.sh` handles the parts that otherwise bite: a distribution whose
package manager is not apt, a Go too old to build the module, wacli missing
(fetched from its published binaries, checksum verified), a headless server
where a clipboard helper would only pull in X11, and adding `~/.local/bin` to
bash, zsh *and* fish rather than only the shell you happened to run it from.

It runs on a headless Ubuntu box as it does on Arch: pure Go, `CGO_ENABLED=0`,
no desktop. `ffmpeg` is the one optional program worth having — without it a
video shows no frame and a voice note no waveform.

It needs [wacli](https://wacli.sh) 0.18+, already authenticated. `wa doctor`
says what it can see; `wa` on its own opens the client.

| Keys | Does |
|---|---|
| `Tab` | move between the conversation and the input box |
| `S-Tab` | cycle all three sections: list, conversation, input |
| `i` | type — the search box on the left, the message composer on the right |
| `Escape` | leave insert; again to leave the draft |
| `Enter` | open a chat, or send the message |
| `j` `k` `gg` `G` `C-d` `C-u` | move |
| `/` `n` `N` | search inside the open conversation |
| `Space` `Space` | jump to a chat by name |
| `Space` `i` | toggle the results list; `Space` `i` `n` walks it |
| `Space` `.` | context menu for whatever has focus |
| `r` | reply to the selected message |
| `Y` | copy the selected message |
| `Space` `e` `w` | react, forward |
| `Space` `d` `D` | download this attachment, or every one in the chat |
| `Space` `u` | browse for a file to attach — the paperclip by the prompt does it too |
| `Space` `A` | attach by typing the path — `:attach <path>` |
| `w` `b` `e` `0` `$` | with the input focused: move through the draft, not the chat |
| `C-a` `C-e` `M-b` `M-f` `C-k` | while typing: the readline keys |
| `C-v` | paste: a picture attaches, text types |
| `Space` `o` | open or play it — mpv for video and audio, the desktop otherwise |
| `Space` `M` `P` | what media this chat holds; inline previews on or off |
| — | attachments up to `media.auto_download` (2MB) fetch themselves |
| — | photographs draw as pixels in kitty, ghostty and wezterm |
| — | press the leader and pause: what may follow appears; `<BS>` back, `<Esc>` out |
| `Space` `?` | every binding, scrollable — `q` or `Escape` closes it |
| `Space` then `Backspace` | the whole top level: what j, k, Tab and the ctrl keys do |
| `C-^` | back to the last chat |
| `C-v` | mark chats, contacts or messages; the next action works on all of them |
| `C-v` `C-n` `C-Down` in the input | column select, a cursor per occurrence, a cursor per line |
| `Space` `f` … | find messages, attachments, pictures, video, docs, links, starred |
| `Space` `C` | the profile: counts, links, media by kind, how far back it goes |
| `Space` `g` … | the chat drawer: favourite, export, clear, archive, mute, delete |
| `Space` `n` … | contacts: address book, rename, tag, add, forget |
| `:lock set` | choose a password from inside wa; `Space` `l` locks the screen |
| `u` | undo the last archive, pin, mute or read |
| `ZZ` | quit |

The look follows the rest of the rice: the same Nerd Font half-circle pills tmux
and waybar use, icons instead of words, spacing from one scale, colours from
the generated `whatsapp/theme.toml` (linked to `~/.config/wa/theme.toml`).
Everything is configuration and applies on `:reload`:

```toml
[ui]
shape = "pill"          # pill, rounded, square
icon_set = "nerd"       # nerd, unicode, ascii
bubble_edges = "half"   # half, ends, all
[ui.layout]
margin = 1
gap = 2
list_rows = 2
[icons]
pin = ""                # any single icon, by name
[theme.colors]
accent = "#AA9B75"      # any single palette role
```

`./install.sh` installs JetBrainsMono Nerd Font when no Nerd Font is present.

The mouse works throughout: left click selects, right click opens the same
context menu WhatsApp shows, dragging selects text and copies it on release
(through `wl-copy`, falling back to OSC 52), and the wheel scrolls whichever
pane the pointer is over.

Pixel-accurate pictures need `set -g allow-passthrough on` in tmux — it is in
`tmux.conf.local` — because kitty's graphics protocol travels in an escape tmux
does not otherwise forward. Without it wa falls back to half blocks.

`wa doctor` reports what it can see, the media cache, and how many of
WhatsApp's newer `@lid` addresses it folded onto phone numbers — without that
folding one person shows up as two chats, each with half the conversation.

URLs are clickable, through OSC 8. A link too long for the bubble wraps but
stays one link, so either half opens the whole address; tmux forwards the
sequence from 3.4 onwards, and a terminal that ignores it just shows the text.
The message context menu lists each link in the message to open or copy.
`ui.links = false` turns it off.

```
:media                      # what attachments this chat holds
:download all               # fetch every attachment in this chat
:retry                      # expired media: ask the phone to upload it again
:w  :wq  :x                 # send the draft; send and quit
:arch                       # any unambiguous abbreviation works
:attach ~/photo.jpg         # send a file; the draft becomes its caption
:detach                     # take the last attachment back off
:preview                    # inline previews on or off
:grep deploy the nuc        # search every conversation into the results list
:filter unread              # narrow the chat list
:chat Team                  # open a chat by name
:set ui.list_width=40       # change a setting for this session
:set! ui.list_width=40      # and keep it
:map n <C-p> picker.chats   # rebind a key now
:actions                    # everything that can be bound
:revoke                     # unsend the selected message
```

The draft is a real vim buffer, one per chat with its own undo history, so
`ciw`, `daw`, `u` and macros work while composing. **`u` never unsends** — only
`:revoke` does, and only your own messages.

Images, video frames and text documents are drawn inside the conversation with
half-block characters, which works in tmux and over ssh — kitty's graphics
protocol would need `set -g allow-passthrough on`. Nothing is downloaded
automatically: `Space` `d` fetches one, `:download all` fetches the chat.

Pinning, muting, archiving, deleting and downloading all need wacli's store
lock, which the background sync holds. `wa` stops it, does the work and starts
it again, so those take a few seconds and say so in the status line. Sending
and reacting are delegated to the running sync and are immediate.

Settings live in `~/.config/wa/config.toml`, which is watched: saving it
re-applies without a restart. `:set!` writes to `overrides.toml` beside it
rather than editing the file you wrote by hand. `blackwall-theme wa` regenerates
the palette, so a wallpaper change re-themes the client with everything else.

`wa lock set` puts a password in front of the interface. It hides the interface
only — it does not encrypt wacli's message store, which stays readable on disk.

---

## ArchPilot

`SUPER+~` toggles the assistant window; `archpilot/README.md` documents all of
it. What is new is which engine answers.

### Claude or Codex

The first chip in the header names the engine — **claude** in the accent
colour, **codex** in link blue. Click it, press `ctrl+alt+tab`, or type
`:engine codex` / `:engine claude`.

The chat stays where it is. The engine you switch to is handed a short replay
of the turns it missed, and the model resets to that engine's default, so
`ctrl+tab` on Codex cycles Codex's own model list. New chats and new tabs open
on the engine you picked last.

Codex's modes are its sandbox: **ask** is read-only, **action** may write
inside the session's folder and has no approval prompt (the Claude side keeps
its PreToolUse gate). Pick a Codex chat up in a terminal with
`codex resume <thread>`.

If Codex is signed out the widget says so and offers the fix, `codex login`.

---

## Theming

One generator feeds every surface. Change the wallpaper and the whole rice
follows — bar, launcher, notifications, terminal, GTK, Qt, Spotify, nvim, tmux.

```
setwall ~/path/to/image.jpg   # wallpaper + re-theme everything
blackwall-theme               # re-derive tokens without changing wallpaper
blackwall-theme --list        # every target and where it is written
blackwall-theme --check       # audit hand-written files against the radius scale
theme/run-tests               # the token system, the scripts, the tmux guard
```

**Never hardcode a colour, radius or gap in a surface's config.** Edit
`theme/blackwall_theme/tokens.py` and re-run the generator.

The scales, so the same role looks the same on every surface:

| | |
|---|---|
| radius | 22 app windows (= Hyprland `rounding`) · 18 panels · 12 rows, buttons, cards, tiles · 8 small marks · pill |
| spacing | 4 between rows · 6 between chips · 8 inside controls · 12 between sections and inside cards · 18 panel padding · 20 screen edge to panel (= `gaps_out`) |
| type | 10 · 11 · 13 body · 15 · 24, in Inter (GTK apps too: `Inter 10`) |
| states | keyboard selection = accent fill · checked or current item = accent tint + accent ring · hover = a faint tint |

Thunar has its own target. `blackwall-theme thunar` writes
`.themes/wallust/gtk-3.0/thunar.css`, and `~/.config/gtk-3.0/gtk.css` imports
it, because user CSS outranks the Sweet theme underneath. Every rule is scoped
to Thunar's main window except menus, which are styled in every GTK3 app.

---

## Liquid glass

Panels and translucent windows are real glass, not just blur. The **hyprglass**
compositor plugin treats a surface as a thick slab of glass. In the middle,
light passes almost straight through: frost and a slight dome. At the rim, the
light bends, pulls in what lies just beyond, and splits a little into colour.
A highlight catches the top edge and a shadow sits on the bottom one.

It is tuned for restraint, the way Apple's material is: desaturated, low in
contrast, with gentle refraction. The tint comes from the wallpaper like every
other colour (`glass_tint` in `tokens.py`).

```
blackwall-glass status     # Hyprland version, what is built, whether it is loaded
blackwall-glass install    # build the release made for this Hyprland, install, load
blackwall-glass off        # plain blur for this session (back at the next reload)
blackwall-glass on         # load it again, config and all
```

Run `blackwall-glass install` again after every Hyprland update. A plugin has
to be built against the exact compositor it runs in, and a mismatch is the
first thing that goes wrong with one.

| What | Where it is decided |
|---|---|
| which panels are glass | the `layers` list in `hypr/lua/glass.lua`: launcher, notifications, control centre, calendar, wifi. **Not waybar**, which stays on the compositor's blur |
| which windows are glass | kitty, Thunar and ArchPilot, tagged `hyprglass_enabled`. Opaque apps are skipped, because glass under an opaque window is GPU spent on pixels nobody sees |
| how it looks | preset `blackwall` for windows, and `blackwall_panel` for panels (more frost and less movement at the rim, so words never swim), both in `glass.lua` |
| never glass | mpv, vlc, imv, and anything fullscreen |

`mask_threshold` (0.45) is the knob to know about. Pixels fainter than it get
no glass. Shadows count as content, so without the threshold a panel with a
drop shadow gets a glass rectangle around the shadow's whole box.

Try a preset on the focused window without editing anything. The tag toggles,
so running the same line twice puts it back:

```
hyprctl dispatch 'hl.dsp.window.tag({ tag = "hyprglass_preset_subtle" })'
hyprctl dispatch 'hl.dsp.window.tag({ tag = "hyprglass_disabled" })'
```

Without the plugin installed, `glass.lua` does nothing and the blur in
`rules.lua` takes over, so a fresh machine still boots into a working rice.
Read the two Lua traps under **The Hyprland config, in Lua** before changing
how the plugin is loaded. Getting that wrong once took the whole session down.

---

## Installing on a new machine

```
git clone -b nuc <remote> ~/.config/.dotfiles/blackwall
cd ~/.config/.dotfiles/blackwall
./install              # probe, ask, show the whole plan, then do it
./install --dry-run    # the same screens, nothing changed
./install --restore    # undo the last run: originals back, added files removed
```

`./install` is only a doorway: it refuses root, offers to install `rust` if
cargo is missing, asks for sudo **once** in a normal terminal (a keep-alive
stops a long pacman run from asking again), builds `installer/` and hands over
to the TUI.

| Screen | What happens there |
|---|---|
| preflight | Arch, network, AUR helper, graphical session, sudo — and a red list if this clone is missing files the catalogue expects |
| what to install | the required core, fonts and theming are locked on; tick optional groups with space |
| a few questions | the four things the machine cannot answer (below) |
| first wallpaper | the whole palette is derived from this one image |
| the plan | everything that will happen, with what is already true greyed out. **space** takes an item out; files in the way are counted in the footer and will be moved to a backup |
| output | live log and progress |
| done | failures, where the backup went, and what waits for the first login |

Nothing is assumed. Every package is checked with pacman, every link against
the filesystem, every step against its own check command, and every
gsettings/xfconf value by reading the value back out of the tool, so running it
again on a half-installed machine proposes only what is left.

`--restore` is the whole undo, not half of it: originals that were moved aside
go back, and the links and copies the run *added* where nothing had been are
removed again — but only where they are still exactly what the installer left,
so a file you have since edited stays and is named in the output.

**What it asks.** Everything answerable by looking is detected, so this screen
is usually four lines and an enter. What is left is in
`installer/data/questions.toml`: the **modifier key** every binding hangs off,
the **VA-API driver** (detected from lspci), whether to **update the system
first**, and whether to make fish the **login shell**. Each answer is exported
to every step as an environment variable.

The first two end up in **`hypr/lua/machine.lua`**, which is gitignored and
written per machine. `hypr/lua/hyprland.lua` defines a `BLACKWALL` table of
this repo's defaults and then `pcall(require, "machine")`, so anything the file
sets wins — the modifier, the terminal, monitors, and an `extra_binds` function
called after `keybinds.lua` so its bindings override the standard ones. This is
the file that used to be hand-edited on each box and lost on every clone;
`hypr/lua/machine.lua.example` is the tracked template.

**It runs in two passes.** Some steps need a live Hyprland session — the
autostart, `setwall`, building the glass plugin, spicetify, the selftest — so
the first run defers them. Log in, open a terminal, run `./install` again.

What it installs is data, not code, in `installer/data/`:

| File | Holds |
|---|---|
| `packages.toml` | 22 groups, 94 required packages. Built from what the configs actually call — `pacman -Qqe` alone misses 30 packages the rice needs that are only installed here as dependencies |
| `links.toml` | every file linked or copied into place, plus gsettings/xfconf values. `home/` in the repo holds the configs that used to live only in `~/.config` |
| `steps.toml` | builds, generators and services, in order, each with a check |

Personal things — ssh config, the WhatsApp session, cloud sync targets,
`scripts/c2a` — are skipped. Anything moved aside goes to
`~/.local/state/blackwall/backups/<timestamp>/`.

**Undoing it.** `./install --restore` puts back everything moved aside and
removes what the run added, and `blackwall-undo` does the same in plain bash so
it still works on a machine where the Rust build is broken:

```fish
blackwall-undo                  # what backups exist
blackwall-undo --show latest    # what it would put back and remove
blackwall-undo --restore latest --dry-run
blackwall-undo --restore latest
```

A file the installer created is removed only if it is still exactly what the
installer left — a symlink still pointing at the repo, or a copy identical to
its source. Anything edited since is kept and named in the output. That is what
makes installing over somebody's existing rice safe: theirs is moved into
`~/.local/state/blackwall/backups/<timestamp>/` with its path intact, never
deleted, and one command puts it back.

**The trap that matters: a file that exists here but was never committed is
missing on every other machine.** The preflight screen lists any such file it
can see. Commit before you clone somewhere else.

---

## Safety net

```
scripts/blackwall-snapshot save "why"    # checkpoint the whole rice
scripts/blackwall-snapshot list
scripts/blackwall-snapshot diff          # what changed since the last save
scripts/blackwall-snapshot restore <id>  # roll back (takes its own snapshot first)
```

Covers the tracked config *and* the bits outside the repo (`~/.config/gtk-*`,
`qt6ct`, `Kvantum`).

---

## Notifications that watch things

Clicking a notification runs its action — from the popup and from the list
inside the control centre alike. Both were checked with a real pointer. It
works because every notification this rice sends names its action `default`,
which is the one swaync invokes on a click.

An action that takes a while says so. Clicking "clean up" answers immediately
with what it is about to reclaim, and the result replaces that card when it is
finished. A click that appears to do nothing gets clicked again, which is how
a cleanup ends up running twice.

**One card per notification.** swaync groups notifications by app by default
and draws a collapsed group as cards stacked behind each other; with two apps
repeating themselves the stacks ran into the row below and the list read as
overlapping rectangles. `notification-grouping` is `false` in
`swaync/config.json`, and the stylesheet gives a group no geometry of its own
in case it is ever turned back on. The keyboard focus ring is styled too — with
`keyboard-shortcuts` on and nothing saying otherwise, GTK drew its own yellow
dashed rectangle.

`blackwall-watch` runs read-only checks in the background and raises a
notification when something wants attention. Each one carries a labelled
action button, drawn by swaync.

| Check | Tier | Fires when | Click does |
|---|---|---|---|
| `disk` | 1 | root ≥85% full | runs the safe cleanup |
| `units` | 1 | any failed systemd unit | opens them in a terminal |
| `pacnew` | 1 | `.pacnew`/`.pacsave` waiting | lists them |
| `archpilot` | 1 | a command awaits approval | opens the widget |
| `updates` | 2 | ≥25 updates pending | shows the list — **never upgrades** |
| `downloads` | 2 | `~/Downloads` over 5 GB | opens the folder |
| `gitdirty` | 2 | repos dirty for a week | — |
| `memory` | 3 | RAM ≥92% | shows the top processes |
| `network` | 3 | no default route | — |

```
blackwall-watch --list          # every check, its tier, when it last fired
blackwall-watch --once          # run them all now
blackwall-watch --check disk    # one check, ignoring its cooldown
TIERS="1 2" blackwall-watch     # drop the noisy tier
```

Each check has a cooldown, so a disk that stays full notifies every six hours,
not every five minutes. It re-notifies early only if the *value* changed.

### Reclaiming disk

```
blackwall-clean          # show what each step would free, change nothing
blackwall-clean --run    # do the safe steps
blackwall-clean --run --deep   # also drop docker images nothing references
```

Only touches things that regenerate themselves: dangling docker images,
wallust's raw image dumps, thumbnails, the yay build cache. Steps needing root
(pacman cache, journal) are printed for you to run, never executed — a cleanup
triggered from a notification must not be able to ask for your password.

---

## Panels

Three of waybar's right-hand icons open a panel each, so no one panel has to
hold everything.

| Icon | Opens |
|---|---|
| wi-fi | network, bluetooth and VPN |
| speaker | audio devices and per-app volume |
| arch | control centre |

### Network

Every row is a control, not a readout.

### Audio

The two sliders you reach for constantly stay in the control centre. This panel
holds what you only occasionally need: which output, which input, and which app
is too loud. Per-app volume is the half of pavucontrol anyone actually opens it
for — one app being loud is not a reason to turn everything down.

## Control centre

Waybar's arch icon (far right) opens it. `~/.config/eww/scripts/toggle control_center`.

Network lives in its own panel now (see above); this leaves the control
centre as audio, system, quick actions and notification history.

**The network panel** — every row is a control, not a readout:

| Row | Left pill | Body |
|---|---|---|
| wi-fi | toggles the radio | expands nearby networks — click one to connect |
| ethernet | — | shows link state |
| tailscale | `tailscale up`/`down` | shows your tailnet IP and peer count |
| bluetooth | powers the adapter | expands known devices — click to connect/disconnect |

Connecting to a locked network asks for the password in a rofi prompt only if
the saved profile fails, so rejoining a known network is one click.

**Audio pane** — the speaker/mic glyph is a **mute button**, the level is a
slider, and the device name on the right expands a picker.

| Keys | Does |
|---|---|
| `SUPER+A` | choose an output device |
| `SUPER+SHIFT+A` | choose an input device |

```
blackwall-audio status      # level, mute and device for both directions
blackwall-audio sinks       # output devices, as JSON
blackwall-audio mute-sink
blackwall-audio set-sink NAME
```

Switching a device also **moves anything already playing** onto it. pactl's
`set-default-sink` alone only affects streams that start afterwards, so without
that step music keeps coming out of the old device after you "switched".

The icon follows *silence*, not the mute flag: a sink at 0% with mute unset
sounds exactly like a muted one, so both show the crossed-out speaker.

**Inputs on this machine:** there is no microphone. The only source is
`internal_monitor`, a loopback of the HDMI output, and the picker labels it
`loopback` so it is not mistaken for a mic.

**System pane** — CPU, RAM, disk and network as gauges. Disk turns amber past 85%.

**Notification history** — every notification, with a relative time and a dot
coloured by urgency (grey low, blue normal, red critical). `clear` empties it.

```
blackwall-notify history 40    # newest first, as JSON
blackwall-notify count
blackwall-notify clear
```

**swaync is the notification daemon** (mako is masked; undo with
`systemctl --user unmask mako.service`). It draws real action buttons, which
mako could not — mako rendered a notification's actions as click targets on
the notification itself, so one offering three actions had one usable one.

Each row in the history carries a badge showing which application sent it,
tinted by urgency — critical ones are red. The glyphs are chosen in
`blackwall-notify`, not in the widget: eww has no user-defined functions, so
the alternative was a ten-branch ternary inside the markup. Adding an
application means one line in `GLYPHS` there.

| Keys | Does |
|---|---|
| `SUPER+D` | open the notification centre — do-not-disturb and
  per-application silencing live in the control centre's notification
  settings, which is where the state is visible |

```
blackwall-quiet dnd on          # and `off`, `toggle`
blackwall-quiet dnd-state
blackwall-quiet mute slack 2h   # silence one app for a while
blackwall-quiet unmute slack
blackwall-quiet silenced        # what is muted, and until when
```

**`swaync-client -dn` turns do-not-disturb *on*; `-df` turns it off.** They read
like "disturb: no" and "disturb: off" and mean the opposite of that — `n` is
enable, `f` is disable. Getting this backwards inverts the whole feature while
looking correct, which it did once.

Text you type anywhere in these panels goes through **rofi**, not through the
panel itself. eww 0.5.0's `focusable` is one boolean meaning *exclusive*
keyboard interactivity on a layer surface — a panel that takes every key and
leaves no way to reach anything else, which froze the session when it was
tried — and there is no on-demand setting to ask for instead. So a text field
inside a panel renders, accepts clicks, and swallows everything you type. The
calendar's plan and note fields, the world-clock city field and the VPN
credential fields are all buttons that open a rofi prompt.

Silencing an app writes a `notification-visibility` rule into swaync's config.
Two settings that read alike:

| Setting | Effect |
|---|---|
| `muted` | not shown, but still recorded in history |
| `ignored` | dropped entirely, as if it never arrived |

blackwall uses `muted`, so a silenced app's notifications are still there to
read afterwards.

Backed by `blackwall-notifyd`, started from `hypr/configs/exec.conf`. It is a
**passive D-Bus monitor**: it logs every notification with a timestamp while
swaync receives and displays them over its own connection, unchanged. swaync
stays the notification daemon; notifyd only watches.

This exists because a daemon's own buffer holds a handful of entries, carries
no timestamps, and empties whenever it restarts — which a re-theme does. The
log keeps the last 500 in `~/.local/share/blackwall/notifications.jsonl`.

The panel itself scrolls, so adding a section later cannot push anything off
the bottom of the screen.

```
blackwall-net status        # everything as one JSON blob
blackwall-net pick-wifi     # rofi wifi picker, no panel needed
blackwall-net pick-bt       # rofi bluetooth picker
blackwall-net vpn-toggle
```

VPN and screen brightness have their own commands:

```
blackwall-vpn status            # every tunnel, as JSON
blackwall-vpn forti-toggle      # and wg-toggle, ts-toggle
blackwall-vpn forti-config      # what openfortivpn is configured with
blackwall-vpn forti-edit        # and wg-edit - open the config in $EDITOR
blackwall-vpn ts-login          # and ts-switch <profile>
blackwall-dim 60                # DDC/CI backlight, 0-100
```

Credentials are edited through the panel, which calls `blackwall-setkey` under
`blackwall-ask` for the password prompt. That helper runs as root, so it
whitelists which keys it will touch per file and refuses to create absent ones.
`PostUp`, `PreUp`, `PostDown` and `pppd-plugin` are permanently excluded — a
wireguard config executes those as root, so a writable `PostUp` is a writable
root shell.

Tailscale's operator grant belongs to the profile it was made on. Switching
profiles loses it and logs you out of the panel's view; `sudo tailscale switch
<profile>` puts it back.

Scanning only runs while its section is open — a wifi scan is not free and
there is no reason to run one when nobody is looking at the list.

---

## Calendar

The **date** half of the waybar clock opens it. Three views in one pane:

- **month** — today is ringed, the selected day filled. A day with unfinished
  plans carries an accent dot; one with a note carries an amber one.
- **picker** — click the month name. Twelve months and a decade of years, so
  jumping to next March is two clicks rather than seven presses of an arrow.
- **day** — click any date. Its plans, with a checkbox each, `+` to send one to
  a sticky board (`SUPER+M`), `×` to delete, and a free-text note for the day.

Reminders are things to tick off; the note is what you want to remember about
the day itself. Forcing both through one list makes neither work.

Unfinished plans for today raise a notification (tier 1, every 4h).

```
blackwall-cal due                      # today's unfinished plans
blackwall-cal add 2026-09-01 "text"
blackwall-cal note 2026-09-01 "text"
blackwall-cal push 2026-09-01 0 global # send plan 0 to a sticky board
```

## Clocks

The **time** half of the clock opens them — the two halves finally mean
different things.

Local time large, then your zones with their offset. A zone on a different
calendar day says so (`wed · tomorrow`) rather than making you compare two
faces. `+` adds one: type a **city** and it is matched against the tz database,
so "lisbon" finds `Europe/Lisbon` without anyone memorising the area prefix.

```
blackwall-cal zone-find lisbon
blackwall-cal zone-remove Asia/Bangkok
```
---

## Wallpapers

67 of them in `wallpapers/`, named for what is in them — `red-lantern-market`,
`teal-hair-hacker`, `water-town-boat`. The picker (`SUPER+U`) reads separators
as spaces, so it lists them as *"red lantern market"*.

Names that encode a **palette** rather than a picture were left alone:
`dracula`, `gruvbox-light`, `cobalt-2`, `blood-moon`, `argonaut` are all the
Arch logo, and the theme name is the only information the filename carries.

### If a wallpaper produces a colourless rice

Two guards exist, because a flat logo is not a photograph:

- **wallust** rejects images with too few distinct colours (its default
  threshold is 10; `arch-logo-dark.png` is 48 shades of near-identical grey).
  `setwall` now walks the threshold down to 5, 2, 1 before giving up, and says
  which one worked. It used to ignore the exit status entirely, so the
  wallpaper changed while the colours stayed from the previous one.
- **The accent** is checked for chroma. A greyscale image yields an accent a
  shade off the background, which makes every selected state invisible. A
  colourless accent is replaced with the fallback blue; a coloured but dim one
  is brightened, keeping its hue.

---

## Scrolling layout

Windows form one horizontal row of columns that scrolls, niri-style, instead
of subdividing the screen.

| Keys | Does |
|---|---|
| `SUPER` + scroll | move along the row |
| `SUPER+CTRL` + scroll | switch workspace (where plain `SUPER`+scroll used to) |
| `SUPER` `[` / `]` | cycle the focused column's width |
| `SUPER+C` | centre the focused column |
| `SUPER+SHIFT+G` | promote the window to the front of the row |

Widths cycle through `0.333, 0.5, 0.667, 1.0`, set in
`hypr/configs/scrolling.conf`.

### Tuning the scroll feel

Two numbers control it, and they do different jobs:

| Where | What |
|---|---|
| `animations.conf` → `windowsMove, 1, 7, bw_ease` | how long the travel takes — 7 = 700ms. Raise to slow it. |
| `scrolling.conf` → `follow_min_visible = 1.0` | when the view moves at all |

`follow_min_visible` is the one that decides whether scrolling feels
*continuous* or *steppy*. Hyprland's default of `0.4` lets a column sit 60%
off-screen and only jumps once it crosses that line, so the view catches up in
lurches. At `1.0` it keeps the focused column whole and travels on every step.

The curve `bw_ease` is generated from `tokens.py` into `configs/colors.conf`,
so the compositor and the widgets share one motion curve — change it there and
a window sliding settles like a panel opening.

**This is Hyprland's own layout, not a plugin.** Worth stating because the
obvious search leads nowhere useful: `hyprwm/hyprscrolling` does not exist, and
`dawsers/hyprscroller` — the plugin everyone links to — was abandoned in April
2025 with a final commit titled *"Last commit :-("*, well before this
compositor was built. Hyprland's plugin ABI breaks between releases, so it
would not load anyway.

### Going back to floating

The rice used to float **every** window via three catch-all rules in
`windowrules.conf`. That is why a tiling layout looked like it did nothing —
it had nothing to tile. The two are mutually exclusive. To return:

1. Uncomment the three `^(.*)$` rules in `hypr/configs/windowrules.conf`
2. Set `layout = dwindle` in `hyprland.conf`

---

## Checking the whole rice still works

```
blackwall-selftest
```

Runs every panel script, checks the daemons are up, clicks through the
calendar and network panels with a real pointer, and confirms state changes
land in eww. 30 checks; exits non-zero if any fail.

The clicks are real ones. `tools/bwclick` drives a wlr virtual pointer,
because this machine has no uinput and Hyprland has no click dispatcher.
That distinction matters: a hover test cannot stand in for it, since GTK
delivers enter/leave to an eventbox but button-press to the button — which is
how a fix once looked verified and was not.

One thing it does that looks odd on purpose: it clicks the calendar
repeatedly until a click registers before it starts measuring. The first
click after a panel maps can land before the widget is hittable, and without
that warm-up a cold run reports failures that are only a race.

---

## Autostart

Everything the session needs is started by one idempotent script, called from
`hypr/lua/env.lua` on every config pass:

```
blackwall-autostart            start whatever is not running
blackwall-autostart --status   what is up and what is not
```

It starts only what is missing, adopts what is already running, waits for the
compositor to answer before starting Wayland clients, and holds a lock so two
passes cannot race. Both earlier shapes were wrong in opposite directions: a
plain list of `hl.exec_cmd` lines re-ran on every reload (four waybars, then
seventeen `blackwall-watch` daemons, then hundreds of each during a reload
storm), while moving that list into `hl.on("hyprland.start", …)` meant nothing
started at all when the event had already fired — the "no bar until I run
hyprctl reload" login.

The wallpaper was part of the same symptom. `hypr/scripts/last_wallpaper` read
`$(cat ~/.cache/last_wallpaper > /dev/null)`, where the redirect applies to
`cat` and not to the substitution, so the path was always empty and
`awww img ""` failed at every login — which is why the desktop came up showing
Hyprland's own default picture.

---

## Scripts on PATH

`scripts/link-bin` symlinks these into `/usr/local/bin`. Until it is run they
must be called by full path.

```
sudo ~/.config/.dotfiles/blackwall/scripts/link-bin
```

Worth knowing: `setwall` and `rofi-paper` were once *copied* into `/usr/bin`
rather than linked, so edits in this repo had no effect on what actually ran.
`link-bin` puts links in `/usr/local/bin`, which precedes `/usr/bin` on PATH, so
it shadows those stale copies without deleting anything.

---

## The Hyprland config, in Lua

Hyprland 0.57 removes the `.conf` format. The config lives in `hypr/lua/` and
**this is what loads now**. The `.conf` is still there, untouched, as the
fallback.

Hyprland prefers `hyprland.lua` over `hyprland.conf` when both exist, so the
symlink is the whole switch:

```
rm ~/.config/hypr/hyprland.lua                                    # revert to the .conf
ln -sfn lua/hyprland.lua ~/.config/hypr/hyprland.lua              # switch back to Lua
```

Both take effect at the **next login** — a config is only read at startup, so
neither does anything to the session you are in. If a login comes up wrong,
reach a TTY with `Ctrl+Alt+F2`, run the `rm`, and log in again.

Two things nesting could not verify, so try them first after switching:
**focus by direction** (hjkl and the arrows) and **SUPER+drag** to move or
resize a window.

Check a config without loading it — this is what makes the switch safe to try:

```
Hyprland --config ~/.config/hypr/lua/hyprland.lua --verify-config
```

Careful: `--verify-config` **executes** the `exec_cmd` entries. It starts
waybar, eww and swaync while checking. Every one is single-instance guarded so
you get no duplicates, but it is not a side-effect-free check.

**`config ok` is not "it works".** It means the Lua ran without raising. A
call can be perfectly valid and still do the wrong thing — `exec_raw` is a
*shell command*, not a dispatcher, and `exec_raw("workspace 3")` parses fine
while trying to run a program called `workspace`. That silently killed 22
binds once.

To actually run it, boot Hyprland **nested**. With `WAYLAND_DISPLAY` set it
starts inside the current session as a window, with its own socket:

```
Hyprland --config ~/.config/hypr/lua/hyprland.lua      # a window, not a takeover
```

Then talk to it by setting `HYPRLAND_INSTANCE_SIGNATURE` to the new entry in
`$XDG_RUNTIME_DIR/hypr/`, and compare against the live session. Strip the
`hl.exec_cmd` lines from a copy first, or it starts a second waybar and eww.

There is a self-test that runs every dispatcher this config uses, inside a
real compositor, and reports what each one actually did:

```
WAYLAND_DISPLAY=wayland-1 Hyprland --config hypr/lua/tests/dispatch-selftest.lua
cat /tmp/bw-dispatch-selftest.txt
```

Read it knowing what it can and cannot prove. Lines showing a state change
(`HL.Workspace(1:1) -> HL.Workspace(3:3)`) are real evidence. Lines saying
`accepted` are not: with no window open, `direction = "banana"` is accepted
too. Argument validation happens at dispatch, against a target that is not
there.

It cannot test focus-by-direction, and this is not fixable. A nested
compositor never assigns itself a focused window - `hl.get_window()` stays nil
even with clients mapped inside it, through host focus, cursor entry and a
real click alike. With nothing focused, every direction reports no change,
`"banana"` included. Those binds have to be checked by using them.

One trap: **`hl.timer` crashes `--verify-config`** — the verifier has no event
loop and dumps core. So the self-test cannot be verified, only run, and a
timer must never go in the real config or the safety check stops working.

The dispatchers are documented inside the binary — the shipped default Lua
config is embedded there:

```
strings /usr/bin/Hyprland | grep '^hl\.'
```

That is where the real spellings came from: directions are `left/right/up/down`
and never `l/r/u/d`, there is no workspace dispatcher (`focus({workspace=…})`
does it), and `bindm` is `{ mouse = true }`.

**Never `rm -rf` anything under `$XDG_RUNTIME_DIR/hypr/`.** Those directories
hold the compositor's *listening* sockets. Deleting a live one leaves the
session running perfectly — windows, input and any client that already
connected keep working — while every new `hyprctl` call fails, and it cannot
be undone: the socket is still open, but an unlinked one cannot be linked back
(the fd is on procfs, the target on tmpfs, so `linkat` returns `EXDEV` even as
root). Only a restart of Hyprland brings it back. Stale directories from
exited nested instances are safe to remove, but the live one is not
distinguishable by reading `/proc/<pid>/environ` — the host's signature is not
in there.

Two traps that cost a session on 2026-09-12:

- **Top-level `hl.exec_cmd` is `exec`, not `exec-once`.** It runs again on
  every reload, and Hyprland reloads whenever a config file is saved. Every
  edit had quietly been starting another waybar. Autostart now lives in
  `hl.on("hyprland.start", function() ... end)` in `env.lua`, which fires once
  per session.
- **`hl.plugin.load(path)` is declarative**, like `plugin =` in the .conf. It
  adds the path to a list that is emptied on every reload. After the config
  runs, Hyprland loads what is listed, unloads what is not, and reloads again
  if anything changed. It must therefore be called on *every* pass. Guarding
  it with `if not hl.plugin.X` skipped it on the second pass, so the plugin was
  unloaded, then loaded again on the pass after, forever. The result was
  hundreds of reloads and about 200 waybars, and then the compositor aborted.

Dispatchers are typed — `hl.dsp.window.close()` rather than `killactive`. Where
there is no typed form (workspace switching, `layoutmsg`, groups),
`hl.dsp.exec_raw` takes the same string the `.conf` used. `colors.lua` is
generated from the same tokens as everything else; never edit it by hand.

---

## eww, and four things that cost hours

**`:onclick` goes on the button, not the eventbox around it.** An `eventbox`
with `:onclick` wrapping a plain `box` fires. The same eventbox wrapping a
`button` does not — GtkButton consumes the press before the eventbox sees it.
The button's own `:onclick` fires. What made this expensive is that hover
*does* reach the eventbox, so a hover test says the eventbox works and the
conclusion is wrong.

**A script an eww handler launches cannot call `eww update`.** eww waits for
the handler to finish; the handler waits for eww to answer. Neither times out
and nothing is logged — the click simply does nothing. Every script eww invokes
re-execs itself detached first:

```bash
if [[ "${BW_DETACHED:-}" != 1 ]]; then
    BW_DETACHED=1 setsid "$(readlink -f "$0")" "$@" >/dev/null 2>&1 &
    exit 0
fi
```

**`:focusable true` on a layer-shell window freezes the session.** It requests
exclusive keyboard interactivity, and a panel that takes every key leaves no
way to reach anything else — including whatever you would use to close it.

**Polls cannot read variables.** `defpoll` has no access to eww state at all, so
anything derived from state has to be *pushed* in by a script rather than
polled. `:visible` is also unreliable on boxes; a `for` over a list that is
empty or has one element is the only conditional rendering that behaves.

---

## Testing that a click actually works

There is no uinput module on this machine and Hyprland has no click dispatcher,
so nothing could press a button to check a fix. `tools/bwclick` is a small
wlr-virtual-pointer client that can:

```
bwclick X Y          # click at an absolute position
bwclick X Y W H      # click the centre of a rectangle
```

Combined with `hyprctl layers` to find a panel's geometry, this turns "I think
that works now" into something you can run. Several fixes that were asserted
and shipped did not work; this is how that stopped.

---

## `eww reload` keeps the old config when the new one is broken (a trap)

A yuck file with one paren too many does not produce an error you will see.
`eww reload` reports success, the daemon keeps serving the **last config that
parsed**, and every edit after that silently does nothing — you change a
widget, reload, screenshot, and see the old one, over and over.

What surfaces it:

```
eww open <window>     # "No window named 'x' exists in config"
```

That message means the config failed to load, not that the window is missing.
To check a file directly:

```
python3 -c "s=open('widgets/…/net.yuck').read(); print(s.count('('), s.count(')'))"
```

Widget definitions also do not always come back on `eww reload`. When a change
refuses to appear and the parens balance, restart the daemon:

```
eww kill && eww daemon
```

---

## A wrapped label that truncates anyway (a trap)

`:wrap true` on an eww label is not enough. `show-truncated` defaults to on
and sets Pango's ellipsize, which wins over wrapping — so a long hint renders
as one clipped line ending in `…` no matter how much width it has. Both must
be set:

```lisp
(label :xalign 0 :hexpand true :wrap true :show-truncated false :text "…")
```

Things that look like the fix and are not: `:hexpand true` alone, `:width N`,
and `:limit-width N` — the last one makes it worse, because that is the
property that turns ellipsize *on*.

---

## Styling text inside buttons (a trap)

`eww.scss` opens with `* { all: unset; font-family: $font_ui; color: $fg; }`.
That sets font and colour **directly on every element**, including the label
eww creates inside a `(button ... "text")`. A directly-set value beats an
inherited one, so a rule on the button never reaches its own text — the button
gets the background, the text keeps the default.

Any rule changing a button's font or colour must name the label too:

```scss
.thing, .thing label { color: $faint; }
```

This bit twice: the audio icons and the calendar's out-of-month days both
looked styled in the stylesheet and rendered unstyled on screen.

Icons additionally need the icon family, via the `$font_icon` token:

```scss
.thing, .thing label { font-family: $font_icon; }
```

Two things bite here:

1. `* { font-family: $font_ui }` in `eww.scss` sets the family *directly* on
   every label. A directly-set value beats an inherited one, so putting an icon
   font on a parent button does nothing to the label inside it.
2. `$font_icon` is `"Symbols Nerd Font"` and nothing else. Asking GTK for
   `"JetBrainsMono Nerd Font"` renders **different symbols** at the same
   codepoints, reproducibly, even though every Nerd Font file on disk contains
   the right glyph when rendered directly. Why is not understood. Use the
   family that works.

Diagnosing this: render the codepoint straight from the `.ttf` with PIL to
learn what it *should* look like. `fc-list :charset=…` only proves a font
*contains* a glyph, never that Pango will reach that font.
