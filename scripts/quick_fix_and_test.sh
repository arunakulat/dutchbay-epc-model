#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-$PWD}"
cd "$REPO"

echo "== Venv =="
if [ -n "${VIRTUAL_ENV:-}" ]; then
  echo "Using VENV: $VIRTUAL_ENV"
elif [ -d .venv311 ]; then
  . .venv311/bin/activate
elif [ -d venv ]; then
  . venv/bin/activate
fi
python -V; command -v python; command -v pip

python - <<'PY'
from pathlib import Path
import re

# 1) Repair scenario_runner.load_config (dedupe + robust search order)
p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")
# drop any prior load_config defs
s = re.sub(r'\n\s*def\s+load_config\([^)]*\):(?s).*?(?=\n\S|\Z)', '\n', s, count=10)

new_fn = """
def load_config(path: str) -> dict:
    \"\"\"Try the provided path, repo-root/inputs, then packaged fallback.\"\"\"
    import os, yaml, importlib.resources as ir
    cands = [
        os.path.abspath(path),
        os.path.join(os.getcwd(), "inputs", os.path.basename(path)),
    ]
    try:
        cands.append(str(ir.files("dutchbay_v13").joinpath("inputs/full_model_variables_updated.yaml")))
    except Exception:
        pass
    for c in cands:
        if c and os.path.exists(c):
            with open(c, "r") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError(f"Config not found. Tried: {cands}")
""".strip()

# append the new def at end (safe regardless of import layout)
if "def load_config(" not in s:
    s = s.rstrip() + "\n\n" + new_fn + "\n"
p.write_text(s, encoding="utf-8")

# 2) Repair Monte Carlo RNG (import Random, define rng, stop using random.uniform)
mc = Path("dutchbay_v13/monte_carlo.py")
t = mc.read_text(encoding="utf-8")
if "from random import Random" not in t:
    t = t.replace(
        "from __future__ import annotations",
        "from __future__ import annotations\nfrom random import Random  # nosec B311 non-crypto RNG",
    )
if "rng = Random()" not in t:
    t = t.replace("\nfrom .scenario_runner", "\nrng = Random()\nfrom .scenario_runner", 1)
t = t.replace("random.uniform(", "rng.uniform(")
mc.write_text(t, encoding="utf-8")

print("✓ Patched: scenario_runner.load_config and monte_carlo RNG")
PY

# 3) ensure tests’ expected config file exists at repo-root/inputs
mkdir -p inputs
if [ -f dutchbay_v13/inputs/full_model_variables_updated.yaml ]; then
  cp -f dutchbay_v13/inputs/full_model_variables_updated.yaml inputs/full_model_variables_updated.yaml
fi
ls -l inputs/full_model_variables_updated.yaml || true

# 4) reinstall editable with extras (into the active venv)
pip install -e '.[dev,test]'

# 5) style + security + tests (verbose fallback if anything fails)
ruff check . --fix || true
black . || true
bandit -r dutchbay_v13 || true
pytest -q || { echo; echo "—— Verbose rerun on CLI/Scenario ——"; pytest -k "cli or scenario" -vv; exit 1; }
