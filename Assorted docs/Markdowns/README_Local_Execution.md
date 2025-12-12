# 🚀 SPRINT 9 B.1 + B.2 + B.3: LOCAL EXECUTION SCRIPTS

**Status:** ✅ Ready for Copy-Paste to Local Terminal
**Date:** December 9, 2025
**GWTF Compliance:** Full ✓

---

## 📋 OVERVIEW

This package contains **three complete scripts** for executing Sprint 9 Phase 2 locally:

1. **`b1_execute_local.py`** - B.1 execution (Contract extension)
2. **`b123_execute_workflow.sh`** - B.1 + B.2 execution (All-in-one bash)
3. **This README** - Instructions & manual fallback

**Key Features:**
- ✅ No external dependencies (stdlib only)
- ✅ No GitHub writes (local changes only)
- ✅ Comprehensive local testing before writing
- ✅ Automatic backups of original files
- ✅ GWTF compliant code
- ✅ Copy-paste ready

---

## 🎯 QUICK START

### Option 1: Bash Workflow (Recommended - One Command)

```bash
# Make script executable
chmod +x b123_execute_workflow.sh

# Run it (from repo root or analytics directory)
bash b123_execute_workflow.sh
```

**What happens:**
1. B.1: Extends contracts_v14.py with TechnologyBreakdown + CasperResult
2. B.2: Adds run() façade to sensitivity_v14.py
3. Tests everything locally
4. Reports results with next steps

### Option 2: Python Script (Individual Control)

```bash
# Run B.1 only with full control
python3 b1_execute_local.py
```

**What happens:**
1. Verifies contracts_v14.py exists
2. Analyzes current state
3. Injects new classes
4. Runs 7 comprehensive tests
5. Writes to disk only if all tests pass

---

## 📖 DETAILED INSTRUCTIONS

### Setup (1 minute)

```bash
# Go to repo root
cd /path/to/dutchbay-epc-model

# Verify you can see the files
ls contracts_v14.py sensitivity_v14.py

# If not found, try:
find . -name "contracts_v14.py" -type f
find . -name "sensitivity_v14.py" -type f
```

### Execution: B.1 Only (30 minutes)

```bash
# Step 1: Run B.1 script
python3 b1_execute_local.py

# Expected output:
# ✓ Found: contracts_v14.py
# ✓ Backup created: contracts_v14.py.backup
# ✓ New classes injected
# ✓ [Test 1] Syntax validation... ✓
# ✓ [Test 2] Module execution... ✓
# ✓ [Test 3] Class availability... ✓
# ✓ [Test 4] TechnologyBreakdown instantiation... ✓
# ✓ [Test 5] TechnologyBreakdown validation... ✓
# ✓ [Test 6] CasperResult instantiation... ✓
# ✓ [Test 7] CasperResult with optional fields... ✓
# ✓ Written to contracts_v14.py
# ✅ B.1 COMPLETE AND VERIFIED

# Step 2: Review changes
git diff contracts_v14.py

# Step 3: Run pytest (optional but recommended)
pytest tests/ -v -k "contract" || echo "No contract-specific tests yet"

# Step 4: Commit (when ready)
git add contracts_v14.py
git commit -m "B.1: Extend CasperResult with TechnologyBreakdown + generation/technology_breakdown fields

- Add TechnologyBreakdown dataclass (per-tech KPI breakdown)
- Add CasperResult dataclass (unified CASPER result)
- Optional fields all backward compatible
- Forward ref MultiTechGenerationResult (Sprint 10 import)
- Validation included for TechnologyBreakdown
- All tests passing: syntax, imports, instantiation"
```

### Execution: B.1 + B.2 (1 hour total)

```bash
# Step 1: Run combined workflow
bash b123_execute_workflow.sh

# Expected output:
# ✓ Pre-flight checks passed
# ✓ B.1 execution
# ✓ contracts_v14.py updated
# ✓ B.2 execution
# ✓ sensitivity_v14.py updated
# ✅ ALL COMPLETE

# Step 2: Review BOTH changes
git diff contracts_v14.py
git diff sensitivity_v14.py

# Step 3: Run full test suite
pytest tests/ -v

# Step 4: Commit both files
git add contracts_v14.py sensitivity_v14.py
git commit -m "B.1+B.2: CASPER contracts and sensitivity façade

CHANGES:
- B.1: Added TechnologyBreakdown and CasperResult dataclasses
- B.2: Added run() façade function to sensitivity_v14.py

All tests passing locally. Ready for code review."
```

---

## 🔍 WHAT GETS MODIFIED

### contracts_v14.py (B.1)

**Added at end of file (before EOF marker):**

```python
@dataclass(frozen=True)
class TechnologyBreakdown:
    """Per-technology KPI breakdown for lender/investor visibility."""
    technology: str
    annual_aep_kwh: float
    annual_cfads_usd: float
    dscr_min: Optional[float]
    capex_usd: float
    capex_per_mw: float

    def __post_init__(self) -> None:
        # Validates non-negative values

@dataclass(frozen=True)
class CasperResult:
    """Unified CASPER analysis result."""
    scenario: ScenarioResult
    kpis: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    sensitivity: Optional['SensitivitySuite'] = None
    monte_carlo: Optional[MonteCarloResult] = None
    analytics_summary: Optional[Dict[str, Any]] = None
    generation: Optional['MultiTechGenerationResult'] = None
    technology_breakdown: Optional[List[TechnologyBreakdown]] = None
```

**Size:** ~60 lines added
**Backward Compatible:** ✅ 100% (all new fields Optional)
**Breaking Changes:** ✅ None

### sensitivity_v14.py (B.2)

**Added before `__all__`:**

```python
def run(request: SensitivityRequest) -> SensitivitySuite:
    """
    Canonical entry point for sensitivity analysis (CASPER orchestration).

    This is a thin wrapper around run_tornado_sensitivity() that preserves
    backward compatibility and provides a clean API for CASPER integration.
    """
    return run_tornado_sensitivity(request)
```

**Updated `__all__`:**
```python
__all__ = [
    "run",  # NEW - Primary CASPER entry point
    "run_tornado_sensitivity",
    # ... rest
]
```

**Size:** ~25 lines added
**Backward Compatible:** ✅ 100%
**Breaking Changes:** ✅ None

---

## ✅ WHAT GETS TESTED

### B.1 Tests (7 total)

```
✓ [Test 1] Syntax validation
✓ [Test 2] Module execution
✓ [Test 3] Class availability
✓ [Test 4] TechnologyBreakdown instantiation
✓ [Test 5] TechnologyBreakdown validation
✓ [Test 6] CasperResult instantiation
✓ [Test 7] CasperResult with optional fields
```

### B.2 Tests (Implicit in B123 workflow)

```
✓ Syntax validation
✓ Module execution
✓ run() function availability
✓ __all__ export correctness
```

---

## 🚨 TROUBLESHOOTING

### Script Not Found

```bash
# Make sure you're in the right directory
pwd

# Should output something like:
# /home/user/dutchbay-epc-model
# OR
# /home/user/dutchbay-epc-model/analytics

# If not, navigate there:
cd /path/to/dutchbay-epc-model
```

### Python Module Not Found

```bash
# Check Python version
python3 --version  # Should be 3.9+

# Check if dataclasses module available (should be built-in)
python3 -c "from dataclasses import dataclass; print('OK')"
```

### File Write Permission Error

```bash
# Check permissions
ls -la contracts_v14.py
ls -la sensitivity_v14.py

# Make writable if needed
chmod 644 contracts_v14.py
chmod 644 sensitivity_v14.py

# Rerun script
python3 b1_execute_local.py
```

### Tests Fail

```bash
# Check the error message carefully
# It will tell you exactly what failed

# If "class not found" - file structure issue
# If "syntax error" - something went wrong in injection

# Restore from backup:
cp contracts_v14.py.backup contracts_v14.py
cp sensitivity_v14.py.backup sensitivity_v14.py

# Then run script again
python3 b1_execute_local.py
```

### Git Not Available

```bash
# That's OK - scripts still work
# You'll just need to manually push to GitHub when ready

bash b123_execute_workflow.sh  # Still works

# Then manual git:
git add contracts_v14.py sensitivity_v14.py
git commit -m "..."
git push origin sprint-9/casper-phase2-implementation
```

---

## 📤 MANUAL GITHUB PUSH (No Automatic Writes)

Once scripts complete successfully locally:

```bash
# 1. Create feature branch (if not done yet)
git checkout -b sprint-9/casper-phase2-implementation

# 2. Stage the files
git add contracts_v14.py
git add sensitivity_v14.py

# 3. Create commit
git commit -m "B.1+B.2: CASPER contracts and sensitivity façade

CHANGES:
- B.1: Added TechnologyBreakdown and CasperResult dataclasses to contracts_v14.py
- B.2: Added run() façade function to sensitivity_v14.py

VERIFICATION:
- All 7 B.1 tests passing locally
- B.2 module syntax and imports verified
- Backward compatible (zero breaking changes)
- Forward compatible (Sprint 10 ready)

NEXT:
- Code review
- B.3: Implement casper_v14.py orchestrator"

# 4. Push to feature branch
git push origin sprint-9/casper-phase2-implementation

# 5. Create PR on GitHub (if using GitHub)
# Then notify team for review
```

---

## 🎓 WHAT YOU LEARN

- ✅ How B.1, B.2, B.3 modifications work
- ✅ GWTF-compliant contract design
- ✅ Local testing before GitHub push
- ✅ Backward compatibility patterns
- ✅ Proper script error handling

---

## ⏭️ AFTER B.1 + B.2

When B.1 and B.2 are complete and merged:

**B.3: Implement casper_v14.py Orchestrator (4 hours)**

Code will be provided separately with:
- 6-phase pipeline implementation
- GWTF compliance enforced (no finance imports)
- Full error handling (fail hard on core, graceful on optional)
- Comprehensive logging
- 100% local testing before GitHub

---

## ✨ SUMMARY

| Step | Time | Status | Files | Commands |
|------|------|--------|-------|----------|
| B.1 | 30 min | ✅ Ready | contracts_v14.py | `python3 b1_execute_local.py` |
| B.2 | 30 min | ✅ Ready | sensitivity_v14.py | `bash b123_execute_workflow.sh` |
| **Total B.1+B.2** | **1 hour** | **✅ Ready** | **2 files** | **1 command** |

**No GitHub writes. All local. All tested. Ready when you are.** 🚀
