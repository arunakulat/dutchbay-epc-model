#!/usr/bin/env bash

# Start the SSH transport during container initialization; the governed
# creation wrapper waits for the listener before making SSH authoritative.

set -euo pipefail

/usr/local/sbin/dutchbay-sshd-start.sh --start
/usr/local/bin/python3.12 -S \
  /usr/local/lib/dutchbay/sshd_readiness.py 15
marker_tmp=$(/usr/bin/mktemp /run/dutchbay-sshd-pre-lifecycle.ready.XXXXXX)
printf '%s\n' "sshd_started_before_post_create" > "$marker_tmp"
chmod 0444 "$marker_tmp"
mv -- "$marker_tmp" /run/dutchbay-sshd-pre-lifecycle.ready

if [ "$#" -eq 0 ]; then
  set -- /usr/bin/sleep infinity
fi
exec "$@"
