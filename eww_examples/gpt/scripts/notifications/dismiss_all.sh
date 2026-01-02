#!/usr/bin/env bash
set -euo pipefail

# makoctl dismiss-all is documented in makoctl(1).
makoctl dismiss-all || true
