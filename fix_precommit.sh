#!/bin/bash
# Retired unsafe Sprint-era automatic formatter/staging utility.
# Preserve the old entrypoint as a fail-closed diagnostic rather than silently
# executing a different command on a caller's worktree.
printf '%s\n' 'STOP: legacy formatter utility retired. Use the canonical pre-commit configuration on a fresh lease-bound exact allowlist; inspect any mutations and reconcile before testing or staging.' >&2
exit 1
