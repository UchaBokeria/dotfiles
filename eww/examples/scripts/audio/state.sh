#!/usr/bin/env bash
set -euo pipefail

out="$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || true)"

vol="$(awk '{print $2}' <<<"$out")"
if [[ -z "${vol}" ]]; then
  echo '{"vol":0.0,"pct":0,"muted":false}'
  exit 0
fi

muted=false
if grep -qi "MUTED" <<<"$out"; then
  muted=true
fi

pct="$(awk -v v="$vol" 'BEGIN { printf("%d", (v*100)+0.5) }')"
printf '{"vol":%s,"pct":%s,"muted":%s}\n' "$vol" "$pct" "$muted"
