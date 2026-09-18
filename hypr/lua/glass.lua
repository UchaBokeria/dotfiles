-- Liquid glass, from the hyprglass plugin.
--
-- Hyprland's own blur only smears what is behind a surface. hyprglass treats a
-- surface as a thick slab of glass instead: flat in the middle, where light
-- passes almost straight through (blur, plus a slight dome), and curved at the
-- edge, where it bends outward, pulls in what lies just beyond the surface and
-- splits into colours. A highlight catches the top rim and a shadow sits on
-- the bottom one. Middle is blur, edges are glass; `edge_thickness` is where
-- one becomes the other.
--
-- The tuning is restraint. Apple's material is desaturated, low in contrast
-- and refracts gently - it sits behind the content and stays out of the way.
-- Every knob turned up gives a windscreen in the rain, not glass. The plugin's
-- defaults are already close to Apple's, so the presets below move a few of
-- them on purpose, and the tint comes from the wallpaper like every other
-- colour in the rice.
--
-- The plugin is built and installed by `blackwall-glass install`. Without the
-- .so this file does nothing, and the compositor blur in rules.lua stays in
-- charge - a fresh machine still boots into a working rice.

local SO = os.getenv("HOME") .. "/.local/share/blackwall/hyprglass/hyprglass.so"

local function exists(path)
    local f = io.open(path, "rb")
    if f then f:close() end
    return f ~= nil
end

-- hl.plugin.load is DECLARATIVE, exactly like `plugin =` in the .conf: it adds
-- the path to a list that Hyprland empties at the start of every reload. After
-- the config has run, Hyprland loads whatever is on the list and unloads
-- whatever is not, and reloads again if either changed. So this call has to
-- happen on every pass, unconditionally.
--
-- It was once guarded with `if not hl.plugin.hyprglass`. The plugin's
-- functions are registered before the config runs, so the second pass saw
-- them, skipped the call, and Hyprland unloaded the plugin. The pass after
-- that loaded it again, and the cycle never ended. Every reload also re-ran
-- the autostart, which left about 200 waybars running. It took the session
-- down (2026-09-12).
if exists(SO) then
    hl.plugin.load(SO)
end

-- On the very first pass the plugin is only queued, not loaded yet, so its
-- namespace is missing. Hyprland loads it right after and runs the config
-- again, and on that pass everything below applies.
--
-- Also: none of this does anything unless hyprland.lua actually requires this
-- file. The plugin's own author lost two hours to that one.
if not hl.plugin.hyprglass then
    return
end

local bw = require("colors")
local hg = hl.plugin.hyprglass

hg.config({
    -- Windows opt in by rule (below). Most windows here are opaque content -
    -- a browser, a chat app - and glass under an opaque window is GPU spent
    -- on pixels nobody can see. Layers are unaffected; they have their own
    -- whitelist.
    enabled = false,
    default_theme = "dark",
    default_preset = "blackwall",
    tint_color = bw.glass_tint,

    layers = {
        enabled = true,
        -- Re-render a panel's glass when what is behind it changes (a video,
        -- a scrolling terminal), capped so an idle scene costs nothing.
        live_resample = true,
        live_resample_fps = 30,
    },
})

-- Apple's own material is the waypoint, not the destination: it is built to
-- work for a billion people over every app ever written, so it is deliberately
-- conservative. This is built for one person, so it pushes where they cannot -
-- the three settings that actually read as glass rather than as blur are
-- refraction (light bending outward at the rim, dragging in what lies beyond
-- the window), chromatic aberration (blue bends most, so the rim fringes), and
-- the dome in the middle.
hg.preset("blackwall", {
    blur_strength        = 1.8,
    blur_iterations      = 3,
    -- The one that separates glass from blur. Below ~0.5 the edge just looks
    -- soft; here the rim visibly pulls the wallpaper in from outside.
    refraction_strength  = 0.72,
    chromatic_aberration = 0.45,
    fresnel_strength     = 0.68,
    specular_strength    = 0.78,
    -- Where the flat middle becomes the curved rim. 0.05 was a hairline; at
    -- 0.09 there is enough curve to see light bend through it.
    edge_thickness       = 0.09,
    lens_distortion      = 0.55,
    dark = {
        brightness   = 0.86,
        contrast     = 1.15,
        saturation   = 0.88,
        vibrancy     = 0.35,
        -- Pulls bright areas behind the glass down so text stays readable
        -- over a light wallpaper. This is the half that makes Apple's work
        -- over any background.
        adaptive_dim = 0.50,
    },
})

-- Panels hold text read at a glance - the launcher, notifications, the
-- control centre. More frost and more dimming behind them, and less movement
-- at the rim, so the words never swim.
hg.preset("blackwall_panel", {
    inherits             = "blackwall",
    blur_strength        = 2.4,
    -- Still glass, but a panel is read, not looked at: half the rim movement
    -- of a window and a third of the dome, so a line of text never swims.
    refraction_strength  = 0.45,
    chromatic_aberration = 0.22,
    lens_distortion      = 0.18,
    edge_thickness       = 0.06,
    dark = {
        brightness   = 0.78,
        contrast     = 1.05,
        saturation   = 0.80,
        vibrancy     = 0.22,
        adaptive_dim = 0.62,
    },
})

-- ---- layers ---------------------------------------------------------------
-- Each call whitelists a namespace; anything not named here keeps Hyprland's
-- blur (rules.lua). An empty whitelist would mean EVERY layer, so this list is
-- never allowed to be empty.
--
-- mask_threshold is an alpha cut-off: pixels fainter than it get no glass.
-- Shadows count as visible content, so without it a panel with a drop shadow
-- gets a glass rectangle around the shadow's whole box. It sits above every
-- panel's shadow alpha and below its fill (the glass tokens are 55-74%).
--
-- waybar is deliberately absent: the bar is finished and stays on the
-- compositor's blur.
local layers = {
    "rofi",
    "notifications",               -- mako
    "swaync-control-center",
    "swaync-notification-window",
    "eww_ios",
    "eww_calendar",
    "eww_wifi",
}
for _, ns in ipairs(layers) do
    hg.layer(ns, { preset = "blackwall_panel", mask_threshold = 0.45 })
end

-- ---- windows --------------------------------------------------------------
-- Only windows that are actually translucent get glass. kitty draws its
-- background at 40%; Thunar and ArchPilot draw theirs from the glass tokens.
for _, class in ipairs({ "kitty", "[Tt]hunar", "dev\\.archpilot\\.ui" }) do
    hl.window_rule({ match = { class = "^(" .. class .. ")$" }, tag = "+hyprglass_enabled" })
end

-- Refraction over a playing video is GPU for nothing, and a fullscreen window
-- has no edge for the glass to bend.
hl.window_rule({ match = { class = "^(mpv|vlc|imv)$" }, tag = "+hyprglass_disabled" })
hl.window_rule({ match = { fullscreen = true }, tag = "+hyprglass_disabled" })
