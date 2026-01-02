#!/usr/bin/env bash
set -euo pipefail

iface="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}' || true)"
if [[ -z "${iface}" ]]; then
  echo '{"rx":"0 KB/s","tx":"0 KB/s"}'
  exit 0
fi

rx1="$(cat "/sys/class/net/$iface/statistics/rx_bytes" 2>/dev/null || echo 0)"
tx1="$(cat "/sys/class/net/$iface/statistics/tx_bytes" 2>/dev/null || echo 0)"
sleep 1
rx2="$(cat "/sys/class/net/$iface/statistics/rx_bytes" 2>/dev/null || echo 0)"
tx2="$(cat "/sys/class/net/$iface/statistics/tx_bytes" 2>/dev/null || echo 0)"

drx=$((rx2-rx1))
dtx=$((tx2-tx1))

fmt() {
  local b="$1"
  if (( b > 1024*1024 )); then
    awk -v v="$b" 'BEGIN{printf "%.1f MB/s", v/1024/1024}'
  elif (( b > 1024 )); then
    awk -v v="$b" 'BEGIN{printf "%.0f KB/s", v/1024}'
  else
    printf "%d B/s" "$b"
  fi
}

printf '{"rx":"%s","tx":"%s"}\n' "$(fmt "$drx")" "$(fmt "$dtx")"
