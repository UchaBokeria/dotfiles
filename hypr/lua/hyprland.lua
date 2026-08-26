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

require("settings")
require("animations")
require("rules")
require("env")
require("keybinds")
