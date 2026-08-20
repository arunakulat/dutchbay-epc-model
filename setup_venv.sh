#!/usr/bin/env bash
# Create or validate the governed DutchBay Python 3.12 environment.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS="$PROJECT_ROOT/requirements.txt"

# shellcheck disable=SC1091
. "$PROJECT_ROOT/scripts/development_environment.sh"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "DutchBay EPC Model - governed environment setup"
echo "Active checkout: $PROJECT_ROOT"

PYTHON_CMD=$(dutchbay_find_python312) || fail \
  "A working Python 3.12 interpreter was not found. Install python@3.12 first."
VENV_DIR=$(dutchbay_resolve_venv "$PROJECT_ROOT" "$PYTHON_CMD") || fail \
  "Unable to resolve DUTCHBAY_VENV from config/development_environment.json."
VENV_PYTHON="$VENV_DIR/bin/python"

echo "Selected environment: $VENV_DIR"

if [ -e "$VENV_DIR" ]; then
  if [ -L "$VENV_DIR" ] || [ ! -d "$VENV_DIR" ]; then
    fail "Selected environment must be a real directory, not a symlink: $VENV_DIR"
  fi
  if [ ! -x "$VENV_PYTHON" ]; then
    fail "Existing environment is incomplete; executable missing: $VENV_PYTHON. Move or remove $VENV_DIR, then rerun ./setup_venv.sh."
  fi
  if ! "$VENV_PYTHON" \
    -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' \
    >/dev/null 2>&1; then
    VENV_VERSION=$("$VENV_PYTHON" --version 2>&1 || echo unknown)
    fail "Existing environment uses $VENV_VERSION; Python 3.12 is required. Move or remove $VENV_DIR, then rerun ./setup_venv.sh."
  fi

  echo "Validating existing environment without modifying it..."
  dutchbay_validate_venv "$PROJECT_ROOT" "$VENV_DIR" || fail \
    "Existing environment failed the governed health contract. Move or repair only $VENV_DIR, then rerun ./setup_venv.sh."
else
  [ -f "$REQUIREMENTS" ] || fail "Pinned dependency lock not found: $REQUIREMENTS"
  echo "Creating Python 3.12 environment at the exact selected path..."
  mkdir -p "$(dirname "$VENV_DIR")"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  "$VENV_PYTHON" -m pip install --quiet --upgrade pip setuptools wheel
  "$VENV_PYTHON" -m pip install --quiet -r "$REQUIREMENTS"
  echo "Validating newly created environment..."
  dutchbay_validate_venv "$PROJECT_ROOT" "$VENV_DIR" || fail \
    "New environment failed validation; inspect and remove only $VENV_DIR before retrying."
fi

echo "Environment ready: $VENV_DIR"
echo "Activate it for this checkout with:"
echo "  cd '$PROJECT_ROOT'"
echo "  source scripts/venv_up.sh"
