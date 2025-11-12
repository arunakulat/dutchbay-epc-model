#!/usr/bin/env bash
set -euo pipefail
f="dutchbay_v13/scenario_runner.py"

cp -f "$f" "${f}.bak.$(date +%s)"

# Strip any previous shim blocks (both old marker styles)
awk '
  /# --- COMPAT SHIM ---/ {skip=1}
  skip==1 && /# --- END COMPAT SHIM ---/ {skip=0; next}
  skip!=1 {print}
' "$f" > "${f}.tmp1"

awk '
  /# --- COMPAT: unwrap nested containers and ignore legacy group keys/ {skip=1}
  skip==1 && /# --- END COMPAT ---/ {skip=0; next}
  skip!=1 {print}
' "${f}.tmp1" > "${f}.clean"

# Append safe, idempotent wrapper
cat >> "${f}.clean" <<'PY'
# --- COMPAT: unwrap nested containers and ignore legacy group keys (safe, idempotent) ---
import os as _os

_IGNORE_KEYS = {s.strip().casefold() for s in _os.getenv(
    "DB13_IGNORE_KEYS",
    "technical,finance,financial,notes,metadata,name,description,id"
).split(",") if s.strip()}

def _db13_strip_ignored(d):
    if isinstance(d, dict):
        return {k: v for k, v in d.items()
                if not isinstance(k, str) or k.casefold() not in _IGNORE_KEYS}
    return d

try:
    _db13_orig_validate = _validate_params_dict  # type: ignore[name-defined]
    # Guard against double-wrapping
    if not getattr(_db13_orig_validate, "__db13_wrapped__", False):
        def _db13_wrapped_validate(params, where=None):  # type: ignore[no-redef]
            if isinstance(params, dict):
                for _k in ("parameters", "override", "overrides"):
                    if _k in params and isinstance(params[_k], dict):
                        params = params[_k]
                        break
                params = _db13_strip_ignored(params)
            return _db13_orig_validate(params, where=where)
        _db13_wrapped_validate.__db13_wrapped__ = True  # type: ignore[attr-defined]
        _validate_params_dict = _db13_wrapped_validate  # type: ignore[assignment]
except NameError:
    # Base validator not present here; nothing to wrap
    pass
# --- END COMPAT ---
PY

mv "${f}.clean" "$f"
echo "✓ Repaired wrapper in $f"
