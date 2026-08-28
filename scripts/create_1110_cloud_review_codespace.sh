#!/usr/bin/env bash

# Create the disposable #1110 Codespace without the CLI's eager SSH-status
# option, then wait boundedly for the repository-owned transport.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly DISPLAY_NAME="DutchBay 1110 independent review"
readonly EXPECTED_REF="main"
readonly READY_COMMAND="/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py 5 /run/dutchbay-sshd-runtime.ready"
readonly POLL_SECONDS=5
readonly API_COMMAND_TIMEOUT_SECONDS=30
readonly CREATE_COMMAND_TIMEOUT_SECONDS=300
readonly AMBIGUOUS_CREATE_RECOVERY_TIMEOUT_SECONDS=120
readonly MAX_TRANSPORT_TIMEOUT_SECONDS=300
readonly PROCESS_CLEANUP_TIMEOUT_SECONDS=2
# A cold authenticated tunnel can complete just after 10 seconds.
readonly REMOTE_PROBE_ATTEMPT_TIMEOUT_SECONDS=30
readonly TRANSPORT_TIMEOUT_SECONDS="${DUTCHBAY_CODESPACE_TRANSPORT_TIMEOUT_SECONDS:-300}"
readonly GOVERNED_VENV="${DUTCHBAY_VENV:-/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv}"
readonly GOVERNED_PYTHON="$GOVERNED_VENV/bin/python"
readonly CREATE_LOCK="/tmp/dutchbay-1110-codespace-create.lock"
readonly LOCAL_CLEANUP_MARKER="$CREATE_LOCK/LOCAL_CLEANUP_UNRESOLVED"
create_lock_held="false"
codespace_name=""
create_phase_started="false"
creation_pending="false"
unresolved_reason=""

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

mark_local_cleanup_unresolved() {
  local status=$1
  local reason=$2
  if [ "$status" -eq 125 ] && [ -d "$CREATE_LOCK" ]; then
    umask 077
    printf 'reason=%s\n' "$reason" > "$LOCAL_CLEANUP_MARKER" || true
  fi
}

bounded_command() {
  local timeout_seconds=$1
  local command_status
  shift
  if "$GOVERNED_PYTHON" -S -c '
import os
import signal
import subprocess
import sys
import time

timeout = float(sys.argv[1])
cleanup_budget = min(float(sys.argv[2]), timeout * 0.25)
overall_deadline = time.monotonic() + timeout
command_deadline = overall_deadline - cleanup_budget
process = subprocess.Popen(sys.argv[3:], start_new_session=True)


def process_group_is_absent() -> bool:
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def signal_process_group(signal_number: int) -> None:
    try:
        os.killpg(process.pid, signal_number)
    except ProcessLookupError:
        return
    except PermissionError:
        if process.poll() is not None and process_group_is_absent():
            return
        if process.poll() is not None:
            raise RuntimeError("create process group could not be signalled")
        try:
            process.send_signal(signal_number)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            raise RuntimeError("create child could not be signalled") from exc


def wait_for_process_group_absence(deadline: float) -> bool:
    while not process_group_is_absent():
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        time.sleep(min(0.02, remaining))
    return True


def stop_process_group() -> None:
    cleanup_deadline = min(
        overall_deadline,
        time.monotonic() + cleanup_budget,
    )
    term_deadline = min(
        cleanup_deadline,
        time.monotonic() + cleanup_budget / 2,
    )
    signal_process_group(signal.SIGTERM)
    if not wait_for_process_group_absence(term_deadline):
        signal_process_group(signal.SIGKILL)
    remaining = cleanup_deadline - time.monotonic()
    if remaining <= 0.0:
        raise RuntimeError("create child cleanup deadline expired")
    try:
        process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("create child could not be reaped") from exc
    if not wait_for_process_group_absence(cleanup_deadline):
        raise RuntimeError("create process group could not be reaped")


def controlled_signal(signum: int, _frame: object) -> None:
    raise SystemExit(128 + signum)


for handled_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    signal.signal(handled_signal, controlled_signal)

try:
    return_code = process.wait(
        timeout=max(0.0, command_deadline - time.monotonic())
    )
except subprocess.TimeoutExpired:
    try:
        stop_process_group()
    except RuntimeError as exc:
        print(f"ERROR: create cleanup unresolved: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
    raise SystemExit(124)
except BaseException:
    try:
        stop_process_group()
    except RuntimeError as exc:
        print(f"ERROR: create cleanup unresolved: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
    raise
if not process_group_is_absent():
    try:
        stop_process_group()
    except RuntimeError as exc:
        print(f"ERROR: create cleanup unresolved: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
raise SystemExit(return_code)
' "$timeout_seconds" "$PROCESS_CLEANUP_TIMEOUT_SECONDS" "$@"; then
    return 0
  else
    command_status=$?
  fi
  mark_local_cleanup_unresolved "$command_status" "bounded_create_command"
  return "$command_status"
}

release_create_lock() {
  local exit_status=$?
  local recovery_status
  trap - EXIT
  if [ "$creation_pending" = "true" ]; then
    if recover_pending_review_codespace_boundedly; then
      unresolved_reason="creation_recovered_after_interrupted_command"
    else
      recovery_status=$?
      case "$recovery_status" in
        1) unresolved_reason="creation_remained_ambiguous_after_recovery_deadline" ;;
        2) unresolved_reason="creation_identity_was_not_unique_or_safe" ;;
        125) unresolved_reason="creation_recovery_helper_cleanup_unresolved" ;;
        *) unresolved_reason="creation_recovery_api_unavailable" ;;
      esac
    fi
    create_lock_held="unresolved"
  fi
  if [ -f "$LOCAL_CLEANUP_MARKER" ]; then
    unresolved_reason="local_helper_cleanup_unresolved"
    create_lock_held="unresolved"
  elif [ "$create_phase_started" = "true" ] \
    && [ "$exit_status" -ne 0 ] \
    && [ "$create_lock_held" = "true" ]; then
    unresolved_reason="creation_workflow_incomplete"
    create_lock_held="unresolved"
  fi
  if [ "$create_lock_held" = "true" ]; then
    if ! rmdir -- "$CREATE_LOCK"; then
      printf '%s\n' \
        "ERROR: create lock cleanup failed: $CREATE_LOCK" >&2
      return 2
    fi
  elif [ "$create_lock_held" = "unresolved" ]; then
    umask 077
    printf 'display_name=%s\nrepository=%s\nref=%s\ncodespace_name=%s\nreason=%s\n' \
      "$DISPLAY_NAME" "$REPOSITORY" "$EXPECTED_REF" "$codespace_name" \
      "${unresolved_reason:-unresolved_creation_lifecycle}" \
      > "$CREATE_LOCK/UNRESOLVED" || true
    printf '%s\n' \
      "ERROR: retaining unresolved create lock: $CREATE_LOCK" >&2
  fi
  return "$exit_status"
}

list_review_codespaces() {
  local timeout_seconds=${1:-$API_COMMAND_TIMEOUT_SECONDS}
  bounded_command "$timeout_seconds" \
    gh api --paginate --slurp \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/user/codespaces?per_page=100"
}

recover_unique_review_codespace_once() {
  local timeout_seconds=${1:-$API_COMMAND_TIMEOUT_SECONDS}
  local codespaces_json
  local list_status
  local matching_count
  local recovered_name
  if codespaces_json=$(list_review_codespaces "$timeout_seconds"); then
    :
  else
    list_status=$?
    [ "$list_status" -eq 125 ] && return 125
    return 3
  fi
  jq -e \
    'type == "array"
      and length > 0
      and all(.[]; type == "object" and (.codespaces | type == "array"))' \
    <<< "$codespaces_json" >/dev/null || return 2
  matching_count=$(
    jq --arg display "$DISPLAY_NAME" \
      --arg repository "$REPOSITORY" \
      --arg ref "$EXPECTED_REF" \
      '[.[].codespaces[]
        | select(.display_name == $display
          and .repository.full_name == $repository
          and .git_status.ref == $ref)] | length' \
      <<< "$codespaces_json"
  ) || return 2
  case "$matching_count" in
    0) return 1 ;;
    1) ;;
    *) return 2 ;;
  esac
  recovered_name=$(
    jq -r --arg display "$DISPLAY_NAME" \
      --arg repository "$REPOSITORY" \
      --arg ref "$EXPECTED_REF" \
      '.[].codespaces[]
        | select(.display_name == $display
          and .repository.full_name == $repository
          and .git_status.ref == $ref)
        | .name' \
      <<< "$codespaces_json"
  ) || return 2
  [[ "$recovered_name" =~ ^[A-Za-z0-9_-]+$ ]] || return 2
  codespace_name=$recovered_name
  creation_pending="false"
}

recover_pending_review_codespace_boundedly() {
  local remaining_seconds
  local recovery_status
  local recovery_deadline=$((SECONDS + AMBIGUOUS_CREATE_RECOVERY_TIMEOUT_SECONDS))
  while [ "$SECONDS" -lt "$recovery_deadline" ]; do
    remaining_seconds=$((recovery_deadline - SECONDS))
    if recover_unique_review_codespace_once "$remaining_seconds"; then
      return 0
    else
      recovery_status=$?
    fi
    case "$recovery_status" in
      1|3) ;;
      125) return 125 ;;
      *) return 2 ;;
    esac
    [ "$SECONDS" -lt "$recovery_deadline" ] || break
    remaining_seconds=$((recovery_deadline - SECONDS))
    if [ "$remaining_seconds" -lt "$POLL_SECONDS" ]; then
      sleep "$remaining_seconds"
    else
      sleep "$POLL_SECONDS"
    fi
  done
  case "$recovery_status" in
    1) return 1 ;;
    3) return 3 ;;
    125) return 125 ;;
    *) return 2 ;;
  esac
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
jq -e \
  'type == "array"
    and length > 0
    and all(.[]; type == "object" and (.codespaces | type == "array"))' \
  <<< "$existing_json" >/dev/null || fail \
  "pre-create Codespaces API population was malformed"
existing_count=$(
  jq --arg display "$DISPLAY_NAME" --arg repository "$REPOSITORY" \
    '[.[].codespaces[] | select(.display_name == $display and .repository.full_name == $repository)] | length' \
    <<< "$existing_json"
)
[ "$existing_count" -eq 0 ] || fail \
  "a Codespace with the governed display name already exists"

create_phase_started="true"
creation_pending="true"
if create_output=$(bounded_command "$CREATE_COMMAND_TIMEOUT_SECONDS" \
  gh codespace create \
    -R "$REPOSITORY" \
    -b "$EXPECTED_REF" \
    -d "$DISPLAY_NAME" \
    -l SouthEastAsia \
    -m standardLinux32gb \
    --idle-timeout 30m \
    --retention-period 72h); then
  :
else
  create_status=$?
  fail "Codespace creation command did not complete safely (status $create_status)"
fi
case "$create_output" in
  ''|*[!A-Za-z0-9_-]*) fail "created Codespace name is malformed" ;;
esac
if recover_pending_review_codespace_boundedly; then
  :
else
  recovery_status=$?
  fail "post-create Codespace identity could not be resolved safely (status $recovery_status)"
fi
[ "$codespace_name" = "$create_output" ] || fail \
  "created Codespace output differs from API identity"

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
  expected_codespace_name=$codespace_name
  if recover_unique_review_codespace_once; then
    :
  else
    final_status=$?
    fail "post-create Codespace identity check failed (status $final_status); inspect lock"
  fi
  [ "$codespace_name" = "$expected_codespace_name" ] || fail \
    "post-create Codespace API identity differs; inspect lock"
  [ ! -f "$LOCAL_CLEANUP_MARKER" ] || fail \
    "a local create helper left unresolved cleanup state"
  rmdir -- "$CREATE_LOCK" || fail \
    "create lock release failed; inspect or delete: $codespace_name"
  create_lock_held="false"
  trap - EXIT
  printf '%s\n' "$codespace_name"
  exit 0
else
  probe_status=$?
  mark_local_cleanup_unresolved "$probe_status" "transport_probe"
fi

if [ "$probe_status" -eq 125 ]; then
  create_lock_held="unresolved"
  fail "Codespace transport helper cleanup was not proved; inspect lock and candidate: $codespace_name"
fi
fail "Codespace transport did not become ready; inspect or delete: $codespace_name"
