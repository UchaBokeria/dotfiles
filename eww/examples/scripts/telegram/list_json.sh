#!/usr/bin/env bash
set -euo pipefail

command -v jq >/dev/null 2>&1 || { echo "[]"; exit 0; }

~/.config/eww/scripts/notifications/list_json.sh \
| jq -c '
  map(select(
    (.app|ascii_downcase|test("telegram")) or
    (.desktop_entry|ascii_downcase|test("telegram"))
  ))
  | .[0:8]
'
