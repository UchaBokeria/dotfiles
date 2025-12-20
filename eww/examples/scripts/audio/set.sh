#!/usr/bin/env bash
set -euo pipefail

# Accept either:
#   0.50
#   0.50/1.5  (we ignore the /1.5 part, it’s only for readable UI)
raw="${1:?value required}"
val="${raw%%/*}"

# wpctl set-volume supports limiting with -l; 1.0 == 100%. :contentReference[oaicite:12]{index=12}
wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ "$val"
