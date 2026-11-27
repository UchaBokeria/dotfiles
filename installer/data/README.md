# the installer's catalogue

Four TOML files. The installer is the program that applies them; these are
what it applies. A change to the rice should land here, not in Rust.

| file | holds | written by |
|---|---|---|
| `packages.toml` | package groups — a required core, then optional groups you tick | inventory of this machine, checked against what the configs actually call |
| `links.toml` | every file that is symlinked or copied into place, plus settings (`gsettings`, `xfconf`, services) | walking `~/.config` and friends and asking what points where |
| `steps.toml` | what has to be built, generated or enabled afterwards, in order | reading each component's own README, Makefile and docs |
| `questions.toml` | the few things the machine cannot answer about itself | what differs between the machines this rice has been on |

## profiles (`--profile desktop|server`)

`steps.toml` entries may carry `profiles = ["server"]` (or `["desktop"]`);
empty (the default) means every profile. The plan builder drops steps whose
list does not name the active profile. Used for: the server-only SDDM
autologin step, and to keep bluetooth (`service-bluetooth`), monitor
brightness (`group-i2c`) and NetworkManager (`service-networkmanager`, which
refuses to replace a cloud image's systemd-networkd) desktop-only on a headless
box. A dropped step is also removed from the `after` list of the steps that
waited on it. The mechanism is
deliberately minimal — a name filter, not a second catalogue.

The server package set is separate and lives in code, not in a catalogue
field: `plan::server_groups()` returns everything the desktop selects
except what the owner leaves behind (`gaming`, `virt`, `dev-unity`) and the
empty `unclassified` group, on top of the always-installed required groups
(`core`, `fonts`, `theming`). The merged server is the owner's daily desktop
over VNC, so browsers, messaging, editors, ai, media, office stay IN; only
hardware *steps* (bluetooth, i2c brightness, NetworkManager/wifi) are
desktop-only. `system` stays selected (kernel/boot tooling); only its `cups`
printing payload is dead weight on a VM, kept for catalogue simplicity.

## the rules these files follow

**Nothing is assumed.** Every package is checked against pacman, every link
against the filesystem, every step against its own `check` command. The plan
the installer shows is the difference between the two, so running it again on
a half-installed machine proposes only what is left.

**Generated files are never linked.** `kind = "generated"` marks the files
`theme/blackwall-theme` writes. Linking one would point the generator at its
own output through a symlink. They are produced by a step instead, after a
wallpaper exists for wallust to derive a palette from.

**Personal things are marked `personal = true`** and skipped unless the person
running it says otherwise: ssh config, the WhatsApp session store, cloud sync
targets, anything with a host or a key in it.

**Order comes from `after`.** A step lists the ids it depends on; the installer
orders them by their declared prerequisites and blocks dependents after failure. Graphical steps are staged by `session-prepare` for automatic first-login completion; no manual second pass is required.

## keeping them honest

`packages.toml` drifts the moment something is installed by hand. The check
that matters: for every binary the configs invoke, is its package in a group?
`theme/run-tests` covers the script/cheatsheet half of that; the package half
is a re-inventory, which is a day's work and worth doing before a release
rather than continuously.


## questions.toml

Four fields carry the weight:

| Field | Means |
|---|---|
| `env` | the environment variable every step sees the answer as |
| `detect` | a shell command whose stdout is the default, so the screen opens on what is already true |
| `default` | the fallback when `detect` is absent or silent — it must be one of the `value`s, and a test enforces that |
| `[[question.option]]` | the choices; omit them entirely and the detected value is simply confirmed |

Keep the list short. A question that could have been a `detect` is a question
that should not be there — and the detector should be written against vendor
strings rather than loose substrings: `grep -iE 'amd|ati'` matched "VGA
compatible controller" through the "ati" in "compatible", and every Intel
machine detected as AMD.

Answers reach steps as ordinary environment variables, which is why a step
reads them as `${BLACKWALL_MOD:-SUPER}` — with that default the step still
does something sensible when it is run outside the TUI, as the tests and the
container runs do.

## First-login completion

`session-prepare` reads the selected noninteractive, unprivileged `needs_session` steps into a durable per-user queue. Group selection and explicitly skipped steps are respected. Required offline prerequisites are checked before registration; session prerequisites are ordered and checked after each job. Machine Lua launches the finalizer; a user timer retries unfinished work. Status and logs live in `$XDG_STATE_HOME/blackwall-installer` (default `~/.local/state/blackwall-installer`). Interactive/root jobs and `selftest` remain manual extras. See `docs/installation.md`.
