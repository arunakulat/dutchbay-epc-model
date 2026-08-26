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
# 3.12 is the CI baseline. Pick it explicitly rather than trusting `python3`, and
# do not silently promote a fresh session to an unqualified later minor release.
PYTHON_CMD=""
for c in python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1 \
     && "$c" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' \
       >/dev/null 2>&1; then
    PYTHON_CMD="$c"; break
  fi
done
if [ -z "$PYTHON_CMD" ]; then
  echo "session-start: Python 3.12 not found; cannot provision" >&2
  exit 1
fi

# --- 2. Virtualenv ------------------------------------------------------------
# A REAL venv is required, not a --user install into the system interpreter:
# Debian's patched setuptools raises `AttributeError: install_layout` when pip
# builds the legacy sdists in the lock (antlr4-python3-runtime, odfpy), which
# fails the whole install. A fresh venv ships clean build tooling and avoids it.
if [ -x "$PY" ] \
   && ! "$PY" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' \
     >/dev/null 2>&1; then
  echo "session-start: existing .venv is not Python 3.12; recreate it before continuing" >&2
  exit 1
fi

if [ ! -x "$PY" ]; then
  echo "session-start: creating $VENV"
  "$PYTHON_CMD" -m venv "$VENV"
  "$PY" -m pip install --quiet --upgrade pip setuptools wheel
fi

# --- 3. Dependencies ----------------------------------------------------------
# requirements.txt is the fully-pinned reproducibility lock; [dev] is the gate
# toolchain (ruff/black/isort, mypy + stubs, pytest + xdist/cov/split, bandit,
# pip-audit). Together these are exactly what the tests and linters need.
# Extras are selectable so a session can be provisioned for the work it will do.
# DUTCHBAY_EXTRAS is a comma-separated extras list. It is normally supplied by the
# `env` block in .claude/settings.json, which the harness injects before this hook
# runs, so a web session provisions FULLY without anyone having to remember a flag.
#
# The fallback below is the same full set rather than a bare `dev`: relying on the
# env alone would mean a silently under-provisioned session if the injection ever
# failed, and an under-provisioned session fails LATE (a missing import halfway
# through a run) instead of loudly at start. Set DUTCHBAY_EXTRAS=dev explicitly
# for the fast tests-and-linters-only path.
#
#   dev                             tests + linters only (fastest)
#   dev,feasibility                 + the reproduce kit: wind/micrositing/gis/
#                                     report/grid — PyWake, TopFarm, WeasyPrint,
#                                     rasterio, pandapower/andes/OpenDSS
#   dev,feasibility,jobs            + redis/arq (async job path)
#   dev,feasibility,jobs,solar,pareto   everything (pvlib, pymoo)
#
# NOTE: several capabilities are CORE and need no extra at all — the BESS stack
# (finance.bess_revenue / bess_lcos / bess_project_economics,
# analytics.grid.capabilities.bess_soc) is always available.
#
# The full set adds roughly a gigabyte (JAX/numba/openmdao/jupyterlab via TopFarm)
# and a few minutes to session start. That cost is paid deliberately: the repo's
# work needs grid, micro-siting and the job path far more often than it needs a
# fast start, and a half-provisioned environment is the more expensive failure.
DUTCHBAY_EXTRAS_DEFAULT="dev,feasibility,jobs,solar,pareto"
DUTCHBAY_EXTRAS="${DUTCHBAY_EXTRAS:-${DUTCHBAY_INSTALL_FEASIBILITY:+dev,feasibility}}"
DUTCHBAY_EXTRAS="${DUTCHBAY_EXTRAS:-$DUTCHBAY_EXTRAS_DEFAULT}"

if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$(manifest_hash)|$DUTCHBAY_EXTRAS" ]; then
  echo "session-start: dependencies already current — skipping install"
else
  echo "session-start: installing pinned lock + [$DUTCHBAY_EXTRAS] (a few minutes)"
  "$PY" -m pip install --quiet -r requirements.txt
  "$PY" -m pip install --quiet -e ".[$DUTCHBAY_EXTRAS]"
  printf '%s|%s' "$(manifest_hash)" "$DUTCHBAY_EXTRAS" > "$STAMP"
fi

# Redis is needed by the async job path ([jobs]). The server binary ships in the
# image; start it only when the extra was actually requested, and never fail the
# session if it cannot start — the job path is opt-in, not load-bearing.
case ",$DUTCHBAY_EXTRAS," in
  *,jobs,*)
    if command -v redis-server >/dev/null 2>&1; then
      if redis-cli ping >/dev/null 2>&1; then
        echo "session-start: redis already running"
      else
        redis-server --daemonize yes --port 6379 --save '' --appendonly no >/dev/null 2>&1 \
          && echo "session-start: redis started on :6379" \
          || echo "session-start: WARNING redis-server failed to start (job path unavailable)"
      fi
    else
      echo "session-start: WARNING redis-server not on PATH (job path unavailable)"
    fi
    ;;
esac

# --- 4. Session environment ---------------------------------------------------
# Put the venv first on PATH so `python`, `pytest` and `ruff` resolve to it
# without every command needing an explicit .venv/bin/ prefix.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    # Prepend only when absent. This file is APPENDED to on every session start
    # and re-sourced by every shell, so an unconditional prepend accumulates one
    # duplicate per resume -- PATH was observed carrying 18 copies of .venv/bin
    # (32 entries, 15 unique) before this guard. First match wins either way, so
    # the duplicates were harmless but unbounded. The manifest-hash stamp above
    # makes the INSTALL idempotent; it never guarded this export.
    printf 'case ":$PATH:" in *":%s/bin:"*) ;; *) export PATH="%s/bin:$PATH" ;; esac\n' "$VENV" "$VENV"
  } >> "$CLAUDE_ENV_FILE"
fi

echo "session-start: ready — $("$PY" -V)"
