#!/usr/bin/env python3
"""
Schema Guard Integration Test for Analytics Engine (Go With The Flow edition).

Confirms that:
- A valid scenario with all required fields runs without error.
- A scenario missing tax config triggers a failure recorded in batch_metadata.failed.

CANONICAL API CONTRACT:
  sa.run() returns (summary_df, timeseries_df, batch_metadata: BatchResultSummary)
  batch_metadata.failed contains names of scenarios that failed.
  batch_metadata.batch_summary["failed_scenarios"] contains error details.
"""

import json

from analytics.scenario_analytics import ScenarioAnalytics


def _make_good_config():
    """Returns a config dict with all required schema fields for analytics."""
    return {
        "project": {
            "capacity_mw": 100,
            "capacity_factor_pct": 36.0,
            "life_years": 20,
        },
        "capex": {
            "epc_usd": 210_000_000,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
        },
        "opex": {
            "usd_per_year": 2_500_000,
        },
        "tariff": {
            "tariff_lkr_per_kwh": 6.5,
        },
        "parameters": {},
    }


def _make_bad_config():
    """Returns a config dict intentionally missing corporate_tax_rate field."""
    cfg = _make_good_config()
    del cfg["tax"]  # Only tax is missing
    return cfg


def test_scenario_analytics_stops_on_missing_corporate_tax(tmp_path):
    """
    Go With The Flow: Confirm schema validation catches missing tax during batch run.

    The batch runner processes all scenarios and reports failures in batch_metadata,
    not via direct exceptions.
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    good_path = scenarios_dir / "good_case.json"
    bad_path = scenarios_dir / "bad_missing_tax.json"

    good_cfg = _make_good_config()
    bad_cfg = _make_bad_config()

    good_path.write_text(json.dumps(good_cfg), encoding="utf-8")
    bad_path.write_text(json.dumps(bad_cfg), encoding="utf-8")

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=None,
        strict=False,  # Allow partial failure in batch
    )

    # Run returns tuple: (summary_df, timeseries_df, batch_metadata)
    summary_df, timeseries_df, batch_metadata = sa.run()

    # Confirm bad_missing_tax failed (check batch_metadata.failed list)
    assert (
        "bad_missing_tax" in batch_metadata.failed
    ), f"Expected 'bad_missing_tax' in failed list, got {batch_metadata.failed}"

    # Confirm good_case succeeded
    assert (
        "good_case" in batch_metadata.successful
    ), f"Expected 'good_case' in successful list, got {batch_metadata.successful}"

    # Confirm the error message mentions corporate_tax_rate
    failed_scenario = next(
        (
            s
            for s in batch_metadata.batch_summary["failed_scenarios"]
            if s["name"] == "bad_missing_tax"
        ),
        None,
    )
    assert failed_scenario is not None, "bad_missing_tax not in failed_scenarios"

    error_msg = failed_scenario["reason"]
    assert (
        "corporate_tax_rate" in error_msg or "corporate_tax_rate_pct" in error_msg
    ), f"Expected 'corporate_tax_rate' in error message, got: {error_msg}"
