#!/usr/bin/env bash
set -Eeuo pipefail

# Args (optional): 1 = branch, 2 = tag
branch="${1:-}"
tag="${2:-}"

# Resolve sensible defaults without triggering set -u
if [[ -z "${branch}" ]]; then
  branch="$(git symbolic-ref --short -q HEAD || echo main)"
fi
if [[ -z "${tag}" ]]; then
  tag="v13-testing-$(date +%Y%m%d-%H%M%S)"
fi

echo "→ Branch resolved: ${branch}"
echo "→ Tag to create  : ${tag}"

# Ensure we're on the intended branch
current="$(git symbolic-ref --short -q HEAD || true)"
if [[ "${current}" != "${branch}" ]]; then
  echo "✗ You are on '${current:-detached}'. Checkout '${branch}' or pass a branch arg."
  exit 1
fi

echo "→ Pushing ${branch}…"
git push origin "${branch}"

# Create annotated tag only if it doesn't already exist
if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
  echo "• Tag ${tag} already exists (skipping create)."
else
  echo "→ Creating annotated tag ${tag}…"
  git tag -a "${tag}" -m "Test checkpoint: ${tag}"
fi

echo "→ Pushing tag ${tag}…"
git push origin "refs/tags/${tag}"

echo "✓ Pushed ${branch} and tag ${tag}"

