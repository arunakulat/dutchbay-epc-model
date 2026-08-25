#!/usr/bin/env bash

# Exercise the structural P02/P03 controls inside the private Codespace. This
# is an environment receipt, not an independent semantic-review decision.

set -euo pipefail

readonly VENV_ROOT="/workspaces/.dutchbay-audit-review-venv"
readonly CONTAINER_PYTHON="/usr/local/bin/python3.12"
readonly SOURCE_ROOT="/workspaces/.dutchbay-private/p03/sources"
readonly BOOTSTRAP_RECEIPT="/workspaces/.dutchbay-private/bootstrap-receipt.json"
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
[ -f "$BOOTSTRAP_RECEIPT" ] && [ ! -L "$BOOTSTRAP_RECEIPT" ] || fail \
  "sandbox bootstrap receipt is unavailable or unsafe"
[ "$(realpath -e "$BOOTSTRAP_RECEIPT")" = "$BOOTSTRAP_RECEIPT" ] || fail \
  "sandbox bootstrap receipt resolved outside its fixed path"
[ "$(stat -c '%U:%G:%a' "$BOOTSTRAP_RECEIPT")" = \
  "vscode:vscode:400" ] || fail \
  "sandbox bootstrap receipt ownership or mode differs"
[ ! -L "$SOURCE_ROOT" ] || fail "private P03 source root must not be a symlink"
[ "$(realpath -e "$SOURCE_ROOT")" = "$SOURCE_ROOT" ] || fail \
  "private P03 source root resolved outside its fixed path"
execution_host=$(
  "$CONTAINER_PYTHON" -S - "$BOOTSTRAP_RECEIPT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open(encoding="utf-8") as stream:
    receipt = json.load(stream)
expected = {
    "schema": "dutchbay.audit_review_sandbox_bootstrap.v3",
    "status": "PASS",
    "environment": "github_codespaces",
    "network_boundary": "creator_private_codespace_outbound_egress_available",
    "completion_authorized": False,
    "release_status": "HOLD",
}
for key, value in expected.items():
    if receipt.get(key) != value:
        raise SystemExit(f"bootstrap receipt field differs: {key}")
git_commit = receipt.get("git_commit")
if not isinstance(git_commit, str) or len(git_commit) != 40 or any(
    value not in "0123456789abcdef" for value in git_commit
):
    raise SystemExit("bootstrap receipt Git identity is malformed")
print(receipt["environment"])
PY
)
[ "$execution_host" = "github_codespaces" ] || fail \
  "protected review receipt is not bound to a real GitHub Codespace"
[ -f "$DEPENDENCY_MARKER" ] || fail "sandbox dependency marker is unavailable"
[ -f "$IMAGE_MARKER" ] || fail "sandbox image marker is unavailable"
[ -f "$PACKAGE_MARKER" ] || fail "sandbox environment-content marker is unavailable"
[ -f "$SSHD_MARKER" ] && [ ! -L "$SSHD_MARKER" ] || fail \
  "sandbox SSH transport identity marker is unavailable or unsafe"
/usr/bin/sudo --non-interactive /usr/sbin/sshd -t
"$CONTAINER_PYTHON" -S /usr/local/lib/dutchbay/sshd_readiness.py \
  5 /run/dutchbay-sshd-runtime.ready \
  || fail "sandbox SSH transport listener is not ready"
sshd_identity_json=$(bash .devcontainer/attest_audit_review_sshd.sh --session)
sshd_identity_digest=$(
  SANDBOX_SSHD_IDENTITY_JSON="$sshd_identity_json" \
    "$CONTAINER_PYTHON" -S -c \
    'import json, os; print(json.loads(os.environ["SANDBOX_SSHD_IDENTITY_JSON"])["sshd_identity_sha256"])'
)
[ "$(tr -d '\r\n' < "$SSHD_MARKER")" = "$sshd_identity_digest" ] || fail \
  "sandbox SSH transport identity changed; delete and recreate the Codespace"
checkout_branch=$(git branch --show-current) || fail \
  "sandbox checkout branch could not be determined"
case "$checkout_branch" in
  main|"") ;;
  *) fail "sandbox checkout must be protected main or detached origin/main" ;;
esac
checkout_status=$(git status --porcelain=v1) || fail \
  "sandbox checkout status could not be determined"
[ -z "$checkout_status" ] || fail \
  "sandbox checkout must be clean before review preflight"
checkout_head=$(git rev-parse HEAD) || fail \
  "sandbox checkout commit could not be determined"
origin_main=$(git rev-parse refs/remotes/origin/main) || fail \
  "fetched origin/main commit could not be determined"
[ "$checkout_head" = "$origin_main" ] || fail \
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

source_probe=$(find "$SOURCE_ROOT" -mindepth 1 -print -quit) || fail \
  "P03 source-root population could not be determined"
source_state="private_root_empty_p03_not_executed"
if [ -n "$source_probe" ]; then
  DUTCHBAY_P03_SOURCE_ROOT="$SOURCE_ROOT" PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$PWD" "$VENV_ROOT/bin/python" \
    scripts/verify_p03_primary_sources.py
  source_state="private_root_populated_p03_structural_verification_passed"
fi

checkout_status=$(git status --porcelain=v1) || fail \
  "sandbox checkout status could not be determined after controls"
[ -z "$checkout_status" ] || fail \
  "sandbox controls modified the checkout during preflight"

SANDBOX_SOURCE_STATE="$source_state" \
SANDBOX_DEPENDENCY_MARKER="$DEPENDENCY_MARKER" \
SANDBOX_IMAGE_MARKER="$IMAGE_MARKER" \
SANDBOX_PACKAGE_MARKER="$PACKAGE_MARKER" \
SANDBOX_VENV_ROOT="$VENV_ROOT" \
SANDBOX_CONTAINER_PYTHON="$CONTAINER_PYTHON" \
SANDBOX_SSHD_IDENTITY_JSON="$sshd_identity_json" \
SANDBOX_EXECUTION_HOST="$execution_host" \
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
            execution_host=os.environ["SANDBOX_EXECUTION_HOST"],
        ),
        sort_keys=True,
    )
)
PY
