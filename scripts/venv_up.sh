#!/usr/bin/env bash
# Usage (must be sourced): source scripts/venv_up.sh
# Safe in bash and zsh. Resolves the configured shared environment or the
# checkout-local portable fallback, validates it, then binds imports to this
# checkout.

if [ -n "${BASH_VERSION-}" ]; then
  _DUTCHBAY_SELF="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION-}" ]; then
  _DUTCHBAY_SELF="${(%):-%N}"
else
  _DUTCHBAY_SELF="$0"
fi
_DUTCHBAY_SCRIPT_DIR="$(cd "$(dirname -- "$_DUTCHBAY_SELF")" && pwd)"
_DUTCHBAY_REPO_ROOT="$(cd "$_DUTCHBAY_SCRIPT_DIR/.." && pwd)"

# shellcheck disable=SC1091
. "$_DUTCHBAY_SCRIPT_DIR/development_environment.sh"

if ! _DUTCHBAY_BOOTSTRAP_PYTHON=$(dutchbay_find_python312); then
  echo "ERR: Python 3.12 is required; install it before activation" >&2
  return 1 2>/dev/null || exit 1
fi
if ! _DUTCHBAY_VENV=$(
    dutchbay_resolve_venv \
      "$_DUTCHBAY_REPO_ROOT" "$_DUTCHBAY_BOOTSTRAP_PYTHON"
  ); then
  echo "ERR: unable to resolve DUTCHBAY_VENV" >&2
  return 1 2>/dev/null || exit 1
fi

if [ ! -x "$_DUTCHBAY_VENV/bin/python" ]; then
  if ! "$_DUTCHBAY_REPO_ROOT/setup_venv.sh"; then
    return 1 2>/dev/null || exit 1
  fi
fi

if ! dutchbay_validate_venv "$_DUTCHBAY_REPO_ROOT" "$_DUTCHBAY_VENV"; then
  return 1 2>/dev/null || exit 1
fi
if ! dutchbay_activate_checkout \
  "$_DUTCHBAY_REPO_ROOT" "$_DUTCHBAY_VENV"; then
  return 1 2>/dev/null || exit 1
fi

echo "Environment active: $VIRTUAL_ENV"
echo "Active checkout imports: $_DUTCHBAY_REPO_ROOT"
echo "GWTF ruleset: $DUTCHBAY_FLOW_RULESET_CSV"
