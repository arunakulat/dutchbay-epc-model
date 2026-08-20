#!/usr/bin/env bash
# Validate the governed environment and optionally run the project bootstrap.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

# shellcheck disable=SC1091
. "$REPO_ROOT/scripts/development_environment.sh"

RUN_BOOTSTRAP_FLAG=${RUN_BOOTSTRAP:-0}

usage() {
  echo "Usage: ./check_venv.sh [--run-bootstrap|--no-bootstrap]"
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --run-bootstrap) RUN_BOOTSTRAP_FLAG=1 ;;
    --no-bootstrap) RUN_BOOTSTRAP_FLAG=0 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
  shift
done

[ -f "$REPO_ROOT/pyproject.toml" ] \
  && [ -f "$REPO_ROOT/go_with_the_flow_rules_v3_0_clean.csv" ] \
  || fail "Required DutchBay checkout markers are missing under $REPO_ROOT."

PYTHON_CMD=$(dutchbay_find_python312) || fail \
  "A working Python 3.12 interpreter was not found."
VENV_DIR=$(dutchbay_resolve_venv "$REPO_ROOT" "$PYTHON_CMD") || fail \
  "Unable to resolve DUTCHBAY_VENV from config/development_environment.json."
[ -x "$VENV_DIR/bin/python" ] || fail \
  "Selected environment is missing or incomplete: $VENV_DIR. Run ./setup_venv.sh."

dutchbay_validate_venv "$REPO_ROOT" "$VENV_DIR" || fail \
  "Selected environment failed the governed health contract: $VENV_DIR"

if [ "$RUN_BOOTSTRAP_FLAG" = "1" ]; then
  dutchbay_activate_checkout "$REPO_ROOT" "$VENV_DIR"
  "$VENV_DIR/bin/python" "$REPO_ROOT/dutchbay_bootstrap.py"
fi

echo "Environment validation PASS: $VENV_DIR"
echo "Active checkout: $REPO_ROOT"
echo "Use: source scripts/venv_up.sh"
