-- Keybinds.
--
-- Typed dispatchers where there is one (`hl.dsp.window.close()`), and
-- `hl.dsp.exec_raw("...")` where there is not - workspace switching and
-- layoutmsg have no typed form, and exec_raw takes exactly the string the
-- .conf used, so those translate without inventing anything.

local SUPER = "SUPER"
local bw    = "~/.config/.dotfiles/blackwall"
local rofi  = "~/.config/rofi/blackwall/launch"

local terminal    = "kitty"
local fileManager = "thunar"
local shot        = bw .. "/scripts/blackwall-shot"
local audio       = bw .. "/scripts/blackwall-audio"
local quiet       = bw .. "/scripts/blackwall-quiet"

local function run(cmd) return hl.dsp.exec_cmd(cmd) end
local function raw(s)   return hl.dsp.exec_raw(s) end

-- ---- launching -----------------------------------------------------------
hl.bind(SUPER .. " + return",         run(terminal))
hl.bind(SUPER .. " + SHIFT + return", run("env START_TMUX=0 " .. terminal))
hl.bind(SUPER .. " + R", run(rofi .. " grid"))
hl.bind(SUPER .. " + F", run(rofi .. " list -show filebrowser -filebrowser-directory ~/.config"))
hl.bind(SUPER .. " + SHIFT + F", run(fileManager))
hl.bind(SUPER .. " + U", run(bw .. "/scripts/rofi-paper"))
hl.bind(SUPER .. " + SHIFT + Q", run("~/.config/wlogout/launch"))
hl.bind(SUPER .. " + CTRL + Q", run("hyprlock"))
hl.bind(SUPER .. " + CTRL + SPACE",
    run("fish -c 'cd $HOME/.config/.dotfiles/blackwall/hyprmod/hyprmod; uv run hyprmod'"))
hl.bind("CTRL + ALT + K", run("hyprctl switchxkblayout current next"))

-- ---- windows -------------------------------------------------------------
hl.bind(SUPER .. " + W", hl.dsp.window.close())
hl.bind(SUPER .. " + B", hl.dsp.window.fullscreen({ mode = 0 }))
hl.bind(SUPER .. " + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind(SUPER .. " + P", hl.dsp.window.pseudo())
hl.bind(SUPER .. " + G", raw("togglegroup"))
hl.bind(SUPER .. " + SHIFT + space", raw("changegroupactive"))
hl.bind(SUPER .. " + ALT + space",   raw("lockgroups toggle"))

hl.bind(SUPER .. " + mouse:272", hl.dsp.window.drag(),   { drag = true })
hl.bind(SUPER .. " + mouse:273", hl.dsp.window.resize(), { drag = true })

-- ---- focus and movement --------------------------------------------------
local dirs = { h = "l", l = "r", k = "u", j = "d" }
for key, dir in pairs(dirs) do
    hl.bind(SUPER .. " + " .. key, hl.dsp.focus({ direction = dir }))
    hl.bind(SUPER .. " + SHIFT + " .. key, hl.dsp.window.move({ direction = dir }), { release = true })
end
local arrows = { left = "l", right = "r", up = "u", down = "d" }
for key, dir in pairs(arrows) do
    hl.bind(SUPER .. " + " .. key, hl.dsp.focus({ direction = dir }), { release = true })
    hl.bind(SUPER .. " + SHIFT + " .. key, hl.dsp.window.move({ direction = dir }), { release = true })
    hl.bind(SUPER .. " + ALT + " .. key,
        raw("resizeactive " .. ({ left = "-20 0", right = "20 0", up = "0 -20", down = "0 20" })[key]),
        { repeating = true })
end
hl.bind(SUPER .. " + CTRL + h",     raw("workspace -1"),    { release = true })
hl.bind(SUPER .. " + CTRL + l",     raw("workspace +1"),    { release = true })
hl.bind(SUPER .. " + CTRL + left",  raw("workspace -1"),    { release = true })
hl.bind(SUPER .. " + CTRL + right", raw("workspace +1"),    { release = true })
hl.bind(SUPER .. " + CTRL + k",     raw("focusmonitor l"),  { release = true })
hl.bind(SUPER .. " + CTRL + j",     raw("focusmonitor r"),  { release = true })
hl.bind(SUPER .. " + CTRL + up",    raw("focusmonitor l"),  { release = true })
hl.bind(SUPER .. " + CTRL + down",  raw("focusmonitor r"),  { release = true })
hl.bind(SUPER .. " + Tab", raw("workspace previous"), { release = true })

-- ---- workspaces ----------------------------------------------------------
for i = 1, 10 do
    local key = (i == 10) and "0" or tostring(i)
    hl.bind(SUPER .. " + " .. key,           raw("workspace " .. i))
    hl.bind(SUPER .. " + SHIFT + " .. key,   raw("movetoworkspace " .. i))
end
hl.bind(SUPER .. " + S",         raw("togglespecialworkspace magic"))
hl.bind(SUPER .. " + SHIFT + S", raw("movetoworkspace special:magic"))
for i = 1, 12 do
    hl.bind(SUPER .. " + F" .. i,           raw("togglespecialworkspace f" .. i))
    hl.bind(SUPER .. " + SHIFT + F" .. i,   raw("movetoworkspace special:f" .. i))
end

-- ---- scrolling layout ----------------------------------------------------
-- SUPER+scroll walks the row of columns, which is the gesture the layout
-- exists for; workspace switching moves to SUPER+CTRL+scroll rather than
-- being lost.
hl.bind(SUPER .. " + mouse_down", hl.dsp.focus({ direction = "r" }))
hl.bind(SUPER .. " + mouse_up",   hl.dsp.focus({ direction = "l" }))
hl.bind(SUPER .. " + CTRL + mouse_down", raw("workspace e+1"))
hl.bind(SUPER .. " + CTRL + mouse_up",   raw("workspace e-1"))
hl.bind(SUPER .. " + bracketright", hl.dsp.layout("colresize", "next"))
hl.bind(SUPER .. " + bracketleft",  hl.dsp.layout("colresize", "prev"))
hl.bind(SUPER .. " + C",            hl.dsp.layout("center"))
hl.bind(SUPER .. " + SHIFT + G",    hl.dsp.layout("promote"))

-- ---- capture -------------------------------------------------------------
hl.bind(SUPER .. " + SHIFT + S",  run(shot .. " region"))
hl.bind(SUPER .. " + Print",      run(shot .. " output"))
hl.bind(SUPER .. " + CTRL + S",   run(shot .. " window"))
hl.bind(SUPER .. " + SHIFT + Print", run(shot .. " region --edit"))
hl.bind(SUPER .. " + O",          run(shot .. " region --ocr"))
hl.bind(SUPER .. " + SHIFT + O",  run(shot .. " region --translate"))
hl.bind(SUPER .. " + ALT + S",    run(shot .. " region --ask"))
hl.bind(SUPER .. " + CTRL + V",   run(bw .. "/scripts/blackwall-shots"))
hl.bind(SUPER .. " + SHIFT + V",  run(bw .. "/scripts/blackwall-clip"))
hl.bind(SUPER .. " + N",          run("flameshot gui"))
hl.bind(SUPER .. " + M",          run("~/.config/eww/scripts/toggle my-sticker-window"))

hl.bind(SUPER .. " + CTRL + ALT + F9",
    run('wf-recorder --audio="$(find_internal_audio)" -g "$(slurp)" -f $(xdg-user-dir VIDEOS)/recording-region-$(date +%Y%m%d-%H%M%S).mp4'))
hl.bind(SUPER .. " + CTRL + SHIFT + F9",
    run('wf-recorder --audio="$(find_internal_audio)" -f $(xdg-user-dir VIDEOS)/recording-$(date +%Y%m%d-%H%M%S).mp4'))
hl.bind(SUPER .. " + CTRL + SHIFT + F10",
    run('pkill wf-recorder && notify-send "Recording" "Stopped"'))

-- ---- audio, notifications, brightness ------------------------------------
hl.bind(SUPER .. " + A",         run(audio .. " pick-sink"))
hl.bind(SUPER .. " + SHIFT + A", run(audio .. " pick-source"))
hl.bind(SUPER .. " + D",         run("swaync-client -t -sw"))
hl.bind(SUPER .. " + SHIFT + D", run(quiet .. " dnd toggle"))
hl.bind(SUPER .. " + CTRL + D",  run(quiet .. " pick"))

-- Media keys talk to wpctl directly rather than through blackwall-audio: a
-- volume key should not pay for a python start-up.
local media = {
    { "XF86AudioRaiseVolume",  "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+" },
    { "XF86AudioLowerVolume",  "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-" },
    { "XF86AudioMute",         "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle" },
    { "XF86AudioMicMute",      "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle" },
    { "XF86MonBrightnessUp",   "brightnessctl -e4 -n2 set 5%+" },
    { "XF86MonBrightnessDown", "brightnessctl -e4 -n2 set 5%-" },
}
for _, m in ipairs(media) do
    hl.bind(m[1], run(m[2]), { repeating = true, locked = true })
end
for _, m in ipairs({
    { "XF86AudioNext",  "playerctl next" },
    { "XF86AudioPause", "playerctl play-pause" },
    { "XF86AudioPlay",  "playerctl play-pause" },
    { "XF86AudioPrev",  "playerctl previous" },
}) do
    hl.bind(m[1], run(m[2]), { locked = true })
end

-- ---- archpilot -----------------------------------------------------------
local ap = bw .. "/archpilot/.venv/bin/archpilot"
hl.bind(SUPER .. " + grave",         run(ap .. " ui --toggle"))
hl.bind(SUPER .. " + SHIFT + grave", run(ap .. " shot"))
hl.bind(SUPER .. " + CTRL + grave",  run(ap .. " sessions"))
hl.bind(SUPER .. " + ALT + grave",   run(ap .. " history"))
