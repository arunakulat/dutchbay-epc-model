from dutchbay_v14chat.finance.debt import apply_debt_layer

params = {
    "capex": {"usd_total": 100.0},
    "Financing_Terms": {
        "debt_ratio": 0.70,
        "tenor_years": 15,
        "construction_periods": 2,
        "construction_schedule": [40.0, 60.0],
        "debt_drawdown_pct": [0.5, 0.5],
        "grace_years": 1,
        "interest_only_years": 0,
        "amortization_style": "annuity",
        "target_dscr": 1.30,
        "mix": {"lkr_max": 0.0, "dfi_max": 0.0, "usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08}
    }
}
annual_rows = [{"cfads_usd": 12.0} for _ in range(20)]

result = apply_debt_layer(params, annual_rows)

print("\n=== V14 Construction Period DEBT TEST ===")
print("DSCR series (23 periods):", result["dscr_series"])
print("Min DSCR (operations):", result["dscr_min"])
print("Total IDC capitalized:", result["total_idc_capitalized"])
print("Debt outstanding, first 5:", result["debt_outstanding"][:5])
print("Period count:", result["timeline_periods"])
print("Grace period years:", result["grace_periods"])
print("========================================\n")
