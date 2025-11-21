#!/usr/bin/env bash
set -euo pipefail

# Portable timestamp for macOS/BSD + Linux
ts="$(date +"%Y-%m-%dT%H:%M:%S%z" || echo "unknown-time")"
rev="$(git rev-parse --short HEAD || echo "no-git")"

echo "=== DutchBay v14 Regression Smoke @ ${ts} (rev: ${rev}) ==="

python -m pytest
