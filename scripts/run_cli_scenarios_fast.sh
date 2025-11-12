#!/usr/bin/env bash
set -euo pipefail
SRC="${BASH_SOURCE[0]:-$0}"
ROOT="$(cd "$(dirname "$SRC")/.." && pwd)"
cd "$ROOT"

OUT="_out_cli_fast"
mkdir -p "$OUT"

python -m dutchbay_v13 scenarios \
  --scenarios inputs \
  --outputs-dir "$OUT" \
  --format both --save-annual

echo "→ Artifacts:"
ls -lh "$OUT" | sed 's/^/   /'

