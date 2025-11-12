#!/usr/bin/env bash
# roll_zip_and_bootstrap.sh
# Usage:
#   bash scripts/roll_zip_and_bootstrap.sh \
#     "$HOME/Desktop/DutchBay_Model_V13_full_patched_Nov10_0931.zip" \
#     "$HOME/Desktop/DutchBay_EPC_Model"
set -Eeuo pipefail

ZIP="${1:-"$HOME/Desktop/DutchBay_Model_V13_full_patched_Nov10_0931.zip"}"
REPO="${2:-"$HOME/Desktop/DutchBay_EPC_Model"}"

say() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m⚠ %s\033[0m\n" "$*"; }
err() { printf "\033[1;31m✗ %s\033[0m\n" "$*"; }
ok()  { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }

run_or_warn() {
  set +e
  "$@"
  rc=$?
  set -e
  if [ $rc -ne 0 ]; then warn "Command failed (rc=$rc): $*"; fi
  return 0
}

# --- 0) sanity checks ---------------------------------------------------------
say "Sanity checks"
[ -f "$ZIP" ]  || { err "Zip not found: $ZIP"; exit 1; }
[ -d "$REPO" ] || { err "Repo dir not found: $REPO"; exit 1; }
command -v git >/dev/null || { err "git not found"; exit 1; }
command -v python3 >/dev/null || { err "python3 not found"; exit 1; }
ok "Inputs ok"

# --- 1) import zip into repo (preserve .git) ---------------------------------
say "Importing code from zip → repo"
if ! git -C "$REPO" rev-parse >/dev/null 2>&1; then
  warn "$REPO is not a git repo; initializing..."
  git -C "$REPO" init
  (cd "$REPO" && git add -A && git commit -m "chore: bootstrap repo")
fi

TMP="$(mktemp -d /tmp/dutchbay_zip.XXXXXX)"; trap 'rm -rf "$TMP"' EXIT
unzip -q "$ZIP" -d "$TMP"

# detect single top-level folder
entries=($(ls -1A "$TMP"))
if [ ${#entries[@]} -eq 1 ] && [ -d "$TMP/${entries[0]}" ]; then
  SRC="$TMP/${entries[0]}"
else
  SRC="$TMP"
fi

# sync into repo; keep .github to allow CI, drop caches
rsync -a --delete \
  --exclude ".git" \
  --exclude ".venv" --exclude "venv" \
  --exclude "__pycache__" --exclude "*.pyc" \
  "$SRC"/ "$REPO"/

# branch + commit
cd "$REPO"
BR="update/from_zip_$(date +%Y%m%d_%H%M%S)"
git checkout -b "$BR"
git add -A
git commit -m "chore(import): $(basename "$ZIP") → repo"
ok "Imported on branch: $BR"

# --- 2) venv bootstrap --------------------------------------------------------
say "Bootstrapping venv"
if [ -d "venv" ]; then
  # prefer existing named venv (your earlier runs used this)
  # shellcheck disable=SC1091
  . venv/bin/activate
elif [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
else
  python3 -m venv .venv
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi
python -V; command -v python; command -v pip

# --- 3) install deps (prefer locks/constraints) --------------------------------
say "Installing dependencies"
python -m pip install --upgrade pip wheel setuptools
if [ -f requirements.lock ]; then
  pip install -r requirements.lock
elif [ -f constraints.txt ]; then
  pip install -e .[dev,test] -c constraints.txt
else
  pip install -e .[dev,test]
fi
# Ensure IRR/NPV helpers
pip install numpy-financial || true

# --- 4) minimal hot-fixes you hit earlier -------------------------------------
say "Applying compatibility hot-fixes (idempotent)"

# 4a) bad relative import in finance/cashflow.py → use parent package types
if [ -f dutchbay_v13/finance/cashflow.py ]; then
  if grep -qE '^from[[:space:]]+\.types[[:space:]]+import' dutchbay_v13/finance/cashflow.py; then
    sed -i '' 's/^from[[:space:]]\+\.types[[:space:]]\+import/from ..types import/' dutchbay_v13/finance/cashflow.py
    ok "fixed relative import of types in finance/cashflow.py"
  fi
fi

# 4b) numpy.irr removal → switch to numpy_financial
if [ -f dutchbay_v13/finance/cashflow.py ]; then
  if grep -q "from numpy import irr" dutchbay_v13/finance/cashflow.py; then
    sed -i '' 's/from numpy import irr/import numpy_financial as npf/' dutchbay_v13/finance/cashflow.py
    sed -i '' 's/\birr(/npf.irr(/g' dutchbay_v13/finance/cashflow.py
    ok "migrated IRR calls to numpy_financial"
  fi
fi

# 4c) DebtYear object access (no dict indexing)
if [ -f dutchbay_v13/finance/cashflow.py ]; then
  sed -i '' 's/schedule\[y - 1\]\[\"interest\"\]/schedule[y - 1].interest/' dutchbay_v13/finance/cashflow.py || true
  sed -i '' 's/schedule\[y - 1\]\[\"principal\"\]/schedule[y - 1].principal/' dutchbay_v13/finance/cashflow.py || true
fi

# 4d) stray '%' at end of debt schedule (seen in your snippet)
if [ -f dutchbay_v13/finance/debt.py ]; then
  sed -i '' 's/return schedule%$/return schedule/' dutchbay_v13/finance/debt.py || true
fi

# 4e) make sure finance is a proper package
[ -d dutchbay_v13/finance ] && [ ! -f dutchbay_v13/finance/__init__.py ] && touch dutchbay_v13/finance/__init__.py

# Reinstall editable after patches
pip install -e .
ok "Patched & reinstalled"

# --- 5) quality gates (lint/type/security/tests) -------------------------------
say "Running quality gates (best-effort)"
# ensure tools present even if extras were thin
run_or_warn pip install black ruff flake8 mypy bandit pytest coverage

if [ -f Makefile ]; then
  run_or_warn make lint
  run_or_warn make type
  run_or_warn make security
  run_or_warn make test
  run_or_warn make cov
else
  run_or_warn black --check .
  run_or_warn ruff check .
  run_or_warn flake8 .
  run_or_warn mypy dutchbay_v13
  run_or_warn bandit -r dutchbay_v13
  if [ -d tests ]; then
    run_or_warn pytest -q
    run_or_warn coverage run -m pytest && run_or_warn coverage report -m
  else
    warn "No tests/ directory found; skipping pytest/coverage"
  fi
fi

# --- 6) quick model smoke (non-fatal) -----------------------------------------
say "Model smoke (non-fatal if your CLI modes differ)"
if [ -f full_model_variables_updated.yaml ]; then
  run_or_warn python -m dutchbay_v13.cli --config full_model_variables_updated.yaml --mode irr
else
  warn "Config full_model_variables_updated.yaml not found; skipping IRR smoke"
fi

# --- 7) freeze/lock and commit ------------------------------------------------
say "Freezing/locking dependencies"
if grep -q '^freeze:' Makefile 2>/dev/null; then
  run_or_warn make freeze
else
  run_or_warn pip freeze > constraints.txt
fi
if grep -q '^lock:' Makefile 2>/dev/null; then
  run_or_warn make lock
else
  run_or_warn pip freeze > requirements.lock
fi

git add constraints.txt requirements.lock 2>/dev/null || true
run_or_warn git commit -m "chore(lock): freeze deps after import + patches"

# --- 8) final summary ---------------------------------------------------------
say "Done."
git status --short || true
echo
ok "Imported zip → $REPO on branch $BR"
echo "Next:"
echo "  git diff main...$BR | less"
echo "  git checkout main && git merge --no-ff $BR && git push"
