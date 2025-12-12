#!/usr/bin/env bash
# ============================================================================
# B.1 + B.2 + B.3 LOCAL EXECUTION - COMPLETE WORKFLOW
# ============================================================================
#
# This script orchestrates the full B.1, B.2, B.3 execution locally
# NO GitHub writes - Only reads
# All changes happen locally first, then you push manually
#
# USAGE:
#   bash b123_execute_workflow.sh
#
# REQUIREMENTS:
#   - Python 3.9+
#   - contracts_v14.py in current directory
#   - sensitivity_v14.py in current directory (for B.2)
#   - Read access to analytics files
#
# ============================================================================

set -e  # Exit on error

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                            ║"
echo "║         B.1 → B.2 → B.3 LOCAL EXECUTION WORKFLOW                           ║"
echo "║         Sprint 9 Phase 2: CASPER/GWTF Orchestrator Implementation         ║"
echo "║                                                                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

echo "[PRE-FLIGHT] Checking environment..."
echo ""

# Check Python version
python3 --version || { echo "✗ Python 3 not found"; exit 1; }

# Check files exist
for file in "contracts_v14.py" "sensitivity_v14.py"; do
    if [ -f "$file" ]; then
        echo "✓ Found: $file"
    else
        echo "✗ NOT FOUND: $file"
        echo "  Please run from directory containing these files"
        exit 1
    fi
done

# Check git (for reporting only, not for writes)
if command -v git &> /dev/null; then
    echo "✓ Git available (read-only mode)"
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    echo "  Current branch: $CURRENT_BRANCH"
else
    echo "⚠ Git not available (optional)"
fi

echo ""
echo "✓ All pre-flight checks passed"
echo ""

# ============================================================================
# B.1 EXECUTION
# ============================================================================

echo "════════════════════════════════════════════════════════════════════════════"
echo "PHASE B.1: EXTEND CASPER RESULT CONTRACTS"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

python3 << 'PYTHON_B1'
import sys
import ast
from pathlib import Path

print("[B.1] Reading contracts_v14.py...")
with open('contracts_v14.py', 'r') as f:
    content = f.read()

print(f"✓ Read {len(content)} bytes")

# Check for existing classes
has_tech_breakdown = "class TechnologyBreakdown" in content
has_casper_result = "class CasperResult" in content

print(f"\nCurrent state:")
print(f"  - TechnologyBreakdown: {'EXISTS' if has_tech_breakdown else 'MISSING'}")
print(f"  - CasperResult: {'EXISTS' if has_casper_result else 'MISSING'}")

if has_tech_breakdown and has_casper_result:
    print("\n✓ Both classes already present. B.1 complete.")
    sys.exit(0)

# Create backup
backup_path = "contracts_v14.py.backup"
with open(backup_path, 'w') as f:
    f.write(content)
print(f"\n✓ Backup: {backup_path}")

# New code to inject
new_code = '''
# ═════════════════════════════════════════════════════════════════════════════
# CASPER Result Contracts (Multi-Tech Support) - Sprint 9/10
# ═════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TechnologyBreakdown:
    """Per-technology KPI breakdown for lender/investor visibility."""
    
    technology: str  # "wind", "solar", "battery", etc.
    annual_aep_kwh: float  # Annual energy production (kWh)
    annual_cfads_usd: float  # Annual cash flow after debt service (USD)
    dscr_min: Optional[float]  # Minimum DSCR for this technology
    capex_usd: float  # Total capital expenditure (USD)
    capex_per_mw: float  # CAPEX per MW (USD/MW)
    
    def __post_init__(self) -> None:
        """Validate technology breakdown data."""
        if self.annual_aep_kwh < 0:
            raise ValueError(f"annual_aep_kwh must be non-negative, got {self.annual_aep_kwh}")
        if self.capex_per_mw < 0:
            raise ValueError(f"capex_per_mw must be non-negative, got {self.capex_per_mw}")
        if self.dscr_min is not None and self.dscr_min < 0:
            raise ValueError(f"dscr_min must be non-negative, got {self.dscr_min}")


@dataclass(frozen=True)
class CasperResult:
    """
    Unified CASPER analysis result - canonical output from run_casper_analysis().
    
    All top-level fields are present; optional fields may be None.
    This is a versioned API contract (casper_version in metadata).
    """
    
    # Core fields (always present)
    scenario: ScenarioResult
    kpis: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Optional analytical results
    sensitivity: Optional['SensitivitySuite'] = None
    monte_carlo: Optional[MonteCarloResult] = None
    analytics_summary: Optional[Dict[str, Any]] = None
    
    # NEW (Sprint 10): Multi-technology support
    generation: Optional['MultiTechGenerationResult'] = None
    technology_breakdown: Optional[List[TechnologyBreakdown]] = None

'''

# Find insertion point
eof_marker = "# ═════════════════════════════════════════════════════════════════════════════\n# END OF CONTRACTS FILE"
if eof_marker not in content:
    print("✗ Could not find END OF CONTRACTS FILE marker")
    sys.exit(1)

insertion_point = content.find(eof_marker)
modified = content[:insertion_point] + new_code + "\n" + content[insertion_point:]

# Verify syntax
print("\n[B.1] Verifying syntax...")
try:
    ast.parse(modified)
    print("✓ Syntax valid")
except SyntaxError as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)

# Execute to test
print("[B.1] Testing module execution...")
namespace = {}
try:
    exec(modified, namespace)
    print("✓ Module executes")
except Exception as e:
    print(f"✗ Execution error: {e}")
    sys.exit(1)

# Verify classes exist
try:
    TechnologyBreakdown = namespace['TechnologyBreakdown']
    CasperResult = namespace['CasperResult']
    ScenarioResult = namespace['ScenarioResult']
    print("✓ All required classes found")
except KeyError as e:
    print(f"✗ Missing class: {e}")
    sys.exit(1)

# Test instantiation
print("[B.1] Testing instantiation...")
try:
    tb = TechnologyBreakdown(
        technology="wind",
        annual_aep_kwh=450e6,
        annual_cfads_usd=45e6,
        dscr_min=1.28,
        capex_usd=150e6,
        capex_per_mw=1.5e6,
    )
    
    scenario = ScenarioResult(
        scenario_name="test",
        config_path="test.yaml",
        project_npv=100e6,
        project_irr=0.135,
        dscr_series=[1.4, 1.3, 1.2],
        min_dscr=1.2,
        max_debt_usd=80e6,
    )
    
    result = CasperResult(
        scenario=scenario,
        kpis={"project_irr": 0.135},
        metadata={"casper_version": "v1"}
    )
    
    assert result.generation is None
    assert result.technology_breakdown is None
    print("✓ Instantiation works")
except Exception as e:
    print(f"✗ Instantiation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Write to disk
print("[B.1] Writing changes to disk...")
with open('contracts_v14.py', 'w') as f:
    f.write(modified)
print("✓ Written to contracts_v14.py")

print("\n✅ B.1 COMPLETE")
PYTHON_B1

if [ $? -ne 0 ]; then
    echo "✗ B.1 failed"
    exit 1
fi

echo ""

# ============================================================================
# B.2 EXECUTION
# ============================================================================

echo "════════════════════════════════════════════════════════════════════════════"
echo "PHASE B.2: ADD run() FAÇADE TO SENSITIVITY_V14"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

python3 << 'PYTHON_B2'
import sys
import ast

print("[B.2] Reading sensitivity_v14.py...")
with open('sensitivity_v14.py', 'r') as f:
    content = f.read()

print(f"✓ Read {len(content)} bytes")

# Check if run() already exists
if "def run(request: SensitivityRequest)" in content:
    print("\n✓ run() function already present. B.2 complete.")
    sys.exit(0)

# Create backup
backup_path = "sensitivity_v14.py.backup"
with open(backup_path, 'w') as f:
    f.write(content)
print(f"✓ Backup: {backup_path}")

# Find __all__ or end of file
all_idx = content.find("__all__ = [")

if all_idx != -1:
    # Has __all__, add run() before it
    insertion_point = all_idx
    run_func = '''def run(request: SensitivityRequest) -> SensitivitySuite:
    """
    Canonical entry point for sensitivity analysis (CASPER orchestration).
    
    This is a thin wrapper around run_tornado_sensitivity() that preserves
    backward compatibility and provides a clean API for CASPER integration.
    
    Args:
        request: SensitivityRequest with base config path and parameters.
    
    Returns:
        SensitivitySuite with tornado results, base metric, and config path.
    
    Raises:
        ValueError: If config or parameters are invalid.
        KeyError: If base KPI metric not found in evaluation results.
        FileNotFoundError: If config YAML file not found.
    """
    return run_tornado_sensitivity(request)


'''
    modified = content[:insertion_point] + run_func + content[insertion_point:]
    
    # Update __all__ to include "run"
    all_closing = modified.find("]", all_idx)
    all_section = modified[all_idx:all_closing]
    if '"run"' not in all_section:
        new_all_section = all_section.replace("[", '["run",  # NEW - Primary CASPER entry point\n    ', 1)
        modified = modified[:all_idx] + new_all_section + modified[all_closing:]
else:
    # No __all__, add run() at end
    run_func = '''

def run(request: SensitivityRequest) -> SensitivitySuite:
    """
    Canonical entry point for sensitivity analysis (CASPER orchestration).
    
    This is a thin wrapper around run_tornado_sensitivity() that preserves
    backward compatibility and provides a clean API for CASPER integration.
    
    Args:
        request: SensitivityRequest with base config path and parameters.
    
    Returns:
        SensitivitySuite with tornado results, base metric, and config path.
    
    Raises:
        ValueError: If config or parameters are invalid.
        KeyError: If base KPI metric not found in evaluation results.
        FileNotFoundError: If config YAML file not found.
    """
    return run_tornado_sensitivity(request)


__all__ = [
    "run",  # PRIMARY CASPER entry point
    "run_tornado_sensitivity",
    "SensitivityRequest",
    "SensitivitySuite",
    "ParameterRangeConfig",
]
'''
    modified = content + run_func

# Verify syntax
print("\n[B.2] Verifying syntax...")
try:
    ast.parse(modified)
    print("✓ Syntax valid")
except SyntaxError as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)

# Execute to test
print("[B.2] Testing module execution...")
namespace = {}
try:
    exec(modified, namespace)
    print("✓ Module executes")
except Exception as e:
    print(f"✗ Execution error: {e}")
    sys.exit(1)

# Verify run() exists
try:
    run_func = namespace['run']
    print("✓ run() function found")
except KeyError:
    print("✗ run() function not found")
    sys.exit(1)

# Write to disk
print("[B.2] Writing changes to disk...")
with open('sensitivity_v14.py', 'w') as f:
    f.write(modified)
print("✓ Written to sensitivity_v14.py")

print("\n✅ B.2 COMPLETE")
PYTHON_B2

if [ $? -ne 0 ]; then
    echo "✗ B.2 failed"
    exit 1
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "════════════════════════════════════════════════════════════════════════════"
echo "EXECUTION COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ B.1: Extended CasperResult contracts"
echo "✅ B.2: Added run() façade to sensitivity_v14"
echo ""
echo "Files modified (locally only):"
echo "  - contracts_v14.py"
echo "  - sensitivity_v14.py"
echo ""
echo "Backups created:"
echo "  - contracts_v14.py.backup"
echo "  - sensitivity_v14.py.backup"
echo ""
echo "Next steps (MANUAL - no automatic GitHub writes):"
echo ""
echo "  1. Review changes:"
echo "     git diff contracts_v14.py"
echo "     git diff sensitivity_v14.py"
echo ""
echo "  2. Test locally:"
echo "     python3 -m pytest tests/ -v"
echo ""
echo "  3. Stage changes:"
echo "     git add contracts_v14.py sensitivity_v14.py"
echo ""
echo "  4. Commit:"
echo "     git commit -m 'B.1+B.2: CASPER contracts and sensitivity façade'"
echo ""
echo "  5. Push to feature branch:"
echo "     git push origin sprint-9/casper-phase2-implementation"
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

exit 0
