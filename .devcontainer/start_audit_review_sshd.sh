#!/usr/bin/env bash

# Generate Codespace-unique host keys at container runtime, validate the
# effective policy, and optionally start the SSH transport.

set -euo pipefail

readonly SSHD_READY_MARKER="/run/dutchbay-sshd-runtime.ready"
readonly SSHD_READY_VALUE="sshd_ready_before_audit_bootstrap"
readonly LOCK_WAIT_SECONDS=30
readonly COMMAND_TIMEOUT_SECONDS=15

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

mode=${1:-}
case "$mode" in
  --prepare-only|--start) ;;
  *)
    printf 'ERROR: expected --prepare-only or --start\n' >&2
    exit 2
    ;;
esac

if [ "$(id -u)" -ne 0 ]; then
  script_path=$(realpath "$0")
  exec /usr/bin/sudo --non-interactive "$script_path" "$@"
fi

exec 9>/run/dutchbay-sshd-start.lock
/usr/bin/flock --exclusive --wait "$LOCK_WAIT_SECONDS" 9 \
  || fail "timed out waiting for the SSH startup lock"
if [ "$mode" = "--start" ] \
  && { [ -e "$SSHD_READY_MARKER" ] || [ -L "$SSHD_READY_MARKER" ]; }; then
  /usr/bin/unlink -- "$SSHD_READY_MARKER"
fi
/usr/bin/install -d -m 0755 /run/sshd
/usr/bin/timeout --signal=TERM --kill-after=2 \
  "$COMMAND_TIMEOUT_SECONDS" /usr/bin/ssh-keygen -A \
  || fail "SSH host-key preparation failed or timed out"
/usr/bin/timeout --signal=TERM --kill-after=2 \
  "$COMMAND_TIMEOUT_SECONDS" /usr/sbin/sshd -t \
  || fail "SSH configuration validation failed or timed out"

if [ "$mode" = "--start" ]; then
  /usr/bin/timeout --signal=TERM --kill-after=2 \
    "$COMMAND_TIMEOUT_SECONDS" /etc/init.d/ssh start \
    || fail "SSH service start failed or timed out"
  /usr/local/bin/python3.12 -S \
    /usr/local/lib/dutchbay/sshd_readiness.py 15
  marker_tmp=$(/usr/bin/mktemp "$SSHD_READY_MARKER.XXXXXX")
  printf '%s\n' "$SSHD_READY_VALUE" > "$marker_tmp"
  chmod 0444 "$marker_tmp"
  mv -- "$marker_tmp" "$SSHD_READY_MARKER"
fi
