#!/usr/bin/env bash

# Create the disposable #1110 Codespace without the CLI's eager SSH-status
# option, then wait boundedly for the repository-owned transport.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly DISPLAY_NAME="DutchBay 1110 independent review"
readonly READY_COMMAND="/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py 5 /run/dutchbay-sshd-runtime.ready"
readonly POLL_SECONDS=5
readonly MAX_TRANSPORT_TIMEOUT_SECONDS=300
readonly PROCESS_CLEANUP_TIMEOUT_SECONDS=2
# A cold authenticated tunnel can complete just after 10 seconds.
readonly REMOTE_PROBE_ATTEMPT_TIMEOUT_SECONDS=30
readonly TRANSPORT_TIMEOUT_SECONDS="${DUTCHBAY_CODESPACE_TRANSPORT_TIMEOUT_SECONDS:-300}"
readonly GOVERNED_VENV="${DUTCHBAY_VENV:-/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv}"
readonly GOVERNED_PYTHON="$GOVERNED_VENV/bin/python"
readonly CREATE_LOCK="/tmp/dutchbay-1110-codespace-create.lock"
create_lock_held="false"
codespace_name=""

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

release_create_lock() {
  local exit_status=$?
  if [ "$create_lock_held" = "true" ]; then
    if ! rmdir -- "$CREATE_LOCK"; then
      printf '%s\n' \
        "ERROR: create lock cleanup failed: $CREATE_LOCK" >&2
      return 2
    fi
  elif [ "$create_lock_held" = "unresolved" ]; then
    umask 077
    printf 'codespace_name=%s\nreason=local_helper_cleanup_unresolved\n' \
      "$codespace_name" > "$CREATE_LOCK/UNRESOLVED" || true
    printf '%s\n' \
      "ERROR: retaining unresolved create lock: $CREATE_LOCK" >&2
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
  "$REMOTE_PROBE_ATTEMPT_TIMEOUT_SECONDS" \
  "$PROCESS_CLEANUP_TIMEOUT_SECONDS" \
  "$codespace_name" "$READY_COMMAND" <<'PY'
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

timeout = float(sys.argv[1])
poll_seconds = float(sys.argv[2])
attempt_timeout_seconds = float(sys.argv[3])
cleanup_budget = min(float(sys.argv[4]), timeout * 0.25)
overall_deadline = time.monotonic() + timeout
attempt_deadline = overall_deadline - cleanup_budget
command = ["gh", "codespace", "ssh", "-c", sys.argv[5], sys.argv[6]]


def process_group_is_absent(process: subprocess.Popen[bytes]) -> bool:
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def signal_process_group(
    process: subprocess.Popen[bytes], signal_number: int
) -> None:
    try:
        os.killpg(process.pid, signal_number)
    except ProcessLookupError:
        return
    except PermissionError:
        if process.poll() is not None and process_group_is_absent(process):
            return
        if process.poll() is not None:
            raise RuntimeError("transport probe process group could not be signalled")
        try:
            process.send_signal(signal_number)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            raise RuntimeError(
                "transport probe child could not be signalled"
            ) from exc


def wait_for_process_group_absence(
    process: subprocess.Popen[bytes], deadline: float
) -> bool:
    while not process_group_is_absent(process):
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        time.sleep(min(0.02, remaining))
    return True


def stop_process_group(process: subprocess.Popen[bytes]) -> None:
    cleanup_deadline = min(
        overall_deadline,
        time.monotonic() + cleanup_budget,
    )
    term_deadline = min(
        cleanup_deadline,
        time.monotonic() + cleanup_budget / 2,
    )
    signal_process_group(process, signal.SIGTERM)
    if not wait_for_process_group_absence(process, term_deadline):
        signal_process_group(process, signal.SIGKILL)
    remaining = cleanup_deadline - time.monotonic()
    if remaining <= 0.0:
        raise RuntimeError("transport probe child cleanup deadline expired")
    try:
        process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("transport probe child could not be reaped") from exc
    if not wait_for_process_group_absence(process, cleanup_deadline):
        raise RuntimeError("transport probe process group could not be reaped")


def controlled_signal(signum: int, _frame: object) -> None:
    raise SystemExit(128 + signum)


for handled_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    signal.signal(handled_signal, controlled_signal)


with open(os.devnull, "wb") as sink:
    while (remaining := attempt_deadline - time.monotonic()) > 0:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=sink,
            start_new_session=True,
        )
        try:
            return_code = process.wait(
                timeout=min(attempt_timeout_seconds, remaining)
            )
        except subprocess.TimeoutExpired:
            try:
                stop_process_group(process)
            except RuntimeError as exc:
                print(
                    f"ERROR: transport probe cleanup unresolved: {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(125) from exc
            return_code = 124
        except BaseException:
            try:
                stop_process_group(process)
            except RuntimeError as exc:
                print(
                    f"ERROR: transport probe cleanup unresolved: {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(125) from exc
            raise
        if not process_group_is_absent(process):
            try:
                stop_process_group(process)
            except RuntimeError as exc:
                print(
                    f"ERROR: transport probe cleanup unresolved: {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(125) from exc
        if return_code == 0:
            raise SystemExit(0)
        remaining = attempt_deadline - time.monotonic()
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
  rmdir -- "$CREATE_LOCK" || fail \
    "create lock release failed; inspect or delete: $codespace_name"
  create_lock_held="false"
  trap - EXIT
  printf '%s\n' "$codespace_name"
  exit 0
else
  probe_status=$?
fi

if [ "$probe_status" -eq 125 ]; then
  create_lock_held="unresolved"
  fail "Codespace transport helper cleanup was not proved; inspect lock and candidate: $codespace_name"
fi
fail "Codespace transport did not become ready; inspect or delete: $codespace_name"
