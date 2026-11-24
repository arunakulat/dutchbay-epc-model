#!/bin/bash
# Read-only R25 preflight for a feature writer. Not a lease or permission to push/merge.
set -euo pipefail
stop() { printf 'STOP: %s\n' "$*" >&2; exit 1; }
[[ $# == 3 ]] || stop 'usage: gwtf-preflight.sh EXPECTED_WORKTREE EXPECTED_BRANCH EXPECTED_BASE_SHA'
for variable in SKIP GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS PRE_COMMIT_ALLOW_NO_CONFIG; do
    [[ ! ${!variable+x} ]] || stop 'execution environment override present'
done
expected_root=$(cd "$1" && pwd -P) || stop 'expected worktree unavailable'
expected_branch=$2
expected_base=$3
[[ "$expected_base" =~ ^[0-9a-f]{40}$ ]] || stop 'exact base SHA required'
root=$(git rev-parse --show-toplevel) || stop 'not a Git worktree'
root=$(cd "$root" && pwd -P)
[[ "$root" == "$expected_root" && "$(pwd -P)" == "$root" ]] || stop 'worktree mismatch; run at the expected root'
branch=$(git branch --show-current)
[[ -n "$branch" && "$branch" != main && "$branch" != master ]] || stop 'protected or detached branch; no override'
[[ "$branch" == "$expected_branch" ]] || stop 'branch mismatch'
git_dir=$(git rev-parse --path-format=absolute --git-dir)
common_dir=$(git rev-parse --path-format=absolute --git-common-dir)
[[ "$git_dir" != "$common_dir" ]] || stop 'dedicated linked worktree required by this writer preflight'
[[ "$(git rev-parse origin/main)" == "$expected_base" ]] || stop 'local origin/main differs from expected base'
remote=$(git ls-remote --exit-code origin refs/heads/main) || stop 'live protected base unavailable'
[[ "$remote" == "$expected_base"$'\t'refs/heads/main ]] || stop 'live protected base differs; refresh and reconcile'
git merge-base --is-ancestor "$expected_base" HEAD || stop 'expected base is not an ancestor of HEAD'
printf 'Verified linked worktree: %s\nBranch: %s\nLive base: %s\n' "$root" "$branch" "$expected_base"
if upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null); then
    ahead=$(git rev-list --count '@{u}..HEAD') || stop 'upstream comparison unavailable'
    printf 'Commits ahead of configured upstream %s: %s (not proof of publication)\n' "$upstream" "$ahead"
else
    printf 'Upstream comparison: UNKNOWN (no resolvable upstream)\n'
fi
git --no-optional-locks status --short
printf 'R25 identity preflight passed. Coordinator must separately verify ownership, lease, allowlist, tests, review, CI and authority.\n'
