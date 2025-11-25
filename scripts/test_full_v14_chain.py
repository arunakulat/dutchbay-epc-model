from dutchbay_v14chat.finance.cashflow import build_annual_rows_v14
from dutchbay_v14chat.finance.debt import apply_debt_layer

# Example scenario params
params = {
    "project": {"capacity_mw": 100, "capacity_factor": 0.35, "degradation": 0.005},
    "tariff": {"lkr_per_kwh": 50},
    "opex": {"usd_per_year": 1_000_000},
    "capex": {"usd_total": 120_000_000},
    "Financing_Terms": {
        "debt_ratio": 0.70,
        "tenor_years": 15,
        "construction_periods": 2,
        "construction_schedule": [60.0, 60.0],
        "debt_drawdown_pct": [0.5, 0.5],
        "grace_years": 1,
        "interest_only_years": 0,
        "amortization_style": "annuity",
        "target_dscr": 1.30,
        "mix": {"lkr_max": 0.0, "dfi_max": 0.0, "usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08}
    }
}

print("\n--- Phase 1: Cashflow ---")
annual_rows = build_annual_rows_v14(params)
for row in annual_rows:
    print(row)

print("\n--- Phase 2: Debt Layer ---")
debt_result = apply_debt_layer(params, annual_rows)

out_kpis = [
    ("Timeline Count", debt_result.get("timeline_periods")),
    ("Min DSCR", debt_result.get("dscr_min")),
    ("Total IDC capitalized", debt_result.get("total_idc_capitalized")),
    ("Outstanding debt (first 5)", debt_result.get("debt_outstanding", [])[:5]),
    ("DSCR series", debt_result.get("dscr_series")),
    ("Grace years", debt_result.get("grace_periods")),
]
print("\n--- Debt KPIs ---")
for k, v in out_kpis:
    print(f"{k}: {v}")
print("\nTest complete.\n")
