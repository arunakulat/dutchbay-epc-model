#!/usr/bin/env python3
"""
Unit tests for Scenario Analytics dataframe construction (Go With The Flow edition).

Tests the canonical API contract:
  sa.run() returns (summary_df, timeseries_df, batch_metadata)
"""

import pytest
from pathlib import Path
from analytics.scenario_analytics import ScenarioAnalytics

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
    
    # Use a real scenario if available; for test, use minimal valid config
    lendercase_config = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "capex": {
            "epc_usd": 225_000_000,
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
        "Financing_Terms": {
            "debt_ratio": 0.70,
            "tenor_years": 15,
        },
        "parameters": {},
    }
    
    import json
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
    
    # Assertions on summary_df
    assert summary_df is not None, "summary_df is None"
    assert isinstance(summary_df, __import__("pandas").DataFrame), \
        f"summary_df must be DataFrame, got {type(summary_df)}"
    assert len(summary_df) > 0, "summary_df is empty"
    assert "scenario_name" in summary_df.columns or summary_df.index.name == "scenario_name", \
        "scenario_name not found as column or index"
    
    # Assertions on timeseries_df
    assert timeseries_df is not None, "timeseries_df is None"
    assert isinstance(timeseries_df, __import__("pandas").DataFrame), \
        f"timeseries_df must be DataFrame, got {type(timeseries_df)}"
    assert len(timeseries_df) > 0, "timeseries_df is empty"
    assert "scenario_name" in timeseries_df.columns, \
        "scenario_name not found in timeseries_df columns"
    
    # Assertions on batch_metadata
    assert batch_metadata is not None, "batch_metadata is None"
    assert hasattr(batch_metadata, "successful"), \
        "batch_metadata missing 'successful' attribute"
    assert hasattr(batch_metadata, "failed"), \
        "batch_metadata missing 'failed' attribute"
    assert batch_metadata.n_success >= 1, \
        f"Expected at least 1 successful scenario, got {batch_metadata.n_success}"
    
    # Confirm scenario name in results
    assert "dutchbay_lendercase_2025Q4" in batch_metadata.successful, \
        f"Expected scenario in successful list, got {batch_metadata.successful}"
