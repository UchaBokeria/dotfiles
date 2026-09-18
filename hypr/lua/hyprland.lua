-- blackwall, in Hyprland's Lua config format.
--
-- Hyprland 0.57 removes the `.conf` format. This is the same configuration
-- translated, kept alongside the .conf rather than replacing it: the .conf is
-- still what loads, and switching is one deliberate step (see README.md next
-- to this file).
--
-- Split the same way the .conf was, because the split is good: settings,
-- animations, rules, environment, keybinds.

package.path = os.getenv("HOME") .. "/.config/hypr/lua/?.lua;" .. package.path

-- What differs between machines, in one table, with the values this repo
-- assumes. hypr/lua/machine.lua overrides any of them; it is gitignored and
-- written by the installer from what it detects and what it asked, which is
-- how the modifier key and the extra bindings that used to be hand-edited on
-- every box (and lost on every clone) now travel with the install instead of
-- with the repo.
BLACKWALL = {
    mod = "SUPER",         -- the modifier every binding hangs off
    terminal = "kitty",
    file_manager = "thunar",
    -- extra_binds = function() ... end   -- called after keybinds.lua
}
pcall(require, "machine")

require("settings")
require("animations")
require("rules")
-- After rules: glass.lua adds its own window rules and whitelists layers that
-- rules.lua gives compositor blur. It does nothing if the plugin is missing.
require("glass")
require("env")
require("keybinds")

-- Whatever this machine wants on top of the standard set. Defined in
-- machine.lua; called here so it binds last and therefore wins.
if type(BLACKWALL.extra_binds) == "function" then
    -- print, not hl.notify: an unknown function here would raise inside the
    -- handler for a raise, and a config that cannot finish loading is a
    -- session that does not start.
    local ok, err = pcall(BLACKWALL.extra_binds)
    if not ok then
        print("blackwall: machine.lua extra_binds failed: " .. tostring(err))
    end
end
