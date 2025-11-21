#!/usr/bin/env bash
set -euo pipefail

echo "Cleaning up fx blocks to canonical mapping..."

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

  echo "  [clean] $f"
  python - "$f" << 'PYEOF'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
lines = text.splitlines(keepends=True)

out = []
i = 0
n = len(lines)

while i < n:
    line = lines[i]
    if line.lstrip().startswith("fx:") and line.startswith("fx:"):
        # Replace entire fx block with canonical mapping
        out.append("fx:\n")
        out.append("  start_lkr_per_usd: 300.0\n")
        out.append("  annual_depr: 0.03\n")
        i += 1
        # Skip original indented fx body (lines starting with two spaces)
        while i < n and lines[i].startswith("  "):
            i += 1
        continue

    out.append(line)
    i += 1

path.write_text("".join(out))
PYEOF

done

echo "Done. Verify with: git diff"
