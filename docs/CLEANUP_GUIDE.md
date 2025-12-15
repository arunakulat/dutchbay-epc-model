# DutchBay Cleanup Scripts - Quick Start Guide

**Generated:** 2025-12-13
**Purpose:** Automated cleanup of legacy/experimental files for v14 focus

---

## 🚀 Quick Start (3 Steps)

### Step 1: Preview What Will Be Cleaned (2 minutes)

```bash
# Make cleanup script executable
chmod +x dutchbay_repo_cleanup.sh

# Dry-run to see what would be moved
./dutchbay_repo_cleanup.sh --dry-run
```

**Output:** Shows exactly what would be archived WITHOUT making changes.

### Step 2: Run Analysis Report (1 minute)

```bash
# Make analyzer executable
chmod +x dutchbay_cleanup_analyzer.py

# Generate detailed analysis
python dutchbay_cleanup_analyzer.py --output cleanup_analysis.json
```

**Output:** JSON report + console summary of all cleanup candidates.

### Step 3: Execute Cleanup (2 minutes)

```bash
# Archive legacy files (safe, preserves history)
./dutchbay_repo_cleanup.sh --archive --confirm

# Or delete files permanently (irreversible - not recommended for first cleanup)
# ./dutchbay_repo_cleanup.sh --delete --confirm
```

**Result:** Files moved to `legacy_scripts/`, `legacy_docs/`, `legacy_tests/`, `legacy_scenarios/`

---

## 📋 Script Reference

### dutchbay_repo_cleanup.sh

**Main cleanup orchestrator. Creates archive directories and moves files.**

**Usage:**
```bash
./dutchbay_repo_cleanup.sh [OPTIONS]
```

**Options:**

| Option | Effect |
|--------|--------|
| `--dry-run` | Preview changes without modifying anything (default behavior) |
| `--archive` | Move files to legacy_* directories (safe, recommended) |
| `--delete` | Permanently delete files (DESTRUCTIVE - use with caution) |
| `--confirm` | Skip interactive prompts (for automation) |
| `--verbose` | Detailed logging (default) |
| `--quiet` | Minimal output |

**Examples:**

```bash
# Preview what will happen
./dutchbay_repo_cleanup.sh --dry-run

# Execute with prompts (you approve each step)
./dutchbay_repo_cleanup.sh --archive

# Execute silently (automated/CI mode)
./dutchbay_repo_cleanup.sh --archive --confirm

# Delete files instead of archiving (WARNING: irreversible)
./dutchbay_repo_cleanup.sh --delete --confirm
```

**What It Does:**

1. ✅ Validates git status (working directory must be clean)
2. ✅ Creates legacy_* archive directories
3. ✅ Moves duplicate scripts from `Assorted docs/scripts/`
4. ✅ Moves experimental scripts from `scripts/`
5. ✅ Moves duplicate test files
6. ✅ Moves old scenario configs
7. ✅ Moves duplicate documentation files
8. ✅ Creates README.md files in each archive directory
9. ✅ Generates cleanup_report_TIMESTAMP.json
10. ✅ Commits changes to git (with prompt)

**Output Files:**

```
cleanup_report_20251213_010000.json    ← Detailed cleanup log
legacy_scripts/                        ← Archive of experimental scripts
  ├── README.md                        ← Archive documentation
  └── archive/
      ├── assorted_docs_scripts_*/     ← Bulk directory of ~70 duplicates
      ├── apply_debt_fix.py
      ├── check_datalake_epc.py
      └── ...

legacy_docs/                           ← Archive of experimental docs
  ├── README.md
  └── archive/
      ├── assorted_docs_docs_*/
      ├── Cashflow_v14.py refactoring notes.md
      └── ...

legacy_tests/                          ← Archive of duplicate tests
  ├── README.md
  └── archive/
      ├── test_irr_quick.py
      ├── test_returns_module.py
      └── ...

legacy_scenarios/                      ← Archive of old scenario configs
  ├── README.md
  └── archive/
      ├── dutchbay_lendercase_2025Q3.yaml
      └── ...
```

### dutchbay_cleanup_analyzer.py

**Pre-cleanup analysis tool. Generates detailed inventory of cleanup candidates.**

**Usage:**
```bash
python dutchbay_cleanup_analyzer.py [--output FILENAME]
```

**Options:**

| Option | Effect |
|--------|--------|
| `--output FILE` | Specify output JSON path (default: cleanup_analysis.json) |

**Examples:**

```bash
# Generate default analysis report
python dutchbay_cleanup_analyzer.py

# Save to custom location
python dutchbay_cleanup_analyzer.py --output exports/cleanup_analysis.json
```

**Output:**

**Console Summary:**
- Total items to archive
- Space to reclaim (MB)
- By category breakdown
- Detailed list of duplicate scripts, tests, docs, and scenarios

**JSON Report (`cleanup_analysis.json`):**
```json
{
  "timestamp": "2025-12-13T...",
  "repo_root": "/path/to/repo",
  "categories": {
    "duplicate_scripts": [
      {
        "path": "Assorted docs/scripts/",
        "type": "directory",
        "file_count": 70,
        "size_kb": 280.5,
        "reason": "DUPLICATES - Multiple versions of cashflow_v14, evaluation_v14, etc.",
        "action": "Archive entire directory"
      },
      ...
    ],
    "duplicate_tests": [...],
    "duplicate_docs": [...],
    "old_scenarios": [...]
  },
  "summary": {
    "total_items": 285,
    "total_size_mb": 8.8,
    "by_category": {
      "duplicate_scripts": { "count": 75, "size_mb": 0.28 },
      ...
    }
  }
}
```

---

## 📊 What Gets Cleaned

### Files Being Archived/Deleted

| Category | Count | Size | Details |
|----------|-------|------|---------|
| **Duplicate Scripts** | ~75 | 280 KB | Assorted docs/scripts/ + experimental scripts/ |
| **Duplicate Tests** | ~85 | 100 KB | Old versions, beta files, experimental tests |
| **Duplicate Docs** | ~150 | 150 KB | Assorted docs/docs/ + old docs/ |
| **Old Scenarios** | ~15 | 50 KB | 2025Q3 configs, example files, edge cases |
| **TOTAL** | ~325 | **~580 KB** | About 0.6% of repo |

### Files Being KEPT (V14 Production)

✅ **Root Scripts:**
- run_full_pipeline_v14.py
- run_scenario_analytics_v14.py
- dutchbay_bootstrap.py
- dutchbay_manifest_builder.py
- go_with_the_flow_ci.py
- check_venv.sh

✅ **Production Code:**
- analytics/pipeline_v14.py, evaluation_v14.py, contracts_v14.py, etc.
- finance/cashflow_v14.py, debt_v14.py, equity_v14.py, etc.

✅ **V14 Tests:**
- tests/api/test_cashflow_v14.py
- tests/analytics_layer/test_monte_carlo_v14.py
- tests/analytics_layer/test_sensitivity_v14.py
- And ~40 other v14-focused tests

✅ **Production Configs:**
- scenarios/dutchbay_lendercase_2025Q4.yaml (and other current 2025Q4 scenarios)
- Current monte_carlo/ configs

✅ **V14 Documentation:**
- docs/architecture_v14.md
- docs/Dev_workflow_v14.md
- docs/PRE-FLIGHT CHECKLIST.md
- And other v14-focused docs

---

## 🔧 Common Workflows

### Workflow 1: Cleanup + Push to Main

```bash
# 1. Preview
./dutchbay_repo_cleanup.sh --dry-run

# 2. Execute with confirmation
./dutchbay_repo_cleanup.sh --archive

# 3. Script will ask to commit and push
# (Answer 'y' when prompted)

# Done! Changes are now on main
```

### Workflow 2: Cleanup in Automation/CI

```bash
# Run without any prompts
./dutchbay_repo_cleanup.sh --archive --confirm

# Or combine with analysis
python dutchbay_cleanup_analyzer.py --output exports/analysis.json
./dutchbay_repo_cleanup.sh --archive --confirm
```

### Workflow 3: Just Check Without Modifying

```bash
# Dry-run shows everything that WOULD happen
./dutchbay_repo_cleanup.sh --dry-run

# Or just analyze
python dutchbay_cleanup_analyzer.py

# Decide later if you want to actually run cleanup
```

### Workflow 4: Verify Cleanup Worked

After cleanup, regenerate the manifest:

```bash
# Run manifest builder to see new state
./dutchbay_manifest_builder.py --output exports/manifest_clean.json

# Compare old vs new
jq '.summary' exports/manifest_2025_12_13.json    # Old
jq '.summary' exports/manifest_clean.json         # New
```

---

## ✅ Verification Checklist

After running cleanup, verify everything worked:

### Step 1: Check Archive Directories Created

```bash
ls -la legacy_scripts/
ls -la legacy_docs/
ls -la legacy_tests/
ls -la legacy_scenarios/
```

Expected: Each has `README.md` and `archive/` subdirectory.

### Step 2: Verify Production Files Still Exist

```bash
# Root scripts
ls -l run_full_pipeline_v14.py
ls -l run_scenario_analytics_v14.py

# Core modules
ls -l analytics/pipeline_v14.py
ls -l finance/cashflow_v14.py

# Test suite
ls -l tests/api/test_cashflow_v14.py
ls -l tests/analytics_layer/test_monte_carlo_v14.py

# Current scenarios
ls -l scenarios/dutchbay_lendercase_2025Q4.yaml
```

All should exist and be readable.

### Step 3: Check Git Commit

```bash
git log --oneline -5
```

Should show: `chore: Archive legacy/experimental files (v14 cleanup) - 580 KB freed`

### Step 4: Regenerate Manifest

```bash
./dutchbay_manifest_builder.py --output exports/manifest_after_cleanup.json

# Compare stats
echo "Before cleanup:"
jq '.summary' exports/manifest_2025_12_13.json | head -5

echo "After cleanup:"
jq '.summary' exports/manifest_after_cleanup.json | head -5
```

Size should show ~580 KB less used.

---

## 🔄 Restore from Archive

If you later need a file from the archive:

```bash
# Option 1: Copy back from legacy directory
cp legacy_scripts/archive/old_script.py scripts/

# Option 2: Restore from git history
git log --all --full-history -- "Assorted docs/scripts/old_script.py"
git checkout <COMMIT_SHA> -- "Assorted docs/scripts/old_script.py"

# Option 3: Check what's in the archive first
ls legacy_scripts/archive/
ls legacy_docs/archive/
ls legacy_tests/archive/
ls legacy_scenarios/archive/
```

---

## 🚨 Troubleshooting

### Problem: "Git working directory is not clean"

**Solution:** Commit or stash all changes first
```bash
git add -A
git commit -m "WIP: work in progress"
# Then run cleanup
```

### Problem: Permission denied on shell script

**Solution:** Make executable
```bash
chmod +x dutchbay_repo_cleanup.sh
chmod +x dutchbay_cleanup_analyzer.py
```

### Problem: "Not in DutchBay repo root"

**Solution:** Run from repo root where `pyproject.toml` or `.git` exist
```bash
cd /path/to/dutchbay-epc-model
./dutchbay_repo_cleanup.sh --dry-run
```

### Problem: Script deleted files instead of archiving

**Solution:** Restore from git
```bash
git reflog
git reset --hard <COMMIT_BEFORE_DELETE>
# Re-run with --archive instead of --delete
```

### Problem: Want to undo the entire cleanup

**Solution:** Revert the cleanup commit
```bash
git log --oneline | head -5
git revert <CLEANUP_COMMIT_HASH>
git push origin main
```

---

## 📝 Output Files Reference

### cleanup_report_TIMESTAMP.json

Generated by `dutchbay_repo_cleanup.sh`. Contains:

```json
{
  "cleanup_timestamp": "2025-12-13T...",
  "repo_root": "...",
  "mode": "archive",
  "dry_run": false,
  "statistics": {
    "scripts_moved": 75,
    "docs_moved": 150,
    "tests_moved": 85,
    "scenarios_moved": 15,
    "files_deleted": 0,
    "total_size_mb": 0.58
  },
  "archive_directories": {
    "legacy_scripts": ".../legacy_scripts",
    "legacy_docs": ".../legacy_docs",
    "legacy_tests": ".../legacy_tests",
    "legacy_scenarios": ".../legacy_scenarios"
  }
}
```

### cleanup_analysis.json

Generated by `dutchbay_cleanup_analyzer.py`. Contains detailed inventory of every file to be cleaned.

### legacy_*/README.md Files

Created in each archive directory. Explain what's in the archive and how to restore if needed.

---

## 📞 Questions?

Refer to the main analysis document: `v14_cleanup_analysis.md`

---

**Last Updated:** 2025-12-13
**Ready to cleanup?** Run: `./dutchbay_repo_cleanup.sh --dry-run`
