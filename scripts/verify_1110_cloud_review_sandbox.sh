#!/usr/bin/env bash

# Exercise the structural P02/P03 controls inside the private Codespace. This
# is an environment receipt, not an independent semantic-review decision.

set -euo pipefail

readonly VENV_ROOT="/workspaces/.dutchbay-audit-review-venv"
readonly CONTAINER_PYTHON="/usr/local/bin/python3.12"
readonly SOURCE_ROOT="/workspaces/.dutchbay-private/p03/sources"
readonly DEPENDENCY_MARKER="$VENV_ROOT/.dutchbay-inputs.sha256"
readonly IMAGE_MARKER="$VENV_ROOT/.dutchbay-image.sha256"
readonly PACKAGE_MARKER="$VENV_ROOT/.dutchbay-environment-content.sha256"
readonly SSHD_MARKER="$VENV_ROOT/.dutchbay-sshd-identity.sha256"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

[ "${CODESPACES:-}" = "true" ] || fail \
  "this control must run inside the governed GitHub Codespace"
[ "${DUTCHBAY_VENV:-}" = "$VENV_ROOT" ] || fail \
  "DUTCHBAY_VENV must select the sandbox environment"
[ "${DUTCHBAY_P03_SOURCE_ROOT:-}" = "$SOURCE_ROOT" ] || fail \
  "DUTCHBAY_P03_SOURCE_ROOT must select the private out-of-tree source root"
[ -x "$CONTAINER_PYTHON" ] && [ ! -L "$CONTAINER_PYTHON" ] || fail \
  "digest-pinned container Python is unavailable"
[ "$(realpath -e "$CONTAINER_PYTHON")" = "$CONTAINER_PYTHON" ] || fail \
  "digest-pinned container Python is aliased"
[ -x "$VENV_ROOT/bin/python" ] || fail "sandbox Python is unavailable"
[ -d "$SOURCE_ROOT" ] || fail "private P03 source root is unavailable"
[ ! -L "$SOURCE_ROOT" ] || fail "private P03 source root must not be a symlink"
[ "$(realpath -e "$SOURCE_ROOT")" = "$SOURCE_ROOT" ] || fail \
  "private P03 source root resolved outside its fixed path"
[ -f "$DEPENDENCY_MARKER" ] || fail "sandbox dependency marker is unavailable"
[ -f "$IMAGE_MARKER" ] || fail "sandbox image marker is unavailable"
[ -f "$PACKAGE_MARKER" ] || fail "sandbox environment-content marker is unavailable"
[ -f "$SSHD_MARKER" ] && [ ! -L "$SSHD_MARKER" ] || fail \
  "sandbox SSH transport identity marker is unavailable or unsafe"
/usr/bin/sudo --non-interactive /usr/sbin/sshd -t
"$CONTAINER_PYTHON" -S /usr/local/lib/dutchbay/sshd_readiness.py \
  5 /run/dutchbay-sshd-pre-lifecycle.ready \
  || fail "sandbox SSH transport listener is not ready"
sshd_identity_json=$(bash .devcontainer/attest_audit_review_sshd.sh)
sshd_identity_digest=$(
  SANDBOX_SSHD_IDENTITY_JSON="$sshd_identity_json" \
    "$CONTAINER_PYTHON" -S -c \
    'import json, os; print(json.loads(os.environ["SANDBOX_SSHD_IDENTITY_JSON"])["sshd_identity_sha256"])'
)
[ "$(tr -d '\r\n' < "$SSHD_MARKER")" = "$sshd_identity_digest" ] || fail \
  "sandbox SSH transport identity changed; delete and recreate the Codespace"
case "$(git branch --show-current)" in
  main|"") ;;
  *) fail "sandbox checkout must be protected main or detached origin/main" ;;
esac
[ -z "$(git status --porcelain)" ] || fail \
  "sandbox checkout must be clean before review preflight"
[ "$(git rev-parse HEAD)" = "$(git rev-parse refs/remotes/origin/main)" ] || fail \
  "sandbox checkout must equal the fetched origin/main before review preflight"

PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S - <<PY
from pathlib import Path
from audit_review_identity import build_identity

build_identity(
    Path.cwd(),
    Path("$DEPENDENCY_MARKER"),
    Path("$IMAGE_MARKER"),
    Path("$PACKAGE_MARKER"),
    Path("$VENV_ROOT"),
    Path("$CONTAINER_PYTHON"),
)
PY

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$VENV_ROOT/bin/python" -m pytest -p no:cacheprovider \
  tests/lint/test_audit_findings_current_state_overlay.py \
  tests/lint/test_audit_primary_source_control.py -q

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$VENV_ROOT/bin/python" \
  docs/audit/2026-08-controlled-successor/scripts/validate_published_pack.py

source_state="private_root_empty_p03_not_executed"
if find "$SOURCE_ROOT" -mindepth 1 -print -quit | grep -q .; then
  DUTCHBAY_P03_SOURCE_ROOT="$SOURCE_ROOT" PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$PWD" "$VENV_ROOT/bin/python" \
    scripts/verify_p03_primary_sources.py
  source_state="private_root_populated_p03_structural_verification_passed"
fi

[ -z "$(git status --porcelain)" ] || fail \
  "sandbox controls modified the checkout during preflight"

SANDBOX_SOURCE_STATE="$source_state" \
SANDBOX_DEPENDENCY_MARKER="$DEPENDENCY_MARKER" \
SANDBOX_IMAGE_MARKER="$IMAGE_MARKER" \
SANDBOX_PACKAGE_MARKER="$PACKAGE_MARKER" \
SANDBOX_VENV_ROOT="$VENV_ROOT" \
SANDBOX_CONTAINER_PYTHON="$CONTAINER_PYTHON" \
SANDBOX_SSHD_IDENTITY_JSON="$sshd_identity_json" \
PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from audit_review_identity import build_identity, build_verification_receipt

identity = build_identity(
    Path.cwd(),
    Path(os.environ["SANDBOX_DEPENDENCY_MARKER"]),
    Path(os.environ["SANDBOX_IMAGE_MARKER"]),
    Path(os.environ["SANDBOX_PACKAGE_MARKER"]),
    Path(os.environ["SANDBOX_VENV_ROOT"]),
    Path(os.environ["SANDBOX_CONTAINER_PYTHON"]),
)
sshd_identity = json.loads(os.environ["SANDBOX_SSHD_IDENTITY_JSON"])

print(
    json.dumps(
        build_verification_receipt(
            identity=identity,
            sshd_identity=sshd_identity,
            source_state=os.environ["SANDBOX_SOURCE_STATE"],
        ),
        sort_keys=True,
    )
)
PY
