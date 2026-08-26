-- Keybinds.
--
-- Everything is a typed dispatcher. There is no generic escape hatch:
-- `hl.dsp.exec_raw` is NOT one - it runs a shell command, exactly like
-- exec_cmd. An earlier version of this file used it as though it took a
-- dispatcher line, so `exec_raw("workspace 3")` tried to run a program called
-- `workspace` and 22 binds silently did nothing. `--verify-config` accepts it
-- happily, because it is a valid call; only running it shows the difference.
--
-- Two more things the .conf spelling does not survive:
--   * directions are left/right/up/down, never l/r/u/d
--   * there is no "workspace" dispatcher - switching is focus({workspace=...})

local SUPER = "SUPER"
local bw    = "~/.config/.dotfiles/blackwall"
local rofi  = "~/.config/rofi/blackwall/launch"

local terminal    = "kitty"
local fileManager = "thunar"
local shot        = bw .. "/scripts/blackwall-shot"
local audio       = bw .. "/scripts/blackwall-audio"
local quiet       = bw .. "/scripts/blackwall-quiet"

local function run(cmd) return hl.dsp.exec_cmd(cmd) end
local function ws(v)    return hl.dsp.focus({ workspace = tostring(v) }) end
local function tows(v)  return hl.dsp.window.move({ workspace = tostring(v) }) end

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
hl.bind(SUPER .. " + B", hl.dsp.window.fullscreen({ action = "toggle", mode = "fullscreen" }))
hl.bind(SUPER .. " + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind(SUPER .. " + P", hl.dsp.window.pseudo())
hl.bind(SUPER .. " + G", hl.dsp.group.toggle())
hl.bind(SUPER .. " + SHIFT + space", hl.dsp.group.next())
hl.bind(SUPER .. " + ALT + space",   hl.dsp.group.lock({ action = "toggle" }))

hl.bind(SUPER .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(SUPER .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- ---- focus and movement --------------------------------------------------
local dirs = { h = "left", l = "right", k = "up", j = "down" }
for key, dir in pairs(dirs) do
    hl.bind(SUPER .. " + " .. key, hl.dsp.focus({ direction = dir }))
    hl.bind(SUPER .. " + SHIFT + " .. key, hl.dsp.window.move({ direction = dir }), { release = true })
end
local arrows = { left = "left", right = "right", up = "up", down = "down" }
for key, dir in pairs(arrows) do
    hl.bind(SUPER .. " + " .. key, hl.dsp.focus({ direction = dir }), { release = true })
    hl.bind(SUPER .. " + SHIFT + " .. key, hl.dsp.window.move({ direction = dir }), { release = true })
    hl.bind(SUPER .. " + ALT + " .. key,
        hl.dsp.window.resize(({ left  = { x = -20, y = 0, relative = true },
                                right = { x =  20, y = 0, relative = true },
                                up    = { x = 0, y = -20, relative = true },
                                down  = { x = 0, y =  20, relative = true } })[key]),
        { repeating = true })
end
hl.bind(SUPER .. " + CTRL + h",     ws("-1"),    { release = true })
hl.bind(SUPER .. " + CTRL + l",     ws("+1"),    { release = true })
hl.bind(SUPER .. " + CTRL + left",  ws("-1"),    { release = true })
hl.bind(SUPER .. " + CTRL + right", ws("+1"),    { release = true })
hl.bind(SUPER .. " + CTRL + k",     hl.dsp.focus({ monitor = "l" }),  { release = true })
hl.bind(SUPER .. " + CTRL + j",     hl.dsp.focus({ monitor = "r" }),  { release = true })
hl.bind(SUPER .. " + CTRL + up",    hl.dsp.focus({ monitor = "l" }),  { release = true })
hl.bind(SUPER .. " + CTRL + down",  hl.dsp.focus({ monitor = "r" }),  { release = true })
hl.bind(SUPER .. " + Tab", ws("previous"), { release = true })

-- ---- workspaces ----------------------------------------------------------
for i = 1, 10 do
    local key = (i == 10) and "0" or tostring(i)
    hl.bind(SUPER .. " + " .. key,           ws(i))
    hl.bind(SUPER .. " + SHIFT + " .. key,   tows(i))
end
hl.bind(SUPER .. " + S",         hl.dsp.workspace.toggle_special("magic"))
hl.bind(SUPER .. " + SHIFT + S", tows("special:magic"))
for i = 1, 12 do
    hl.bind(SUPER .. " + F" .. i,           hl.dsp.workspace.toggle_special("f" .. i))
    hl.bind(SUPER .. " + SHIFT + F" .. i,   tows("special:f" .. i))
end

-- ---- scrolling layout ----------------------------------------------------
-- SUPER+scroll walks the row of columns, which is the gesture the layout
-- exists for; workspace switching moves to SUPER+CTRL+scroll rather than
-- being lost.
hl.bind(SUPER .. " + mouse_down", hl.dsp.focus({ direction = "right" }))
hl.bind(SUPER .. " + mouse_up",   hl.dsp.focus({ direction = "left" }))
hl.bind(SUPER .. " + CTRL + mouse_down", ws("e+1"))
hl.bind(SUPER .. " + CTRL + mouse_up",   ws("e-1"))
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

-- ---- passthrough submap --------------------------------------------------
-- SUPER+Escape stops Hyprland acting on any bind, so a VM or a remote desktop
-- can have the whole keyboard, and the same chord gives it back. In Lua a
-- submap is a callback that receives its own bind table rather than a mode the
-- rest of the file falls into, so the binds inside cannot leak out by being
-- written after it - which is exactly what `submap = reset` existed to stop.
hl.bind(SUPER .. " + Escape", function()
    hl.dsp.exec_cmd('notify-send "Passthrough Mode"')
    hl.dispatch(hl.dsp.submap("Passthrough"))
end)

hl.define_submap("Passthrough", function()
    hl.bind(SUPER .. " + Escape", function()
        hl.dsp.exec_cmd('notify-send "Normal Mode"')
        hl.dispatch(hl.dsp.submap("reset"))
    end)
end)
