#!/usr/bin/env python3
"""
Integration tests for ScenarioAnalytics with schema guard enforcement.

Go with the Flow Compliance (v3.0):
  - R5: Schema guard always enforced (no bypass mechanism)
  - R22: All scenarios must be v14-compliant
  - Batch runner reports failures in metadata, not via exceptions
"""

import json
from pathlib import Path

from analytics.scenario_analytics import ScenarioAnalytics


def _make_good_config():
    """Minimal v14-compliant config."""
    return {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "capex": {
            "epc_usd": 225_000_000,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,  # ✅ Required field
        },
        "opex": {
            "usd_per_year": 2_500_000,
        },
        "tariff": {
            "tariff_lkr_per_kwh": 6.5,
        },
        "Financing_Terms": {
            "debt_ratio": 0.70,
            "tenor_years": 15,
        },
        "fx": {
            "start_lkr_per_usd": 300.0,
            "annual_depr": 0.03,
        },
        "parameters": {},
    }


def _make_bad_config():
    """Config missing required tax field (violates R5)."""
    cfg = _make_good_config()
    del cfg["tax"]  # ❌ Schema guard will reject this
    return cfg


def test_scenario_analytics_stops_on_missing_corporate_tax(tmp_path):
    """
    Go With The Flow R5/R22: Schema guard catches missing tax during batch run.

    The batch runner processes all scenarios and reports failures in batch_metadata.
    Good scenarios pass through; bad ones are logged and excluded from results.

    Expected:
    - good_case passes schema guard and flows through to analytics
    - bad_missing_tax fails schema validation, recorded in batch_metadata.failed
    - Batch returns results from good_case only
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    good_path = scenarios_dir / "good_case.json"
    bad_path = scenarios_dir / "bad_missing_tax.json"

    good_cfg = _make_good_config()
    bad_cfg = _make_bad_config()

    good_path.write_text(json.dumps(good_cfg), encoding="utf-8")
    bad_path.write_text(json.dumps(bad_cfg), encoding="utf-8")

    # ✅ R5: Schema validation always enforced (no strict parameter)
    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=None,
    )

    # Run batch - bad scenario should fail gracefully
    summary_df, timeseries_df, batch_meta = sa.run(export_excel=False)

    # Assertions
    assert batch_meta.n_success == 1, "Expected 1 successful scenario"
    assert batch_meta.n_failed == 1, "Expected 1 failed scenario"
    assert "good_case" in batch_meta.successful
    assert "bad_missing_tax" in batch_meta.failed

    # Good scenario should have results
    assert len(summary_df) == 1, "Expected 1 row in summary"
    assert (
        "good_case" in summary_df.index
        or "good_case" in summary_df["scenario_name"].values
    )


def test_scenario_analytics_all_bad_scenarios_raises(tmp_path):
    """
    Go With The Flow R5: Batch with all invalid scenarios raises RuntimeError.

    Per VAL-02, if ALL scenarios fail schema validation, the batch should
    raise RuntimeError since there are no results to summarize.
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    bad_path = scenarios_dir / "bad_missing_tax.json"

    bad_cfg = _make_bad_config()
    bad_path.write_text(json.dumps(bad_cfg), encoding="utf-8")

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=None,
    )

    # Expected: RuntimeError when all scenarios fail
    try:
        sa.run(export_excel=False)
        assert False, "Expected RuntimeError when all scenarios fail"
    except RuntimeError as e:
        assert "All scenarios failed" in str(e)


# EOF
