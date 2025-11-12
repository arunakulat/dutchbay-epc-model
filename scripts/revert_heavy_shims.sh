#!/usr/bin/env bash
set -Eeuo pipefail

strip_shims () {
  local f="$1"
  [[ -f "$f" ]] || { echo "• Skip (missing): $f"; return; }
  # Remove lines between the explicit shim markers
  if grep -q "=== BEGIN TEST SHIM" "$f"; then
    tmp="$(mktemp)"
    awk '
      /=== BEGIN TEST SHIM/ {inshim=1; next}
      /=== END TEST SHIM/   {inshim=0; next}
      !inshim {print}
    ' "$f" > "$tmp"
    mv "$tmp" "$f"
    echo "✓ Shims stripped from $f"
  else
    echo "• No shims found in $f"
  fi
}

strip_shims dutchbay_v13/monte_carlo.py
strip_shims dutchbay_v13/sensitivity.py
strip_shims dutchbay_v13/optimization.py

echo "✓ Shim removal complete. Consider running tests and committing."

