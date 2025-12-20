#!/usr/bin/env bash
set -euo pipefail

# Always control the SAME eww instance & config-dir as your daemon.
EWW_DIR="/home/scriptkid/.config/eww"
EWW="eww -c $EWW_DIR"

WIN="${1:?window name required}"
VAR="${2:?state var required}"

if $EWW active-windows | awk '{print $1}' | grep -qx "$WIN"; then
  $EWW close "$WIN" || true
  $EWW update "${VAR}=false" || true
else
  $EWW open "$WIN"
  $EWW update "${VAR}=true" || true
fi

