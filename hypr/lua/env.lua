-- Environment and autostart.

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

local env = {
    XCURSOR_SIZE = "24",
    HYPRCURSOR_SIZE = "24",
    -- LIBVA_DRIVER_NAME is NOT here. It used to be "iHD", which is the right
    -- answer for the Intel card in this machine and the wrong one everywhere
    -- else; the installer detects the GPU and writes it into machine.lua.
    -- Without machine.lua, mesa picks the driver itself, which works.
    QT_QPA_PLATFORMTHEME = "qt6ct",
    QT_WAYLAND_DISABLE_WINDOWDECORATION = "1",
    QT_AUTO_SCREEN_SCALE_FACTOR = "1",
    GTK_USE_PORTAL = "1",
    GDK_BACKEND = "wayland",
    XDG_CURRENT_DESKTOP = "Hyprland",
    XDG_SESSION_DESKTOP = "Hyprland",
    XDG_SESSION_TYPE = "wayland",
}
for k, v in pairs(env) do hl.env(k, v) end

local bw = "~/.config/.dotfiles/blackwall"

-- One line, because the list it replaced had two failure modes and this has
-- neither.
--
-- A top-level hl.exec_cmd is the .conf's `exec`, not `exec-once`: it runs
-- again on every reload, and Hyprland reloads whenever a config file is saved.
-- That is how four waybars were running before anyone counted, how a plugin
-- reload storm started hundreds, and how seventeen blackwall-watch daemons
-- accumulated. Moving the list into `hl.on("hyprland.start", ...)` fixed the
-- duplicates and broke the opposite way: if the event has already fired by the
-- time the config registers the handler, nothing starts at all and the session
-- comes up with no bar and Hyprland's default wallpaper.
--
-- blackwall-autostart is idempotent instead: it starts only what is not
-- already running, waits for the compositor to answer before starting Wayland
-- clients, and holds a lock so two passes cannot race. Running it again costs
-- nothing, so it can be called the simple way - every pass, unconditionally.
hl.exec_cmd(bw .. "/scripts/blackwall-autostart")
