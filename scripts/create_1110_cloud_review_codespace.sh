#!/usr/bin/env bash

# Create the disposable #1110 Codespace without the CLI's eager SSH-status
# option, then wait boundedly for the repository-owned transport.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly DISPLAY_NAME="DutchBay 1110 independent review"
readonly READY_COMMAND="/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py 5 /run/dutchbay-sshd-pre-lifecycle.ready"
readonly POLL_SECONDS=5
readonly MAX_TRANSPORT_TIMEOUT_SECONDS=300
readonly TRANSPORT_TIMEOUT_SECONDS="${DUTCHBAY_CODESPACE_TRANSPORT_TIMEOUT_SECONDS:-300}"
readonly GOVERNED_VENV="${DUTCHBAY_VENV:-/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv}"
readonly GOVERNED_PYTHON="$GOVERNED_VENV/bin/python"
readonly CREATE_LOCK="/tmp/dutchbay-1110-codespace-create.lock"
create_lock_held="false"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

release_create_lock() {
  local exit_status=$?
  if [ "$create_lock_held" = "true" ]; then
    rmdir -- "$CREATE_LOCK" || printf '%s\n' \
      "ERROR: create lock cleanup failed: $CREATE_LOCK" >&2
  fi
  return "$exit_status"
}

list_review_codespaces() {
  gh api --paginate --slurp \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/user/codespaces?per_page=100"
}

command -v gh >/dev/null || fail "GitHub CLI is unavailable"
command -v jq >/dev/null || fail "jq is unavailable"
[ -x "$GOVERNED_PYTHON" ] || fail "governed Python is unavailable"
case "$TRANSPORT_TIMEOUT_SECONDS" in
  ''|*[!0-9]*) fail "transport timeout must be a positive integer" ;;
esac
[ "$TRANSPORT_TIMEOUT_SECONDS" -ge 1 ] \
  && [ "$TRANSPORT_TIMEOUT_SECONDS" -le "$MAX_TRANSPORT_TIMEOUT_SECONDS" ] \
  || fail "transport timeout must be between 1 and 300 seconds"
mkdir -- "$CREATE_LOCK" || fail \
  "another local #1110 Codespace creation is active or left a stale lock"
create_lock_held="true"
trap release_create_lock EXIT

existing_json=$(list_review_codespaces)
existing_count=$(
  jq --arg display "$DISPLAY_NAME" --arg repository "$REPOSITORY" \
    '[.[].codespaces[] | select(.display_name == $display and .repository.full_name == $repository)] | length' \
    <<< "$existing_json"
)
[ "$existing_count" -eq 0 ] || fail \
  "a Codespace with the governed display name already exists"

codespace_name=$(gh codespace create \
  -R "$REPOSITORY" \
  -b main \
  -d "$DISPLAY_NAME" \
  -l SouthEastAsia \
  -m standardLinux32gb \
  --idle-timeout 30m \
  --retention-period 72h)
case "$codespace_name" in
  ''|*[!A-Za-z0-9_-]*) fail "created Codespace name is malformed" ;;
esac

if "$GOVERNED_PYTHON" - \
  "$TRANSPORT_TIMEOUT_SECONDS" "$POLL_SECONDS" \
  "$codespace_name" "$READY_COMMAND" <<'PY'
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

timeout = float(sys.argv[1])
poll_seconds = float(sys.argv[2])
cleanup_budget = min(1.0, timeout * 0.25)
deadline = time.monotonic() + timeout - cleanup_budget
command = ["gh", "codespace", "ssh", "-c", sys.argv[3], sys.argv[4]]


def stop_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=cleanup_budget / 2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=cleanup_budget / 2)
    except subprocess.TimeoutExpired:
        pass


with open(os.devnull, "wb") as sink:
    while (remaining := deadline - time.monotonic()) > 0:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=sink,
            start_new_session=True,
        )
        try:
            return_code = process.wait(timeout=min(10.0, remaining))
        except subprocess.TimeoutExpired:
            stop_process_group(process)
            return_code = 124
        if return_code == 0:
            raise SystemExit(0)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(poll_seconds, remaining))
raise SystemExit(124)
PY
then
  final_json=$(list_review_codespaces)
  final_count=$(
    jq --arg display "$DISPLAY_NAME" --arg repository "$REPOSITORY" \
      '[.[].codespaces[] | select(.display_name == $display and .repository.full_name == $repository)] | length' \
      <<< "$final_json"
  )
  final_name=$(
    jq -r --arg display "$DISPLAY_NAME" --arg repository "$REPOSITORY" \
      '[.[].codespaces[] | select(.display_name == $display and .repository.full_name == $repository)] | if length == 1 then .[0].name else "" end' \
      <<< "$final_json"
  )
  [ "$final_count" -eq 1 ] && [ "$final_name" = "$codespace_name" ] || fail \
    "post-create Codespace identity/collision check failed; inspect or delete: $codespace_name"
  printf '%s\n' "$codespace_name"
  exit 0
fi

fail "Codespace transport did not become ready; inspect or delete: $codespace_name"
