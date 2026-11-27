#!/usr/bin/env bash
# Install the configured pre-commit hook set into a DutchBay checkout.

set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [ "$#" -ne 2 ]; then
  fail "Usage: $0 <project-root> <venv-python>"
fi

PROJECT_ROOT="$1"
VENV_PYTHON="$2"

[ -n "$PROJECT_ROOT" ] || fail "Project root must not be empty."
[ -n "$VENV_PYTHON" ] || fail "Interpreter path must not be empty."

# Install the configured pre-commit hook set so GOV-02's no-commit-to-branch defence and
# the formatting, lint, import-order and file checks can run automatically.
# The configured set excludes local mypy by owner decision #1270; mandatory CI and
# local type verification remain in force. Hooks live in .git/hooks, which git does not
# track, so a fresh clone or an older checkout has none until setup installs them.
if [ -n "${DUTCHBAY_SKIP_HOOKS:-}" ]; then
  echo "Skipping pre-commit hook installation (DUTCHBAY_SKIP_HOOKS is set)."
elif ! git -C "$PROJECT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not a git checkout; skipping pre-commit hook installation."
else
  echo "Installing configured pre-commit hooks (GOV-02; R10 type-check scope recorded in #1270)..."
  (cd "$PROJECT_ROOT" && "$VENV_PYTHON" -m pre_commit install) || fail \
    "Pre-commit hook installation failed; configured checks and GOV-02 are inactive." \
    "Repair with: '$VENV_PYTHON' -m pre_commit install"
fi
