#!/usr/bin/env bash
set -euo pipefail

# ——— 0) ensure we're in the repo root ———
cd "$(dirname "$0")/.."

echo "== Python/venv =="
python -V
command -v python
command -v pip

# ——— 1) editable install with dev/test (quote the extras!) ———
python -m pip install --upgrade pip wheel setuptools
pip install -e '.[dev,test]'

# ——— 2) quick import sanity ———
python - <<'PY'
import importlib
m = importlib.import_module('dutchbay_v13')
print("import ok:", bool(m))
PY

# ——— 3) quality gates (run one-by-one; never crash the shell) ———
echo "== Quality: format/lint/type/security/test =="
pip install -q black ruff flake8 mypy bandit pytest coverage || true

echo "-- black --"
black --check . || true

echo "-- ruff --"
ruff check . || true

echo "-- flake8 --"
flake8 . || true

echo "-- mypy --"
mypy dutchbay_v13 || true

echo "-- bandit --"
[ -d dutchbay_v13 ] && bandit -r dutchbay_v13 || true

echo "-- pytest --"
[ -d tests ] && pytest -q || true

echo "✅ sanity complete"
