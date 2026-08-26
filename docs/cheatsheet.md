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
| `SUPER+SHIFT+S` | select a region |
| `SUPER+Print` | the whole focused monitor |
| `SUPER+CTRL+S` | the focused window only |
| `SUPER+SHIFT+Print` | select a region, then open it in flameshot to annotate |
| `SUPER+O` | select a region, put **its text** on the clipboard (OCR) |
| `SUPER+SHIFT+O` | select a region, OCR it, then **translate** it |
| `SUPER+ALT+S` | select a region and **ask ArchPilot** about it |
| `SUPER+CTRL+V` | **browse past captures** — pick one, then pick an action |
| `SUPER+N` | flameshot's own GUI (unchanged) |

The history browser offers every action above on an old capture: copy, edit,
extract text, translate, ask ArchPilot, open the folder, delete.

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

## Clipboard

| Keys | Does |
|---|---|
| `SUPER+SHIFT+V` | clipboard history — pick an entry to copy it back |

Backed by `cliphist`, recording text **and** images. The watcher starts from
`hypr/configs/exec.conf`; without it history stays empty, which is how it sat
until 2026-08-25.

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

All three share one generated theme (`rofi/shared/blackwall.rasi`); the layouts
in `rofi/blackwall/` hold nothing but geometry.

---

## The bar

```
waybar/variant              # which variant is active
waybar/variant capsule      # one glass pill per module group  (current)
waybar/variant pill         # workspaces + media + ONE right-hand pill
waybar/variant dock         # a single full-width sheet
```

Switching is a symlink swap plus a restart — no diff to revert.

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

---

## Theming

One generator feeds every surface. Change the wallpaper and the whole rice
follows — bar, launcher, notifications, terminal, GTK, Qt, Spotify, nvim, tmux.

```
setwall ~/path/to/image.jpg   # wallpaper + re-theme everything
blackwall-theme               # re-derive tokens without changing wallpaper
blackwall-theme --list        # every target and where it is written
blackwall-theme --check       # audit hand-written files against the radius scale
theme/run-tests               # 69 tests over the token system
```

**Never hardcode a colour or radius in a surface's config.** Edit
`theme/blackwall_theme/tokens.py` and re-run the generator.

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
| `SUPER+D` | open the notification centre |
| `SUPER+SHIFT+D` | do not disturb |
| `SUPER+CTRL+D` | silence an application |

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
