#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REV=f72ecdd21bc8795fe673dce0d27f49a281273e78
TARGET="$HOME/.local/share/browser-pane/casty"
PATCH_HASH=$(python3 -c 'import hashlib,sys; from pathlib import Path; h=hashlib.sha256(sys.argv[1].encode()); [h.update(Path(x).read_bytes()) for x in sys.argv[2:]]; print(h.hexdigest())' "$REV" "$HERE/shared-chrome.patch" "$HERE/placeholder-diacritics.json" "$HERE/package-lock.casty.json")
if [[ -f "$TARGET/.browser-pane-patch-sha256" && "$(cat "$TARGET/.browser-pane-patch-sha256")" == "$PATCH_HASH" ]]; then
  echo "Page runtime already current." >&2
else
  mkdir -p "$(dirname "$TARGET")"
  STAGING=$(mktemp -d "$(dirname "$TARGET")/.install.XXXXXXXX")
  trap 'rm -rf "$STAGING"' EXIT
  git clone -q https://github.com/sanohiro/casty.git "$STAGING/casty"
  git -C "$STAGING/casty" checkout -q --detach "$REV"
  git -C "$STAGING/casty" apply "$HERE/shared-chrome.patch"
  cp "$HERE/placeholder-diacritics.json" "$STAGING/casty/"
  cp "$HERE/package-lock.casty.json" "$STAGING/casty/package-lock.json"
  npm --prefix "$STAGING/casty" ci --omit=dev --ignore-scripts --no-audit --no-fund
  printf '%s\n' "$PATCH_HASH" > "$STAGING/casty/.browser-pane-patch-sha256"
  if [[ -e "$TARGET" ]]; then mv "$TARGET" "$TARGET.before-update.$(date +%s).$$"; fi
  mv "$STAGING/casty" "$TARGET"
fi
mkdir -p "$HOME/.local/bin"
if [[ ! -x "$HOME/.local/share/browser-pane/venv/bin/python" ]]; then
  python3 -m venv --system-site-packages "$HOME/.local/share/browser-pane/venv"
fi
if ! "$HOME/.local/share/browser-pane/venv/bin/python" -c 'from PIL import Image; import cryptography' 2>/dev/null; then
  "$HOME/.local/share/browser-pane/venv/bin/python" -m pip install 'Pillow>=10,<13' 'cryptography>=41,<49'
fi
if [[ -f "$HERE/../browser.sh" ]]; then
  ln -sfn "$HERE/../browser.sh" "$HOME/.local/bin/chrome-desktop"
fi
if [[ ! -f "$HOME/.config/.claude-chrome-vncpw.txt" && ! -f "$HOME/.config/browser-pane/config.json" ]]; then
  mkdir -p "$HOME/.config/browser-pane"
  printf '%s\n' '{"ssh_host":"scriptkid@13.140.155.113","ssh_identity":"~/.ssh/idiot-doll"}' > "$HOME/.config/browser-pane/config.json"
fi
if [[ -e "$HOME/.local/bin/chrome" || -L "$HOME/.local/bin/chrome" ]]; then
  if [[ "$(readlink -f "$HOME/.local/bin/chrome")" != "$HERE/chrome" ]]; then
    mv "$HOME/.local/bin/chrome" "$HOME/.local/bin/chrome.before-browser-pane.$(date +%Y%m%d%H%M%S)"
  fi
fi
ln -sfn "$HERE/chrome" "$HOME/.local/bin/chrome"
printf '%s\n' 'Installed: chrome [URL] renders your shared Chrome inside this terminal; --page keeps single-page mode.'
