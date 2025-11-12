#!/usr/bin/env bash
set -euo pipefail

# 1) Find repo root and stamp
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
STAMP="$(date +'%Y%m%d_%H%M')"
OUT="/tmp/DutchBay_Code_${STAMP}.zip"

# 2) Stage area (we’ll assemble everything here, then zip once)
STAGE="$(mktemp -d)"
PREFIX="DutchBay_EPC_Model"               # zip root folder name
DEST="${STAGE}/${PREFIX}"
mkdir -p "$DEST"

# 3) Export tracked files into DEST using tar (so we can merge extras cleanly)
git archive --format=tar HEAD | tar -x -C "$DEST"

# 4) Add untracked-but-important extras if they exist (copy into the same tree)
add_extra() {
  local rel="$1"
  if [ -e "$rel" ]; then
    echo "• adding extra: $rel"
    # Ensure directory exists in DEST, then copy
    if [ -d "$rel" ]; then
      mkdir -p "${DEST}/$(dirname "$rel")"
      rsync -a --delete "$rel" "${DEST}/$(dirname "$rel")/../" >/dev/null 2>&1 || true
    else
      mkdir -p "${DEST}/$(dirname "$rel")"
      cp -f "$rel" "${DEST}/$rel"
    fi
  fi
}

# Common extras you’ve used recently
add_extra "full_model_variables_updated.yaml"
add_extra "inputs/overrides"
add_extra "dutchbay_v13/inputs/scenarios"
add_extra "dutchbay_v13/inputs/schema/financing_terms.schema.yaml"

# 5) Final zip (exclude heavy junk if it somehow slipped in)
cd "$STAGE"
zip -qr "$OUT" "$PREFIX" -x \
  "*/.git/*" "*/.venv*/*" "*/venv/*" "*/__pycache__/*" "*/.pytest_cache/*" \
  "*/.mypy_cache/*" "*/.DS_Store" "*/dist/*" "*/build/*" "*.egg-info/*" "*/outputs/*"

# 6) Preview + path
echo "— Contents —"
zipinfo -1 "$OUT" | sed 's/^/  /'
echo "→ Zip ready: $OUT"

