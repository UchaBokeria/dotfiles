# the installer's catalogue

Three TOML files. The installer is the program that applies them; these are
what it applies. A change to the rice should land here, not in Rust.

| file | holds | written by |
|---|---|---|
| `packages.toml` | package groups — a required core, then optional groups you tick | inventory of this machine, checked against what the configs actually call |
| `links.toml` | every file that is symlinked or copied into place, plus settings (`gsettings`, `xfconf`, services) | walking `~/.config` and friends and asking what points where |
| `steps.toml` | what has to be built, generated or enabled afterwards, in order | reading each component's own README, Makefile and docs |

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
runs them in that order and defers anything needing a graphical session to a
second pass after the first login.

## keeping them honest

`packages.toml` drifts the moment something is installed by hand. The check
that matters: for every binary the configs invoke, is its package in a group?
`theme/run-tests` covers the script/cheatsheet half of that; the package half
is a re-inventory, which is a day's work and worth doing before a release
rather than continuously.
