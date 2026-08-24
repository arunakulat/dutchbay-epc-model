#!/usr/bin/env bash

# Build the private, reusable Codespaces environment for #1110 P02/P03 review.
# The environment and retained source root live outside the Git checkout. No
# source object, credential or raw runtime log is written into the repository.

set -euo pipefail

readonly VENV_ROOT="/workspaces/.dutchbay-audit-review-venv"
readonly CONTAINER_PYTHON="/usr/local/bin/python3.12"
readonly PRIVATE_ROOT="/workspaces/.dutchbay-private"
readonly P03_ROOT="$PRIVATE_ROOT/p03"
readonly SOURCE_ROOT="$P03_ROOT/sources"
readonly TRANSPORT_ROOT="$PRIVATE_ROOT/transport-smoke"
readonly SITE_PACKAGES="$VENV_ROOT/lib/python3.12/site-packages"
readonly MARKER="$VENV_ROOT/.dutchbay-inputs.sha256"
readonly IMAGE_MARKER="$VENV_ROOT/.dutchbay-image.sha256"
readonly PACKAGE_MARKER="$VENV_ROOT/.dutchbay-environment-content.sha256"
readonly REQUIRED_PIP_VERSION="26.2.1"
readonly REQUIRED_SETUPTOOLS_VERSION="84.0.0"
readonly REQUIRED_WHEEL_VERSION="0.48.0"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

package_content_fingerprint() {
  PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
    'import sys; from pathlib import Path; from audit_review_identity import installed_environment_content_sha256; print(installed_environment_content_sha256(Path(sys.argv[1]), Path(sys.argv[2])))' \
    "$VENV_ROOT" "$CONTAINER_PYTHON"
}

package_set_fingerprint() {
  PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
    'import sys; from pathlib import Path; from audit_review_identity import installed_distribution_set_sha256; print(installed_distribution_set_sha256(Path(sys.argv[1])))' \
    "$SITE_PACKAGES"
}

[ "${CODESPACES:-}" = "true" ] || fail \
  "the independent audit sandbox must be built inside a GitHub Codespace"
[ -n "${CODESPACE_NAME:-}" ] || fail "CODESPACE_NAME is missing"
[ -f "requirements.txt" ] && [ -f "pyproject.toml" ] || fail \
  "run the bootstrap from the DutchBay repository root"
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
[ "$P03_ROOT" = "/workspaces/.dutchbay-private/p03" ] || fail \
  "unexpected P03 private-root target"
[ "$SOURCE_ROOT" = "/workspaces/.dutchbay-private/p03/sources" ] || fail \
  "unexpected P03 source-root target"
[ "$TRANSPORT_ROOT" = "/workspaces/.dutchbay-private/transport-smoke" ] || fail \
  "unexpected transport-smoke target"
[ "$SITE_PACKAGES" = "/workspaces/.dutchbay-audit-review-venv/lib/python3.12/site-packages" ] || fail \
  "unexpected sandbox site-packages target"
[ ! -L "$PRIVATE_ROOT" ] || fail "private-source root must not be a symlink"
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

input_digest=$(PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
  'from pathlib import Path; from audit_review_identity import dependency_input_sha256; print(dependency_input_sha256(Path.cwd()))')
image_digest=$(PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S -c \
  'from pathlib import Path; from audit_review_identity import configured_image_digest; print(configured_image_digest(Path.cwd()).removeprefix("sha256:"))')

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
if [ ! -f "$MARKER" ] \
  && { [ -e "$IMAGE_MARKER" ] || [ -e "$PACKAGE_MARKER" ]; }; then
  fail "unbound sandbox identity marker exists; delete and recreate the Codespace"
fi
if [ -f "$IMAGE_MARKER" ] \
  && [ "$(tr -d '\r\n' < "$IMAGE_MARKER")" != "$image_digest" ]; then
  fail "container image changed; delete and recreate the Codespace"
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

source_state="private_root_empty"
if find "$SOURCE_ROOT" -mindepth 1 -print -quit | grep -q .; then
  source_state="private_root_populated"
fi

package_set_digest=$(package_set_fingerprint)
package_content_digest=$(package_content_fingerprint)
[ "$(tr -d '\r\n' < "$PACKAGE_MARKER")" = "$package_content_digest" ] || fail \
  "installed environment content changed during bootstrap; recreate the Codespace"

SANDBOX_INPUT_DIGEST="$input_digest" \
SANDBOX_IMAGE_DIGEST="sha256:$image_digest" \
SANDBOX_PACKAGE_SET_DIGEST="$package_set_digest" \
SANDBOX_PACKAGE_CONTENT_DIGEST="$package_content_digest" \
SANDBOX_SOURCE_STATE="$source_state" "$CONTAINER_PYTHON" -S - <<'PY'
from __future__ import annotations

import json
import os

print(
    json.dumps(
        {
            "schema": "dutchbay.audit_review_sandbox_bootstrap.v1",
            "status": "PASS",
            "environment": "github_codespaces",
            "python": "3.12",
            "dependency_input_sha256": os.environ["SANDBOX_INPUT_DIGEST"],
            "devcontainer_image_digest": os.environ["SANDBOX_IMAGE_DIGEST"],
            "installed_distribution_set_sha256": os.environ[
                "SANDBOX_PACKAGE_SET_DIGEST"
            ],
            "installed_environment_content_sha256": os.environ[
                "SANDBOX_PACKAGE_CONTENT_DIGEST"
            ],
            "p03_source_state": os.environ["SANDBOX_SOURCE_STATE"],
            "network_boundary": "creator_private_codespace_outbound_egress_available",
            "completion_authorized": False,
            "release_status": "HOLD",
        },
        sort_keys=True,
    )
)
PY
