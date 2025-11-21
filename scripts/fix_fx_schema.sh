#!/usr/bin/env bash
set -euo pipefail

echo "Normalizing top-level fx blocks to structured mapping..."

FILES=(
  "scenarios/example_a.yaml"
  "scenarios/example_a_old.yaml"
  "scenarios/dutchbay_lendercase_2025Q4.yaml"
  "scenarios/edge_extreme_stress.yaml"
)

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "  [skip] $f (not found)"
    continue
  fi

  echo "  [fix] $f"
  python - "$f" << 'PYEOF'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

needle = "fx:\n"
replacement = (
    "fx:\n"
    "  start_lkr_per_usd: 375.0\n"
    "  annual_depr: 0.03\n"
)

if needle not in text:
    # nothing to do
    sys.exit(0)

# replace only the first occurrence to avoid surprises
path.write_text(text.replace(needle, replacement, 1))
PYEOF

done

echo "Done. Review diffs and adjust FX numbers if needed."
