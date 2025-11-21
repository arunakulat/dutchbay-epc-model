#!/usr/bin/env bash
set -euo pipefail

# Bootstrap labels needed by create_v14_analytics_issues.sh into the current repo.

echo "Bootstrapping v14 label set in $(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo 'current repo')"

# Core scope labels
for label in v14 analytics "finance-core" exports excel charts cli logging docs ci tests tax enhancement; do
  echo "Ensuring label: $label"
  gh label create "$label" --color "0366d6" --description "" 2>/dev/null || echo "  (label '$label' already exists or could not be created)"
done

# Priority labels
for label in P0 P1 P1.5 P2 P2-optional; do
  echo "Ensuring label: $label"
  gh label create "$label" --color "d93f0b" --description "Priority $label" 2>/dev/null || echo "  (label '$label' already exists or could not be created)"
done

echo "Label bootstrap complete."
