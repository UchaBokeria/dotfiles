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

## Terminal and remote use

Use Kitty, Ghostty or a terminal implementing Kitty graphics, including on the
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

## Implementation and verification

Full mode uses rfb.py (password-authenticated shared RFB 3.8, raw/zlib rectangles),
Pillow and Kitty inline PNG rendering. Actual VNC keys and pointer events operate
Chrome's native UI. The installer uses existing Pillow/cryptography when present,
otherwise installs them in a private venv. It does not repair unrelated dpkg state.

Page mode pins Casty 1.3.3 source at
f72ecdd21bc8795fe673dce0d27f49a281273e78, applies shared-chrome.patch and installs
the locked WebSocket dependency with npm lifecycle scripts disabled. Runtime:
~/.local/share/browser-pane/casty. Upstream https://github.com/sanohiro/casty
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
