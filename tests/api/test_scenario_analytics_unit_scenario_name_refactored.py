"""
Scenario Analytics unit tests - scenario_name labeling and shapes.

Purpose: Validate that ScenarioAnalytics.run() returns correctly shaped
DataFrames with proper scenario_name labeling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from analytics.scenario_analytics import ScenarioAnalytics


def _make_complete_config() -> dict:
    """Create a minimal but complete v14-compatible scenario config."""
    return {
        "project": {
            "name": "Test Project",
            "capacity_mw": 150,
            "capacity_factor_pct": 45.0,
            "degradation_pct": 0.5,
            "grid_loss_pct": 2.0,
            "life_years": 20,
        },
        "capex": {
            "usd_total": 225_000_000,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
            "depreciation_years": 20,
            "tax_holiday_years": 10,
            "tax_holiday_start_year": 1,
            "enhanced_capital_allowance_pct": 150.0,
        },
        "opex": {
            "usd_per_year": 2_500_000,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "statutory": {
            "success_fee_pct": 2.0,
            "env_surcharge_pct": 0.25,
            "social_levy_pct": 0.25,
        },
        "Financing_Terms": {
            "construction_periods": 2,
            "construction_schedule": [50.0, 50.0],
            "debt_drawdown_pct": [0.5, 0.5],
            "grace_years": 0,
            "debt_ratio": 0.70,
            "tenor_years": 15,
            "interest_only_years": 2,
            "amortization_style": "sculpted",
            "target_dscr": 1.30,
            "mix": {
                "lkr_max": 0.25,
                "dfi_max": 0.50,
                "usd_commercial_min": 0.25,
            },
            "rates": {
                "lkr_nominal": 0.16,
                "usd_nominal": 0.08,
                "dfi_nominal": 0.06,
            },
        },
        "risk": {
            "haircut_pct": 10.0,
        },
        "fx": {
            "start_lkr_per_usd": 375.0,
            "annual_depr": 0.02,
        },
    }


def test_scenario_analytics_labels_and_shapes(tmp_path):
    """
    Go With The Flow: Confirm sa.run() returns correct DataFrame shapes and labels.

    Canonical API contract:
      summary_df: per-scenario summary with scenario_name index/column
      timeseries_df: annual rows with scenario_name column
      batch_metadata: BatchResultSummary with successful/failed lists
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()

    # Create a complete, valid config
    lendercase_config = _make_complete_config()

    config_path = scenarios_dir / "dutchbay_lendercase_2025Q4.json"
    config_path.write_text(json.dumps(lendercase_config), encoding="utf-8")

    output_path = tmp_path / "analytics_output.xlsx"

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
        strict=False,
    )

    # CANONICAL API: unpack all three return values
    summary_df, timeseries_df, batch_metadata = sa.run(export_excel=False)

    # Verify summary_df structure
    assert isinstance(summary_df, pd.DataFrame)
    assert len(summary_df) >= 1, "summary_df should have at least one scenario"
    assert (
        "scenario_name" in summary_df.columns
        or "scenario_name" in summary_df.index.names
    )

    # Verify timeseries_df structure
    assert isinstance(timeseries_df, pd.DataFrame)
    assert len(timeseries_df) > 0, "timeseries_df should have annual rows"
    assert "scenario_name" in timeseries_df.columns

    # Verify batch_metadata
    assert batch_metadata is not None
    assert hasattr(batch_metadata, "successful")
    assert hasattr(batch_metadata, "failed")

    # At least one scenario should succeed
    assert len(batch_metadata.successful) >= 1


def test_scenario_analytics_runs_multiple_scenarios(tmp_path):
    """
    Go With The Flow: Confirm sa.run() handles multiple scenarios correctly.
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()

    base_config = _make_complete_config()

    # Create two scenarios
    for i, name in enumerate(["scenario_base", "scenario_stress"]):
        config = base_config.copy()
        config["project"]["name"] = name

        # Stress: lower capacity factor
        if i == 1:
            config["project"]["capacity_factor_pct"] = 35.0

        config_path = scenarios_dir / f"{name}.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

    output_path = tmp_path / "analytics_output.xlsx"

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
        strict=False,
    )

    summary_df, timeseries_df, batch_metadata = sa.run(export_excel=False)

    # Both scenarios should succeed
    assert len(summary_df) == 2, "Should have 2 scenarios in summary"
    assert "scenario_base" in timeseries_df["scenario_name"].values
    assert "scenario_stress" in timeseries_df["scenario_name"].values
