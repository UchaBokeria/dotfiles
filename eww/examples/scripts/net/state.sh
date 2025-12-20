#!/usr/bin/env bash
set -euo pipefail

iface="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}' || true)"

if [[ -z "${iface}" ]]; then
  # fallback: first connected device from nmcli
  iface="$(nmcli -t -f DEVICE,STATE device status | awk -F: '$2=="connected"{print $1; exit}' || true)"
fi

type="$(nmcli -t -f DEVICE,TYPE device status | awk -F: -v d="$iface" '$1==d{print $2}' || true)"
state="$(nmcli -t -f DEVICE,STATE device status | awk -F: -v d="$iface" '$1==d{print $2}' || true)"

ip4="$(ip -4 -o addr show dev "$iface" 2>/dev/null | awk '{print $4}' | head -n1 | cut -d/ -f1 || true)"

ssid=""
if [[ "$type" == "wifi" ]]; then
  ssid="$(nmcli -t -f IN-USE,SSID dev wifi 2>/dev/null | awk -F: '$1=="*"{print $2; exit}' || true)"
fi

printf '{"iface":"%s","type":"%s","state":"%s","ssid":"%s","ip":"%s"}\n' \
  "${iface:-}" "${type:-}" "${state:-}" "${ssid:-}" "${ip4:-}"
