#!/usr/bin/env bash
set -euo pipefail

echo "== Using venv =="
if [ -n "${VIRTUAL_ENV:-}" ]; then
  echo "VENV: $VIRTUAL_ENV"
elif [ -d .venv311 ]; then
  . .venv311/bin/activate
elif [ -d venv ]; then
  . venv/bin/activate
fi
python -V; command -v python; command -v pip

python - <<'PY'
from pathlib import Path

# 1) Append a robust load_config() (no regex deletions, no global imports)
sr = Path("dutchbay_v13/scenario_runner.py")
s = sr.read_text(encoding="utf-8")

marker = "# ROBUST_LOAD_CONFIG_V1"
snippet = f"""
{marker}
def load_config(path: str) -> dict:
    \"\"\"Resolve config by trying: explicit path -> repo-root/inputs -> packaged fallback.\"\"\"
    import os, yaml, importlib.resources as ir
    candidates = []
    if path:
        candidates.append(os.path.abspath(path))
    if path:
        candidates.append(os.path.join(os.getcwd(), "inputs", os.path.basename(path)))
    try:
        pkg_fallback = ir.files("dutchbay_v13").joinpath("inputs/full_model_variables_updated.yaml")
        candidates.append(str(pkg_fallback))
    except Exception:
        pass
    tried = []
    for c in candidates:
        if c and os.path.exists(c):
            with open(c, "r") as f:
                return yaml.safe_load(f)
        tried.append(c)
    raise FileNotFoundError(f"Config not found. Tried: {tried}")
"""

if marker not in s:
    # append at EOF; Python will prefer the last definition
    s = s.rstrip() + "\n\n" + snippet + "\n"
    sr.write_text(s, encoding="utf-8")
    print("✓ Appended robust load_config()")
else:
    print("• load_config() patch already present")

# 2) Patch Monte Carlo RNG: import Random, create rng, replace random.uniform
mc = Path("dutchbay_v13/monte_carlo.py")
m = mc.read_text(encoding="utf-8")

changed = False
if "from random import Random" not in m:
    m = m.replace(
        "from __future__ import annotations",
        "from __future__ import annotations\nfrom random import Random  # nosec B311 (non-crypto RNG)",
        1
    )
    changed = True

if "rng = Random()" not in m:
    # place rng after the future import and before local imports
    if "from .scenario_runner" in m:
        m = m.replace("from .scenario_runner", "rng = Random()\nfrom .scenario_runner", 1)
    else:
        m = m + "\n\nrng = Random()\n"
    changed = True

if "random.uniform(" in m:
    m = m.replace("random.uniform(", "rng.uniform(")
    changed = True

if changed:
    mc.write_text(m, encoding="utf-8")
    print("✓ Patched Monte Carlo RNG")
else:
    print("• Monte Carlo RNG already patched")
PY

# 3) Ensure tests’ expected config path exists at repo root
mkdir -p inputs
if [ -f dutchbay_v13/inputs/full_model_variables_updated.yaml ]; then
  cp -f dutchbay_v13/inputs/full_model_variables_updated.yaml inputs/full_model_variables_updated.yaml
fi
ls -l inputs/full_model_variables_updated.yaml || true

# 4) Reinstall package with dev/test extras
python -m pip install -U pip wheel setuptools
pip install -e '.[dev,test]'

# 5) Lint/format/security/tests
ruff check . --fix || true
black . || true
bandit -r dutchbay_v13 || true

echo
echo "== Pytest (full) =="
pytest -q || {
  echo; echo "== Pytest (focused: cli|scenario, verbose) =="
  pytest -k "cli or scenario" -vv
  exit 1
}
