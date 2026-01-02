#!/usr/bin/env bash
set -euo pipefail

ssid_b64="${1:?ssid_b64 required}"
ssid="$(printf '%s' "$ssid_b64" | base64 -d)"

# Use --ask so secrets are prompted securely when needed. :contentReference[oaicite:16]{index=16}
nmcli --ask device wifi connect "$ssid"
