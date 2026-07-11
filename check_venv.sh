#!/usr/bin/env bash
#
# check_venv.sh – sanity and workflow helper for the DutchBay_EPC_Model virtualenv
#
# Responsibilities:
#   - Confirm we are in a DutchBay_EPC_Model checkout.
#   - Confirm .venv exists (shared project venv).
#   - Optionally activate .venv and run dutchbay_bootstrap.py.
#   - Always print the R21 standard local workflow for humans.
#
# Usage:
#   ./check_venv.sh
#   ./check_venv.sh --run-bootstrap
#
# Environment:
#   RUN_BOOTSTRAP=1   # same as passing --run-bootstrap
#
# Notes (Go-with-the-Flow v3.0):
#   - Repo root is the directory containing this script (not its parent).
#   - Fails fast on missing repo markers or virtualenv.
#   - Bootstrap step is optional and clearly logged.

set -euo pipefail

# ---------------------------------------------------------------------------
# Minimal colouring helpers (no-op when not on a TTY)
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
  DB_BOLD=$'\033[1m'
  DB_RED=$'\033[31m'
  DB_GREEN=$'\033[32m'
  DB_YELLOW=$'\033[33m'
  DB_BLUE=$'\033[34m'
  DB_RESET=$'\033[0m'
else
  DB_BOLD=''
  DB_RED=''
  DB_GREEN=''
  DB_YELLOW=''
  DB_BLUE=''
  DB_RESET=''
fi

info()  { printf '%b>>%b %s\n'        "${DB_BLUE}"  "${DB_RESET}" "$*"; }
ok()    { printf '%b✅%b %s\n'        "${DB_GREEN}" "${DB_RESET}" "$*"; }
warn()  { printf '%b⚠️ %b %s\n'       "${DB_YELLOW}" "${DB_RESET}" "$*"; }
err()   { printf '%b❌%b %s\n'        "${DB_RED}"   "${DB_RESET}" "$*"; }
fatal() { err "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

print_usage() {
  cat << 'USAGE'
Usage: ./check_venv.sh [OPTIONS]

Options:
  --run-bootstrap   Activate .venv and run dutchbay_bootstrap.py
  --no-bootstrap    Explicitly skip bootstrap (overrides RUN_BOOTSTRAP=1)
  -h, --help        Show this help and exit

Environment:
  RUN_BOOTSTRAP=1   Same as passing --run-bootstrap.

This script is intended to be run from anywhere; it always resolves the repo
root as the directory containing check_venv.sh and performs the standard R21
sanity checks before development or CI work.
USAGE
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

RUN_BOOTSTRAP_FLAG=0

# Env var still respected
if [[ "${RUN_BOOTSTRAP:-0}" == "1" ]]; then
  RUN_BOOTSTRAP_FLAG=1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-bootstrap)
      RUN_BOOTSTRAP_FLAG=1
      shift
      ;;
    --no-bootstrap)
      RUN_BOOTSTRAP_FLAG=0
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      fatal "Unknown argument: $1 (use --help for usage)"
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Locate repo root (directory containing this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

cd "${REPO_ROOT}"

info "check_venv.sh – repo root: ${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Basic repo sanity
# ---------------------------------------------------------------------------

if [[ ! -f "pyproject.toml" ]] || [[ ! -f "VERSION" ]]; then
  err "This does not look like the DutchBay_EPC_Model repo root."
  echo "    Expected pyproject.toml and VERSION under: ${REPO_ROOT}"
  echo "    (Hint: run this script from the cloned DutchBay_EPC_Model folder.)"
  exit 1
fi

ok "Repo markers found (pyproject.toml, VERSION)."

# ---------------------------------------------------------------------------
# Virtualenv presence
# ---------------------------------------------------------------------------

VENV_DIR="${REPO_ROOT}/.venv"
VENV_PY="${VENV_DIR}/bin/python"

if [[ -d "${VENV_DIR}" ]]; then
  ok "Found .venv in repo root."
else
  err ".venv not found in repo root."
  echo "   Please create it first, for example:"
  echo "     cd ${REPO_ROOT}"
  echo "     ./setup_venv.sh"
  echo "   or:"
  echo "     python3 -m venv .venv"
  echo "     source .venv/bin/activate"
  echo "     pip install --upgrade pip"
  echo "     pip install -r requirements.txt && pip install -e \".[dev]\""
  echo ""
  echo "R21 – Standard local workflow will not run cleanly without .venv."
  exit 1
fi

if [[ ! -x "${VENV_PY}" ]]; then
  warn "Python executable not found at ${VENV_PY}."
  warn "Virtualenv may be incomplete; consider re-running setup_venv.sh."
else
  ok "Virtualenv Python detected at ${VENV_PY}."
fi

# ---------------------------------------------------------------------------
# Optional bootstrap run
# ---------------------------------------------------------------------------

if [[ "${RUN_BOOTSTRAP_FLAG}" -eq 1 ]]; then
  echo ""
  info "[R21] Activating .venv and running dutchbay_bootstrap.py ..."

  # shellcheck disable=SC1091
  # (project-local venv activation)
  # We guard this so a missing activate script gives a clear error.
  if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
    fatal "activate script not found at ${VENV_DIR}/bin/activate – venv is broken."
  fi

  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"

  python -V || warn "Unable to report python version from venv."

  if [[ -f "dutchbay_bootstrap.py" ]]; then
    python dutchbay_bootstrap.py
  else
    warn "dutchbay_bootstrap.py not found in ${REPO_ROOT} (unexpected)."
  fi
else
  echo ""
  info "Skipping automatic bootstrap (no --run-bootstrap / RUN_BOOTSTRAP=1)."
fi

# ---------------------------------------------------------------------------
# Always print the R21 workflow for humans
# ---------------------------------------------------------------------------

echo ""
echo "R21 – Standard local workflow (Go-with-the-Flow v3.0):"
echo ""
echo "  cd ${REPO_ROOT}"
echo "  source .venv/bin/activate"
echo "  python dutchbay_bootstrap.py"
echo "  pytest"
echo ""
echo "Use this sequence before making changes or pushing to CI."
echo ""
ok "check_venv.sh completed."
# EOF
