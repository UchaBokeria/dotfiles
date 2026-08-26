-- Environment and autostart.

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

local env = {
    XCURSOR_SIZE = "24",
    HYPRCURSOR_SIZE = "24",
    LIBVA_DRIVER_NAME = "iHD",              -- for the Quest 3
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

-- Notifications: swaync if it is installed, mako otherwise. Both own
-- org.freedesktop.Notifications, so exactly one may run; the test is on the
-- binary so that installing the package is the only step needed to switch.
hl.exec_cmd("sh -c 'if command -v swaync >/dev/null; then systemctl --user stop mako.service 2>/dev/null; exec swaync; else exec systemctl --user start mako.service; fi'")

-- Records every notification with a timestamp. Passive: it becomes a D-Bus
-- monitor while the daemon above receives and displays them unchanged.
hl.exec_cmd(bw .. "/scripts/blackwall-notifyd")

hl.exec_cmd("~/.config/hypr/scripts/last_wallpaper")
hl.exec_cmd("waybar")
hl.exec_cmd("eww daemon")
hl.exec_cmd("wayvnc -R -v -L debug 127.0.0.1 5900")
hl.exec_cmd("xfsettingsd")

-- cliphist records nothing unless something feeds it; without this the
-- clipboard history stays empty, which is how it sat for months.
hl.exec_cmd(bw .. "/scripts/blackwall-clip --daemon")
hl.exec_cmd(bw .. "/scripts/blackwall-watch --daemon")
