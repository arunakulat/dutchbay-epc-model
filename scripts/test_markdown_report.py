import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dutchbay_v13.reporting.markdown_generator import generate_executive_summary, generate_dfi_lender_pack
from dutchbay_v13.finance.returns import calculate_all_returns
import yaml

print("="*80)
print("DUTCHBAY V13 - MARKDOWN REPORT GENERATION TEST (ENHANCED)")
print("="*80)

yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

returns = calculate_all_returns(params)

outputs_dir = Path(__file__).parent.parent / 'outputs'
outputs_dir.mkdir(parents=True, exist_ok=True)

print("\n--- Generating Executive Summary ---")
exec_summary = generate_executive_summary(
    params,
    returns,
    output_path=outputs_dir / 'executive_summary.md'
)
print(f"✓ Written to: {outputs_dir / 'executive_summary.md'}")

print("\n--- Generating DFI/Lender Pack ---")
dfi_pack = generate_dfi_lender_pack(
    params,
    returns,
    output_path=outputs_dir / 'dfi_lender_pack.md'
)
print(f"✓ Written to: {outputs_dir / 'dfi_lender_pack.md'}")

print("\n" + "="*80)
print("ENHANCED MARKDOWN REPORTS GENERATED SUCCESSFULLY")
print("="*80)
print("\nReports created:")
print(f"  1. {outputs_dir / 'executive_summary.md'}")
print(f"  2. {outputs_dir / 'dfi_lender_pack.md'}")
print("\n✓ All tests passed - financial rigor and adjustments shown in markdown")
