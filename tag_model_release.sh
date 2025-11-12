#!/bin/bash

# ============================================================================
# Audit Tagging Script - GH Edition
# Purpose: Authenticate, stage, commit, tag, and push with GitHub CLI
# ============================================================================

# Step 0: Authenticate with GitHub CLI (if not already)
gh auth login --hostname github.com --git-protocol https

# Step 1: Stage all critical model files
git add dutchbay_v13/finance/debt.py
git add full_model_variables_updated.yaml
git add tests/test_debt_validation.py

# Step 2: Commit with audit-ready message (edit date/message as appropriate)
git commit -m "P0-1B Release: Enhanced debt module w/ balloon, refinancing, YAML alignment, audit test suite [2025-11-12]"

# Step 3: Tag this commit as a DFI/institutional checkpoint (annotated tag)
git tag -a "release-P0-1B-2025-11-12" -m "Release: Debt module & constraints checkpoint post-DFI compliance validation"

# Step 4: Check that remote is set to GitHub repo
gh repo view

# Step 5: Push the commit and the new tag using GitHub CLI
git push
git push --tags

# Step 6: Optional — Create a GitHub Release from this tag with CLI (adds to Releases dashboard)
gh release create release-P0-1B-2025-11-12 \
    --title "P0-1B: Debt Module & Audit Constraints Checkpoint" \
    --notes "DFI/commercial/ECA constraints, refinancing logic, balloon mitigation, audit results, and validation suite. Tag reflects full compliance as of 2025-11-12."

echo "SUCCESS: Model checkpoint and DFI-grade release completed, audit tag pushed and available in repo."
