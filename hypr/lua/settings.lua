-- Everything that was `general {}`, `decoration {}`, `input {}` and friends.
--
-- Comments carried over from the .conf verbatim where they still explain a
-- choice; a migration that drops the reasoning leaves you with a config nobody
-- can safely change later.

local bw = require("colors")

hl.config({
    render = {
        send_content_type = false,
        cm_auto_hdr = 0,
    },

    general = {
        gaps_in = 5,
        gaps_out = 20,
        border_size = 2,

        -- Was Hyprland's stock demo gradient - a cyan-to-green that belonged
        -- to no palette this rice has ever had. These follow the wallpaper.
        col = {
            active_border = bw.border_active,
            inactive_border = bw.border_inactive,
        },

        resize_on_border = false,
        allow_tearing = false,

        -- `scrolling` is Hyprland's own niri-style layout. Floating windows
        -- are on by request (see rules.lua), and the two are mutually
        -- exclusive, so this stays dwindle.
        layout = "dwindle",
    },

    decoration = {
        -- 12 is the app-window step of the radius scale in
        -- theme/blackwall_theme/tokens.py. Panels round themselves in their
        -- own CSS and are larger.
        rounding = 12,
        rounding_power = 2,

        -- Content windows are opaque. Translucency in this rice lives in the
        -- chrome layer, applied to each surface's own background colour. A
        -- compositor opacity rule fades the text along with the fill, which is
        -- the one thing frosted glass never does.
        active_opacity = 1.0,
        inactive_opacity = 1.0,

        shadow = {
            enabled = true,
            -- Wide, soft and weak reads as a window floating above a surface;
            -- range 4 at ee alpha read as a hard dark outline.
            range = 22,
            render_power = 3,
            offset = "0 6",
            color = bw.shadow,
            color_inactive = bw.shadow_inactive,
        },

        blur = {
            enabled = true,
            size = 8,
            passes = 3,

            -- xray made blur skip other windows and sample only the wallpaper,
            -- so a terminal behind a translucent surface stayed perfectly
            -- sharp through it. Off means the blur shows what is behind.
            xray = false,
            ignore_opacity = false,
            new_optimizations = true,

            -- Menus and dropdowns are chrome too.
            popups = true,
            popups_ignorealpha = 0.2,
        },
    },

    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
    },

    misc = {
        mouse_move_enables_dpms = true,
        key_press_enables_dpms = true,
        force_default_wallpaper = -1,
        disable_hyprland_logo = false,
    },

    input = {
        kb_layout = "us,ge",
        kb_options = "grp:ctrl_alt_k_toggle",
        follow_mouse = 1,
        sensitivity = 0,
        touchpad = {
            natural_scroll = false,
        },
    },

    -- Hyprland's own niri-style scrolling layout, kept configured so switching
    -- `general.layout` to "scrolling" is the only change needed.
    scrolling = {
        column_width = 0.5,
        explicit_column_widths = "0.333, 0.5, 0.667, 1.0",
        focus_fit_method = 1,
        -- How much of the focused column must be visible before the view
        -- scrolls. The default 0.4 lets a column sit 60% off-screen and only
        -- jumps when it passes that line, which is what makes movement feel
        -- like a series of jump cuts.
        follow_min_visible = 1.0,
        follow_focus = true,
        wrap_focus = false,
    },
})

hl.device({ name = "epic-mouse-v1", sensitivity = -0.5 })
