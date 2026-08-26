# The Lua config

Hyprland 0.57 removes the `.conf` format; this is the same configuration in
Lua. **It is not live.** `~/.config/hypr/hyprland.conf` is still what loads.

## Checking it

    Hyprland --config ~/.config/hypr/lua/hyprland.lua --verify-config

Note this *executes* the `exec_cmd` entries - it starts waybar, eww and the
rest. Every one of those is single-instance guarded, so it does not produce
duplicates, but it is not a side-effect-free check.

## Switching

    ln -sf ~/.config/hypr/lua/hyprland.lua ~/.config/hypr/hyprland.lua

Hyprland prefers `hyprland.lua` over `hyprland.conf` when both exist, so that
symlink is the whole switch. Log out and back in.

## Reverting

    rm ~/.config/hypr/hyprland.lua

The `.conf` tree is untouched by any of this and takes over again immediately.

## What changed in translation

Nothing behavioural was meant to. Two things read differently:

- **Layer rules are a loop.** The `.conf` needed three lines per namespace
  (`blur`, `ignore_alpha`, `xray`) and adding a panel meant remembering all
  three. `rules.lua` lists the namespaces and applies the same treatment to
  each.
- **Dispatchers are typed** - `hl.dsp.window.close()` rather than
  `killactive`. Where there is no typed form (workspace switching, `layoutmsg`,
  group commands) `hl.dsp.exec_raw("...")` takes the same string the `.conf`
  used, so those lines did not have to be reinvented.

The palette still comes from the token generator: `blackwall-theme hyprlua`
writes `colors.lua`, the Lua sibling of `configs/colors.conf`.
