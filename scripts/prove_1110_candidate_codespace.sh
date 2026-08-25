#!/usr/bin/env bash

# Prove one exact, P03-empty topic-branch candidate in real GitHub Codespaces.
# This disposable pre-merge control is separate from the protected-main review
# environment used for P02/P03 work.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly GOVERNED_VENV="${DUTCHBAY_VENV:-/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv}"
readonly GOVERNED_PYTHON="$GOVERNED_VENV/bin/python"
readonly READY_COMMAND="/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py 5 /run/dutchbay-sshd-runtime.ready"
readonly CREATE_LOCK="/tmp/dutchbay-1110-candidate-codespace.lock"
readonly POLL_SECONDS=5
readonly TRANSPORT_TIMEOUT_SECONDS=300
readonly SHUTDOWN_TIMEOUT_SECONDS=120
readonly REMOTE_REPO="/workspaces/dutchbay-epc-model"
readonly REMOTE_SOURCE_ROOT="/workspaces/.dutchbay-private/p03/sources"
readonly REMOTE_SMOKE_ROOT="/workspaces/.dutchbay-private/transport-smoke"
readonly REMOTE_SMOKE_PATH="$REMOTE_SMOKE_ROOT/candidate-devcontainer.json"

codespace_name=""
display_name=""
create_lock_held="false"
codespace_created="false"

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

verify_api_identity() {
  local branch=$1
  local identity_json
  identity_json=$(codespace_identity)
  jq -e \
    --arg name "$codespace_name" \
    --arg display "$display_name" \
    --arg repository "$REPOSITORY" \
    --arg branch "$branch" \
    '.name == $name
      and .display_name == $display
      and .repository.full_name == $repository
      and .git_status.ref == $branch' \
    <<< "$identity_json" >/dev/null \
    || fail "candidate Codespace API identity differs"
}

cleanup() {
  local exit_status=$?
  trap - EXIT
  if [ "$codespace_created" = "true" ]; then
    if [ -n "$codespace_name" ] \
      && [[ "$codespace_name" =~ ^[A-Za-z0-9_-]+$ ]]; then
      if ! gh codespace delete -c "$codespace_name" --force; then
        printf 'ERROR: exact candidate Codespace deletion failed: %s\n' \
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
    "bash -se -- $branch $expected_sha" <<'REMOTE_VERIFY'
set -euo pipefail
readonly expected_branch=$1
readonly expected_sha=$2
readonly repo_root="/workspaces/dutchbay-epc-model"
readonly source_root="/workspaces/.dutchbay-private/p03/sources"
readonly smoke_root="/workspaces/.dutchbay-private/transport-smoke"
cd "$repo_root"
test "$(id -un)" = vscode
test "$CODESPACES" = true
test "$DUTCHBAY_VENV" = /workspaces/.dutchbay-audit-review-venv
test "$DUTCHBAY_P03_SOURCE_ROOT" = "$source_root"
test "$PYTHONPATH" = "$repo_root"
test "$(git branch --show-current)" = "$expected_branch"
test "$(git rev-parse HEAD)" = "$expected_sha"
test -z "$(git status --porcelain=v1)"
test -d "$source_root"
test ! -L "$source_root"
test "$(realpath -e "$source_root")" = "$source_root"
test -z "$(find "$source_root" -mindepth 1 -print -quit)"
test -d "$smoke_root"
test ! -L "$smoke_root"
test "$(realpath -e "$smoke_root")" = "$smoke_root"
test -z "$(find "$smoke_root" -mindepth 1 -print -quit)"
/usr/local/bin/python3.12 -S /usr/local/lib/dutchbay/sshd_readiness.py \
  5 /run/dutchbay-sshd-runtime.ready
bash .devcontainer/attest_audit_review_sshd.sh >/dev/null
REMOTE_VERIFY
}

run_copy_smoke() {
  gh codespace cp --expand -c "$codespace_name" \
    ".devcontainer/devcontainer.json" \
    "remote:$REMOTE_SMOKE_PATH"
  gh codespace ssh -c "$codespace_name" "bash -se" <<'REMOTE_COPY'
set -euo pipefail
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
[ -z "$(git status --porcelain=v1)" ] || fail \
  "local candidate checkout must be clean"

remote_sha=$(git ls-remote --heads origin "refs/heads/$CANDIDATE_BRANCH" \
  | awk 'NR == 1 {print $1}')
[ "$remote_sha" = "$EXPECTED_SHA" ] || fail \
  "remote candidate branch does not equal the expected SHA"

display_name="DutchBay 1110 candidate ${EXPECTED_SHA:0:12}"
existing_json=$(list_codespaces)
existing_count=$(jq --arg display "$display_name" --arg repository "$REPOSITORY" \
  '[.[].codespaces[] | select(.display_name == $display and .repository.full_name == $repository)] | length' \
  <<< "$existing_json")
[ "$existing_count" -eq 0 ] || fail \
  "a candidate Codespace with the exact display name already exists"

mkdir -- "$CREATE_LOCK" || fail \
  "another local #1110 candidate Codespace proof is active or left a stale lock"
create_lock_held="true"

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
codespace_created="true"

wait_for_transport || fail "candidate Codespace SSH transport did not become ready"
verify_api_identity "$CANDIDATE_BRANCH"
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

jq -n \
  --arg branch "$CANDIDATE_BRANCH" \
  --arg sha "$EXPECTED_SHA" \
  '{
    schema: "dutchbay.audit_review_candidate_codespace.v1",
    status: "PASS",
    candidate_branch: $branch,
    candidate_sha: $sha,
    api_identity: "matched",
    checkout: "clean_exact_head",
    p03_source_state: "private_root_empty_p03_not_executed",
    authenticated_codespaces_tunnel: "passed",
    copy_transport: "passed",
    stop_resume_recovery: "passed",
    ssh_attestation: "passed_before_and_after_resume",
    completion_authorized: false,
    release_status: "HOLD"
  }'
