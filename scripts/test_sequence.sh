#!/usr/bin/env bash
set -euo pipefail
mods=(irr debt cashflow metrics scenario cli optimize sensitivity)
for m in "${mods[@]}"; do
  echo "=== Testing $m ==="
  if ! bash scripts/test_one_module.sh "$m"; then
    echo "✗ $m failed. Fix and re-run."; exit 1
  fi
done
echo "✓ All selected modules passed."