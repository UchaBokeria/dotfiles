#!/usr/bin/env bash
set -euo pipefail

MODE="do-not-disturb"

current="$(makoctl mode 2>/dev/null || true)"
if grep -q "$MODE" <<<"$current"; then
  makoctl mode -r "$MODE"
else
  makoctl mode -a "$MODE"
fi
