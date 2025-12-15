# Sprint 10 P0: Validation + Pipeline Canonical

## Critical Path (Must Complete Before Features)

### P0.1: Fix Validation Script (5 min) ✅
**Status:** DONE
- scripts/run_sprint9_validation.sh already calls `python run_full_pipeline_v14.py` (root-level)
- Fallback to `scripts/run_full_analytics_v14.py` in place
- No longer checks non-existent `scripts/run_full_pipeline_v14.py` path

### P0.2: Clean Tracked Artifacts (10 min)
**Status:** IN PROGRESS

**Problem:** `git ls-files` shows tracked output files that should be ignored:
- outputs/*.json (pipeline_result.json, etc.)
- outputs/*.csv
- outputs/**/*.hydra/*

**Solution (2 options):**

**Option A: Remove from tracking, rely on .gitignore (RECOMMENDED)**
```bash
# Untrack all outputs/ files
git rm --cached outputs/ -r --force
git rm --cached sensitivity_analysis/ -r --force  # if exists
git rm --cached multirun/ -r --force  # if exists

# Verify they're removed but directory structure intact
ls -la outputs/  # should still exist locally

# Commit the removal
git commit -m "Sprint 10 P0.2: Stop tracking generated artifacts (outputs/, sensitivity_analysis/, multirun/)"
git push origin sprint-10-linting-cleanup
```

**Option B: Keep tracking (not recommended)**
- Accept repo bloat
- Diffs will show every run's output
- Merge conflicts on every pipeline run
- **Decision: Option A is correct.**

### P0.3: Verify Canonical Path (5 min)
**Status:** PENDING

After P0.2, validate:
```bash
# Pull the P0.2 commit
git pull origin sprint-10-linting-cleanup

# Run the validation script
./scripts/run_sprint9_validation.sh

# Step [6/8] should find and run python run_full_pipeline_v14.py
# Check for line: "✅ Full pipeline v14 completed"
```

**Expected behavior:**
- Step [6/8] finds root-level `run_full_pipeline_v14.py`
- Executes it without 404 errors
- Completes with warnings or success (not skipped)

---

## Why P0 Matters

**Without P0:**
- Validation script appears to run, but [6/8] silently skips ("not found")
- Future "features" built on top of skipped step
- Merge conflicts when outputs/ tracked vs. untracked
- Merge conflicts every time pipeline runs

**With P0:**
- Validation script is canonical baseline
- Every PR can run it as sanity check
- outputs/ not in repo = clean history
- Ready for P1 (Monte Carlo optimization) without merge-conflict debt

---

## P1 (Next): Monte Carlo Speed

Once P0 done, start with:
- Caching parsed scenario configs (no re-load per iteration)
- Avoid CSV/JSONL writes unless requested
- Parallel iterations with thread-safe seeding
- Target: 54.82s → ~20s (no architecture churn)

---

## Timeline

- **P0.1**: ✅ DONE
- **P0.2**: START NOW (Option A: untrack artifacts)
- **P0.3**: Validate after P0.2
- **P1**: Begin after P0 merged to main

---

## Sign-off

P0 is blocker for all feature work. Do P0.2 now (git rm --cached outputs/).
