#!/usr/bin/env bash
#
# check_venv.sh – sanity check for the DutchBay_EPC_Model virtualenv
#
# Responsibilities:
#   - Confirm we are in a DutchBay_EPC_Model checkout.
#   - Confirm .venv311 exists (shared project venv).
#   - Optionally activate .venv311 and run dutchbay_bootstrap.py.
#   - Always print the R21 workflow for humans.
#
# Usage:
#   ./check_venv.sh
#   ./check_venv.sh --run-bootstrap
#
# You can also drive behaviour via:
#   RUN_BOOTSTRAP=1 ./check_venv.sh

set -euo pipefail  # safer bash: exit on error, unset var, fail on pipe errors [web:12][web:15]

# ---------------------------------------------------------------------------
# Locate repo root (directory containing this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo ">> check_venv.sh – repo root: ${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Basic repo sanity
# ---------------------------------------------------------------------------

if [[ ! -f "pyproject.toml" ]] || [[ ! -f "pytest.ini" ]]; then
  echo "❌ This does not look like the DutchBay_EPC_Model repo root."
  echo "    Expected pyproject.toml and pytest.ini under: ${REPO_ROOT}"
  exit 1
fi

# ---------------------------------------------------------------------------
# Virtualenv presence
# ---------------------------------------------------------------------------

VENV_DIR="${REPO_ROOT}/.venv311"

if [[ -d "${VENV_DIR}" ]]; then
  echo "✅ Found .venv311 in repo root."
else
  echo "❌ .venv311 not found in repo root."
  echo "   Please create it first, e.g.:"
  echo "     cd ${REPO_ROOT}"
  echo "     ./setup_venv.sh"
  echo "   or:"
  echo "     python3 -m venv .venv311"
  echo "     source .venv311/bin/activate"
  echo "     pip install --upgrade pip"
  echo "     pip install -r requirements_dev.txt"
  echo ""
  echo "R21 – Standard local workflow will not run cleanly without .venv311."
  exit 1
fi

# ---------------------------------------------------------------------------
# Optional bootstrap run
# ---------------------------------------------------------------------------

RUN_BOOTSTRAP_FLAG=0

# Allow CLI flag and/or env var
if [[ "${RUN_BOOTSTRAP:-0}" == "1" ]]; then
  RUN_BOOTSTRAP_FLAG=1
fi

if [[ "${1:-}" == "--run-bootstrap" ]]; then
  RUN_BOOTSTRAP_FLAG=1
fi

if [[ "${RUN_BOOTSTRAP_FLAG}" -eq 1 ]]; then
  echo ""
  echo ">> [R21] Activating .venv311 and running dutchbay_bootstrap.py ..."
  # shellcheck disable=SC1091  # local, project-specific venv activate [web:17][web:30]
  source "${VENV_DIR}/bin/activate"

  python -V || true
  if [[ -f "dutchbay_bootstrap.py" ]]; then
    python dutchbay_bootstrap.py
  else
    echo "⚠️ dutchbay_bootstrap.py not found in ${REPO_ROOT} (unexpected)."
  fi
else
  echo ""
  echo ">> Skipping automatic bootstrap run (no --run-bootstrap / RUN_BOOTSTRAP=1)."
fi

# ---------------------------------------------------------------------------
# Always print the R21 workflow for humans
# ---------------------------------------------------------------------------

echo ""
echo "R21 – Standard local workflow (Go-with-the-Flow v3.0):"
echo ""
echo "  cd ${REPO_ROOT}"
echo "  source .venv311/bin/activate"
echo "  python dutchbay_bootstrap.py"
echo "  pytest"
echo ""
echo "Use this sequence before making changes or pushing to CI."

echo ""
echo "check_venv.sh completed."
