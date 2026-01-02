#!/usr/bin/env bash
set -euo pipefail

command -v jq >/dev/null 2>&1 || { echo '{"count":0,"dnd":false}'; exit 0; }

count="$(~/.config/eww/scripts/notifications/list_json.sh | jq 'length' 2>/dev/null || echo 0)"

dnd=false
modes="$(makoctl mode 2>/dev/null || true)"
if grep -q "do-not-disturb" <<<"$modes"; then
  dnd=true
fi

printf '{"count":%s,"dnd":%s}\n' "$count" "$dnd"

