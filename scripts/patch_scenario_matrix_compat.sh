#!/usr/bin/env bash
set -euo pipefail
f="dutchbay_v13/scenario_runner.py"

# backup
cp -f "$f" "${f}.bak.$(date +%s)"

# strip any old block between our markers
awk '
  /# --- COMPAT: unwrap nested containers and ignore legacy group keys ---/ {skip=1}
  /# --- END COMPAT ---/ {skip=0; next}
  skip!=1 {print}
' "$f" > "${f}.tmp"

# append corrected block
cat >> "${f}.tmp" <<'PY'
# --- COMPAT: unwrap nested containers and ignore legacy group keys ---
import os as _os

_IGNORE_KEYS = {s.strip().casefold() for s in _os.getenv(
    "DB13_IGNORE_KEYS",
    "technical,finance,financial,notes,metadata,name,description,id"
).split(",") if s.strip()}

def _db13_strip_ignored(d):
    return {k: v for k, v in d.items() if k.casefold() not in _IGNORE_KEYS} if isinstance(d, dict) else d

try:
    _db13_orig_validate = _validate_params_dict  # type: ignore[name-defined]
    def _validate_params_dict(params, where=None):  # type: ignore[no-redef]
        # unwrap common containers from scenario-matrix style
        if isinstance(params, dict):
            for _k in ("parameters", "override", "overrides"):
                if _k in params and isinstance(params[_k], dict):
                    params = params[_k]
                    break
            params = _db13_strip_ignored(params)
        return _db13_orig_validate(params, where=where)  # type: ignore[misc]
except NameError:
    # base validator not present here; nothing to wrap
    pass
# --- END COMPAT ---
PY

mv "${f}.tmp" "$f"
echo "✓ Patched $f"
