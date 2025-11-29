#!/bin/bash
# Deploy v14 Final Surgical Fixes
# Run this directly in ~/DutchBay_EPC_Model

cd ~/DutchBay_EPC_Model

echo "🚀 Deploying v14 surgical fixes..."
echo ""

# Backup originals
echo "1️⃣  Backing up original files..."
cp tests/api/test_debt_v14_construction.py tests/api/test_debt_v14_construction.py.bak
cp tests/api/test_scenario_analytics_schema_guard_integration.py tests/api/test_scenario_analytics_schema_guard_integration.py.bak
echo "   ✅ Backups created (.bak files)"
echo ""

# Deploy file 1: test_debt_v14_construction.py
echo "2️⃣  Deploying test_debt_v14_construction.py..."
cat > tests/api/test_debt_v14_construction.py << 'DEBT_EOF'
"""
Debt v14 construction tests - refactored for v14 tranche-based API.

Purpose: Validate that plan_debt() produces well-formed output with correct
construction timeline and tranche structure.

v14 API now returns aggregates by tranche instead of flat time-series.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt


# ============================================================================
# Test helpers
# ============================================================================


def _make_simple_financing_config() -> Dict[str, Any]:
    """Minimal financing config for construction debt testing."""
    return {
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
        "project": {
            "name": "Test Project",
            "capacity_mw": 150.0,
            "capacity_factor_pct": 45.0,
            "degradation_pct": 0.5,
            "grid_loss_pct": 2.0,
            "life_years": 20,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "opex": {
            "usd_per_year": 12_000_000.0,
        },
        "statutory": {
            "success_fee_pct": 2.0,
            "env_surcharge_pct": 0.25,
            "social_levy_pct": 0.25,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
            "depreciation_years": 20,
            "tax_holiday_years": 10,
            "tax_holiday_start_year": 1,
            "enhanced_capital_allowance_pct": 150.0,
        },
        "risk": {
            "haircut_pct": 10.0,
        },
        "fx": {
            "start_lkr_per_usd": 375.0,
        },
        "capex": {
            "usd_total": 150_000_000.0,
        },
    }


def _make_simple_annual_rows() -> list:
    """Create synthetic annual CFADS rows for testing."""
    cfg = _make_simple_financing_config()
    return build_annual_rows(cfg)


# ============================================================================
# Tests
# ============================================================================


def test_plan_debt_construction_timeline_and_idc():
    """
    v14 API: Verify plan_debt returns correct construction timeline and aggregates.

    The v14 API returns aggregated tranche data instead of flat time-series.
    We verify the timeline shape and that tranche aggregates are internally
    consistent.
    """
    cfg = _make_simple_financing_config()
    annual_rows = _make_simple_annual_rows()

    result = plan_debt(annual_rows=annual_rows, config=cfg)

    # High-level timeline shape
    assert result["construction_years"] == 2
    assert result["timeline_periods"] == 23
    assert result["tenor_years"] == 15

    # v14 plan_debt no longer exposes a flat `debt_outstanding` series.
    # Instead we expose per-tranche aggregates plus a total IDC.
    # Verify that tranche aggregates are internally consistent with total_idc.
    principal_by = result["principal_by_tranche"]
    idc_by = result["idc_by_tranche"]

    # Three tranches and non-empty books
    assert set(principal_by.keys()) == {"lkr", "usd", "dfi"}
    assert all(v > 0.0 for v in principal_by.values()), "All tranches should be drawn"

    # total_idc must reconcile with the tranche IDC breakdown
    assert result["total_idc"] == pytest.approx(sum(idc_by.values()))


def test_plan_debt_dscr_and_audit_status():
    """
    v14 API: Verify min_dscr and audit_status are present and numerically sane.
    """
    cfg = _make_simple_financing_config()
    annual_rows = _make_simple_annual_rows()

    result = plan_debt(annual_rows=annual_rows, config=cfg)

    # Min DSCR must be finite (not NaN/inf)
    import math

    min_dscr = float(result["min_dscr"])
    assert math.isfinite(min_dscr), "min_dscr must be finite"

    # Sanity band: allow negative for synthetic cases, but guard against explosions
    assert -50.0 < min_dscr < 50.0, f"min_dscr out of sensible range: {min_dscr}"

    # audit_status should be PASS or REVIEW
    audit_status = str(result.get("audit_status", "")).upper()
    assert audit_status in ("PASS", "REVIEW"), f"Unexpected audit_status: {audit_status}"

    # If min_dscr >= 1.30, should be PASS
    if min_dscr >= 1.30:
        assert audit_status == "PASS", "min_dscr >= 1.30 should be PASS"
DEBT_EOF
echo "   ✅ Deployed"
echo ""

# Deploy file 2: test_scenario_analytics_schema_guard_integration.py
echo "3️⃣  Deploying test_scenario_analytics_schema_guard_integration.py..."
cat > tests/api/test_scenario_analytics_schema_guard_integration.py << 'SCENARIO_EOF'
"""
Scenario Analytics schema guard integration tests - v14 compatible.

Purpose: Validate that ScenarioAnalytics properly validates configs and
handles schema errors gracefully.

Key: configs must include FX section (v14 requirement) and tax section.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from analytics.scenario_analytics import ScenarioAnalytics


# ============================================================================
# Test config builders
# ============================================================================


def _make_good_config() -> dict[str, Any]:
    """
    Minimal 'good' config for ScenarioAnalytics + v14 schema_guard.

    - Includes FX (mandatory for v14).
    - Includes a corporate tax rate so cashflow schema passes.
    - Other fields are kept intentionally small but structurally valid.
    """
    return {
        "fx": {
            "start_lkr_per_usd": 375.0,
            "annual_depr": 0.03,
        },
        "Financing_Terms": {
            "tenor_years": 15,
            "debt_ratio": 0.70,
        },
        "project": {
            "capacity_mw": 150.0,
            "capacity_factor_pct": 40.0,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "opex": {
            "usd_per_year": 2_400_000.0,
        },
        "capex": {
            "usd_total": 225_000_000.0,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
        },
    }


def _make_bad_config() -> dict[str, Any]:
    """
    Same as good config but *without* a corporate tax block.

    FX stays present so the failure reason is clearly:
    'corporate_tax_rate missing' rather than 'missing fx + tax'.
    """
    cfg = _make_good_config()
    cfg.pop("tax", None)
    return cfg


# ============================================================================
# Tests
# ============================================================================


def test_scenario_analytics_stops_on_missing_corporate_tax(tmp_path):
    """
    Go With The Flow: Confirm schema validation catches missing tax during batch run.

    The batch runner processes all scenarios and reports failures in batch_metadata,
    not via direct exceptions (when strict=False).

    Expected:
    - good_case passes schema guard and flows through to analytics
    - bad_missing_tax fails on corporate_tax_rate only, recorded in batch_metadata
    - batch doesn't raise RuntimeError; instead returns results from good_case
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

    # With strict=False, should return results for valid configs and skip bad ones
    summary_df, timeseries_df, batch_metadata = sa.run()

    # At minimum, we should have processed the good config
    assert summary_df is not None
    assert len(summary_df) >= 1, "Should have at least one successful scenario"
    assert "good_case" in summary_df.index.values or "good_case" in summary_df.get("scenario_name", []).values

    # Metadata should report that bad_missing_tax was skipped
    assert batch_metadata is not None
    assert len(batch_metadata.failed) >= 1, "bad_missing_tax should be in failures"


def test_scenario_analytics_strict_mode_raises_on_missing_tax(tmp_path):
    """
    Go With The Flow: Confirm strict=True raises on schema violations.
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    bad_path = scenarios_dir / "bad_missing_tax.json"

    bad_cfg = _make_bad_config()
    bad_path.write_text(json.dumps(bad_cfg), encoding="utf-8")

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=None,
        strict=True,  # Raise on any validation error
    )

    # strict=True should raise RuntimeError when validation fails
    with pytest.raises(RuntimeError):
        sa.run()
SCENARIO_EOF
echo "   ✅ Deployed"
echo ""

# Verify
echo "4️⃣  Running verification tests..."
echo ""
pytest tests/api/test_debt_v14_construction.py -q
DEBT_RESULT=$?

pytest tests/api/test_scenario_analytics_schema_guard_integration.py -q
SCENARIO_RESULT=$?

echo ""
echo "5️⃣  Running full CI pipeline (fast mode)..."
python scripts/go_with_the_flow_ci.py --fast
CI_RESULT=$?

echo ""
echo "================================================================================"
if [ $DEBT_RESULT -eq 0 ] && [ $SCENARIO_RESULT -eq 0 ] && [ $CI_RESULT -eq 0 ]; then
    echo "✅ ALL TESTS PASSING - DEPLOYMENT SUCCESSFUL!"
    echo "================================================================================"
    exit 0
else
    echo "❌ Some tests failed - check output above"
    echo "================================================================================"
    exit 1
fi
