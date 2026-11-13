## Goal
2026-11-13, Claude Code (took over permanently from Codex): clipboard for the graphical Chrome tmux pane (`chrome`, browser/pane) — text and images copied on the client must paste in Chrome.

## State
Done and verified on Blackwall and Arch, committed to ~/opt/cloud (197cc73) and the rice repo (browser/pane). New browser/pane/clipboard.py; desktop.py/rfb.py/chrome hooked in.
- Ctrl+V, Ctrl+Shift+V (CSI-u), Shift+Insert, right-click in a full-mode browser pane first pull the client clipboard (image/* as PNG, else UTF-8 text) into Xvfb :99's clipboard (xclip, now installed on Blackwall), then Chrome pastes. Unchanged client content is never re-pushed, so a copy made inside Chrome wins.
- Viewer on Blackwall: source = `ssh archlinux clipboard.py read` (only when Arch holds an ssh connection to Blackwall; config.json `clipboard_source`, "" disables). Viewer on Arch: wl-paste locally, sink over ssh to Blackwall. Both use viewer-owned ControlMaster sockets in ~/.cache/browser-pane.
- Bracketed (kitty ctrl+shift+v) paste goes via clipboard + Ctrl+V instead of typing.
- Chrome copy (text) -> x11vnc ServerCutText -> `tmux set-buffer -w` (OSC 52) -> client clipboard.
- Verified: test-clipboard.py (6 PASS both hosts); real Arch->:99 sync 0.24 s, Blackwall pulling Arch 0.53 s; image sink byte-identical. Not live-tested inside an open kitty pane by hand.

Earlier tmux picker/workspace work: unchanged, see Git history (2026-11-10 entry).

## Next
Owner: Ctrl+Q any open `chrome` view and reopen to load it. Page mode (`--page`, casty) has no clipboard sync yet. Chrome -> client images not supported.

## Gotchas
Blackwall ~/.config/tmux is not Git; canonical copy is Arch ~/.config/.dotfiles/blackwall/tmux. Blackwall deployed browser copy is ~/opt/cloud/browser/pane (own git); keep both in sync. Arch login shell is fish: use scripts, not bash heredocs, over ssh. Never restart live tmux/Chrome/x11vnc. Sonata tiers are unrouted in plain sessions here (model_not_found / "no harness routes"); sonnet-high was used.
