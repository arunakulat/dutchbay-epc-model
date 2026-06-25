#!/usr/bin/env python
"""Line-coverage tests for analytics.casper.casper_payload.

These tests drive the optional-field branches of the CASPER payload
assembler that the contract-freeze / equity-contract suites do not reach:

- ``_scenario_summary_to_dict`` for ``None`` and bare-string scenarios.
- WACC serialization for both the ``WaccResult`` object form and the
  pre-serialized ``dict`` form.
- ``debt_profile`` and ``debt_covenants`` overlays.
- ``_sensitivity_to_dict`` tornado-row construction, including the
  ``base_case`` / ``label`` fallbacks.
- ``_monte_carlo_to_dict`` full body via the public ``build_casper_payload``.
- ``_generation_to_dict`` and ``_technology_breakdown_to_list``.
- ``_tail_risk_from_metadata`` for the populated, non-mapping, and
  empty/garbage-only cases.

All inputs are synthetic ``contracts_v14`` objects; payloads are asserted
to be JSON-safe. No network, cdsapi, or matplotlib is touched.
"""

from __future__ import annotations

import json
import pytest
from typing import Any

from analytics.casper.casper_payload import (
    CASPER_CONTRACT_VERSION,
    _monte_carlo_to_dict,
    _scenario_summary_to_dict,
    _sensitivity_to_dict,
    _tail_risk_from_metadata,
    build_casper_payload,
)
from analytics.contracts_v14 import (
    DebtCovenantSnapshot,
    MonteCarloResult,
    MultiTechGenerationResult,
    ScenarioResult,
    SensitivitySuite,
    ShockResult,
    TechnologyBreakdown,
    TornadoResult,
    TrancheDebtProfile,
    WaccComponents,
    WaccResult,
)
from analytics.contracts_v14 import (
    GenerationProfile,
)

# ────────────────────────── builders ──────────────────────────────


def _bare_scenario(**overrides: Any) -> ScenarioResult:
    """Minimal canonical ScenarioResult with all overlays absent."""
    kwargs: dict[str, Any] = {
        "scenario_name": "cov_scenario",
        "config_path": "tests/fixtures/none.yaml",
        "project_npv": 1.0,
        "project_irr": 0.1,
        "dscr_series": [1.3, 1.4],
        "min_dscr": 1.3,
        "max_debt_usd": 5.0,
    }
    kwargs.update(overrides)
    return ScenarioResult(**kwargs)


def _wacc_result() -> WaccResult:
    return WaccResult(
        base=WaccComponents(
            mode="nominal",
            wacc_nominal=0.082,
            wacc_real=0.05,
            wacc_prudential=0.09,
            risk_free_rate=0.04,
            market_risk_premium=0.06,
            asset_beta=0.7,
            target_debt_to_equity=1.5,
            target_debt_to_value=0.6,
            target_equity_to_value=0.4,
            cost_of_debt_pretax=0.07,
            cost_of_debt_aftertax=0.05,
            cost_of_equity=0.12,
            tax_rate=0.3,
            inflation_rate=0.03,
            prudential_spread_bps=150,
        ),
        prudential_rate=0.095,
        prudential_npv=-1_000.0,
        meta={"source": "test"},
    )


def _debt_profile() -> TrancheDebtProfile:
    return TrancheDebtProfile(
        construction_years=2,
        tenor_years=15,
        timeline_periods=17,
        total_debt=80_000_000.0,
        total_idc=5_000_000.0,
        lkr_principal=10.0,
        usd_principal=20.0,
        dfi_principal=50.0,
        lkr_idc=1.0,
        usd_idc=2.0,
        dfi_idc=2.0,
        lkr_rate=0.12,
        usd_rate=0.07,
        dfi_rate=0.05,
        interest_only_years=2,
        amortization_style="sculpted",
        dscr_target=1.30,
    )


def _debt_covenants() -> DebtCovenantSnapshot:
    return DebtCovenantSnapshot(
        dscr_min=1.30,
        dscr_threshold=1.20,
        years_below_threshold=0,
        first_breach_year=None,
        last_breach_year=None,
        balloon_remaining=0.36,
        balloon_flag=True,
        audit_status="ok",
    )


def _monte_carlo() -> MonteCarloResult:
    return MonteCarloResult(
        scenario_name="cov_scenario",
        iterations=1000,
        failed_iterations=10,
        project_irr_mean=0.10,
        project_irr_std=0.02,
        project_irr_p10=0.07,
        project_irr_p50=0.10,
        project_irr_p90=0.13,
        project_npv_mean=1.0,
        project_npv_p10=-1.0,
        project_npv_p50=1.0,
        project_npv_p90=3.0,
        dscr_min_p10=1.20,
        dscr_min_p50=1.35,
    )


# ────────────────────────── scenario summary branches ─────────────


def test_scenario_summary_none_returns_none() -> None:
    """A ``None`` scenario yields ``None`` (line 113-114 branch)."""
    assert _scenario_summary_to_dict(None) is None


def test_scenario_summary_bare_string_minimal_descriptor() -> None:
    """A bare scenario-name string yields the minimal descriptor."""
    assert _scenario_summary_to_dict("just_a_name") == {
        "scenario_name": "just_a_name"
    }


def test_build_payload_with_bare_string_scenario() -> None:
    """build_casper_payload accepts a bare string scenario end-to-end."""
    payload = build_casper_payload(scenario="string_scenario")
    assert payload["scenario"] == {"scenario_name": "string_scenario"}
    assert payload["contract_version"] == CASPER_CONTRACT_VERSION


def test_scenario_summary_minimal_has_no_optional_overlays() -> None:
    """A bare ScenarioResult emits the core keys but no WACC/debt overlays."""
    summary = _scenario_summary_to_dict(_bare_scenario())
    assert summary is not None
    assert summary["scenario_name"] == "cov_scenario"
    assert "wacc" not in summary
    assert "debt_profile" not in summary
    assert "debt_covenants" not in summary
    assert "equity_performance" not in summary


# ────────────────────────── WACC branches ─────────────────────────


def test_wacc_object_form_serialized() -> None:
    """A WaccResult object is fully expanded into the wacc block."""
    summary = _scenario_summary_to_dict(_bare_scenario(wacc=_wacc_result()))
    assert summary is not None
    wacc = summary["wacc"]
    assert wacc["mode"] == "nominal"
    assert wacc["wacc_nominal"] == 0.082
    assert wacc["wacc_real"] == 0.05
    assert wacc["wacc_prudential"] == 0.09
    assert wacc["prudential_rate"] == 0.095
    assert wacc["prudential_npv"] == -1_000.0
    assert wacc["cost_of_equity"] == 0.12
    assert wacc["tax_rate"] == 0.3
    assert wacc["prudential_spread_bps"] == 150
    assert wacc["meta"] == {"source": "test"}
    # Must be JSON-safe.
    json.dumps(summary)


def test_wacc_dict_form_passed_through() -> None:
    """A pre-serialized dict WACC is copied through unchanged."""
    legacy = {"mode": "real", "wacc_nominal": 0.07, "note": "legacy"}
    summary = _scenario_summary_to_dict(_bare_scenario(wacc=legacy))  # type: ignore[arg-type]
    assert summary is not None
    assert summary["wacc"] == legacy
    # A copy, not the same object.
    assert summary["wacc"] is not legacy


# ────────────────────────── debt overlays ─────────────────────────


def test_debt_profile_overlay_surfaced() -> None:
    """An attached TrancheDebtProfile is flattened into debt_profile."""
    summary = _scenario_summary_to_dict(
        _bare_scenario(debt_profile=_debt_profile())
    )
    assert summary is not None
    dp = summary["debt_profile"]
    assert dp["tenor_years"] == 15
    assert dp["total_debt"] == 80_000_000.0
    assert dp["amortization_style"] == "sculpted"
    assert dp["dscr_target"] == 1.30
    assert dp["usd_rate"] == 0.07


def test_debt_covenants_overlay_uses_model_dump() -> None:
    """An attached DebtCovenantSnapshot is surfaced via model_dump()."""
    summary = _scenario_summary_to_dict(
        _bare_scenario(debt_covenants=_debt_covenants())
    )
    assert summary is not None
    cov = summary["debt_covenants"]
    assert cov["dscr_min"] == 1.30
    assert cov["balloon_flag"] is True
    assert cov["audit_status"] == "ok"
    json.dumps(summary)


# ────────────────────────── sensitivity ───────────────────────────


def _suite() -> SensitivitySuite:
    """Suite with one tornado containing two shock rows that exercise both
    the ``sr.base_case``-present and ``sr.base_case``-None fallbacks and the
    ``sr.label`` / ``sr.variable_name`` label fallback."""
    tr = TornadoResult(
        metric_name="project_irr",
        base_metric=0.10,
        shock_results=[
            ShockResult(
                variable_name="capex",
                label="CAPEX",
                low_case=0.08,
                high_case=0.12,
                base_case=0.10,
                impact=0.5,
                impact_abs=0.02,
            ),
            ShockResult(
                variable_name="aep",
                label=None,  # falls back to variable_name
                low_case=0.07,
                high_case=0.13,
                base_case=None,  # falls back to tr.base_metric
                impact=0.6,
                impact_abs=0.03,
            ),
        ],
    )
    return SensitivitySuite(
        base_config_path="tests/fixtures/none.yaml",
        metric="project_irr",
        tornado_results=[tr],
        base_kpis={"project_irr": 0.10},
    )


def test_sensitivity_none_returns_none() -> None:
    assert _sensitivity_to_dict(None) is None


def test_sensitivity_tornado_rows_and_fallbacks() -> None:
    out = _sensitivity_to_dict(_suite())
    assert out is not None
    assert out["metric"] == "project_irr"
    assert out["base_metric"] == 0.10
    assert out["base_config_path"] == "tests/fixtures/none.yaml"
    rows = out["tornado"]
    assert len(rows) == 2

    # Row 0: label present, base_case present.
    assert rows[0]["variable"] == "CAPEX"
    assert rows[0]["base_irr"] == 0.10
    assert rows[0]["low_irr"] == 0.08
    assert rows[0]["high_irr"] == 0.12
    assert rows[0]["impact_abs"] == 0.02
    assert rows[0]["impact_pct"] == 0.5

    # Row 1: label None -> variable_name; base_case None -> tr.base_metric.
    assert rows[1]["variable"] == "aep"
    assert rows[1]["base_irr"] == 0.10
    json.dumps(out)


# ────────────────────────── monte carlo ───────────────────────────


def test_monte_carlo_none_returns_none() -> None:
    assert _monte_carlo_to_dict(None) is None


def test_monte_carlo_full_body() -> None:
    out = _monte_carlo_to_dict(_monte_carlo())
    assert out is not None
    assert out["scenario_name"] == "cov_scenario"
    assert out["iterations"] == 1000
    assert out["failed_iterations"] == 10
    assert out["success_rate_pct"] == 99.0
    assert out["irr"]["p10"] == 0.07
    assert out["npv"]["p90"] == 3.0
    assert out["dscr_min"]["p50"] == 1.35
    json.dumps(out)


# ────────────────────────── generation + tech breakdown ───────────


def test_generation_surfaced_via_to_dict() -> None:
    gen = MultiTechGenerationResult(
        total_aep_kwh=473_800_000.0,
        total_cfads_usd=12_000_000.0,
        technologies={
            "wind": GenerationProfile(
                technology="wind",
                annual_aep_kwh=473_800_000.0,
                annual_cfads_usd=12_000_000.0,
                availability_pct=0.97,
                losses_breakdown={"wake": 0.05},
            )
        },
    )
    payload = build_casper_payload(scenario="s", generation=gen)
    g = payload["generation"]
    assert g["total_aep_kwh"] == 473_800_000.0
    assert g["technologies"]["wind"]["availability_pct"] == 0.97


def test_technology_breakdown_list_and_none() -> None:
    payload_none = build_casper_payload(scenario="s")
    assert payload_none["technology_breakdown"] is None

    breakdown = [
        TechnologyBreakdown(
            technology="wind",
            share_of_capex_pct=0.85,
            share_of_cfads_pct=0.90,
            share_of_aep_pct=1.0,
            notes="primary",
        ),
        TechnologyBreakdown(technology="bess"),
    ]
    payload = build_casper_payload(scenario="s", technology_breakdown=breakdown)
    rows = payload["technology_breakdown"]
    assert rows[0]["technology"] == "wind"
    assert rows[0]["share_of_capex_pct"] == 0.85
    assert rows[0]["notes"] == "primary"
    assert rows[1]["technology"] == "bess"
    assert rows[1]["notes"] is None


# ────────────────────────── tail risk ─────────────────────────────


def test_tail_risk_absent_returns_none() -> None:
    assert _tail_risk_from_metadata({}) is None


def test_tail_risk_non_mapping_returns_none() -> None:
    """A non-Mapping tail_risk_summary is ignored."""
    assert _tail_risk_from_metadata({"tail_risk_summary": [1, 2, 3]}) is None


def test_tail_risk_only_garbage_entries_returns_none() -> None:
    """When the summary maps to only non-Mapping snapshots, the filtered
    result is empty and the function returns None (``out or None``)."""
    raw = {"tail_risk_summary": {"project_irr": "not-a-mapping"}}
    assert _tail_risk_from_metadata(raw) is None


def test_tail_risk_populated_snapshot() -> None:
    raw = {
        "tail_risk_summary": {
            "project_irr": {"var": 0.05, "cvar": 0.04, "p10": 0.07},
            "skip_me": 42,  # non-mapping is dropped
        }
    }
    out = _tail_risk_from_metadata(raw)
    assert out is not None
    assert out["project_irr"]["cvar"] == 0.04
    assert "skip_me" not in out


def test_build_payload_surfaces_tail_risk_top_level() -> None:
    """build_casper_payload lifts tail_risk_summary into top-level tail_risk
    while leaving the original metadata intact."""
    metadata = {
        "tail_risk_summary": {"npv": {"var": 1.0, "cvar": 2.0}},
        "note": "audit",
    }
    payload = build_casper_payload(scenario="s", metadata=metadata)
    assert payload["tail_risk"]["npv"]["cvar"] == 2.0
    assert payload["metadata"]["note"] == "audit"
    json.dumps(payload)


# ────────────────────────── baseline_kpis ─────────────────────────


def test_baseline_kpis_coerced_to_float() -> None:
    """A ScenarioResult.kpis mapping is coerced to {str: float}."""
    scenario = _bare_scenario(kpis={"project_irr": 0.1, "min_dscr": 1})
    payload = build_casper_payload(scenario=scenario)
    kpis = payload["baseline_kpis"]
    assert kpis == {"project_irr": 0.1, "min_dscr": 1.0}
    assert isinstance(kpis["min_dscr"], float)


def test_payload_survives_live_dict_shaped_scenario() -> None:
    """The LIVE pipeline populates ScenarioResult.kpis with non-numeric entries
    (scenario_name str, dscr_series list) and debt_profile/wacc/equity_performance as
    DICTS, not the typed dataclasses. build_casper_payload crashed on all of these
    (float() over the kpis dict; .attr access on dict sub-objects). It must now build a
    valid payload from that real shape (round-3 fix)."""
    scenario = _bare_scenario(
        kpis={
            "scenario_name": "DutchBay Wind Farm",   # str — must be skipped, not float()'d
            "wacc_label": "build_up",                # str
            "dscr_series": [1.3, 1.45],              # list
            "project_irr": 0.0505,                   # numeric — kept
            "min_dscr": 1.30,                        # numeric — kept
        },
        debt_profile={"construction_years": 2, "total_debt": 1.0e8},  # dict, not typed
        wacc={"wacc_nominal": 0.081},                                  # dict
        equity_performance={"equity_irr": -0.008, "equity_npv": -3.5e7, "metadata": {}},
        debt_covenants="computed",                                     # bare status str
    )
    payload = build_casper_payload(scenario=scenario)
    assert json.dumps(payload, default=str)  # serialises without raising
    summary = payload["scenario"]
    assert summary["debt_profile"] == {"construction_years": 2, "total_debt": 1.0e8}
    assert summary["wacc"] == {"wacc_nominal": 0.081}
    # numeric KPIs survive; the str/list ones are dropped (not coerced)
    assert payload["baseline_kpis"]["project_irr"] == pytest.approx(0.0505)
    assert "scenario_name" not in payload["baseline_kpis"]
