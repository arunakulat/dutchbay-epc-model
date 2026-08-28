#!/usr/bin/env bash

# Run the structural #1110 verifier through an API-authenticated Codespaces
# envelope. The nested receipt remains HOLD-side structural evidence only.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly DISPLAY_NAME="DutchBay 1110 independent review"
readonly GOVERNED_VENV="${DUTCHBAY_VENV:-/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv}"
readonly GOVERNED_PYTHON="$GOVERNED_VENV/bin/python"
readonly CODESPACE_NAME="${DUTCHBAY_1110_REVIEW_CODESPACE_NAME:-}"
readonly API_TIMEOUT_SECONDS=30
readonly REMOTE_TIMEOUT_SECONDS=1800
readonly PROCESS_CLEANUP_TIMEOUT_SECONDS=2

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

bounded_command() {
  local timeout_seconds=$1
  shift
  "$GOVERNED_PYTHON" -S -c '
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
            raise RuntimeError("verification process group could not be signalled")
        try:
            process.send_signal(signal_number)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            raise RuntimeError(
                "verification child could not be signalled"
            ) from exc


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
        raise RuntimeError("verification child cleanup deadline expired")
    try:
        process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("verification child could not be reaped") from exc
    if not wait_for_process_group_absence(cleanup_deadline):
        raise RuntimeError("verification process group could not be reaped")


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
        print(f"ERROR: verification cleanup unresolved: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
    raise SystemExit(124)
except BaseException:
    try:
        stop_process_group()
    except RuntimeError as exc:
        print(f"ERROR: verification cleanup unresolved: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
    raise
if not process_group_is_absent():
    try:
        stop_process_group()
    except RuntimeError as exc:
        print(f"ERROR: verification cleanup unresolved: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
raise SystemExit(return_code)
' "$timeout_seconds" "$PROCESS_CLEANUP_TIMEOUT_SECONDS" "$@"
}

codespace_identity() {
  bounded_command "$API_TIMEOUT_SECONDS" \
    gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/user/codespaces/$CODESPACE_NAME"
}

verify_api_identity() {
  local identity_json
  identity_json=$(codespace_identity) || fail \
    "review Codespace API identity could not be determined"
  jq -e \
    --arg name "$CODESPACE_NAME" \
    --arg display "$DISPLAY_NAME" \
    --arg repository "$REPOSITORY" \
    '.name == $name
      and .display_name == $display
      and .repository.full_name == $repository
      and .git_status.ref == "main"
      and .state == "Available"' \
    <<< "$identity_json" >/dev/null || fail \
    "review Codespace API identity differs from authorization"
}

[ "${CODESPACES:-}" != "true" ] || fail \
  "outer verification must start from the governed local host"
case "$CODESPACE_NAME" in
  ''|*[!A-Za-z0-9_-]*) fail "review Codespace name is missing or malformed" ;;
esac
[ -x "$GOVERNED_PYTHON" ] || fail "governed Python is unavailable"
command -v gh >/dev/null || fail "GitHub CLI is unavailable"
command -v jq >/dev/null || fail "jq is unavailable"
[ "$(git branch --show-current)" = "main" ] || fail \
  "outer verification must run from protected main"
checkout_status=$(git status --porcelain=v1) || fail \
  "local checkout status could not be determined"
[ -z "$checkout_status" ] || fail "local protected-main checkout must be clean"
bounded_command "$API_TIMEOUT_SECONDS" git fetch --prune origin main
expected_main_sha=$(git rev-parse refs/remotes/origin/main) || fail \
  "origin/main identity could not be determined"
[ "$(git rev-parse HEAD)" = "$expected_main_sha" ] || fail \
  "local protected main is not synchronized with origin/main"

verify_api_identity
verification_receipt=$(bounded_command "$REMOTE_TIMEOUT_SECONDS" \
  gh codespace ssh -c "$CODESPACE_NAME" \
  "bash -se -- $CODESPACE_NAME $expected_main_sha" <<'REMOTE_VERIFY'
set -euo pipefail
readonly expected_codespace_name=$1
readonly expected_main_sha=$2
readonly repo_root="/workspaces/dutchbay-epc-model"
readonly bootstrap_receipt="/workspaces/.dutchbay-private/bootstrap-receipt.json"
cd "$repo_root"
test "$CODESPACES" = true
/usr/local/bin/python3.12 -S - \
  "$bootstrap_receipt" "$expected_codespace_name" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    receipt = json.load(stream)
if receipt.get("codespace_name") != sys.argv[2]:
    raise SystemExit("bootstrap Codespace identity differs")
PY
checkout_status=$(git status --porcelain=v1) || exit 2
test -z "$checkout_status"
git fetch --prune origin main
git switch --detach origin/main
test "$(git rev-parse HEAD)" = "$expected_main_sha"
export DUTCHBAY_VENV="/workspaces/.dutchbay-audit-review-venv"
export DUTCHBAY_P03_SOURCE_ROOT="/workspaces/.dutchbay-private/p03/sources"
export DUTCHBAY_EXPECTED_CODESPACE_NAME="$expected_codespace_name"
export PYTHONPATH="$repo_root"
scripts/verify_1110_cloud_review_sandbox.sh
REMOTE_VERIFY
)
verify_api_identity

jq -e \
  --arg name "$CODESPACE_NAME" \
  --arg sha "$expected_main_sha" \
  '.schema == "dutchbay.audit_review_sandbox_receipt.v3"
    and .status == "PASS"
    and .environment == "github_codespaces"
    and .codespace_name == $name
    and .git_commit == $sha
    and .completion_authorized == false
    and .release_status == "HOLD"' \
  <<< "$verification_receipt" >/dev/null || fail \
  "nested cloud-review verification receipt differs"

jq -n \
  --arg name "$CODESPACE_NAME" \
  --arg display "$DISPLAY_NAME" \
  --arg repository "$REPOSITORY" \
  --arg sha "$expected_main_sha" \
  --argjson nested "$verification_receipt" \
  '{
    schema: "dutchbay.audit_review_outer_verification.v1",
    status: "PASS",
    api_identity: {
      name: $name,
      display_name: $display,
      repository: $repository,
      ref: "main"
    },
    exact_main_sha: $sha,
    nested_verification_receipt: $nested,
    semantic_review_completed: false,
    completion_authorized: false,
    release_status: "HOLD"
  }'
