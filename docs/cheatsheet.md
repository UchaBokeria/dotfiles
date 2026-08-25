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
notification when something wants attention. **Left-click a notification to run
its action** — mako does not draw buttons, so the whole notification is the
button.

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

## Control centre

Waybar's arch icon (far right) opens it. `~/.config/eww/scripts/toggle control_center`.

**Network pane** — every row is a control, not a readout:

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

Backed by `blackwall-notifyd`, started from `hypr/configs/exec.conf`. It becomes
a **passive D-Bus monitor**: it logs every notification with a timestamp while
mako receives and displays them over its own connection, unchanged. mako stays
the notification daemon.

This exists because mako's own buffer holds only a handful of entries, carries
no timestamps at all, and empties whenever mako restarts — which a re-theme
does. The log keeps the last 500 in
`~/.local/share/blackwall/notifications.jsonl`.

The panel itself scrolls, so adding a section later cannot push anything off
the bottom of the screen.

```
blackwall-net status        # everything as one JSON blob
blackwall-net pick-wifi     # rofi wifi picker, no panel needed
blackwall-net pick-bt       # rofi bluetooth picker
blackwall-net vpn-toggle
```

Scanning only runs while its section is open — a wifi scan is not free and
there is no reason to run one when nobody is looking at the list.

---

## Calendar and clocks

Either half of the waybar clock opens it.

- **Today** is ringed in accent; the **selected** day is filled. A day with
  unfinished reminders carries a dot under the number.
- `‹` `›` page months; clicking the month name jumps back to this one.
- Click a day to see its reminders. Type in the box and press Enter to add one,
  click a reminder to tick it off, `×` to delete it.
- **elsewhere** shows configured timezones. A zone in a different calendar day
  says so (`wed · tomorrow`) rather than making you compare two clock faces.

Unfinished reminders for today also raise a notification (tier 1, every 4h,
click to open the calendar).

```
blackwall-cal due                       # today's unfinished reminders
blackwall-cal add 2026-09-01 "text"
blackwall-cal zone-add Europe/Lisbon    # optionally: ... "lisbon"
blackwall-cal zone-remove Asia/Bangkok
```

Timezones live in `~/.config/blackwall/timezones`, one per line as
`Area/City | label`. Reminders live in
`~/.local/share/blackwall/calendar.json`.

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
