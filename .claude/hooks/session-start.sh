#!/bin/bash
# =============================================================================
# SessionStart hook — provision the environment for Claude Code on the web.
#
# The remote container is ephemeral: it is cloned fresh and reclaimed on
# inactivity, so a .venv cannot be persisted between sessions. What CAN be
# persisted is the recipe — this hook — so every web session boots with an
# environment that can actually run the tests and the linters.
#
# Local sessions are left alone (see CLAUDE_CODE_REMOTE below); on your own
# machine `make setup` / `setup_venv.sh` remain the canonical bootstrap and this
# hook deliberately does not second-guess them.
# =============================================================================
set -euo pipefail

# Web/remote only. A local session keeps whatever venv the developer has.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$REPO"

VENV="$REPO/.venv"
PY="$VENV/bin/python"
STAMP="$VENV/.session-start-stamp"

# Idempotence: re-installing costs several minutes, so skip when the venv
# already matches the current dependency manifests. Any edit to the lock or to
# pyproject changes the hash and forces a refresh.
manifest_hash() {
  cat requirements.txt pyproject.toml 2>/dev/null | sha256sum | cut -d' ' -f1
}

# --- 1. Interpreter -----------------------------------------------------------
# 3.12 is the CI baseline. Pick it explicitly rather than trusting `python3`.
PYTHON_CMD=""
for c in python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1 \
     && "$c" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
    PYTHON_CMD="$c"; break
  fi
done
if [ -z "$PYTHON_CMD" ]; then
  echo "session-start: no Python >=3.12 found; cannot provision" >&2
  exit 1
fi

# --- 2. Virtualenv ------------------------------------------------------------
# A REAL venv is required, not a --user install into the system interpreter:
# Debian's patched setuptools raises `AttributeError: install_layout` when pip
# builds the legacy sdists in the lock (antlr4-python3-runtime, odfpy), which
# fails the whole install. A fresh venv ships clean build tooling and avoids it.
if [ ! -x "$PY" ]; then
  echo "session-start: creating $VENV"
  "$PYTHON_CMD" -m venv "$VENV"
  "$PY" -m pip install --quiet --upgrade pip setuptools wheel
fi

# --- 3. Dependencies ----------------------------------------------------------
# requirements.txt is the fully-pinned reproducibility lock; [dev] is the gate
# toolchain (ruff/black/isort, mypy + stubs, pytest + xdist/cov/split, bandit,
# pip-audit). Together these are exactly what the tests and linters need.
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$(manifest_hash)" ]; then
  echo "session-start: dependencies already current — skipping install"
else
  echo "session-start: installing pinned lock + [dev] toolchain (a few minutes)"
  "$PY" -m pip install --quiet -r requirements.txt
  "$PY" -m pip install --quiet -e ".[dev]"
  manifest_hash > "$STAMP"
fi

# The feasibility reproduce kit (feasibility_reproduce/run_all.sh) needs a much
# heavier set — PyWake, TopFarm, WeasyPrint, rasterio and their JAX/numba stack,
# roughly another gigabyte. It is not needed to run tests or linters, so it is
# opt-in rather than paid for on every session start:
#     DUTCHBAY_INSTALL_FEASIBILITY=1
if [ "${DUTCHBAY_INSTALL_FEASIBILITY:-}" = "1" ]; then
  echo "session-start: installing [feasibility] extra"
  "$PY" -m pip install --quiet -e ".[feasibility]"
fi

# --- 4. Session environment ---------------------------------------------------
# Put the venv first on PATH so `python`, `pytest` and `ruff` resolve to it
# without every command needing an explicit .venv/bin/ prefix.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi

echo "session-start: ready — $("$PY" -V)"
