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
from solar_resource.cashflow_adapter import SolarAdapterDriftError
from wind_resource.cashflow_adapter import WindAdapterDriftError

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
HYBRID_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"

REQUIRED_KPIS = {"project_irr", "equity_irr", "min_dscr", "avg_dscr", "llcr", "plcr"}


def _scenario() -> Dict[str, Any]:
    """The canonical lender scenario as a fresh in-memory dict."""
    return dict(load_scenario_config(str(LENDER_SCENARIO)))


def _valid_wind_export() -> Dict[str, Any]:
    """A schema-valid P75 wind export (CF in percent; capacity = the 159.6 MW nameplate).

    Uses the real 159.6 MW (not the round 150) so that when the adapter overwrites the
    scenario's capacity, capacity x CF reconciles with the lendercase frozen AEP (473.8)
    at the service-seam reconciliation guard.
    """
    return {
        "scenario": "P75",
        "annual_generation_mwh": 286_300.0,
        "capacity_factor_percent": 33.2,
        "revenue_annual_usd": 19_400_000.0,
        "revenue_cumulative_usd": 388_000_000.0,
        "project_capacity_mw": 159.6,
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


def test_run_finance_case_rejects_stale_capacity_vs_bankable_aep() -> None:
    """The seam reconciliation guard fires: a capacity that disagrees with the declared
    bankable AEP fails loud over the in-memory-dict seam (makes the wire-in non-deletable —
    the same inline-dict bypass that lets an unapproved AEP source through, closed here).
    """
    from analytics.aep_reconciliation import AepReconciliationError

    scen = (
        _scenario()
    )  # lendercase: 159.6 MW reconciles with the frozen 464.3 GWh AEP (post haircut)
    scen["project"] = dict(scen["project"])
    scen["project"]["capacity_mw"] = 200.0  # 200 x 0.332 x 8.760 = 582 GWh >> 464.3
    with pytest.raises(AepReconciliationError):
        run_finance_case(scen)


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
        run_integrated_case(_scenario(), _valid_wind_export(), scenario_name="P50")


def test_run_integrated_case_drift_raises_in_fill_mode() -> None:
    # fill_if_absent compares a present scenario value against the export; a
    # large capacity mismatch must trip the drift guard.
    export = _valid_wind_export()
    export["project_capacity_mw"] = 999.0  # far from the scenario's 159.6 MW
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


def test_run_integrated_case_requires_an_export() -> None:
    # CESSPIT: with neither export the seam refuses (use run_finance_case instead).
    with pytest.raises(ValueError, match="wind_export and/or a solar_export"):
        run_integrated_case(_scenario())


# --------------------------------------------------------------------------- #
# run_integrated_case — solar export (hybrid path)
# --------------------------------------------------------------------------- #
def _hybrid_scenario() -> Dict[str, Any]:
    """The canonical hybrid wind+solar scenario as a fresh in-memory dict."""
    return dict(load_scenario_config(str(HYBRID_SCENARIO)))


def _valid_solar_export() -> Dict[str, Any]:
    """A schema-valid P50 solar export — the pvlib-modelled CF for the 50 MWp block."""
    return {
        "scenario": "P50",
        "technology": "solar",
        "annual_energy_gwh": 78.4,
        "capacity_factor": 0.179,  # DECIMAL (modelled P50), vs the declared 0.20
        "dc_capacity_mw": 50.0,
        "specific_yield_kwh_per_kwp": 1568.2,
    }


def test_run_integrated_case_solar_overwrite_runs_finance() -> None:
    result = run_integrated_case(
        _hybrid_scenario(),
        solar_export=_valid_solar_export(),
        solar_adapter_mode="overwrite",
    )
    assert result["status"] == "success"
    assert REQUIRED_KPIS <= set(result["kpis"])


def test_run_integrated_case_solar_overwrite_lowers_irr() -> None:
    """The frozen solar export genuinely flows into finance (not shelfware).

    Overwrite with a solar CF deliberately *well below* whatever the scenario
    declares — less solar generation must drop project IRR versus the un-patched
    run. Two robustness choices keep this independent of the scenario's declared
    solar P50 (which the #469 re-baseline lowers from 0.20 to 0.179):

    * the export CF is a fixed low 0.10 (below both 0.20 and 0.179);
    * the bankable AEP references are stripped first, so the deliberately large
      blend shift does not trip ``analytics.aep_reconciliation`` (which couples the
      blended headline to the declared bankable AEP). The reconciliation guard is
      proven separately by ``run_finance_case`` tests; here we isolate flow-through.
    """
    scen = _hybrid_scenario()
    scen.pop("expected_results", None)
    resource = scen.get("resource")
    if isinstance(resource, dict):
        resource.pop("aep_summary_path", None)

    base = run_finance_case(scen)
    low_export = dict(
        _valid_solar_export(),
        capacity_factor=0.10,
        annual_energy_gwh=43.8,  # 50 MW * 8760 h * 0.10 / 1000
    )
    over = run_integrated_case(
        scen, solar_export=low_export, solar_adapter_mode="overwrite"
    )
    assert over["kpis"]["project_irr"] < base["kpis"]["project_irr"]


def test_run_integrated_case_solar_plevel_mismatch() -> None:
    # Export is P50 but caller asks for P90 -> refuse to mix P-levels.
    with pytest.raises(ValueError, match="refusing to mix|scenario"):
        run_integrated_case(
            _hybrid_scenario(),
            solar_export=_valid_solar_export(),
            solar_scenario_name="P90",
        )


def test_run_integrated_case_solar_drift_raises_in_fill_mode() -> None:
    # fill_if_absent compares the scenario's present declared solar CF against the export;
    # a CF deliberately off from the declared (0.16) trips the solar drift guard at the
    # default 0.5% tolerance. Using an off-by value (not the modelled 0.179, which the #469
    # re-baseline made the declared CF) keeps this robust to the scenario's declared P50.
    off_export = dict(
        _valid_solar_export(),
        capacity_factor=0.16,
        annual_energy_gwh=70.08,  # 50 MW * 8760 h * 0.16 / 1000
    )
    with pytest.raises(SolarAdapterDriftError):
        run_integrated_case(
            _hybrid_scenario(),
            solar_export=off_export,
            solar_adapter_mode="fill_if_absent",
        )


def test_run_integrated_case_solar_does_not_mutate_inputs() -> None:
    scen, export = _hybrid_scenario(), _valid_solar_export()
    scen_before, export_before = copy.deepcopy(scen), copy.deepcopy(export)
    run_integrated_case(scen, solar_export=export, solar_adapter_mode="overwrite")
    assert scen == scen_before
    assert export == export_before
