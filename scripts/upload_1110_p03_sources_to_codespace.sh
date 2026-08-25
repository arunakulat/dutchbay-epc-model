#!/usr/bin/env bash

# Fail-closed, allowlisted ingress of the retained P03 corpus into the one
# creator-private #1110 review Codespace. The existing P03 verifier proves the
# exact 74-object/hash population locally before any cloud transfer begins.

set -euo pipefail

readonly REPOSITORY="arunakulat/dutchbay-epc-model"
readonly DISPLAY_NAME="DutchBay 1110 independent review"
readonly REMOTE_SOURCE_ROOT="/workspaces/.dutchbay-private/p03/sources"
readonly REMOTE_SMOKE_ROOT="/workspaces/.dutchbay-private/transport-smoke"
readonly REMOTE_SMOKE_PATH="$REMOTE_SMOKE_ROOT/devcontainer.json"
transport_codespace_name=""
transport_probe_pending="false"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

verify_codespace_identity() {
  local codespace_name=$1
  local identity_json
  identity_json=$(
    gh api \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "/user/codespaces/$codespace_name"
  )
  jq -e \
    --arg name "$codespace_name" \
    --arg display "$DISPLAY_NAME" \
    --arg repository "$REPOSITORY" \
    '.name == $name and .display_name == $display and .repository.full_name == $repository' \
    <<< "$identity_json" >/dev/null \
    || fail "review Codespace API identity differs from authorization"
}

cleanup_transport_probe() {
  local exit_status=$?
  if [ "$transport_probe_pending" = "true" ]; then
    if ! gh codespace ssh -c "$transport_codespace_name" "bash -se" \
      <<'REMOTE_TRANSPORT_CLEANUP'
set -euo pipefail
readonly smoke_path="/workspaces/.dutchbay-private/transport-smoke/devcontainer.json"
if [ -e "$smoke_path" ]; then
  test -f "$smoke_path"
  test ! -L "$smoke_path"
  rm -- "$smoke_path"
fi
REMOTE_TRANSPORT_CLEANUP
    then
      printf '%s\n' \
        "ERROR: transport-probe cleanup could not reach the Codespace; delete and recreate it before retrying" >&2
    fi
  fi
  return "$exit_status"
}

run_transport_smoke() {
  transport_codespace_name=$1
  transport_probe_pending="true"
  trap cleanup_transport_probe EXIT

  gh codespace cp --expand -c "$transport_codespace_name" \
    ".devcontainer/devcontainer.json" \
    "remote:$REMOTE_SMOKE_PATH"
  gh codespace ssh -c "$transport_codespace_name" "bash -se" \
    <<'REMOTE_TRANSPORT_SMOKE'
set -euo pipefail
readonly repo_root="/workspaces/dutchbay-epc-model"
readonly smoke_path="/workspaces/.dutchbay-private/transport-smoke/devcontainer.json"
cleanup() {
  if [ -e "$smoke_path" ]; then
    test -f "$smoke_path"
    test ! -L "$smoke_path"
    rm -- "$smoke_path"
  fi
}
trap cleanup EXIT
test -f "$smoke_path"
test ! -L "$smoke_path"
cmp -- "$repo_root/.devcontainer/devcontainer.json" "$smoke_path"
REMOTE_TRANSPORT_SMOKE

  transport_probe_pending="false"
  trap - EXIT
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then

[ "${CODESPACES:-}" != "true" ] || fail \
  "P03 ingress must start from the controlled local retained-source host"
[ "${DUTCHBAY_P03_CLOUD_INGRESS_AUTHORIZED:-}" = "YES" ] || fail \
  "explicit P03 cloud-ingress authorization is required"
[ -f "go_with_the_flow_rules_v3_0_clean.csv" ] \
  && [ -f "scripts/verify_p03_primary_sources.py" ] || fail \
  "run P03 ingress from the DutchBay repository root"
source_root=${DUTCHBAY_P03_RETAINED_SOURCE_ROOT:-}
[ -n "$source_root" ] || fail "DUTCHBAY_P03_RETAINED_SOURCE_ROOT is unset"
[ "$source_root" != "/" ] || fail "filesystem root is not a valid P03 source root"
[ "${source_root#/}" != "$source_root" ] || fail \
  "P03 retained-source root must be absolute"
[ ! -L "$source_root" ] || fail "P03 retained-source root must not be a symlink"
[ -d "$source_root" ] || fail "P03 retained-source root is unavailable"

resolved_source_root=$(cd "$source_root" && pwd -P)
[ "$resolved_source_root" = "$source_root" ] || fail \
  "P03 retained-source root must be its canonical path"
[ "$(basename "$resolved_source_root")" = "sources" ] || fail \
  "P03 retained-source root must be narrowly scoped and named sources"

venv_root=${DUTCHBAY_VENV:-}
[ -n "$venv_root" ] || fail "DUTCHBAY_VENV is unset"
[ "${venv_root#/}" != "$venv_root" ] || fail "DUTCHBAY_VENV must be absolute"
[ -x "$venv_root/bin/python" ] || fail "governed Python is unavailable"
command -v gh >/dev/null 2>&1 || fail "GitHub CLI is unavailable"
command -v jq >/dev/null 2>&1 || fail "jq is unavailable"
checkout_branch=$(git branch --show-current) || fail \
  "local P03 ingress branch could not be determined"
[ "$checkout_branch" = "main" ] || fail \
  "local P03 ingress checkout must be protected main"
checkout_status=$(git status --porcelain=v1) || fail \
  "local P03 ingress checkout status could not be determined"
[ -z "$checkout_status" ] || fail \
  "local P03 ingress checkout must be clean"
git fetch --prune origin
checkout_head=$(git rev-parse HEAD) || fail \
  "local P03 ingress commit could not be determined"
origin_main=$(git rev-parse refs/remotes/origin/main) || fail \
  "fetched origin/main commit could not be determined"
[ "$checkout_head" = "$origin_main" ] || fail \
  "local P03 ingress checkout is stale; synchronize main before retrying"
DUTCHBAY_VENV="$venv_root" ./check_venv.sh --no-bootstrap

# The receipt is path-free. A missing manifest, extra object, symlink, hash
# drift or governed-exception drift stops here before any gh command runs.
DUTCHBAY_P03_SOURCE_ROOT="$resolved_source_root" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "$venv_root/bin/python" scripts/verify_p03_primary_sources.py

codespace_name=${DUTCHBAY_1110_REVIEW_CODESPACE_NAME:-}
[ -n "$codespace_name" ] || fail \
  "DUTCHBAY_1110_REVIEW_CODESPACE_NAME is unset"
case "$codespace_name" in
  *[!A-Za-z0-9_-]*) fail "review Codespace name contains unexpected characters" ;;
esac
verify_codespace_identity "$codespace_name"

# Currency and destination checks happen before ingress while network access is
# still required. No fetch or package installation occurs after retained data is
# copied. The fixed destination must exist, be real, and be empty.
gh codespace ssh -c "$codespace_name" \
  "bash -se -- $codespace_name" <<'REMOTE_PREFLIGHT'
set -euo pipefail
readonly expected_codespace_name=$1
readonly repo_root="/workspaces/dutchbay-epc-model"
readonly source_root="/workspaces/.dutchbay-private/p03/sources"
readonly smoke_root="/workspaces/.dutchbay-private/transport-smoke"
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
checkout_branch=$(git branch --show-current) || exit 2
case "$checkout_branch" in
  main|"") ;;
  *) exit 2 ;;
esac
checkout_status=$(git status --porcelain=v1) || exit 2
test -z "$checkout_status"
git fetch --prune origin
git switch --detach origin/main
checkout_head=$(git rev-parse HEAD) || exit 2
origin_main=$(git rev-parse refs/remotes/origin/main) || exit 2
test "$checkout_head" = "$origin_main"
test -d "$source_root"
test ! -L "$source_root"
test "$(realpath -e "$source_root")" = "$source_root"
source_probe=$(find "$source_root" -mindepth 1 -print -quit) || exit 2
test -z "$source_probe"
test -d "$smoke_root"
test ! -L "$smoke_root"
test "$(realpath -e "$smoke_root")" = "$smoke_root"
test "$(stat -c '%a' "$smoke_root")" = "700"
smoke_probe=$(find "$smoke_root" -mindepth 1 -print -quit) || exit 2
test -z "$smoke_probe"
export DUTCHBAY_VENV="/workspaces/.dutchbay-audit-review-venv"
export DUTCHBAY_P03_SOURCE_ROOT="$source_root"
export DUTCHBAY_EXPECTED_CODESPACE_NAME="$expected_codespace_name"
export PYTHONPATH="$repo_root"
scripts/verify_1110_cloud_review_sandbox.sh >&2
REMOTE_PREFLIGHT

# Prove both SSH and copy transport with a non-sensitive, controlled file before
# any retained source object crosses the boundary. Local and remote traps both
# attempt exact cleanup if copy or follow-up SSH fails.
run_transport_smoke "$codespace_name"

verify_codespace_identity "$codespace_name"
gh codespace cp --expand --recursive -c "$codespace_name" \
  "$resolved_source_root/original" \
  "$resolved_source_root/converted" \
  "$resolved_source_root/SOURCE_ARCHIVE_MANIFEST.v2.sha256" \
  "$resolved_source_root/SOURCE_ARCHIVE_MANIFEST.sha256" \
  "$resolved_source_root/IEC_CATALOGUE_QUERY_LOG.json" \
  "remote:$REMOTE_SOURCE_ROOT/"

# Re-run through the same API-authenticated outer envelope. Its nested receipt
# now binds the transferred population while every completion/release field
# remains fail-closed.
scripts/run_1110_cloud_review_verification.sh
fi
