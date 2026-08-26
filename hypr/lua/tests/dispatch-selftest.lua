-- Runs every dispatcher this config uses, inside a real compositor, and
-- writes what each one actually did to $BW_SELFTEST_OUT.
--
-- Why this exists: `--verify-config` reports `config ok` for a call that is
-- valid Lua and does the wrong thing. `hl.dsp.exec_raw("workspace 3")` parses,
-- loads, raises nothing, and tries to run a program called `workspace`. 22
-- binds were dead that way. Parsing is not running.
--
-- Run it nested, so it cannot touch the live session:
--
--   WAYLAND_DISPLAY=wayland-1 Hyprland --config hypr/lua/tests/dispatch-selftest.lua
--   cat /tmp/bw-dispatch-selftest.txt
--
-- With WAYLAND_DISPLAY set, Hyprland starts as a window with its own socket.
-- Kill it by PID when done; `hyprctl dispatch exit` does not always take.
--
-- Do NOT run this through --verify-config: hl.timer crashes it (the verifier
-- has no event loop to run the timer and dumps core). That is also a reason
-- not to put a timer in the real config - it would make the safety check
-- unusable. Boot it, as above.
--
-- Focus-direction binds cannot be tested this way. A nested compositor whose
-- own window is not focused on the host has no focused window of its own -
-- hl.get_window() returns nil, and dispatching focus({window = w}) does not
-- change that. So every direction, including "banana", reports no change.
-- Testing those needs the nested window focused on the host first
-- (`hyprctl dispatch focuswindow`), which is a host-side step this file
-- cannot do for you.
--
-- Limits worth knowing: with no windows open, window-scoped dispatchers report
-- "accepted" whether or not their arguments are meaningful - `direction =
-- "banana"` builds and dispatches without complaint. So "accepted" here means
-- the call shape was tolerated, NOT that the argument is valid. Only the lines
-- that show a state change are positive evidence.

local OUT = os.getenv("BW_SELFTEST_OUT") or "/tmp/bw-dispatch-selftest.txt"

hl.config({ misc = { disable_hyprland_logo = true, disable_splash_rendering = true } })

local function say(s)
    local f = io.open(OUT, "a")
    if f then f:write(s .. "\n"); f:close() end
end

local function ws() return tostring(hl.get_active_workspace()) end
local function special() return tostring(hl.get_active_special_workspace()) end

local function try(label, make, observe)
    local before = observe and observe() or ""
    local ok, err = pcall(function() hl.dispatch(make()) end)
    if not ok then
        say(string.format("%-40s ERROR: %s", label, tostring(err)))
    elseif observe then
        local after = observe()
        say(string.format("%-40s %s -> %s%s", label, before, after,
            before == after and "   (no change)" or "   MOVED"))
    else
        say(string.format("%-40s accepted", label))
    end
end

hl.timer(function()
    say("-- workspace switching --")
    try('focus{workspace="3"}',        function() return hl.dsp.focus({ workspace = "3" }) end, ws)
    try('focus{workspace="+1"}',       function() return hl.dsp.focus({ workspace = "+1" }) end, ws)
    try('focus{workspace="-1"}',       function() return hl.dsp.focus({ workspace = "-1" }) end, ws)
    try('focus{workspace="previous"}', function() return hl.dsp.focus({ workspace = "previous" }) end, ws)

    say("-- special workspaces --")
    try('workspace.toggle_special("magic")',
        function() return hl.dsp.workspace.toggle_special("magic") end, special)

    say("-- shapes only (no window open: see the note at the top) --")
    try('focus{direction="left"}',      function() return hl.dsp.focus({ direction = "left" }) end)
    try('focus{monitor="l"}',           function() return hl.dsp.focus({ monitor = "l" }) end)
    try("group.toggle()",               function() return hl.dsp.group.toggle() end)
    try("group.next()",                 function() return hl.dsp.group.next() end)
    try('group.lock{action="toggle"}',  function() return hl.dsp.group.lock({ action = "toggle" }) end)
    try('window.move{workspace="3"}',   function() return hl.dsp.window.move({ workspace = "3" }) end)
    try("window.resize{x,y,relative}",  function() return hl.dsp.window.resize({ x = 20, y = 0, relative = true }) end)
    try('window.fullscreen{action,mode}',
        function() return hl.dsp.window.fullscreen({ action = "toggle", mode = "fullscreen" }) end)
    try('layout("colresize next")',     function() return hl.dsp.layout("colresize next") end)
    say("DONE")
end, { timeout = 2500, type = "oneshot" })
