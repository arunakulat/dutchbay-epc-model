#!/usr/bin/env python3
"""
Test Script for Markdown Report Generation - LLCR/PLCR Enhanced, All Years
DutchBay V13 - Option A Step 5 (Final)

This script:
1. Loads YAML configuration
2. Calculates all returns (post-tax, post-regulatory, post-risk)
3. Computes LLCR/PLCR coverage ratios
4. Generates Executive Summary and DFI/Lender Pack markdown reports
5. Outputs all years from construction through end-of-life

All values are fully parameterized from YAML.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.reporting.markdown_generator import generate_executive_summary, generate_dfi_lender_pack
from dutchbay_v13.finance.returns import calculate_all_returns
from dutchbay_v13.finance.metrics import calculate_llcr, calculate_plcr
import yaml

print("=" * 80)
print("DUTCHBAY V13 - MARKDOWN REPORT GENERATION TEST")
print("LLCR/PLCR Enhanced | All Years | Fully Parameterized")
print("=" * 80)

# Load YAML configuration
yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
if not yaml_path.exists():
    print(f"\n❌ ERROR: YAML config not found at {yaml_path}")
    sys.exit(1)

print(f"\n--- Loading Configuration ---")
print(f"YAML: {yaml_path}")
with open(yaml_path) as f:
    params = yaml.safe_load(f)
print(f"✓ Configuration loaded")

# Calculate all returns (includes tax, regulatory, risk, DSCR)
print("\n--- Computing Financial Returns ---")
print("Computing: Revenue (grid loss) → Regulatory deductions → Risk haircut → Tax → DSCR sculpting")
returns = calculate_all_returns(params)
ds_list = returns['debt_service']
cfads_list = returns['cfads']
print(f"✓ Returns calculated: {len(cfads_list)} years of data")

# Display summary
print(f"\n--- Financial Summary (Post-All-Adjustments) ---")
print(f"Project IRR: {returns['project']['project_irr']*100:.2f}%")
print(f"Project NPV (10%): ${returns['project']['project_npv']:,.2f}")
print(f"Equity IRR: {returns['equity']['equity_irr']*100:.2f}%")
print(f"Equity NPV (12%): ${returns['equity']['equity_npv']:,.2f}")

# Calculate LLCR/PLCR
print("\n--- Computing Coverage Ratios (LLCR/PLCR) ---")
print("LLCR: Loan Life Coverage Ratio (NPV of remaining CFADS / Debt Outstanding)")
print("PLCR: Project Life Coverage Ratio (NPV of all CFADS / Debt Outstanding)")
debt_outstanding_list = returns['debt_outstanding']  # ← NEW: Get from returns
llcr_summary = calculate_llcr(cfads_list, debt_outstanding_list, discount_rate=0.10)
plcr_summary = calculate_plcr(cfads_list, debt_outstanding_list, discount_rate=0.10)
dscr_min = min(
    [cfads_list[y] / ds_list[y] for y in range(len(ds_list)) if ds_list[y] > 1e-7],
    default=0
)
print(f"✓ Coverage ratios calculated")


print(f"\n--- Coverage Summary ---")
print(f"Minimum DSCR: {dscr_min:.2f}x")
print(f"Minimum LLCR: {llcr_summary['llcr_min']:.2f}x")
print(f"Minimum PLCR: {plcr_summary['plcr_min']:.2f}x")

# Create output directory
outputs_dir = Path(__file__).parent.parent / 'outputs'
outputs_dir.mkdir(parents=True, exist_ok=True)

# Generate Executive Summary
print("\n--- Generating Executive Summary ---")
print("Output: All financial years with coverage ratios and full financials")
exec_summary = generate_executive_summary(
    params,
    returns,
    dscr_min,
    llcr_summary,
    plcr_summary,
    output_path=outputs_dir / 'executive_summary.md'
)
print(f"✓ Written to: {outputs_dir / 'executive_summary.md'}")

# Generate DFI/Lender Pack
print("\n--- Generating DFI/Lender Due Diligence Pack ---")
print("Output: Full debt tenor + covenant compliance + all financials")
dfi_pack = generate_dfi_lender_pack(
    params,
    returns,
    dscr_min,
    llcr_summary,
    plcr_summary,
    output_path=outputs_dir / 'dfi_lender_pack.md'
)
print(f"✓ Written to: {outputs_dir / 'dfi_lender_pack.md'}")

# Final summary
print("\n" + "=" * 80)
print("MARKDOWN REPORTS GENERATED SUCCESSFULLY")
print("=" * 80)
print("\n✓ Reports created:")
print(f"  1. {outputs_dir / 'executive_summary.md'}")
print(f"  2. {outputs_dir / 'dfi_lender_pack.md'}")
print(f"\n✓ All {len(cfads_list)} project years included")
print("✓ Full coverage ratios (DSCR, LLCR, PLCR) displayed")
print("✓ Post-tax, post-regulatory, post-risk financials shown")
print("✓ All values parameterized from YAML config")
print("\n✓ Ready for DFI/lender/board review")
print("=" * 80)
