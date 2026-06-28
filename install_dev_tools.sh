#!/bin/bash
# Install the full dev/CI toolchain from pyproject's [dev] extra — the single
# abstract source of truth (ruff / black / isort / flake8 / pylint, mypy + the
# type stubs, bandit + pip-audit, pytest + xdist / cov / html / timeout,
# hypothesis, httpx, libcst, build).
#
# Replaces the old "pip install <ad-hoc list>; pip freeze > requirements_dev.txt"
# flow, which polluted the dev surface with non-dependencies (e.g. Django) and
# drifted from pyproject. Run inside your activated virtualenv.
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

echo "✓ Dev toolchain installed from pyproject [dev]."
