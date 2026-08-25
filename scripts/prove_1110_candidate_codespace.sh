#!/usr/bin/env bash

# Prove one exact, P03-empty topic-branch candidate in real GitHub Codespaces.
# This disposable pre-merge control is separate from the protected-main review
# environment used for P02/P03 work.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly GOVERNED_VENV="${DUTCHBAY_VENV:-/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv}"
readonly GOVERNED_PYTHON="$GOVERNED_VENV/bin/python"
readonly READY_COMMAND="/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py 5 /run/dutchbay-sshd-runtime.ready && test -f /workspaces/.dutchbay-private/bootstrap-receipt.json"
readonly CREATE_LOCK="/tmp/dutchbay-1110-candidate-codespace.lock"
readonly POLL_SECONDS=5
readonly TRANSPORT_TIMEOUT_SECONDS=300
readonly SHUTDOWN_TIMEOUT_SECONDS=120
readonly DELETION_TIMEOUT_SECONDS=120
readonly AMBIGUOUS_CREATE_RECOVERY_TIMEOUT_SECONDS=120
readonly REMOTE_REPO="/workspaces/dutchbay-epc-model"
readonly REMOTE_SOURCE_ROOT="/workspaces/.dutchbay-private/p03/sources"
readonly REMOTE_SMOKE_ROOT="/workspaces/.dutchbay-private/transport-smoke"
readonly REMOTE_SMOKE_PATH="$REMOTE_SMOKE_ROOT/candidate-devcontainer.json"
codespace_name=""
display_name=""
create_lock_held="false"
codespace_created="false"
creation_pending="false"
candidate_branch=""
run_nonce=""

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

list_codespaces() {
  gh api --paginate --slurp \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/user/codespaces?per_page=100"
}

codespace_identity() {
  gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/user/codespaces/$codespace_name"
}

api_identity_matches() {
  local branch=$1
  local identity_json
  identity_json=$(codespace_identity) || return 2
  jq -e \
    --arg name "$codespace_name" \
    --arg display "$display_name" \
    --arg repository "$REPOSITORY" \
    --arg branch "$branch" \
    '.name == $name
      and .display_name == $display
      and .repository.full_name == $repository
      and .git_status.ref == $branch' \
    <<< "$identity_json" >/dev/null || return 1
}

verify_api_identity() {
  local branch=$1
  local identity_status
  if api_identity_matches "$branch"; then
    return 0
  else
    identity_status=$?
  fi
  if [ "$identity_status" -eq 2 ]; then
    fail "candidate Codespace API identity could not be determined"
  fi
  fail "candidate Codespace API identity differs"
}

candidate_is_absent() {
  local codespaces_json
  codespaces_json=$(list_codespaces) || return 2
  jq -e \
    'type == "array"
      and length > 0
      and all(.[]; type == "object" and (.codespaces | type == "array"))' \
    <<< "$codespaces_json" >/dev/null || return 2
  jq -e --arg name "$codespace_name" \
    '[.[].codespaces[] | select(.name == $name)] | length == 0' \
    <<< "$codespaces_json" >/dev/null
}

wait_for_candidate_absence() {
  local absence_status
  local deletion_deadline=$((SECONDS + DELETION_TIMEOUT_SECONDS))
  while [ "$SECONDS" -lt "$deletion_deadline" ]; do
    if candidate_is_absent; then
      return 0
    else
      absence_status=$?
    fi
    [ "$absence_status" -eq 1 ] || return 2
    sleep "$POLL_SECONDS"
  done
  if candidate_is_absent; then
    return 0
  else
    absence_status=$?
  fi
  [ "$absence_status" -eq 1 ] || return 2
  return 1
}

delete_candidate_and_confirm_absent() {
  local branch=$1
  verify_api_identity "$branch"
  gh codespace delete -c "$codespace_name" --force
  wait_for_candidate_absence || fail \
    "exact candidate Codespace deletion was not API-confirmed"
  codespace_created="false"
}

recover_unique_pending_candidate_once() {
  local codespaces_json
  local matching_count
  local recovered_name
  codespaces_json=$(list_codespaces) || return 2
  jq -e \
    'type == "array"
      and length > 0
      and all(.[]; type == "object" and (.codespaces | type == "array"))' \
    <<< "$codespaces_json" >/dev/null || return 2
  matching_count=$(
    jq --arg display "$display_name" \
      --arg repository "$REPOSITORY" \
      --arg branch "$candidate_branch" \
      '[.[].codespaces[]
        | select(.display_name == $display
          and .repository.full_name == $repository
          and .git_status.ref == $branch)] | length' \
      <<< "$codespaces_json"
  ) || return 2
  case "$matching_count" in
    0) return 1 ;;
    1) ;;
    *) return 2 ;;
  esac
  recovered_name=$(
    jq -r --arg display "$display_name" \
      --arg repository "$REPOSITORY" \
      --arg branch "$candidate_branch" \
      '.[].codespaces[]
        | select(.display_name == $display
          and .repository.full_name == $repository
          and .git_status.ref == $branch)
        | .name' \
      <<< "$codespaces_json"
  ) || return 2
  [[ "$recovered_name" =~ ^[A-Za-z0-9_-]+$ ]] || return 2
  codespace_name=$recovered_name
  codespace_created="true"
  creation_pending="false"
}

recover_pending_candidate_boundedly() {
  local recovery_status
  local recovery_deadline=$((SECONDS + AMBIGUOUS_CREATE_RECOVERY_TIMEOUT_SECONDS))
  while [ "$SECONDS" -lt "$recovery_deadline" ]; do
    if recover_unique_pending_candidate_once; then
      return 0
    else
      recovery_status=$?
    fi
    [ "$recovery_status" -eq 1 ] || return 2
    sleep "$POLL_SECONDS"
  done
  if recover_unique_pending_candidate_once; then
    return 0
  else
    recovery_status=$?
  fi
  [ "$recovery_status" -eq 1 ] || return 2
  return 1
}

cleanup() {
  local exit_status=$?
  local recovery_status
  trap - EXIT
  if [ "$creation_pending" = "true" ]; then
    if recover_pending_candidate_boundedly; then
      :
    else
      recovery_status=$?
      if [ "$recovery_status" -eq 2 ]; then
        printf 'ERROR: ambiguous candidate creation could not be recovered safely\n' \
          >&2
        exit_status=2
      fi
      creation_pending="false"
    fi
  fi
  if [ "$codespace_created" = "true" ]; then
    if [ -n "$codespace_name" ] \
      && [[ "$codespace_name" =~ ^[A-Za-z0-9_-]+$ ]]; then
      if ! api_identity_matches "$candidate_branch"; then
        printf 'ERROR: refusing candidate deletion because API identity differs: %s\n' \
          "$codespace_name" >&2
        exit_status=2
      elif ! gh codespace delete -c "$codespace_name" --force; then
        printf 'ERROR: exact candidate Codespace deletion failed: %s\n' \
          "$codespace_name" >&2
        exit_status=2
      elif ! wait_for_candidate_absence; then
        printf 'ERROR: exact candidate Codespace absence was not confirmed: %s\n' \
          "$codespace_name" >&2
        exit_status=2
      fi
    else
      printf 'ERROR: candidate Codespace name was unsafe for deletion\n' >&2
      exit_status=2
    fi
  fi
  if [ "$create_lock_held" = "true" ]; then
    if ! rmdir -- "$CREATE_LOCK"; then
      printf 'ERROR: candidate create-lock cleanup failed: %s\n' \
        "$CREATE_LOCK" >&2
      exit_status=2
    fi
  fi
  exit "$exit_status"
}
trap cleanup EXIT

wait_for_transport() {
  "$GOVERNED_PYTHON" - \
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
}

verify_remote_candidate() {
  local branch=$1
  local expected_sha=$2
  gh codespace ssh -c "$codespace_name" \
    "bash -se -- $branch $expected_sha $codespace_name" <<'REMOTE_VERIFY'
set -Eeuo pipefail
remote_error() {
  local exit_status=$?
  printf 'ERROR: remote candidate invariant failed at line %s\n' "$1" >&2
  exit "$exit_status"
}
trap 'remote_error "$LINENO"' ERR
readonly expected_branch=$1
readonly expected_sha=$2
readonly expected_codespace_name=$3
readonly repo_root="/workspaces/dutchbay-epc-model"
readonly source_root="/workspaces/.dutchbay-private/p03/sources"
readonly smoke_root="/workspaces/.dutchbay-private/transport-smoke"
readonly bootstrap_receipt="/workspaces/.dutchbay-private/bootstrap-receipt.json"
cd "$repo_root"
test "$(id -un)" = vscode
test "$CODESPACES" = true
test "$CODESPACE_NAME" = "$expected_codespace_name"
test "$DUTCHBAY_VENV" = /workspaces/.dutchbay-audit-review-venv
test "$DUTCHBAY_P03_SOURCE_ROOT" = "$source_root"
test "$PYTHONPATH" = "$repo_root"
checkout_branch=$(git branch --show-current) || exit 2
test "$checkout_branch" = "$expected_branch"
checkout_head=$(git rev-parse HEAD) || exit 2
test "$checkout_head" = "$expected_sha"
checkout_status=$(git status --porcelain=v1) || exit 2
test -z "$checkout_status"
test -d "$source_root"
test ! -L "$source_root"
test "$(realpath -e "$source_root")" = "$source_root"
source_probe=$(find "$source_root" -mindepth 1 -print -quit) || exit 2
test -z "$source_probe"
test -d "$smoke_root"
test ! -L "$smoke_root"
test "$(realpath -e "$smoke_root")" = "$smoke_root"
smoke_probe=$(find "$smoke_root" -mindepth 1 -print -quit) || exit 2
test -z "$smoke_probe"
test -f "$bootstrap_receipt"
test ! -L "$bootstrap_receipt"
test "$(realpath -e "$bootstrap_receipt")" = "$bootstrap_receipt"
test "$(stat -c '%U:%G:%a' "$bootstrap_receipt")" = vscode:vscode:400
/usr/local/bin/python3.12 -S - "$bootstrap_receipt" "$expected_sha" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

with Path(sys.argv[1]).open(encoding="utf-8") as stream:
    receipt = json.load(stream)
expected = {
    "schema": "dutchbay.audit_review_sandbox_bootstrap.v3",
    "status": "PASS",
    "environment": "github_codespaces",
    "network_boundary": "creator_private_codespace_outbound_egress_available",
    "git_commit": sys.argv[2],
    "completion_authorized": False,
    "release_status": "HOLD",
}
for key, value in expected.items():
    if receipt.get(key) != value:
        raise SystemExit(f"bootstrap receipt field differs: {key}")
PY
/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py \
  5 /run/dutchbay-sshd-runtime.ready
session_sshd_identity=$(bash .devcontainer/attest_audit_review_sshd.sh --session)
session_sshd_digest=$(
  SSHD_IDENTITY_JSON="$session_sshd_identity" /usr/local/bin/python3.12 -S -c \
    'import json, os; print(json.loads(os.environ["SSHD_IDENTITY_JSON"])["sshd_identity_sha256"])'
)
test "$(tr -d '\r\n' < /workspaces/.dutchbay-audit-review-venv/.dutchbay-sshd-identity.sha256)" = \
  "$session_sshd_digest"
REMOTE_VERIFY
}

run_copy_smoke() {
  gh codespace cp --expand -c "$codespace_name" \
    ".devcontainer/devcontainer.json" \
    "remote:$REMOTE_SMOKE_PATH"
  gh codespace ssh -c "$codespace_name" "bash -se" <<'REMOTE_COPY'
set -Eeuo pipefail
remote_copy_error() {
  local exit_status=$?
  printf 'ERROR: remote copy invariant failed at line %s\n' "$1" >&2
  exit "$exit_status"
}
trap 'remote_copy_error "$LINENO"' ERR
readonly repo_file="/workspaces/dutchbay-epc-model/.devcontainer/devcontainer.json"
readonly smoke_path="/workspaces/.dutchbay-private/transport-smoke/candidate-devcontainer.json"
test -f "$smoke_path"
test ! -L "$smoke_path"
cmp -- "$repo_file" "$smoke_path"
unlink -- "$smoke_path"
test ! -e "$smoke_path"
REMOTE_COPY
}

[ "$#" -eq 2 ] || fail "expected CANDIDATE_BRANCH and EXPECTED_SHA"
readonly CANDIDATE_BRANCH=$1
readonly EXPECTED_SHA=$2
candidate_branch=$CANDIDATE_BRANCH
[[ "$CANDIDATE_BRANCH" =~ ^codex/[A-Za-z0-9._/-]+$ ]] \
  || fail "candidate branch must be an allowlisted codex/* branch"
git check-ref-format --branch "$CANDIDATE_BRANCH" >/dev/null \
  || fail "candidate branch identity is malformed"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] \
  || fail "candidate commit identity must be a full SHA-1"
command -v gh >/dev/null || fail "GitHub CLI is unavailable"
command -v jq >/dev/null || fail "jq is unavailable"
[ -x "$GOVERNED_PYTHON" ] || fail "governed Python is unavailable"
[ "${CODESPACES:-}" != "true" ] || fail \
  "candidate proof must start from the governed local host"
[ -f ".devcontainer/devcontainer.json" ] || fail \
  "run candidate proof from the DutchBay repository root"
checkout_status=$(git status --porcelain=v1) || fail \
  "local candidate checkout status could not be determined"
[ -z "$checkout_status" ] || fail \
  "local candidate checkout must be clean"

remote_sha=$(git ls-remote --heads origin "refs/heads/$CANDIDATE_BRANCH" \
  | awk 'NR == 1 {print $1}')
[ "$remote_sha" = "$EXPECTED_SHA" ] || fail \
  "remote candidate branch does not equal the expected SHA"

run_nonce=$(
  "$GOVERNED_PYTHON" -S -c \
    'import secrets; print(secrets.token_hex(8))'
) || fail "candidate run nonce could not be generated"
[[ "$run_nonce" =~ ^[0-9a-f]{16}$ ]] || fail \
  "candidate run nonce is malformed"
display_name="DB1110-${EXPECTED_SHA:0:12}-$run_nonce"
[ "${#display_name}" -le 48 ] || fail \
  "candidate display name exceeds the GitHub Codespaces limit"
existing_json=$(list_codespaces)
existing_count=$(jq --arg display "$display_name" --arg repository "$REPOSITORY" \
  '[.[].codespaces[] | select(.display_name == $display and .repository.full_name == $repository)] | length' \
  <<< "$existing_json")
[ "$existing_count" -eq 0 ] || fail \
  "a candidate Codespace with the exact display name already exists"

mkdir -- "$CREATE_LOCK" || fail \
  "another local #1110 candidate Codespace proof is active or left a stale lock"
create_lock_held="true"

creation_pending="true"
codespace_name=$(gh codespace create \
  -R "$REPOSITORY" \
  -b "$CANDIDATE_BRANCH" \
  -d "$display_name" \
  -l SouthEastAsia \
  -m standardLinux32gb \
  --idle-timeout 30m \
  --retention-period 24h)
[[ "$codespace_name" =~ ^[A-Za-z0-9_-]+$ ]] \
  || fail "created candidate Codespace name is malformed"
verify_api_identity "$CANDIDATE_BRANCH"
codespace_created="true"
creation_pending="false"

wait_for_transport || fail "candidate Codespace SSH transport did not become ready"
verify_remote_candidate "$CANDIDATE_BRANCH" "$EXPECTED_SHA"
run_copy_smoke
before_marker=$(gh codespace ssh -c "$codespace_name" \
  "stat -c '%i:%y' /run/dutchbay-sshd-runtime.ready")

gh codespace stop -c "$codespace_name"
shutdown_deadline=$((SECONDS + SHUTDOWN_TIMEOUT_SECONDS))
while [ "$SECONDS" -lt "$shutdown_deadline" ]; do
  [ "$(codespace_identity | jq -r .state)" = "Shutdown" ] && break
  sleep "$POLL_SECONDS"
done
[ "$(codespace_identity | jq -r .state)" = "Shutdown" ] || fail \
  "candidate Codespace did not reach Shutdown boundedly"

wait_for_transport || fail "candidate Codespace did not resume through SSH"
verify_api_identity "$CANDIDATE_BRANCH"
verify_remote_candidate "$CANDIDATE_BRANCH" "$EXPECTED_SHA"
after_marker=$(gh codespace ssh -c "$codespace_name" \
  "stat -c '%i:%y' /run/dutchbay-sshd-runtime.ready")
[ "$before_marker" != "$after_marker" ] || fail \
  "candidate Codespace post-start marker was not refreshed"

readonly completed_codespace_name=$codespace_name
delete_candidate_and_confirm_absent "$CANDIDATE_BRANCH"
rmdir -- "$CREATE_LOCK"
create_lock_held="false"
trap - EXIT

jq -n \
  --arg codespace_name "$completed_codespace_name" \
  --arg display_name "$display_name" \
  --arg run_nonce "$run_nonce" \
  --arg branch "$CANDIDATE_BRANCH" \
  --arg sha "$EXPECTED_SHA" \
  '{
    schema: "dutchbay.audit_review_candidate_codespace.v1",
    status: "PASS",
    candidate_codespace_name: $codespace_name,
    candidate_display_name: $display_name,
    candidate_run_nonce: $run_nonce,
    candidate_branch: $branch,
    candidate_sha: $sha,
    api_identity: "matched",
    checkout: "clean_exact_head",
    p03_source_state: "private_root_empty_p03_not_executed",
    authenticated_codespaces_tunnel: "passed",
    copy_transport: "passed",
    stop_resume_recovery: "passed",
    ssh_attestation: "passed_before_and_after_resume",
    deletion: "confirmed_absent_via_codespaces_api",
    create_lock: "released_before_receipt",
    completion_authorized: false,
    release_status: "HOLD"
  }'
