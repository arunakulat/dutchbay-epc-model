"""Tests for Year-1 bridge debt service and CFADS waterfall alignment (#1564).

Issue #1564: In projects where a half-year bridge period precedes commercial operations,
the debt engine sizes debt against a timeline that includes this bridge period with
CFADS_bridge = 0.5 * CFADS_year1.
In the equity waterfall, historical behavior folds the bridge debt service into Year 1
to prevent it from escaping the debt service deductions, but does not fold the matching
bridge CFADS into Year 1 equity cashflow. Under the post-#1452 debt-shortfall model, this
creates an artificial Year 1 shortfall cure in 11 scenarios.

This test suite verifies:
1. `resolve_bridge_period_treatment` correctly resolves config keys:
   - "historical_fold" (default, byte-identical baseline)
   - "equity_cfads_match" (Option A: credits matching bridge CFADS to year 1 equity CF)
   - "construction_capitalized" (Option B: capitalizes bridge debt service)
2. Schema validation fails loud on unrecognized treatments.
3. `_enrich_annual_rows_with_debt` correctly enriches rows according to the selected treatment.
4. Full scenario evaluation cures the artificial Year 1 shortfall under both Option A and Option B.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides, load_scenario_config
from analytics.pipeline_v14_enhanced import _enrich_annual_rows_with_debt
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.debt_v14 import (
    BRIDGE_TREATMENT_CONSTRUCTION_CAPITALIZED,
    BRIDGE_TREATMENT_EQUITY_CFADS_MATCH,
    BRIDGE_TREATMENT_HISTORICAL_FOLD,
    resolve_bridge_period_treatment,
)
from finance.subperiod_coverage_v14 import DEBT_ENRICHMENT_KEYS


def test_resolve_treatment_default_is_historical_fold() -> None:
    """An empty config or config without bridge_period_treatment defaults to historical_fold."""
    assert resolve_bridge_period_treatment({}) == BRIDGE_TREATMENT_HISTORICAL_FOLD
    assert (
        resolve_bridge_period_treatment({"Financing_Terms": {}})
        == BRIDGE_TREATMENT_HISTORICAL_FOLD
    )
    assert (
        resolve_bridge_period_treatment({"finance": {"debt": {}}})
        == BRIDGE_TREATMENT_HISTORICAL_FOLD
    )


def test_resolve_treatment_explicit_modes() -> None:
    """Explicitly configured treatments are recognized under Financing_Terms and debt."""
    cfg_a = {
        "Financing_Terms": {
            "bridge_period_treatment": BRIDGE_TREATMENT_EQUITY_CFADS_MATCH
        }
    }
    assert resolve_bridge_period_treatment(cfg_a) == BRIDGE_TREATMENT_EQUITY_CFADS_MATCH

    cfg_b = {
        "Financing_Terms": {
            "bridge_period_treatment": BRIDGE_TREATMENT_CONSTRUCTION_CAPITALIZED
        }
    }
    assert (
        resolve_bridge_period_treatment(cfg_b)
        == BRIDGE_TREATMENT_CONSTRUCTION_CAPITALIZED
    )

    # Dotted or nested debt structure
    cfg_nested = {
        "finance": {"debt": {"bridge_period_treatment": "EQUITY_CFADS_MATCH"}}
    }
    assert (
        resolve_bridge_period_treatment(cfg_nested)
        == BRIDGE_TREATMENT_EQUITY_CFADS_MATCH
    )


def test_resolve_treatment_case_and_whitespace_insensitive() -> None:
    """Whitespace and mixed casing are normalized."""
    cfg = {"Financing_Terms": {"bridge_period_treatment": "  Equity_CFADS_Match  "}}
    assert resolve_bridge_period_treatment(cfg) == BRIDGE_TREATMENT_EQUITY_CFADS_MATCH


def test_resolve_treatment_unknown_raises_value_error() -> None:
    """An unknown bridge period treatment raises ValueError with available choices."""
    cfg = {"Financing_Terms": {"bridge_period_treatment": "invented_treatment"}}
    with pytest.raises(ValueError, match="Unknown bridge_period_treatment"):
        resolve_bridge_period_treatment(cfg)


def test_schema_guard_validates_bridge_treatment() -> None:
    """validate_config_for_v14 fails loudly on an invalid bridge_period_treatment."""
    base_scenario = Path("scenarios/ceb_solar_bess_nightpeak_10mw.yaml")
    cfg = load_scenario_config(base_scenario)
    cfg_invalid = dict(cfg)
    cfg_invalid["Financing_Terms"] = {
        **dict(cfg.get("Financing_Terms", {})),
        "bridge_period_treatment": "bogus_treatment",
    }
    with pytest.raises(ConfigValidationError, match="Unknown bridge_period_treatment"):
        validate_config_for_v14(cfg_invalid, "<test>", modules=["debt"])


def test_enrich_annual_rows_historical_fold() -> None:
    """Under historical_fold, Year 1 bears bridge debt service but no matching bridge CFADS."""
    annual_rows = [
        {"year": 1, "cfads_usd": 1000.0},
        {"year": 2, "cfads_usd": 1000.0},
    ]
    debt_result = {
        "debt_service_total": [
            300.0,
            400.0,
            150.0,
        ],  # period 0: yr 1, period 1: yr 2, period 2: bridge
        "interest_total": [50.0, 60.0, 25.0],
        "balloon_resolution": [0.0, 0.0, 0.0],
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "debt_period": 0},
            {"annual_row_index": 1, "debt_period": 1},
        ],
        "cfads_bridge_debt_period": 2,
    }
    cfg = {"Financing_Terms": {"bridge_period_treatment": "historical_fold"}}
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result, config=cfg)

    # Year 1 bears its own 300.0 + bridge 150.0 = 450.0
    assert enriched[0]["debt_service_total"] == pytest.approx(450.0)
    assert enriched[0]["interest_usd"] == pytest.approx(75.0)
    # Year 1 CFADS is untouched at 1000.0
    assert enriched[0]["cf_pre_debt"] == pytest.approx(1000.0)
    assert enriched[0]["cf_after_debt"] == pytest.approx(550.0)
    assert enriched[0]["bridge_period_treatment"] == "historical_fold"
    assert enriched[0]["bridge_debt_service_usd"] == pytest.approx(150.0)
    assert enriched[0]["bridge_cfads_usd"] == pytest.approx(0.0)

    # Year 2 is untouched
    assert enriched[1]["debt_service_total"] == pytest.approx(400.0)
    assert enriched[1]["cf_pre_debt"] == pytest.approx(1000.0)


def test_enrich_annual_rows_equity_cfads_match() -> None:
    """Under equity_cfads_match, Year 1 bears bridge debt service AND gets matching bridge CFADS credited."""
    annual_rows = [
        {"year": 1, "cfads_usd": 1000.0},
        {"year": 2, "cfads_usd": 1000.0},
    ]
    debt_result = {
        "debt_service_total": [300.0, 400.0, 150.0],
        "interest_total": [50.0, 60.0, 25.0],
        "balloon_resolution": [0.0, 0.0, 0.0],
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "debt_period": 0},
            {"annual_row_index": 1, "debt_period": 1},
        ],
        "cfads_bridge_debt_period": 2,
    }
    cfg = {"Financing_Terms": {"bridge_period_treatment": "equity_cfads_match"}}
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result, config=cfg)

    # Year 1 bears 450.0 service
    assert enriched[0]["debt_service_total"] == pytest.approx(450.0)
    # Year 1 CFADS is 1000.0 + (0.5 * 1000.0) = 1500.0
    assert enriched[0]["cf_pre_debt"] == pytest.approx(1500.0)
    assert enriched[0]["cf_after_debt"] == pytest.approx(1050.0)
    assert enriched[0]["bridge_period_treatment"] == "equity_cfads_match"
    assert enriched[0]["bridge_debt_service_usd"] == pytest.approx(
        1500.0 * 0.1
    )  # 150.0
    assert enriched[0]["bridge_cfads_usd"] == pytest.approx(500.0)


def test_enrich_annual_rows_construction_capitalized() -> None:
    """Under construction_capitalized, Year 1 does NOT bear bridge debt service."""
    annual_rows = [
        {"year": 1, "cfads_usd": 1000.0},
        {"year": 2, "cfads_usd": 1000.0},
    ]
    debt_result = {
        "debt_service_total": [300.0, 400.0, 150.0],
        "interest_total": [50.0, 60.0, 25.0],
        "balloon_resolution": [0.0, 0.0, 0.0],
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "debt_period": 0},
            {"annual_row_index": 1, "debt_period": 1},
        ],
        "cfads_bridge_debt_period": 2,
    }
    cfg = {"Financing_Terms": {"bridge_period_treatment": "construction_capitalized"}}
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result, config=cfg)

    # Year 1 bears only its own 300.0 debt service
    assert enriched[0]["debt_service_total"] == pytest.approx(300.0)
    assert enriched[0]["interest_usd"] == pytest.approx(50.0)
    assert enriched[0]["cf_pre_debt"] == pytest.approx(1000.0)
    assert enriched[0]["cf_after_debt"] == pytest.approx(700.0)
    assert enriched[0]["bridge_period_treatment"] == "construction_capitalized"
    assert enriched[0]["bridge_debt_service_usd"] == pytest.approx(0.0)
    assert enriched[0]["bridge_cfads_usd"] == pytest.approx(0.0)


def test_ceb_solar_bess_scenario_treatment_comparison(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verifies that the artificial Year 1 shortfall in ceb_solar_bess is cured under equity_cfads_match."""
    scen = "scenarios/ceb_solar_bess_nightpeak_10mw.yaml"

    # 1. Baseline: historical fold exhibits Year 1 shortfall
    caplog.clear()
    res_hist = cast(
        dict[str, Any], evaluate_with_overrides(scen, {}, return_full_result=True)
    )
    kpis_hist = cast(dict[str, Any], res_hist["kpis"])
    assert any("debt-service shortfall of USD" in rec.message for rec in caplog.records)
    irr_hist = kpis_hist.get("equity_irr")
    assert irr_hist is not None and irr_hist > 0.0

    # 2. Option A: equity_cfads_match eliminates the Year 1 shortfall and improves equity IRR
    caplog.clear()
    res_match = cast(
        dict[str, Any],
        evaluate_with_overrides(
            scen,
            {"Financing_Terms.bridge_period_treatment": "equity_cfads_match"},
            return_full_result=True,
        ),
    )
    kpis_match = cast(dict[str, Any], res_match["kpis"])
    # No shortfall warnings logged
    assert not any(
        "debt-service shortfall of USD" in rec.message for rec in caplog.records
    )
    irr_match = kpis_match.get("equity_irr")
    assert irr_match is not None and irr_match > irr_hist

    # 3. Option B: construction_capitalized also eliminates the Year 1 shortfall
    caplog.clear()
    res_cap = cast(
        dict[str, Any],
        evaluate_with_overrides(
            scen,
            {"Financing_Terms.bridge_period_treatment": "construction_capitalized"},
            return_full_result=True,
        ),
    )
    kpis_cap = cast(dict[str, Any], res_cap["kpis"])
    assert not any(
        "debt-service shortfall of USD" in rec.message for rec in caplog.records
    )
    irr_cap = kpis_cap.get("equity_irr")
    assert irr_cap is not None and irr_cap > irr_hist


def test_debt_enrichment_keys_cover_bridge_row_fields() -> None:
    """Enriched bridge metadata keys are stripped before sub-annual allocation."""
    assert {
        "bridge_period_treatment",
        "bridge_debt_service_usd",
        "bridge_cfads_usd",
    } <= DEBT_ENRICHMENT_KEYS
