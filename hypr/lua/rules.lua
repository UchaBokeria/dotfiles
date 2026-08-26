-- Window and layer rules.

-- Every panel in this rice is a layer-shell surface that wants the same
-- treatment: blur what is behind it, skip fully transparent pixels, and do not
-- use xray - xray makes blur sample only the wallpaper, so a terminal behind a
-- translucent surface stays perfectly sharp through it.
--
-- A loop rather than 24 near-identical lines: the .conf had three lines per
-- namespace and adding a panel meant remembering all three.
local panels = {
    { ns = "waybar",                    alpha = 0.2  },
    { ns = "rofi",                      alpha = 0.15 },
    { ns = "notifications",             alpha = 0.15 },
    { ns = "eww_ios",                   alpha = 0.15 },
    { ns = "eww_calendar",              alpha = 0.15 },
    { ns = "eww_wifi",                  alpha = 0.15 },
    { ns = "swaync-control-center",     alpha = 0.15 },
    { ns = "swaync-notification-window", alpha = 0.15 },
}

for _, p in ipairs(panels) do
    hl.layer_rule({
        match = { namespace = p.ns },
        blur = true,
        ignore_alpha = p.alpha,
        xray = false,
    })
end

-- These two dim what is behind them as well; they are modal.
for _, ns in ipairs({ "logout_dialog", "gtk-layer-shell" }) do
    hl.layer_rule({
        match = { namespace = ns },
        blur = true,
        ignore_alpha = 0.05,
        dim_around = true,
    })
end

-- ---- windows -------------------------------------------------------------

hl.window_rule({
    name = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name = "fix-xwayland-drags",
    match = {
        class = "^$", title = "^$",
        xwayland = true, float = true,
        fullscreen = false, pin = false,
    },
    no_focus = true,
})

hl.window_rule({
    name = "move-hyprland-run",
    match = { class = "hyprland-run" },
    move = "20 monitor_h-120",
    float = true,
})

-- Portal dialogs are dialogs; they float wherever they are asked to appear.
hl.window_rule({ match = { tag = "portal-dialogs" }, float = true, center = true, size = "50 60" })
for _, c in ipairs({ "xdg-desktop-portal-gtk", "xdg-desktop-portal-kde" }) do
    hl.window_rule({ match = { class = "^(" .. c .. ")$" }, float = true, center = true, size = "1000 750" })
end
hl.window_rule({ match = { class = "^(xdg-desktop-portal-hyprland)$" }, float = true, center = true })

-- Every new window floats, centred, by request. This is mutually exclusive
-- with the scrolling layout - a tiling layout with nothing to tile arranges an
-- empty set - so general.layout stays dwindle. Drop these three and set
-- layout = "scrolling" in settings.lua to switch back.
hl.window_rule({ match = { class = "^(.*)$" }, float = true, center = true, size = "1200 800" })

-- Genuine dialogs get a size that suits them rather than the blanket one.
hl.window_rule({
    match = { class = "^(pavucontrol|nm-connection-editor|blueman-manager)$" },
    float = true, center = true, size = "900 640",
})

-- ArchPilot and the sticker board pin themselves above everything.
for _, c in ipairs({ "eww-archpilot", "eww-my-sticker-window" }) do
    hl.window_rule({ match = { class = "^(" .. c .. ")$" }, float = true, pin = true })
end
