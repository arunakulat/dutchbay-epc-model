#!/bin/bash

set -e  # Stop on any error, show trace

# Activate the Python virtual environment (edit this if your venv name or location differs)
source .venv311/bin/activate

# Discover all .py files under the current directory (project root by default)
PY_FILES=$(find . -type f -name '*.py')

echo "=============================="
echo "Running automated code quality and testing checks..."
echo "=============================="

# 1. Static type checking: mypy
echo ">> Running mypy (static typing)..."
mypy $PY_FILES

# 2. Linting: flake8 and pylint
echo ">> Running flake8 (PEP8/lint checks)..."
flake8 $PY_FILES

echo ">> Running pylint (code quality/linting)... [Most severe shown, for all .py modules]"
pylint $PY_FILES --exit-zero | grep -E 'missing|error|fatal|convention|refactor|warning|score'

# 3. Security scan
echo ">> Running bandit (security scan)..."
bandit -r . -c

# 4. Code formatting (check-only)
echo ">> Checking black (code style)..."
black --check --diff $PY_FILES

echo ">> Checking isort (import order)..."
isort --check-only $PY_FILES

# 5. Test execution with coverage for all tests (pytest, unittest, hypothesis)
echo ">> Running all tests (pytest with coverage)..."
coverage run -m pytest
coverage report -m
coverage html

# 6. Optionally, check Django or FastAPI app (if present)
if [ -f manage.py ]; then
  echo ">> Running Django checks..."
  python manage.py check
fi

if grep -q 'FastAPI' $PY_FILES; then
  echo ">> [FastAPI detected: run uvicorn main:app or test with httpx/pytest as appropriate]"
fi

echo "=============================="
echo "All code quality, test, type, style, and security checks passed!"
echo "=============================="
