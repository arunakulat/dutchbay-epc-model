#!/usr/bin/env bash
set -euo pipefail

TARGET="dutchbay_v13/finance/debt.py"

# Only append the shim if it's not present
if ! grep -q "def create_default_debt_structure" "$TARGET"; then
  cat >> "$TARGET" <<'PY'

# --- Shim added for core.py import compatibility ---
def create_default_debt_structure(params: dict | None = None) -> dict:
    """Return a minimal default debt structure dict.
    Keeps compatibility with core.py without changing logic tested elsewhere.
    """
    p = (params or {}).get("debt", {}) if isinstance(params, dict) else {}
    return {
        "debt_ratio": p.get("debt_ratio", 0.70),
        "tenor_years": p.get("tenor_years", 12),
        "grace_years": p.get("grace_years", 1),
    }
PY
  echo "✓ Added create_default_debt_structure shim to $TARGET"
else
  echo "= Shim already present in $TARGET"
fi