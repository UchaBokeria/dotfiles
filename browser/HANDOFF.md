## Goal
2026-11-08, Codex: real graphical Chrome in tmux on Blackwall and Arch, tied to pane lifetime, resizing/movement, native browser controls and scoped mouse. Preserve shared Chrome and live tmux work.

## State
Installed on both hosts. Sources: Blackwall ~/opt/cloud/browser/pane; Arch rice ~/.config/.dotfiles/blackwall/browser/pane (nuc). chrome / --full mirrors the exact existing Xvfb desktop as Remmina, including Chrome tabs/extensions. --page retains the single-page graphical view in the same profile. Arch connects using private SSH tunnels; no new profile/public ports or committed credentials.

Pane supervisor stops only owned viewer/tunnel children on HUP/TERM/closure, including Linux parent-death handling. Per-server/window leases share and restore passthrough and follow window moves. Kitty virtual placements use pane-owned Unicode cells; synchronized updates preserve complete diacritics on newer tmux/Kitty. Only owned image IDs are removed. Frames periodically refresh after hidden-window changes. Flicker follow-up: keep both alternating image buffers resident until reuse; deleting the previous frame during upload can outrun tmux placeholder redraw. Cleanup removes both owned IDs. Continuous 10fps pixel sampling now checks for blank frames in full/page modes on both hosts.

Default browser mode forwards native Ctrl keys. Ctrl+A Esc toggles browser/tmux controls; Ctrl+Q exits the view. Namespaced hooks restore prior prefix/key-table/paste settings and keep mouse enabled only in displayed browser windows, respecting previous/global settings outside them. Multiple concurrent views are supported. Installer fingerprints pinned Casty source/patch/data/lock, upgrades stale runtime with backup and uses private Python deps.

Verification passed on both hosts: actual shared Chrome full/page input, native tab/URL controls, mouse with global mouse off/on, resize/move, owned-process cleanup, concurrent-view survival, final settings restoration and original tabs/Chrome/tmux preservation. Real Kitty pixel checks passed hide/return/resize/break-pane/close on Blackwall Kitty 0.32.2 and Arch Kitty 0.49.1 + tmux 3.7c. Only task-owned fixtures were closed.

Focus-switch follow-up: both renderers now query attached tmux clients (cached 100ms) and emit no frames unless their pane is active for a client. The last image stays visible in an inactive split; returning forces a full-mode refresh. Page frame callbacks also skip URL-bar redraws when inactive. This avoids passthrough repeatedly invalidating the active sibling tty. The regression failed on the old page runtime (13 extra frames while inactive), then passed both modes on Blackwall and Arch using actual Ctrl+A h/l keyboard navigation, trace assertions for zero background graphics, and pixel checks for a retained image.

## Next
No feature work pending. Open a fresh chrome view to use the changes; existing loaded viewers keep their old code. Re-run browser/pane/install.sh after changing the pinned patch/data/lock. See browser/pane/README.md for commands and regression tests.

## Gotchas
Requires terminal Kitty graphics with Unicode placeholders; nested tmux layers need passthrough. Floating placements caused the original orphaned-image bug. Batch graphics + placeholder cells with CSI ?2026 h/l; incremental combining-character redraws produced blank images on Arch. Run GUI tests sequentially (shared desktop focus). Full view controls the same desktop as Remmina. Never restart shared Chrome/tmux to deploy. Preserve unrelated dirty infra/rice files. Unrelated dpkg interruption was left untouched; test Kitty was extracted under /tmp. SSH shell on Arch is fish: feed multiline scripts through ssh archlinux bash.
