#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Ensure package layout =="
# Make sure the real package exists
test -f dutchbay_v13/__init__.py || {
  echo "from .config import __all__  # minimal marker" > dutchbay_v13/__init__.py
}

echo "== Write/patch pyproject.toml to pin discovery =="
# This forces setuptools to ONLY package dutchbay_v13 and exposes the CLI.
cat > pyproject.toml <<'TOML'
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dutchbay_v13"
version = "13.1.0"
requires-python = ">=3.10"
description = "DutchBay finance model v13"
readme = "README.md"
authors = [{name="DutchBay"}]
dependencies = [
  "numpy>=1.26",
  "pandas>=2.0",
  "numpy-financial>=1.0",
  "matplotlib>=3.8",
  "reportlab>=4.1",
  "pydantic>=2",
  "PyYAML>=6",
]

[project.optional-dependencies]
dev  = ["black","ruff","flake8","mypy","bandit"]
test = ["pytest","coverage"]

[tool.setuptools]
# Explicit list avoids auto-discovery of 'inputs' at repo root
packages = ["dutchbay_v13"]

[tool.setuptools.package-data]
# If you later move inputs under the package (dutchbay_v13/inputs),
# these globs will include them in wheels.
dutchbay_v13 = [
  "inputs/**/*.yaml", "inputs/**/*.yml",
  "inputs/**/*.json", "inputs/**/*.csv", "inputs/**/*.jsonl",
]

[project.scripts]
dutchbay = "dutchbay_v13.cli:main"
TOML

git add pyproject.toml dutchbay_v13/__init__.py 2>/dev/null || true
git commit -m "build: pin setuptools to package only dutchbay_v13; add CLI entry" || true

echo "== Bootstrap venv =="
# Prefer existing venv; do NOT create anew (you already have one active)
python -V
command -v python
command -v pip

echo "== Editable install with dev/test (quote extras) =="
python -m pip install --upgrade pip wheel setuptools
# Quote extras so zsh/bash don't glob them
pip install -e '.[dev,test]'

echo "== Smoke import & CLI =="
python - <<'PY'
import importlib, sys
m = importlib.import_module('dutchbay_v13')
print("import ok:", bool(m))
print("module file:", getattr(m, '__file__', None))
PY

# CLI help shouldn't crash; fine if it prints usage and exits 0/2
set +e
dutchbay --help >/dev/null 2>&1
echo "CLI help exit code: $?"
set -e

echo "== Optional quality gates (non-fatal) =="
pip install -q black ruff flake8 mypy bandit pytest coverage || true
black --check . || true
ruff check . || true
flake8 . || true
mypy dutchbay_v13 || true
[ -d dutchbay_v13 ] && bandit -r dutchbay_v13 || true
[ -d tests ] && pytest -q || true

echo "✅ Done. Packaging fixed and editable install complete."
