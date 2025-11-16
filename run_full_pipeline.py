import yaml
from dutchbay_v13.finance.cashflow import build_annual_rows
from dutchbay_v13.finance.debt import apply_debt_layer
from dutchbay_v13.finance.returns import summarize_all_returns

with open("full_model_variables_updated.yaml") as f:
    config = yaml.safe_load(f)

if "Financing_Terms" not in config:
    raise RuntimeError("YAML missing 'Financing_Terms' at root")

financing_params = config["Financing_Terms"]

# Build cashflow (CFADS in LKR)
annual_rows = build_annual_rows(config)
cfads_series = [row["cfads_final_lkr"] for row in annual_rows]

# Get FX curve for debt service conversion
start_fx = config.get("fx", {}).get("start_lkr_per_usd", 300.0)
annual_depr = config.get("fx", {}).get("annual_depr", 0.03)
fx_curve = [start_fx * ((1 + annual_depr) ** i) for i in range(len(cfads_series))]

# Get debt service (in USD from debt.py)
debt_results = apply_debt_layer(financing_params, annual_rows)
debt_service_usd = debt_results["debt_service_total"]

# CRITICAL: Convert debt service USD → LKR
debt_service_lkr = [ds_usd * fx for ds_usd, fx in zip(debt_service_usd, fx_curve)]

# Ensure matching lengths
if len(debt_service_lkr) < len(cfads_series):
    debt_service_lkr.extend([0.0] * (len(cfads_series) - len(debt_service_lkr)))
elif len(debt_service_lkr) > len(cfads_series):
    debt_service_lkr = debt_service_lkr[:len(cfads_series)]

print(f"CFADS length: {len(cfads_series)}, Debt Service length: {len(debt_service_lkr)}")
print(f"Debt Service USD (Years 1-3): {[int(ds) for ds in debt_service_usd[:3]]}")
print(f"FX Rates (Years 1-3): {fx_curve[:3]}")
print(f"Debt Service LKR (Years 1-3): {[int(ds) for ds in debt_service_lkr[:3]]}")

# Pass LKR debt service to returns
returns = summarize_all_returns(config, cfads_series, debt_service_lkr)

print("\n=== DutchBay Full Pipeline Results (CORRECTED) ===")
print(f"Project IRR: {returns['summary']['project_irr']:.2%}")
print(f"Equity IRR: {returns['summary']['equity_irr']:.2%}")
print(f"Project NPV: LKR {returns['summary']['project_npv']:,.0f}")
print(f"Equity NPV: LKR {returns['summary']['equity_npv']:,.0f}")
print(f"CFADS (Years 1-3): {[int(cf) for cf in cfads_series[:3]]}")
