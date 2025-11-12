#!/usr/bin/env bash
set -euo pipefail

# ---- venv ----
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -d .venv311 ]]; then . .venv311/bin/activate
  elif [[ -d venv ]]; then . venv/bin/activate
  fi
fi
echo "== VENV =="
python -V
command -v python
command -v pip

echo "== Patch: loader + RNG =="

python - <<'PY'
from pathlib import Path
import re

# --- 1) Repair scenario_runner.load_config ---
sr = Path("dutchbay_v13/scenario_runner.py")
txt = sr.read_text(encoding="utf-8")

# Drop any existing load_config definitions
txt = re.sub(r"(?ms)^\s*def\s+load_config\s*\([^)]*\)\s*:[\s\S]*?(?=^\s*def\s|\Z)", "", txt)
# Normalise extra blank lines
txt = re.sub(r"\n{3,}", "\n\n", txt).rstrip() + "\n"

new_func = """
def load_config(path: str) -> dict:
    \"\"\"Resolve YAML config from: exact path -> repo-root/inputs -> packaged fallback.\"\"\"
    import os, yaml, importlib.resources as ir
    candidates = []
    if path:
        candidates.append(os.path.abspath(path))
        candidates.append(os.path.join(os.getcwd(), "inputs", os.path.basename(path)))
    else:
        candidates.append(os.path.join(os.getcwd(), "inputs", "full_model_variables_updated.yaml"))
    try:
        pkg = ir.files("dutchbay_v13").joinpath("inputs/full_model_variables_updated.yaml")
        candidates.append(str(pkg))
    except Exception:
        pass
    tried = []
    for c in candidates:
        if c and os.path.exists(c):
            with open(c, "r") as f:
                return yaml.safe_load(f)
        tried.append(c)
    raise FileNotFoundError(f"Config not found. Tried: {tried}")
""".strip() + "\n"

# Insert after the last import (or at top if none)
last_import = None
for m in re.finditer(r"^(?:from\s+\S+\s+import\s+\S+|import\s+\S+).*$", txt, re.M):
    last_import = m
if last_import:
    i = last_import.end()
    txt = txt[:i] + "\n\n" + new_func + txt[i:]
else:
    txt = new_func + "\n\n" + txt

sr.write_text(txt, encoding="utf-8")

# --- 2) Repair monte_carlo RNG + import ordering ---
mc = Path("dutchbay_v13/monte_carlo.py")
m = mc.read_text(encoding="utf-8")

# Ensure 'import random' right after future annotations (or at top)
if "import random" not in m:
    m = m.replace(
        "from __future__ import annotations",
        "from __future__ import annotations\nimport random",
        1
    )

# Remove stray "rng = Random()" lines
m = re.sub(r"^\s*rng\s*=\s*Random\(\).*?$", "", m, flags=re.M)

# Ensure a single 'rng = random.Random()' just after 'import random'
if "rng = random.Random()" not in m:
    m = re.sub(r"(import\s+random[^\n]*\n)", r"\1rng = random.Random()  # nosec B311\n", m, count=1)

# Guarantee scenario_runner import appears after rng is defined
m = re.sub(r"^\s*from\s+\.\s*scenario_runner\s+import\s+.*?$", "", m, flags=re.M)
m = re.sub(
    r"(rng = random\.Random\(\).*?\n)",
    r"\1from .scenario_runner import run_single_scenario, load_config\n",
    m,
    flags=re.S,
    count=1
)

# Replace any random.uniform calls with rng.uniform (non-crypto MC)
m = m.replace("random.uniform(", "rng.uniform(")

# Clean blank lines
m = re.sub(r"\n{3,}", "\n\n", m)

mc.write_text(m, encoding="utf-8")
print("✓ Patched: scenario_runner.load_config + monte_carlo RNG/imports")
PY

echo "== Ensure tests' config path =="
mkdir -p inputs
if [[ ! -f inputs/full_model_variables_updated.yaml ]] && [[ -f dutchbay_v13/inputs/full_model_variables_updated.yaml ]]; then
  cp -f dutchbay_v13/inputs/full_model_variables_updated.yaml inputs/
fi
ls -l inputs/full_model_variables_updated.yaml || true

echo "== Reinstall (editable) =="
python -m pip install -U pip wheel setuptools
pip install -e ".[dev,test]"

echo "== Lint/format/security =="
ruff check . --fix || true
black . || true
bandit -r dutchbay_v13 || true

echo "== Pytest =="
pytest -q
