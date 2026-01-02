#!/usr/bin/env bash
set -euo pipefail

state="$(nmcli -t -f WIFI general status | awk -F: '{print $2}' || true)"
if [[ "$state" == "enabled" ]]; then
  nmcli radio wifi off
else
  nmcli radio wifi on
fi
