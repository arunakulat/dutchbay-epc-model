#!/usr/bin/env bash
# Shared shell helpers for the governed DutchBay development environment.

# This file is sourced by bash and zsh entrypoints. Keep its syntax portable
# between those shells and leave error-policy choices to the caller.

dutchbay_find_python312() {
  local candidate
  for candidate in python3.12 /opt/homebrew/bin/python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" \
        -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' \
        >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

dutchbay_resolve_venv() {
  local repo_root=$1
  local bootstrap_python=$2
  DUTCHBAY_REPO_ROOT="$repo_root" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}" \
    "$bootstrap_python" -c \
      'import os; from pathlib import Path; from dutchbay_environment import resolve_environment; print(resolve_environment(Path(os.environ["DUTCHBAY_REPO_ROOT"])).path)'
}

dutchbay_validate_venv() {
  local repo_root=$1
  local venv=$2
  DUTCHBAY_REPO_ROOT="$repo_root" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}" \
    "$venv/bin/python" "$repo_root/dutchbay_environment.py"
}

dutchbay_activate_checkout() {
  local repo_root=$1
  local venv=$2
  local activate="$venv/bin/activate"
  if [ ! -f "$activate" ]; then
    echo "ERR: activator not found: $activate" >&2
    return 1
  fi

  # shellcheck disable=SC1090
  . "$activate"
  export PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}"
  export DUTCHBAY_FLOW_RULESET_CSV="$repo_root/go_with_the_flow_rules_v3_0_clean.csv"
}
