# Real Chrome inside tmux: two views of the same browser

```
chrome                       # full, exact Xvfb desktop/window
chrome https://example.com   # open URL in that Chrome, then show full window
chrome --page example.com    # compact single-page graphics view
```

Full mode mirrors **the same Xvfb Chrome used by Remmina**, through its existing
shared VNC server. It shows Chrome's actual tabs, address bar, toolbar, extensions,
menus, side panels and dialogs. Mouse/keyboard input controls that same desktop;
Remmina and this view see each other's actions. No separate browser/profile is
created, and closing the viewer does not close Chrome. Other Xvfb windows, if
raised, also appear because this is the real shared desktop.

Full-mode controls are native Chrome controls: **Ctrl+L** address, **Ctrl+T** new
tab, **Ctrl+W** close tab, and normal mouse/scroll/typing. **Ctrl+Q** disconnects
this viewer and returns to the shell. Ctrl+C copies inside Chrome in full mode.
Terminal paste is forwarded as text. Use Vimium's normal page bindings when the
page has keyboard focus. Chrome's extension button and side panel are real UI.

`--page` keeps Casty's single-page view, with **Alt+L** address/search, **Alt+F**
hints, **Alt+Left/Right** history and **Ctrl+Q** (or Ctrl+C) quit. It creates a new
tab in the existing profile, without the desktop toolbar. Quitting leaves the tab
open and clears its viewport override. Both modes retain logins and extensions.
`chrome-desktop [URL]` remains the separate VNC launcher on Blackwall.

## Pane lifetime, scaling and controls

Graphics use Kitty Unicode placeholders (`U=1` virtual placements), not floating
screen overlays. They belong to tmux's pane cells: closing/hiding a pane removes
its display, switching back restores it, and moving/breaking it into another
window carries its image with it. Both modes rescale when the pane changes size.
The launcher watches the pane, supervises its own viewer/tunnel processes and
handles hangup/termination; Linux parent-death signalling also stops a child if
its launcher is killed. Shared Chrome is never stopped.

Browser controls start enabled in a browser pane. **Ctrl+A then Esc** toggles to
normal tmux controls; repeat it to return to browser controls. Chrome's Ctrl
shortcuts are forwarded in browser mode, including Ctrl+A select-all and native
tab/address controls. Ctrl+Q remains the viewer exit. Prefix/session key defaults
are saved and restored when focus leaves browser mode or the viewer exits.

Mouse input is temporarily allowed in a window containing a browser even if the
global tmux mouse option is off. Other windows retain their previous setting.
Per-window graphics leases support multiple browser panes; closing one does not
disable another's graphics. Pane movement transfers those leases. Only the
browser's hook index and key bindings are managed; existing plugin hooks remain.

Placeholder protocol and row/column diacritics follow Kitty's public specification:
https://sw.kovidgoyal.net/kitty/graphics-protocol/#unicode-placeholders
`placeholder-diacritics.json` contains the Unicode code points from Kitty's
rowcolumn-diacritics table. A compatible terminal must implement this feature.

## Terminal and remote use

Use Kitty or a terminal implementing Kitty graphics with Unicode placeholders, including on the
local end of SSH. A text-only terminal or the VNC desktop's Zutty cannot display
these pixels. Tmux passthrough is enabled only for the current window and restored
on exit; nested multiplexers need passthrough at every layer. Images have private
IDs and cleanup never deletes another pane's images. Pixel dimensions preserve
aspect ratio with letterboxing; mouse coordinates follow that mapping.

On Blackwall, connection.py wakes/maps/focuses existing Chrome and reads the VNC
password from its existing private file. Full mode uses loopback VNC :5900. Page
mode attaches to loopback CDP :9222. Neither port is newly exposed.

On Arch, run `~/.config/.dotfiles/blackwall/browser/pane/install.sh` after pulling
the rice repository. It installs both views, a private Python environment and the
pinned Casty runtime. The `chrome` launcher lives in ~/.local/bin. Source files are
tracked in the rice repository; Blackwall also keeps a deployed copy in
~/opt/cloud/browser/pane. Existing unrelated chrome launchers are backed up.

Without a local VNC password file, it uses SSH to Blackwall. The installer creates
~/.config/browser-pane/config.json only if absent, with:

```json
{"ssh_host":"scriptkid@13.140.155.113","ssh_identity":"~/.ssh/idiot-doll"}
```

Adjust these to your existing SSH setup, or use `chrome --ssh blackwall` /
`CHROME_SSH_HOST=blackwall chrome`. No password is stored in this config. Connection
information is obtained over SSH and kept in memory. Each view uses a temporary,
loopback-only SSH tunnel to VNC or CDP, closed on exit. No public VNC/CDP firewall
change is needed. Full/page modes display the Blackwall profile, not a new local
Chrome on Arch.

## Clipboard (full mode)

Copy on your own machine, paste in the browser pane. Before **Ctrl+V** (all encodings),
**Ctrl+Shift+V**, **Shift+Insert** and a **right-button press** the viewer pulls the client
clipboard and, only if it changed since the last push, writes it to Blackwall's `:99`
clipboard (text as `UTF8_STRING`, any image as `image/png`; 32 MiB cap, 1.5 s budget,
failures just forward the key). Kitty's bracketed paste (Ctrl+Shift+V text) is written to the
`:99` clipboard and sent as Ctrl+V instead of being typed. Text copied inside Chrome goes
to the client through `tmux set-buffer -w` (OSC 52; direct OSC 52 outside tmux), 1 MiB cap,
without echoing back what was just pushed, and only within 3 s of a copy key (Ctrl+C/X,
Ctrl+Insert) or a click, so a page writing the clipboard on its own cannot reach yours. Page mode is unchanged.

- Arch viewer (Wayland): source is local `wl-paste`; sink is `ssh <host> clipboard.py write MIME`
  on Blackwall (same ssh_host/ssh_identity as the launcher, passed as `CHROME_CLIP_SINK`).
- Blackwall viewer: sink is local `xclip` on `DISPLAY=:99`; source is
  `ssh archlinux clipboard.py read`, used only while Arch holds an established ssh connection
  to Blackwall. Change the host with `clipboard_source` in `~/.config/browser-pane/config.json`
  (`""` disables). Both ssh paths use a viewer-owned ControlMaster in `~/.cache/browser-pane/`.
- Needs `xclip` on Blackwall and `wl-paste` on Arch. Test: `python3 test-clipboard.py`.

## Implementation and verification

Full mode uses rfb.py (password-authenticated shared RFB 3.8, raw/zlib rectangles),
Pillow and Kitty inline PNG rendering. Actual VNC keys and pointer events operate
Chrome's native UI. The installer uses existing Pillow/cryptography when present,
otherwise installs them in a private venv. It does not repair unrelated dpkg state.

Page mode pins Casty 1.3.3 source at
f72ecdd21bc8795fe673dce0d27f49a281273e78, applies shared-chrome.patch and installs
the locked WebSocket dependency with npm lifecycle scripts disabled. Runtime:
~/.local/share/browser-pane/casty. The installer fingerprints the patch/data/lock;
rerunning upgrades an older runtime and retains a backup. Upstream https://github.com/sanohiro/casty
(MIT; see CASTY-LICENSE). The patch skips browser downloads/launches, UA/stealth
scripts, microphone/camera hooks and global download changes. Shared exit never
sends Browser.close or kills a browser process.

Run `python3 browser/pane/test-full.py` and `python3 browser/pane/test-pane.py`
on Blackwall. They use fixture tabs/windows, a disposable tmux socket and a PTY.
Tests verify real PNG delivery through tmux, mouse/typing, navigation, resizing,
return-to-shell, passthrough/viewport restoration and preserved original tabs and
browser/server PIDs. Full mode additionally tests native Chrome Ctrl+T/Ctrl+W
and Ctrl+L; its extracted image includes the actual Chrome toolbar. Only task-owned
fixtures are closed. Python websocket-client is needed for these tests.


Additional regressions: `test-close.py` closes actual full/page panes and verifies
owned processes exit, surviving browser panes keep working, and settings restore.
`test-lifetime.py` uses real Kitty on Xvfb and pixel counts to verify hiding,
returning, resizing, moving to a window and closing a pane. Set
`KITTY_TEST_BINARY` to the test Kitty executable. Blackwall verification used an
extracted Ubuntu Kitty 0.32.2 package and its libraries in /tmp; no system package
installation or dpkg repair was performed. Both full/page rendering passed.

Arch live installation and real SSH/VNC/CDP integration checks passed, including
full/page controls, movement, pane closure and settings restoration. Pixel checks
also passed in Arch Kitty 0.49.1 with tmux 3.7c. Frames use synchronized updates
to preserve complete Unicode placeholder marks during redraws. Both modes were
verified on Blackwall Kitty 0.32.2 as well. For a private test display, set
`BROWSER_TEST_DISPLAY` in addition to `KITTY_TEST_BINARY`.

Frame updates retain both alternating image buffers until reuse instead of deleting
the displayed frame before tmux redraws its text cells. This prevents a blank gap
on slower terminal connections. Exit cleans up both private image IDs. The real
Kitty lifetime test also samples continuous redraws in both modes for blank frames.

When you switch to another pane or window, the browser view holds its last frame
and pauses terminal graphics output. Chrome itself continues running. Returning
to the browser pane resumes rendering. This prevents background passthrough
commands from repeatedly disturbing tmux redraws in the active pane. Focus is
checked against attached clients, so a pane active in another client still runs.
The Kitty regression uses Ctrl+A h/l and verifies no graphics are transmitted
while a sibling pane is active, then verifies rendering resumes on return.
