# Code Freeze Policy

**Scope:** All code under `dutchbay_v13/`, inputs used by CI, and workflows.

**Freeze start:** 2025-11-10
**Version:** v13.1.0

## Rules
1. No feature changes—only hotfixes for CI breakage or critical bugs.
2. Branch protections on `main`: required status checks (CI), no force-push, 1+ review, signed commits.
3. All PRs must pass: black, ruff, flake8, mypy, bandit, unit tests, and coverage threshold (>= 80%).

## Exit Criteria
- Green CI on `main` at tag `v13.1.0`.
- Published GitHub Release asset `DutchBay_Model_V13.1.0.zip`.
