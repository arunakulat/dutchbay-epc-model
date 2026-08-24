#!/usr/bin/env bash

# Emit a path-free JSON identity for the installed and effective SSH surface.

set -euo pipefail

readonly CONTAINER_PYTHON="/usr/local/bin/python3.12"
readonly SSHD_DROP_IN="/etc/ssh/sshd_config.d/00-dutchbay-audit-review.conf"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

[ -x "$CONTAINER_PYTHON" ] && [ ! -L "$CONTAINER_PYTHON" ] || fail \
  "digest-pinned container Python is unavailable"
[ -f "$SSHD_DROP_IN" ] && [ ! -L "$SSHD_DROP_IN" ] || fail \
  "controlled SSH policy is unavailable or unsafe"

effective_config=$(
  /usr/bin/sudo --non-interactive /usr/sbin/sshd -T
)
package_inventory=$(
  /usr/bin/dpkg-query --show \
    --showformat='${Package}|${Architecture}|${Status}|${Version}\n' \
    openssh-client openssh-server openssh-sftp-server \
    | LC_ALL=C /usr/bin/sort
)
package_paths=$(
  /usr/bin/dpkg-query --listfiles \
    openssh-client openssh-server openssh-sftp-server \
    | LC_ALL=C /usr/bin/sort --unique
)

expected_host_private_keys=(
  /etc/ssh/ssh_host_ecdsa_key
  /etc/ssh/ssh_host_ed25519_key
  /etc/ssh/ssh_host_rsa_key
)
shopt -s nullglob
host_private_keys=(/etc/ssh/ssh_host_*_key)
[ "${#host_private_keys[@]}" -eq "${#expected_host_private_keys[@]}" ] || fail \
  "runtime SSH host-key population differs"
for index in "${!expected_host_private_keys[@]}"; do
  [ "${host_private_keys[$index]}" = "${expected_host_private_keys[$index]}" ] \
    || fail "runtime SSH host-key algorithm population differs"
done

host_public_key_material=""
host_public_key_sidecars=""
for key in "${host_private_keys[@]}"; do
  [ -f "$key" ] && [ ! -L "$key" ] || fail \
    "runtime SSH host private key is unavailable or unsafe"
  [ -f "$key.pub" ] && [ ! -L "$key.pub" ] || fail \
    "runtime SSH host public-key sidecar is unavailable or unsafe"
  derived=$(
    /usr/bin/sudo --non-interactive /usr/bin/ssh-keygen -y -f "$key"
  )
  sidecar=$(/usr/bin/awk '{print $1 " " $2; exit}' "$key.pub")
  case "$key" in
    *_ecdsa_key) expected_algorithm="ecdsa-sha2-nistp256" ;;
    *_ed25519_key) expected_algorithm="ssh-ed25519" ;;
    *_rsa_key) expected_algorithm="ssh-rsa" ;;
    *) fail "runtime SSH host-key filename is unsupported" ;;
  esac
  [ "${derived%% *}" = "$expected_algorithm" ] || fail \
    "runtime SSH host-key filename/algorithm differs"
  [ "$derived" = "$sidecar" ] || fail \
    "runtime SSH host private/public key pair differs"
  host_public_key_material+="${host_public_key_material:+$'\n'}$derived"
  host_public_key_sidecars+="${host_public_key_sidecars:+$'\n'}$sidecar"
done

SSHD_EFFECTIVE_CONFIG="$effective_config" \
SSHD_PACKAGE_INVENTORY="$package_inventory" \
SSHD_PACKAGE_PATHS="$package_paths" \
SSHD_HOST_PUBLIC_KEY_MATERIAL="$host_public_key_material" \
SSHD_HOST_PUBLIC_KEY_SIDECARS="$host_public_key_sidecars" \
PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from audit_review_identity import build_sshd_transport_identity

identity = build_sshd_transport_identity(
    effective_config=os.environ["SSHD_EFFECTIVE_CONFIG"],
    package_inventory=os.environ["SSHD_PACKAGE_INVENTORY"],
    package_paths=[
        Path(value)
        for value in os.environ["SSHD_PACKAGE_PATHS"].splitlines()
        if value
    ],
    extra_paths=[
        Path("/etc/pam.d/sshd"),
        Path("/etc/ssh/sshd_config.d/00-dutchbay-audit-review.conf"),
        Path("/usr/local/sbin/dutchbay-ssh-entrypoint.sh"),
        Path("/usr/local/sbin/dutchbay-sshd-start.sh"),
        Path("/usr/local/lib/dutchbay/sshd_readiness.py"),
    ],
    host_public_key_material=[
        value
        for value in os.environ["SSHD_HOST_PUBLIC_KEY_MATERIAL"].splitlines()
        if value
    ],
    host_public_key_sidecars=[
        value
        for value in os.environ["SSHD_HOST_PUBLIC_KEY_SIDECARS"].splitlines()
        if value
    ],
)
print(json.dumps(identity, sort_keys=True))
PY
