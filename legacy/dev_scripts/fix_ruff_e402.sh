#!/usr/bin/env bash
set -euo pipefail

FILES=(
"analytics/evaluation_v14.py"
"analytics/sensitivity_v14.py"
)

for f in "${FILES[@]}"; do
if [[ ! -f "$f" ]]; then
continue
fi

if grep -q "ruff: noqa: E402" "$f"; then
continue
fi

if grep -q "^from **future** import annotations" "$f"; then
sed -i '' $'1,/^from **future** import annotations/{/^from **future** import annotations/a\

# ruff: noqa: E402  # imports intentionally allowed after other statements

}' "$f"
else
sed -i '' $'1i\

# ruff: noqa: E402  # imports intentionally allowed after other statements

' "$f"
fi
done
