#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# config.load_config
if ! grep -q "def load_config\s*(" "$root/dutchbay_v13/config.py" 2>/dev/null; then
  cat >> "$root/dutchbay_v13/config.py" <<'PY'

# --- BEGIN AUTO-SHIM ---
def load_config(path_or_dict):
    """Very small loader that accepts a dict or YAML path."""
    if isinstance(path_or_dict, dict):
        return dict(path_or_dict)
    try:
        from pathlib import Path
        import yaml  # optional; if missing, use a naive parser
        p = Path(path_or_dict)
        with p.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # ultra-naive key: value loader
        data = {}
        with open(path_or_dict, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip()
        return data
# --- END AUTO-SHIM ---
PY
fi

# validate.validate_params
if ! grep -q "def validate_params\s*(" "$root/dutchbay_v13/validate.py" 2>/dev/null; then
  cat >> "$root/dutchbay_v13/validate.py" <<'PY'

# --- BEGIN AUTO-SHIM ---
def validate_params(d):
    """Minimal parameter validator: only known tariff keys allowed."""
    if not isinstance(d, dict):
        raise TypeError("params must be a dict")
    allowed = {"tariff_lkr_per_kwh", "debt", "mode", "name"}
    for k in d:
        if k not in allowed:
            raise ValueError(f"Unknown parameter '{k}'")
    return True
# --- END AUTO-SHIM ---
PY
fi
echo "✓ Minimal core APIs ensured."

