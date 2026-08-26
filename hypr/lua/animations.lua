-- Curves and animations.
--
-- `bw_ease` is the rice's own motion curve, generated from tokens.py into
-- colors.lua - so a window sliding settles exactly like a panel opening, from
-- one definition.

local bw = require("colors")

hl.curve("bw_ease",    { type = "bezier", points = bw.ease })
hl.curve("md3_decel",  { type = "bezier", points = { {0.05, 0.7},  {0.1, 1}    } })
hl.curve("md3_accel",  { type = "bezier", points = { {0.3, 0.8},   {0.15, 0}   } })
hl.curve("menu_decel", { type = "bezier", points = { {0.1, 1},     {0, 1}      } })
hl.curve("menu_accel", { type = "bezier", points = { {0.38, 0.04}, {1, 0.07}   } })

hl.config({ animations = { enabled = true } })

hl.animation({ leaf = "windows",       enabled = true, speed = 3,   bezier = "md3_decel",  style = "popin 60%" })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 3,   bezier = "md3_decel",  style = "slide" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 3,   bezier = "md3_accel",  style = "popin 60%" })

-- Movement is deliberately slower than opening and closing: under the
-- scrolling layout this is the column scroll, the one motion you watch all the
-- way through rather than glance at.
hl.animation({ leaf = "windowsMove",   enabled = true, speed = 7,   bezier = "bw_ease" })

hl.animation({ leaf = "layersIn",      enabled = true, speed = 5,   bezier = "menu_decel", style = "slide right" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 3,   bezier = "menu_accel", style = "slide right" })
hl.animation({ leaf = "fadeLayersIn",  enabled = true, speed = 2,   bezier = "menu_decel" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 4.5, bezier = "menu_accel" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 7,   bezier = "menu_decel", style = "slide" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3, bezier = "md3_decel", style = "slide" })
hl.animation({ leaf = "fade",          enabled = true, speed = 3,   bezier = "md3_decel" })
