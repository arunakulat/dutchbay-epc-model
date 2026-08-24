#!/usr/bin/env bash

# Generate Codespace-unique host keys at container runtime, validate the
# effective policy, and optionally start the SSH transport.

set -euo pipefail

readonly SSHD_READY_MARKER="/run/dutchbay-sshd-runtime.ready"
readonly SSHD_READY_VALUE="sshd_ready_before_audit_bootstrap"

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
/usr/bin/flock --exclusive 9
/usr/bin/install -d -m 0755 /run/sshd
/usr/bin/ssh-keygen -A
/usr/sbin/sshd -t

if [ "$mode" = "--start" ]; then
  /etc/init.d/ssh start
  /usr/local/bin/python3.12 -S \
    /usr/local/lib/dutchbay/sshd_readiness.py 15
  marker_tmp=$(/usr/bin/mktemp "$SSHD_READY_MARKER.XXXXXX")
  printf '%s\n' "$SSHD_READY_VALUE" > "$marker_tmp"
  chmod 0444 "$marker_tmp"
  mv -- "$marker_tmp" "$SSHD_READY_MARKER"
fi
