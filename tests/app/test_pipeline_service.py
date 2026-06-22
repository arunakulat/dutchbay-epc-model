"""Tests for the framework-agnostic service seam (app.services.pipeline_service).

The service adds no finance logic — it delegates to the canonical
``run_v14_pipeline`` and the wind adapter. These tests drive the LIVE engine
through the canonical lender scenario (loaded by repo-relative path, never an
absolute one) and assert structure / invariants / fail-fast behaviour, not
hardcoded economic magic numbers.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.scenario_loader import load_scenario_config
from app.services.pipeline_service import (
    DEFAULT_VALIDATION_MODULES,
    run_finance_case,
    run_integrated_case,
)
from wind_resource.cashflow_adapter import WindAdapterDriftError

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

REQUIRED_KPIS = {"project_irr", "equity_irr", "min_dscr", "avg_dscr", "llcr", "plcr"}


def _scenario() -> Dict[str, Any]:
    """The canonical lender scenario as a fresh in-memory dict."""
    return dict(load_scenario_config(str(LENDER_SCENARIO)))


def _valid_wind_export() -> Dict[str, Any]:
    """A schema-valid P75 wind export (CF in percent; capacity = 150 MW)."""
    return {
        "scenario": "P75",
        "annual_generation_mwh": 286_300.0,
        "capacity_factor_percent": 33.9,
        "revenue_annual_usd": 19_400_000.0,
        "revenue_cumulative_usd": 388_000_000.0,
        "project_capacity_mw": 150.0,
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10_000.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.30,
        "exchange_rate_lkr_usd": 333.79,
    }


# --------------------------------------------------------------------------- #
# run_finance_case
# --------------------------------------------------------------------------- #
def test_run_finance_case_returns_lender_kpis() -> None:
    result = run_finance_case(_scenario())
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    kpis = result["kpis"]
    assert REQUIRED_KPIS <= set(kpis)
    assert kpis["min_dscr"] > 0
    assert isinstance(result["annual_rows"], list) and result["annual_rows"]


def test_run_finance_case_validation_modules_none_runs() -> None:
    # The validation_modules=None branch validates all registered modules.
    result = run_finance_case(_scenario(), validation_modules=None)
    assert result["status"] == "success"


def test_run_finance_case_default_modules_constant() -> None:
    assert DEFAULT_VALIDATION_MODULES == ("cashflow", "debt")


def test_run_finance_case_does_not_mutate_input() -> None:
    scen = _scenario()
    before = copy.deepcopy(scen)
    run_finance_case(scen)
    assert scen == before


def test_run_finance_case_fails_fast_on_invalid_scenario() -> None:
    # CESSPIT: strict validation rejects an empty config rather than degrading.
    with pytest.raises(Exception):
        run_finance_case({})


# --------------------------------------------------------------------------- #
# run_integrated_case
# --------------------------------------------------------------------------- #
def test_run_integrated_case_overwrite_runs_finance() -> None:
    result = run_integrated_case(
        _scenario(), _valid_wind_export(), adapter_mode="overwrite"
    )
    assert result["status"] == "success"
    assert REQUIRED_KPIS <= set(result["kpis"])


def test_run_integrated_case_rejects_plevel_mismatch() -> None:
    # Export is P75 but caller asks for P50 -> refuse to mix P-levels.
    with pytest.raises(ValueError, match="refusing to mix|scenario"):
        run_integrated_case(
            _scenario(), _valid_wind_export(), scenario_name="P50"
        )


def test_run_integrated_case_drift_raises_in_fill_mode() -> None:
    # fill_if_absent compares a present scenario value against the export; a
    # large capacity mismatch must trip the drift guard.
    export = _valid_wind_export()
    export["project_capacity_mw"] = 999.0  # far from the scenario's 150 MW
    with pytest.raises(WindAdapterDriftError):
        run_integrated_case(
            _scenario(), export, adapter_mode="fill_if_absent", tolerance_pct=0.5
        )


def test_run_integrated_case_does_not_mutate_inputs() -> None:
    scen, export = _scenario(), _valid_wind_export()
    scen_before, export_before = copy.deepcopy(scen), copy.deepcopy(export)
    run_integrated_case(scen, export, adapter_mode="overwrite")
    assert scen == scen_before
    assert export == export_before
