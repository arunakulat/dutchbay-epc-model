"""Smoke tests for the v14 cashflow module.

Canonical engine path (from repo root):
    dutchbay_v14chat/finance/cashflow.py

These tests pin the public-ish CFADS surface so that future refactors
can't silently break behaviour.
"""

from pathlib import Path
import sys

import pytest

from constants import HOURS_PER_YEAR

# ---------------------------------------------------------------------------
# Ensure repo root (/DutchBay_EPC_Model) is on sys.path
# ---------------------------------------------------------------------------

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]  # .../DutchBay_EPC_Model

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Canonical import: v14chat cashflow engine
# ---------------------------------------------------------------------------

from dutchbay_v14chat.finance import cashflow as cf_mod  # type: ignore


def test_cashflow_module_path_is_v14chat():
    """Ensure we are really testing the v14chat cashflow engine at the expected path."""
    cf_path = Path(cf_mod.__file__).as_posix()
    assert "dutchbay_v14chat/finance/cashflow.py" in cf_path, cf_path


def test_net_production_uses_hours_per_year_constant():
    """_calculate_net_production should be consistent with HOURS_PER_YEAR."""
    # 1 MW, 50% CF, no degradation, no grid losses, year 0
    capacity_mw = 1.0
    capacity_factor = 0.5
    degradation = 0.0
    grid_loss_pct = 0.0
    year = 0

    gross_kwh, net_kwh = cf_mod._calculate_net_production(  # type: ignore[attr-defined]
        capacity_mw,
        capacity_factor,
        degradation,
        grid_loss_pct,
        year,
    )

    expected_gross = capacity_mw * 1000.0 * HOURS_PER_YEAR * capacity_factor
    assert gross_kwh == pytest.approx(expected_gross, rel=1e-9)
    # With zero grid losses, net and gross should match
    assert net_kwh == pytest.approx(gross_kwh, rel=1e-9)


def test_build_annual_cfads_minimal_valid_params():
    """build_annual_cfads should produce a sensible CFADS series for a simple config."""
    params = {
        "project": {
            "capacity_mw": 100.0,
            "capacity_factor": 0.40,
        },
        "tariff": {
            "lkr_per_kwh": 20.0,
        },
        "opex": {
            "usd_per_year": 3_000_000.0,
        },
        # Simplest way to fix the project life:
        "returns": {
            "project_life_years": 5,
        },
        # Optional explicit tax block to avoid surprises
        "tax": {
            "corporate_tax_rate": 0.30,
            "depreciation_years": 15,
            "tax_holiday_years": 0,
            "tax_holiday_start_year": 1,
            "enhanced_capital_allowance_pct": 1.0,
        },
    }

    # Validate should produce no ERRORs
    issues = cf_mod.validate_parameters(params)  # type: ignore[attr-defined]
    assert not any("ERROR" in msg for msg in issues)

    cfads = cf_mod.build_annual_cfads(params)  # type: ignore[attr-defined]

    # We asked for 5 project life years, so CFADS list should have length 5
    assert len(cfads) == 5
    # All entries should be numeric
    assert all(isinstance(x, (int, float)) for x in cfads)
    # And it should not be a degenerate all-zero series
    assert any(x != 0.0 for x in cfads)
