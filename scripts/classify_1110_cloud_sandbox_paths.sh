#!/usr/bin/env bash

# Classify whether one exact commit range touches the governed #1110 cloud
# sandbox. Any invalid, unavailable or empty diff fails toward running the gate.

set -euo pipefail

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

[ "$#" -eq 2 ] || fail "expected BASE_SHA and HEAD_SHA"
readonly BASE_SHA=$1
readonly HEAD_SHA=$2
readonly SHA_PATTERN='^[0-9a-f]{40}([0-9a-f]{24})?$'

[[ "$BASE_SHA" =~ $SHA_PATTERN ]] || fail "base commit identity is malformed"
[[ "$HEAD_SHA" =~ $SHA_PATTERN ]] || fail "head commit identity is malformed"
git cat-file -e "$BASE_SHA^{commit}" 2>/dev/null \
  || fail "base commit is unavailable"
git cat-file -e "$HEAD_SHA^{commit}" 2>/dev/null \
  || fail "head commit is unavailable"

changed_paths=$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/dutchbay-audit-paths.XXXXXX")
cleanup() {
  unlink -- "$changed_paths" 2>/dev/null || true
}
trap cleanup EXIT

if ! git diff --name-only -z --diff-filter=ACDMRT \
  "$BASE_SHA" "$HEAD_SHA" > "$changed_paths"; then
  fail "exact audit-sandbox path diff failed"
fi

# An empty or indeterminate population is never permission to skip a required
# control. Running the heavier gate is the safe false-positive outcome.
if [ ! -s "$changed_paths" ]; then
  printf 'true\n'
  exit 0
fi

relevant=false
while IFS= read -r -d '' changed_path; do
  case "$changed_path" in
    .devcontainer/*|.dockerignore|.github/workflows/audit-cloud-sandbox.yml|scripts/classify_1110_cloud_sandbox_paths.sh|scripts/create_1110_cloud_review_codespace.sh|scripts/upload_1110_p03_sources_to_codespace.sh|scripts/verify_1110_cloud_review_sandbox.sh|tests/lint/test_cloud_audit_review_sandbox.py)
      relevant=true
      break
      ;;
  esac
done < "$changed_paths"

printf '%s\n' "$relevant"
