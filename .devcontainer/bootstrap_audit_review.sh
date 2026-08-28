#!/usr/bin/env bash

# Build the private, reusable Codespaces environment for #1110 P02/P03 review.
# The environment and retained source root live outside the Git checkout. No
# source object, credential or raw runtime log is written into the repository.

set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

readonly VENV_ROOT="/workspaces/.dutchbay-audit-review-venv"
readonly CONTAINER_PYTHON="/usr/local/bin/python3.12"
readonly PRIVATE_ROOT="/workspaces/.dutchbay-private"
readonly BOOTSTRAP_RECEIPT_PATH="$PRIVATE_ROOT/bootstrap-receipt.json"
readonly P03_ROOT="$PRIVATE_ROOT/p03"
readonly SOURCE_ROOT="$P03_ROOT/sources"
readonly TRANSPORT_ROOT="$PRIVATE_ROOT/transport-smoke"
readonly SSHD_RUNTIME_MARKER="/run/dutchbay-sshd-runtime.ready"
readonly MARKER="$VENV_ROOT/.dutchbay-inputs.sha256"
readonly IMAGE_MARKER="$VENV_ROOT/.dutchbay-image.sha256"
readonly PACKAGE_MARKER="$VENV_ROOT/.dutchbay-environment-content.sha256"
readonly SSHD_MARKER="$VENV_ROOT/.dutchbay-sshd-identity.sha256"
readonly REQUIRED_PIP_VERSION="26.2.1"
readonly REQUIRED_SETUPTOOLS_VERSION="84.0.0"
readonly REQUIRED_WHEEL_VERSION="0.48.0"
execution_host_input="${DUTCHBAY_SANDBOX_EXECUTION_HOST:-}"
if [ -n "$execution_host_input" ]; then
  EXECUTION_HOST=$execution_host_input
elif [ "${CODESPACES:-}" = "true" ] && [ -n "${CODESPACE_NAME:-}" ]; then
  EXECUTION_HOST="github_codespaces"
else
  printf '%s\n' \
    "ERROR: sandbox execution-host provenance is missing" >&2
  exit 2
fi
readonly EXECUTION_HOST

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

reject_repository_bytecode() {
  local bytecode_probe
  bytecode_probe=$(find .devcontainer \
    \( -type d -name __pycache__ \
      -o -type f \( -name '*.pyc' -o -name '*.pyo' \) \) \
    -print -quit) || fail "repository bytecode population could not be determined"
  [ -z "$bytecode_probe" ] || fail \
    "repository bytecode is executable untracked input; recreate the Codespace"
}

package_content_fingerprint() {
  PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
    'import sys; from pathlib import Path; from audit_review_identity import installed_environment_content_sha256; print(installed_environment_content_sha256(Path(sys.argv[1]), Path(sys.argv[2])))' \
    "$VENV_ROOT" "$CONTAINER_PYTHON"
}

[ "${CODESPACES:-}" = "true" ] || fail \
  "the independent audit sandbox must be built inside a GitHub Codespace"
[ -n "${CODESPACE_NAME:-}" ] || fail "CODESPACE_NAME is missing"
case "$EXECUTION_HOST" in
  github_codespaces|github_actions_devcontainer_emulation) ;;
  *) fail "sandbox execution-host provenance is missing or unsupported" ;;
esac
/usr/local/sbin/dutchbay-sshd-start.sh --start
"$CONTAINER_PYTHON" -S /usr/local/lib/dutchbay/sshd_readiness.py \
  30 "$SSHD_RUNTIME_MARKER" \
  || fail "SSH transport did not become ready before the audit bootstrap"
[ -f "requirements.txt" ] && [ -f "pyproject.toml" ] || fail \
  "run the bootstrap from the DutchBay repository root"
reject_repository_bytecode
[ -x "$CONTAINER_PYTHON" ] && [ ! -L "$CONTAINER_PYTHON" ] || fail \
  "digest-pinned container Python is unavailable"
[ "$(realpath -e "$CONTAINER_PYTHON")" = "$CONTAINER_PYTHON" ] || fail \
  "digest-pinned container Python is aliased"

# These paths are deliberately fixed and narrow so a variable or checkout-name
# mistake cannot redirect an environment rebuild or private-source copy.
[ "$VENV_ROOT" = "/workspaces/.dutchbay-audit-review-venv" ] || fail \
  "unexpected sandbox environment target"
[ "$PRIVATE_ROOT" = "/workspaces/.dutchbay-private" ] || fail \
  "unexpected private-source target"
[ "$BOOTSTRAP_RECEIPT_PATH" = \
  "/workspaces/.dutchbay-private/bootstrap-receipt.json" ] || fail \
  "unexpected bootstrap-receipt target"
[ "$P03_ROOT" = "/workspaces/.dutchbay-private/p03" ] || fail \
  "unexpected P03 private-root target"
[ "$SOURCE_ROOT" = "/workspaces/.dutchbay-private/p03/sources" ] || fail \
  "unexpected P03 source-root target"
[ "$TRANSPORT_ROOT" = "/workspaces/.dutchbay-private/transport-smoke" ] || fail \
  "unexpected transport-smoke target"
[ "$(id -un)" = "vscode" ] || fail \
  "the audit bootstrap must run as the non-root vscode user"
/usr/bin/sudo --non-interactive /usr/bin/install \
  -d -m 0755 -o vscode -g vscode /workspaces
[ "$(/usr/bin/stat -c '%U:%G:%a' /workspaces)" = "vscode:vscode:755" ] || fail \
  "the fixed workspace parent ownership differs"
[ ! -L "$PRIVATE_ROOT" ] || fail "private-source root must not be a symlink"
[ ! -L "$BOOTSTRAP_RECEIPT_PATH" ] || fail \
  "bootstrap receipt must not be a symlink"
[ ! -L "$P03_ROOT" ] || fail "P03 private root must not be a symlink"
[ ! -L "$SOURCE_ROOT" ] || fail "P03 source root must not be a symlink"
[ ! -L "$TRANSPORT_ROOT" ] || fail "transport-smoke root must not be a symlink"

install -d -m 0700 \
  "$PRIVATE_ROOT" "$P03_ROOT" "$SOURCE_ROOT" "$TRANSPORT_ROOT"
[ "$(realpath -e "$PRIVATE_ROOT")" = "$PRIVATE_ROOT" ] || fail \
  "private-source root resolved outside its fixed path"
[ "$(realpath -e "$P03_ROOT")" = "$P03_ROOT" ] || fail \
  "P03 private root resolved outside its fixed path"
[ "$(realpath -e "$SOURCE_ROOT")" = "$SOURCE_ROOT" ] || fail \
  "P03 source root resolved outside its fixed path"
[ "$(realpath -e "$TRANSPORT_ROOT")" = "$TRANSPORT_ROOT" ] || fail \
  "transport-smoke root resolved outside its fixed path"

bash .devcontainer/start_audit_review_sshd.sh --prepare-only
sshd_identity_json=$(bash .devcontainer/attest_audit_review_sshd.sh --construction)
sshd_identity_digest=$(
  SANDBOX_SSHD_IDENTITY_JSON="$sshd_identity_json" \
    "$CONTAINER_PYTHON" -S -c \
    'import json, os; print(json.loads(os.environ["SANDBOX_SSHD_IDENTITY_JSON"])["sshd_identity_sha256"])'
)

input_digest=$(PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
  'from pathlib import Path; from audit_review_identity import dependency_input_sha256; print(dependency_input_sha256(Path.cwd()))')
image_digest=$(PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
  'from pathlib import Path; from audit_review_identity import configured_base_image_digest; print(configured_base_image_digest(Path.cwd()).removeprefix("sha256:"))')

installed_digest=""
if [ -f "$MARKER" ]; then
  installed_digest=$(tr -d '\r\n' < "$MARKER")
fi

if [ -f "$MARKER" ] && [ "$installed_digest" != "$input_digest" ]; then
  fail "sandbox inputs changed; delete and recreate the Codespace"
fi
if [ -f "$MARKER" ] && [ ! -f "$IMAGE_MARKER" ]; then
  fail "container image marker is missing; delete and recreate the Codespace"
fi
if [ -f "$MARKER" ] && [ ! -f "$PACKAGE_MARKER" ]; then
  fail "installed environment-content marker is missing; delete and recreate the Codespace"
fi
if [ -f "$MARKER" ] && [ ! -f "$SSHD_MARKER" ]; then
  fail "SSH transport identity marker is missing; delete and recreate the Codespace"
fi
if [ ! -f "$MARKER" ] \
  && { [ -e "$IMAGE_MARKER" ] || [ -e "$PACKAGE_MARKER" ] \
    || [ -e "$SSHD_MARKER" ]; }; then
  fail "unbound sandbox identity marker exists; delete and recreate the Codespace"
fi
if [ -f "$IMAGE_MARKER" ] \
  && [ "$(tr -d '\r\n' < "$IMAGE_MARKER")" != "$image_digest" ]; then
  fail "container image changed; delete and recreate the Codespace"
fi
if [ -f "$SSHD_MARKER" ] \
  && { [ -L "$SSHD_MARKER" ] \
    || [ "$(tr -d '\r\n' < "$SSHD_MARKER")" != "$sshd_identity_digest" ]; }; then
  fail "SSH transport identity changed; delete and recreate the Codespace"
fi

if [ ! -f "$MARKER" ]; then
  [ ! -e "$VENV_ROOT" ] || fail \
    "unbound sandbox environment residue exists; recreate the Codespace"
  "$CONTAINER_PYTHON" -m venv "$VENV_ROOT"
  "$VENV_ROOT/bin/python" -m pip install \
    "pip==$REQUIRED_PIP_VERSION" \
    "setuptools==$REQUIRED_SETUPTOOLS_VERSION" \
    "wheel==$REQUIRED_WHEEL_VERSION"
  "$VENV_ROOT/bin/python" -m pip install --requirement requirements.txt
  "$VENV_ROOT/bin/python" -m pip install --no-deps --editable .
  package_content_digest=$(package_content_fingerprint)
  printf '%s\n' "$input_digest" > "$MARKER"
  printf '%s\n' "$image_digest" > "$IMAGE_MARKER"
  printf '%s\n' "$package_content_digest" > "$PACKAGE_MARKER"
  printf '%s\n' "$sshd_identity_digest" > "$SSHD_MARKER"
fi

# Reused environments are content-verified by container Python under -S before
# any venv interpreter, .pth file or sitecustomize module can execute.
package_content_digest=$(package_content_fingerprint)
[ "$(tr -d '\r\n' < "$PACKAGE_MARKER")" = "$package_content_digest" ] || fail \
  "installed environment content changed; delete and recreate the Codespace"

PYTHONDONTWRITEBYTECODE=1 DUTCHBAY_VENV="$VENV_ROOT" PYTHONPATH="$PWD" \
  ./check_venv.sh --no-bootstrap

DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$VENV_ROOT/bin/python" dutchbay_bootstrap_rules.py

source_probe=$(find "$SOURCE_ROOT" -mindepth 1 -print -quit) || fail \
  "P03 source-root population could not be determined"
source_state="private_root_empty"
if [ -n "$source_probe" ]; then
  source_state="private_root_populated"
fi

package_content_digest=$(package_content_fingerprint)
[ "$(tr -d '\r\n' < "$PACKAGE_MARKER")" = "$package_content_digest" ] || fail \
  "installed environment content changed during bootstrap; recreate the Codespace"

receipt_tmp=""
cleanup_receipt_tmp() {
  local exit_status=$?
  trap - EXIT
  if [ -n "$receipt_tmp" ] && [ -f "$receipt_tmp" ] \
    && [ ! -L "$receipt_tmp" ]; then
    if ! unlink -- "$receipt_tmp"; then
      printf 'ERROR: bootstrap receipt temporary-file cleanup failed\n' >&2
      exit_status=2
    fi
  fi
  exit "$exit_status"
}
trap cleanup_receipt_tmp EXIT

receipt_tmp=$(mktemp "$PRIVATE_ROOT/.bootstrap-receipt.XXXXXX")
SANDBOX_SOURCE_STATE="$source_state" \
SANDBOX_DEPENDENCY_MARKER="$MARKER" \
SANDBOX_IMAGE_MARKER="$IMAGE_MARKER" \
SANDBOX_PACKAGE_MARKER="$PACKAGE_MARKER" \
SANDBOX_VENV_ROOT="$VENV_ROOT" \
SANDBOX_CONTAINER_PYTHON="$CONTAINER_PYTHON" \
SANDBOX_SSHD_IDENTITY_JSON="$sshd_identity_json" \
SANDBOX_EXECUTION_HOST="$EXECUTION_HOST" \
SANDBOX_CODESPACE_NAME="$CODESPACE_NAME" \
PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S - <<'PY' \
  > "$receipt_tmp"
from __future__ import annotations

import json
import os
from pathlib import Path

from audit_review_identity import build_bootstrap_receipt, build_identity

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
        build_bootstrap_receipt(
            identity=identity,
            sshd_identity=sshd_identity,
            source_state=os.environ["SANDBOX_SOURCE_STATE"],
            execution_host=os.environ["SANDBOX_EXECUTION_HOST"],
            codespace_name=os.environ["SANDBOX_CODESPACE_NAME"],
        ),
        sort_keys=True,
    )
)
PY
chmod 0400 "$receipt_tmp"
mv --no-target-directory -- "$receipt_tmp" "$BOOTSTRAP_RECEIPT_PATH"
receipt_tmp=""
trap - EXIT
[ "$(realpath -e "$BOOTSTRAP_RECEIPT_PATH")" = \
  "$BOOTSTRAP_RECEIPT_PATH" ] || fail \
  "bootstrap receipt resolved outside its fixed path"
[ "$(stat -c '%U:%G:%a' "$BOOTSTRAP_RECEIPT_PATH")" = \
  "vscode:vscode:400" ] || fail "bootstrap receipt ownership or mode differs"
cat -- "$BOOTSTRAP_RECEIPT_PATH"
