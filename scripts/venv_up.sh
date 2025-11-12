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
VENV_DIR="${VENV_DIR:-.venv311}"
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

# optional hygiene
python -m pip install --upgrade pip >/dev/null 2>&1 || true
[ -f requirements.txt ] && pip install -r requirements.txt || true
[ -f pyproject.toml ] && pip install -e . || true

echo "✓ venv active: $VIRTUAL_ENV"
