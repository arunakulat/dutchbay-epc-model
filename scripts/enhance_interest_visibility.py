"""
Sprint 16 Enhancement: Add interest_usd visibility to annual_rows

This enhancement extends the DSCR fix to also expose interest separately
in annual_rows for Excel exports.

Changes:
1. Extract interest schedules from debt_result['debt_schedules']
2. Aggregate interest across all tranches (LKR, USD, DFI)
3. Add 'interest_usd' field to each annual row
4. Add 'principal_repayment_usd' field for transparency

Integration Point: analytics/pipeline_v14.py::_merge_debt_service_into_annual_rows()
"""


def _merge_debt_service_into_annual_rows_enhanced(
    annual_rows: list[dict[str, any]],
    debt_result: dict[str, any],
) -> None:
    """Merge debt service schedule AND interest breakdown from debt_result into annual_rows.

    ENHANCEMENT: Now also adds 'interest_usd' and 'principal_repayment_usd' fields
    for complete debt service visibility in Excel exports.

    Adds these fields to each annual row:
    - debt_service_usd: Total debt service (interest + principal)
    - interest_usd: Interest component only
    - principal_repayment_usd: Principal repayment component only
    - dscr: Debt Service Coverage Ratio

    Modifies annual_rows in-place.

    Parameters
    ----------
    annual_rows : list[dict[str, Any]]
        Annual cashflow rows from build_annual_rows
    debt_result : dict[str, Any]
        Debt result from plan_debt containing:
        - debt_service_total: Total service schedule
        - dscr_series: DSCR series
        - debt_schedules: Per-tranche schedules with (interest, principal, service) tuples

    Notes
    -----
    Period mapping: Year 1 → Period 2 (after 2 construction periods 0-1)
    inf DSCR values (construction years) are converted to 0.0
    Interest is aggregated from all tranches (LKR, USD, DFI)
    """
    import logging

    logger = logging.getLogger(__name__)

    debt_service_schedule = debt_result.get("debt_service_total", [])
    dscr_series = debt_result.get("dscr_series", [])
    debt_schedules = debt_result.get("debt_schedules", {})

    logger.info(
        "Merging debt service + interest breakdown into %d annual rows",
        len(annual_rows),
    )

    # Build aggregated interest and principal schedules
    # debt_schedules is dict: {'LKR': [(int, prin, svc), ...], 'USD': [...], 'DFI': [...]}
    max_periods = (
        max(len(sched) for sched in debt_schedules.values()) if debt_schedules else 0
    )

    interest_schedule_usd = []
    principal_schedule_usd = []

    for period in range(max_periods):
        period_interest = 0.0
        period_principal = 0.0

        for tranche_name, schedule in debt_schedules.items():
            if period < len(schedule):
                interest, principal, service = schedule[period]
                period_interest += float(interest)
                period_principal += float(principal)

        interest_schedule_usd.append(period_interest)
        principal_schedule_usd.append(period_principal)

    logger.debug(
        "Built interest schedule: %d periods, range $%.0f to $%.0f",
        len(interest_schedule_usd),
        min(interest_schedule_usd) if interest_schedule_usd else 0,
        max(interest_schedule_usd) if interest_schedule_usd else 0,
    )

    # Merge into annual_rows
    for idx, row in enumerate(annual_rows):
        year = int(row.get("year", idx + 1))
        # Period mapping: construction years + operational years
        # Year 1 maps to period 2 (after 2 construction periods 0-1)
        period = year + 1

        if period < len(debt_service_schedule):
            # Debt service (already in USD)
            row["debt_service_usd"] = debt_service_schedule[period]

            # DSCR
            dscr_val = dscr_series[period] if period < len(dscr_series) else 0.0
            row["dscr"] = dscr_val if dscr_val != float("inf") else 0.0

            # NEW: Interest and principal breakdown
            if period < len(interest_schedule_usd):
                row["interest_usd"] = interest_schedule_usd[period]
                row["principal_repayment_usd"] = principal_schedule_usd[period]
            else:
                row["interest_usd"] = 0.0
                row["principal_repayment_usd"] = 0.0
        else:
            row["debt_service_usd"] = 0.0
            row["dscr"] = 0.0
            row["interest_usd"] = 0.0
            row["principal_repayment_usd"] = 0.0

    # Log statistics
    dscr_values = [r.get("dscr", 0) for r in annual_rows if r.get("dscr", 0) > 0]
    interest_values = [
        r.get("interest_usd", 0) for r in annual_rows if r.get("interest_usd", 0) > 0
    ]

    if dscr_values:
        logger.info(
            "Successfully merged debt service: min DSCR=%.2f, max DSCR=%.2f, avg DSCR=%.2f",
            min(dscr_values),
            max(dscr_values),
            sum(dscr_values) / len(dscr_values),
        )

    if interest_values:
        logger.info(
            "Successfully merged interest: min=$%.0f, max=$%.0f, avg=$%.0f",
            min(interest_values),
            max(interest_values),
            sum(interest_values) / len(interest_values),
        )
    else:
        logger.warning("No positive interest values found after merge")


# Test the enhancement
if __name__ == "__main__":
    import json

    print("=" * 80)
    print("SPRINT 16 ENHANCEMENT: Interest Visibility")
    print("=" * 80)

    # Load test data
    with open("out/dutchbay_lendercase_2025Q4_results.json") as f:
        results = json.load(f)

    annual_rows = results["annual_rows"]
    debt_result = results["debt_result"]

    print(f"\n📊 Current State:")
    print(f"  Annual rows: {len(annual_rows)}")
    print(f"  Has interest_usd: {'interest_usd' in annual_rows[0]}")
    print(
        f"  Has principal_repayment_usd: {'principal_repayment_usd' in annual_rows[0]}"
    )

    # Apply enhancement
    _merge_debt_service_into_annual_rows_enhanced(annual_rows, debt_result)

    print(f"\n✅ Enhanced State:")
    print(f"  Has interest_usd: {'interest_usd' in annual_rows[0]}")
    print(
        f"  Has principal_repayment_usd: {'principal_repayment_usd' in annual_rows[0]}"
    )

    print(f"\n📈 Sample Data (First 10 Years):")
    print("=" * 100)
    print(
        f"{'Year':<6} {'DSCR':<8} {'Debt Service':<18} {'Interest':<18} {'Principal':<18}"
    )
    print("-" * 100)

    for row in annual_rows[:10]:
        year = row.get("year", 0)
        dscr = row.get("dscr", 0)
        debt_svc = row.get("debt_service_usd", 0)
        interest = row.get("interest_usd", 0)
        principal = row.get("principal_repayment_usd", 0)

        dscr_str = f"{dscr:.2f}" if dscr > 0 else "N/A"
        print(
            f"{year:<6.0f} {dscr_str:<8} ${debt_svc:>16,.0f} ${interest:>16,.0f} ${principal:>16,.0f}"
        )

    print("=" * 100)
    print("\n✅ Enhancement complete! Interest is now visible in annual_rows.")
