#!/bin/bash
# Install the full dev/CI toolchain from pyproject's [dev] extra — the single
# abstract source of truth (ruff / black / isort, mypy + the type stubs, bandit +
# pip-audit, pytest + xdist / cov / html / timeout, hypothesis, httpx, libcst,
# build). flake8 + pylint were retired in the #610 lint-stack consolidation (ruff
# subsumes flake8; a scoped pylint pass is not viable on this codebase).
#
# Replaces the old "pip install <ad-hoc list>; pip freeze > requirements_dev.txt"
# flow, which polluted the dev surface with non-dependencies (e.g. Django) and
# drifted from pyproject. Run inside your activated virtualenv.
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

echo "✓ Dev toolchain installed from pyproject [dev]."
