#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/scenario_runner.py"
[ -f "$F" ] || { echo "Missing $F"; exit 1; }

if ! grep -q 'base = f"scenario_' "$F"; then
  if grep -qE 'name\s*=\s*p\.stem' "$F"; then
    # insert right after name = p.stem
    sed -i '' -E '/name\s*=\s*p\.stem/a\
\        base = f"scenario_{name or '\''000'\''}"
' "$F"
    echo "✓ inserted base after name=p.stem"
  else
    # fallback: insert before first _annual_ write
    sed -i '' -E '0,/_annual_/{
/_annual_/i\
\        base = f"scenario_{name or '\''000'\''}"
}' "$F"
    echo "✓ inserted base before first _annual_ use"
  fi
else
  echo "↷ base assignment already present; no change"
fi

# Normalize any direct literals to use {base} (harmless if none exist)
sed -i '' -E "s/f\"scenario_\\{name\\}_annual_/f\"{base}_annual_/g" "$F" || true
sed -i '' -E "s/f\"scenario_\\{name\\}_results_/f\"{base}_results_/g" "$F" || true
sed -i '' -E "s/(['\"])scenario_000_results_/\\1{base}_results_/g" "$F" || true
sed -i '' -E "s/(['\"])scenario_000_annual_/\\1{base}_annual_/g" "$F" || true
