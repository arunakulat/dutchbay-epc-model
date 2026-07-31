#!/usr/bin/env bash
# Usage (must be sourced):  source scripts/venv_up.sh
# zsh:                      . scripts/venv_up.sh
# Safe in bash/zsh; creates venv if missing, then activates current shell.

# ---- detect script dir in bash OR zsh, even when sourced ----
if [ -n "${BASH_VERSION-}" ]; then
  _SELF="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION-}" ]; then
  # zsh gives the current script path via this expansion
  _SELF="${(%):-%N}"
else
  _SELF="$0"
fi
_SCRIPT_DIR="$(cd "$(dirname -- "$_SELF")" && pwd)"
_REPO_ROOT="$(cd "${_SCRIPT_DIR}/.." && pwd)"

# ---- config ----
VENV_DIR="${VENV_DIR:-.venv}"
PY311="${PY311:-/opt/homebrew/bin/python3.11}"

# ---- ensure venv exists ----
cd "$_REPO_ROOT" || { echo "ERR: cannot cd to repo root"; return 1 2>/dev/null || exit 1; }
if [ ! -d "$VENV_DIR" ]; then
  if command -v "$PY311" >/dev/null 2>&1; then
    "$PY311" -m venv "$VENV_DIR"
  elif command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv "$VENV_DIR"
  else
    python3 -m venv "$VENV_DIR"
  fi
fi

# ---- must be sourced to affect current shell ----
_activator="$VENV_DIR/bin/activate"
if [ ! -f "$_activator" ]; then
  echo "ERR: activator not found: $_activator"
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
. "$_activator"

# ---- optional hygiene: keep it, but don't explode on failure ----
python -m pip install --upgrade pip >/dev/null 2>&1 || true
[ -f requirements.txt ] && pip install -r requirements.txt >/dev/null 2>&1 || true
[ -f pyproject.toml ] && pip install -e . >/dev/null 2>&1 || true

# ---- Go with the Flow ruleset bootstrap ------------------------------------
# Canonical tracked rules CSV in the repository root.
RULESET_SRC="${_REPO_ROOT}/go_with_the_flow_rules_v3_0_clean.csv"

if [ -f "$RULESET_SRC" ]; then
  # Put a copy inside the venv so it's hermetic to this environment
  RULESET_DIR="${VIRTUAL_ENV}/share/dutchbay"
  mkdir -p "$RULESET_DIR"

  RULESET_DST="${RULESET_DIR}/go_with_the_flow_rules.csv"

  # Cheap idempotent copy – if content is the same, this is effectively a no-op
  cp "$RULESET_SRC" "$RULESET_DST"

  # Export an env var so Python / scripts can find it trivially
  export DUTCHBAY_FLOW_RULESET_CSV="$RULESET_DST"

  echo "✓ venv active: $VIRTUAL_ENV"
  echo "✓ Go-with-the-Flow ruleset loaded: $DUTCHBAY_FLOW_RULESET_CSV"
else
  echo "✓ venv active: $VIRTUAL_ENV"
  echo "⚠ Go-with-the-Flow ruleset not found at: $RULESET_SRC"
  echo "  (env var DUTCHBAY_FLOW_RULESET_CSV not set)"
fi

# EOF
