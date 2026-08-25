#!/usr/bin/env bash

# Emit a path-free JSON identity for the installed and effective SSH surface.

set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

readonly CONTAINER_PYTHON="/usr/local/bin/python3.12"
readonly SSHD_MAIN_CONFIG="/etc/ssh/sshd_config"
readonly SSHD_DROP_IN="/etc/ssh/sshd_config.d/00-dutchbay-audit-review.conf"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

bytecode_probe=$(find .devcontainer \
  \( -type d -name __pycache__ \
    -o -type f \( -name '*.pyc' -o -name '*.pyo' \) \) \
  -print -quit) || fail "repository bytecode population could not be determined"
[ -z "$bytecode_probe" ] || fail \
  "repository bytecode is executable untracked input; recreate the Codespace"

[ -x "$CONTAINER_PYTHON" ] && [ ! -L "$CONTAINER_PYTHON" ] || fail \
  "digest-pinned container Python is unavailable"
[ -f "$SSHD_MAIN_CONFIG" ] && [ ! -L "$SSHD_MAIN_CONFIG" ] || fail \
  "SSH main configuration is unavailable or unsafe"
[ -f "$SSHD_DROP_IN" ] && [ ! -L "$SSHD_DROP_IN" ] || fail \
  "controlled SSH policy is unavailable or unsafe"
[ "$#" -eq 1 ] || fail "expected --construction or --session"

case "$1" in
  --construction)
    connection_context='user=vscode,host=localhost,addr=127.0.0.1,laddr=127.0.0.1,lport=2222'
    ;;
  --session)
    [ -n "${SSH_CONNECTION:-}" ] && [ -n "${SSH_CLIENT:-}" ] || fail \
      "authenticated SSH connection context is unavailable"
    connection_context=$(
      SSH_CONNECTION_VALUE="$SSH_CONNECTION" SSH_CLIENT_VALUE="$SSH_CLIENT" \
        PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S - <<'PY'
from __future__ import annotations

import os

from audit_review_identity import build_sshd_session_connection_context

print(
    build_sshd_session_connection_context(
        os.environ["SSH_CONNECTION_VALUE"],
        os.environ["SSH_CLIENT_VALUE"],
    )
)
PY
    ) || fail "authenticated SSH connection context is unsupported"
    ;;
  *) fail "expected --construction or --session" ;;
esac

effective_config=$(
  /usr/bin/sudo --non-interactive /usr/sbin/sshd -T \
    -C "$connection_context"
)
package_inventory=$(
  /usr/bin/dpkg-query --show \
    --showformat='${Package}|${Architecture}|${Status}|${Version}\n' \
    lsof openssh-client openssh-server openssh-sftp-server \
    | LC_ALL=C /usr/bin/sort
)
package_paths=$(
  /usr/bin/dpkg-query --listfiles \
    lsof openssh-client openssh-server openssh-sftp-server \
    | LC_ALL=C /usr/bin/sort --unique
)

sshd_configuration_paths="$SSHD_MAIN_CONFIG"
shopt -s nullglob
sshd_drop_in_population=(/etc/ssh/sshd_config.d/*)
for path in "${sshd_drop_in_population[@]}"; do
  [ -f "$path" ] && [ ! -L "$path" ] || fail \
    "runtime SSH configuration population is unsafe"
  case "${path##*/}" in
    *[!A-Za-z0-9_.-]*) fail "runtime SSH configuration filename is unsafe" ;;
  esac
  sshd_configuration_paths+=$'\n'"$path"
done
printf '%s\n' "$sshd_configuration_paths" | grep -Fxq "$SSHD_DROP_IN" || fail \
  "controlled SSH policy is absent from the runtime population"

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
  host_public_key_material+="${host_public_key_material:+$'\n'}$derived"
  host_public_key_sidecars+="${host_public_key_sidecars:+$'\n'}$sidecar"
done

SSHD_EFFECTIVE_CONFIG="$effective_config" \
SSHD_PACKAGE_INVENTORY="$package_inventory" \
SSHD_PACKAGE_PATHS="$package_paths" \
SSHD_CONFIGURATION_PATHS="$sshd_configuration_paths" \
SSHD_HOST_PUBLIC_KEY_MATERIAL="$host_public_key_material" \
SSHD_HOST_PUBLIC_KEY_SIDECARS="$host_public_key_sidecars" \
PYTHONPATH="$PWD/.devcontainer" "$CONTAINER_PYTHON" -S - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from audit_review_identity import (
    build_sshd_transport_identity,
    validate_sshd_include_graph,
)

configuration_paths = [
    Path(value)
    for value in os.environ["SSHD_CONFIGURATION_PATHS"].splitlines()
    if value
]
validate_sshd_include_graph(configuration_paths[0], configuration_paths[1:])

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
        *configuration_paths,
        Path("/usr/local/share/ssh-init.sh"),
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
