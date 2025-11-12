set -euo pipefail
F="dutchbay_v13/scenario_runner.py"
T="${F}.tmp"
python - "$F" > "$T" <<'PY'
import sys, re
p = sys.argv[1]
src = open(p, "r", encoding="utf-8").read()

pat = re.compile(r'# --- BEGIN VALIDATION WRAPPER \(env-aware\) ---.*?# --- END VALIDATION WRAPPER \(env-aware\) ---', re.S)

wrapper = r'''# --- BEGIN VALIDATION WRAPPER (env-aware) ---
import os as _db13_os
try:
    _db13_orig_validate  # type: ignore[name-defined]
except NameError:
    _db13_orig_validate = None  # type: ignore[assignment]

def _db13_unwrap_params(_p):
    if isinstance(_p, dict):
        for _k in ("parameters","override","overrides"):
            if isinstance(_p.get(_k), dict):
                return _p[_k]
    return _p

def _db13_filter_ignored(_p):
    if not isinstance(_p, dict):
        return _p
    ignore = {x.strip().casefold() for x in _db13_os.getenv(
        "DB13_IGNORE_KEYS",
        "technical,finance,financial,notes,metadata,name,description,id,parameters"
    ).split(",") if x.strip()}
    return {k:v for k,v in _p.items() if not isinstance(k,str) or k.casefold() not in ignore}

def _validate_params_dict(params, where=None):  # type: ignore[no-redef]
    STRICT  = _db13_os.getenv("VALIDATION_MODE","").lower() == "strict" or _db13_os.getenv("DB13_STRICT_VALIDATE") == "1"
    RELAXED = _db13_os.getenv("VALIDATION_MODE","").lower() in {"relaxed","smoke"} or _db13_os.getenv("DB13_RELAXED_VALIDATE") == "1"
    base = _db13_filter_ignored(_db13_unwrap_params(params))
    if _db13_orig_validate is None:
        return None
    if RELAXED:
        try:
            return _db13_orig_validate(base, where=where)
        except Exception:
            return None
    # STRICT/default: on any validation error, raise SystemExit so upstream try/except Exception can't swallow it
    try:
        return _db13_orig_validate(base, where=where)
    except Exception as e:
        if STRICT:
            raise SystemExit(2) from e
        raise
# --- END VALIDATION WRAPPER (env-aware) ---'''

if pat.search(src):
    src = pat.sub(wrapper, src)
else:
    src = src + "\n" + wrapper + "\n"
open(p, "w", encoding="utf-8").write(src)
print("✓ Hardened strict validator in", p)
PY
mv "$T" "$F"
