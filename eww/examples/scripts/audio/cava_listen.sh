#!/usr/bin/env bash
set -euo pipefail

BARS="${1:-20}"
EWW_BIN="${EWW_BIN:-eww}"

zeros() {
  local i
  printf "["
  for ((i=0; i<BARS; i++)); do
    printf "0"
    [[ $i -lt $((BARS-1)) ]] && printf ","
  done
  printf "]\n"
}

visible() {
  "$EWW_BIN" get volume_visible 2>/dev/null | tr -d '\n' || true
}

run_cava() {
  # CAVA raw output supports ascii + delimiters. :contentReference[oaicite:14]{index=14}
  cava -p <(cat <<EOF
[general]
bars = ${BARS}
framerate = 60

[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 100
bar_delimiter = 32
frame_delimiter = 10
EOF
)
}

# Keep process light: only run cava while the volume popup is visible
while true; do
  if [[ "$(visible)" != "true" ]]; then
    zeros
    while [[ "$(visible)" != "true" ]]; do sleep 0.4; done
  fi

  run_cava | while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if [[ "$(visible)" != "true" ]]; then
      break
    fi
    # line is space-separated ints 0..100
    # Convert to JSON array
    printf "[%s]\n" "$(awk 'BEGIN{ORS="";} {for(i=1;i<=NF;i++){printf "%s%s",$i,(i==NF?"":",")}}' <<<"$line")"
  done
done
