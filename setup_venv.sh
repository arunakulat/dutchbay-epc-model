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

# GWTF R10 and GOV-02 both describe the pre-commit hook set as LOCAL enforcement that
# runs automatically on commit - R10 says "hooks run automatically on git commit. Failed
# hooks prevent commit", and GOV-02 relies on `no-commit-to-branch` blocking a commit on
# main BEFORE the confusing push-time ruleset rejection. Hooks live in .git/hooks, which
# git does not track, so a fresh clone - or any .git predating this step - has none and
# both claims are silently false. Installing is idempotent, so doing it on every setup
# costs nothing and keeps the claims true. Observed 2026-09-13: this repository had no
# pre-commit hook installed at all, so neither rule's local enforcement existed.
if [ -n "${DUTCHBAY_SKIP_HOOKS:-}" ]; then
  echo "Skipping pre-commit hook installation (DUTCHBAY_SKIP_HOOKS is set)."
elif ! git -C "$PROJECT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not a git checkout; skipping pre-commit hook installation."
else
  echo "Installing pre-commit hooks (GWTF R10, GOV-02)..."
  if ! (cd "$PROJECT_ROOT" && "$VENV_PYTHON" -m pre_commit install); then
    echo "WARNING: pre-commit hook installation FAILED." >&2
    echo "         R10 and GOV-02 local enforcement is NOT active in this checkout." >&2
    echo "         Repair with: $VENV_PYTHON -m pre_commit install" >&2
  fi
fi

echo "Environment ready: $VENV_DIR"
echo "Activate it for this checkout with:"
echo "  cd '$PROJECT_ROOT'"
echo "  source scripts/venv_up.sh"
