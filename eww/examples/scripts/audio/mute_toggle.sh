#!/usr/bin/env bash
set -euo pipefail

# wpctl set-mute … toggle is documented. :contentReference[oaicite:13]{index=13}
wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
