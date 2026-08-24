#!/usr/bin/env bash

# Start the SSH transport during container initialization; the governed
# creation wrapper waits for the listener before making SSH authoritative.

set -euo pipefail

/usr/local/sbin/dutchbay-sshd-start.sh --start

if [ "$#" -eq 0 ]; then
  set -- /usr/bin/sleep infinity
fi
exec "$@"
