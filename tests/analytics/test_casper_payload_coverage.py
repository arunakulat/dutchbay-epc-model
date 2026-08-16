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
from typing import Any

import pytest

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
    GenerationProfile,
    MonteCarloResult,
    MultiTechGenerationResult,
    ParameterRangeConfig,
    ScenarioResult,
    SensitivitySuite,
    ShockResult,
    TechnologyBreakdown,
    TornadoResult,
    TrancheDebtProfile,
    WaccComponents,
    WaccResult,
)
from analytics.sensitivity.adapters import engine_to_tornado_result

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


def _debt_covenants(dscr_threshold: float = 1.20) -> DebtCovenantSnapshot:
    return DebtCovenantSnapshot(
        dscr_min=1.30,
        dscr_threshold=dscr_threshold,
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
    assert _scenario_summary_to_dict("just_a_name") == {"scenario_name": "just_a_name"}


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
    summary = _scenario_summary_to_dict(_bare_scenario(debt_profile=_debt_profile()))
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


def test_real_adapter_populates_canonical_shock_contract() -> None:
    """The sole production adapter carries its known driver metadata to the child row."""
    parameter = ParameterRangeConfig(
        variable_name="capex.usd_total",
        base_value=159_600_000.0,
        low_pct=-0.10,
        high_pct=0.10,
        label="CAPEX",
    )
    tornado = engine_to_tornado_result(
        parameter=parameter,
        metric_key="project_irr",
        base_value=0.014551597740253388,
        cases=[
            {"label": "capex=low", "value": 0.025129198450968886},
            {"label": "capex=high", "value": 0.005493346017928717},
        ],
    )

    shock = tornado.shock_results[0]
    assert shock.variable_name == "capex.usd_total"
    assert shock.label == "CAPEX"
    assert shock.base_case == 0.014551597740253388
    assert shock.low_case == 0.025129198450968886
    assert shock.high_case == 0.005493346017928717
    assert shock.impact == -0.01963585243304017
    assert shock.impact_abs == 0.01963585243304017
    assert shock.metric_name == "project_irr"


def test_real_adapter_unlabelled_parameter_remains_identifiable() -> None:
    """An optional display label may be absent; the canonical dotted path must survive."""
    parameter = ParameterRangeConfig(
        variable_name="project.capacity_factor",
        base_value=0.332,
        low_value=0.2988,
        high_value=0.3652,
    )
    tornado = engine_to_tornado_result(
        parameter=parameter,
        metric_key="project_irr",
        base_value=0.014,
        cases=[
            {"label": "capacity_factor=low", "value": 0.010},
            {"label": "capacity_factor=high", "value": 0.020},
        ],
    )
    suite = SensitivitySuite(
        base_config_path="synthetic.yaml",
        metric="project_irr",
        tornado_results=[tornado],
        base_kpis={"project_irr": 0.014},
    )

    serialized = _sensitivity_to_dict(suite)
    assert serialized is not None
    assert serialized["tornado"][0]["variable"] == "project.capacity_factor"
    assert serialized["tornado"][0]["impact_abs"] == pytest.approx(0.010)


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
            "scenario_name": "DutchBay Wind Farm",  # str — must be skipped, not float()'d
            "wacc_label": "build_up",  # str
            "dscr_series": [1.3, 1.45],  # list
            "project_irr": 0.0505,  # numeric — kept
            "min_dscr": 1.30,  # numeric — kept
        },
        debt_profile={"construction_years": 2, "total_debt": 1.0e8},  # dict, not typed
        wacc={"wacc_nominal": 0.081},  # dict
        equity_performance={"equity_irr": -0.008, "equity_npv": -3.5e7, "metadata": {}},
        debt_covenants="computed",  # bare status str
    )
    payload = build_casper_payload(scenario=scenario)
    assert json.dumps(payload, default=str)  # serialises without raising
    summary = payload["scenario"]
    assert summary["debt_profile"] == {"construction_years": 2, "total_debt": 1.0e8}
    assert summary["wacc"] == {"wacc_nominal": 0.081}
    # numeric KPIs survive; the str/list ones are dropped (not coerced)
    assert payload["baseline_kpis"]["project_irr"] == pytest.approx(0.0505)
    assert "scenario_name" not in payload["baseline_kpis"]


# ────────────────────────── mc_risk block (real MC VaR/CVaR/breach) ─────────────
def _monte_carlo_with_trials() -> MonteCarloResult:
    """A MonteCarloResult carrying raw trial arrays (what build_casper_risk_blocks needs)."""
    dscr = [1.10, 1.22, 1.28, 1.31, 1.35, 1.40, 1.45, 1.20, 1.33, 1.27]
    irr = [0.02 + 0.005 * i for i in range(10)]
    npv = [-5.0e6 + 1.0e6 * i for i in range(10)]
    trials = {
        "dscr_min": dscr,
        "project_irr": irr,
        "project_npv": npv,
    }
    return MonteCarloResult(
        scenario_name="cov_scenario",
        iterations=10,
        failed_iterations=0,
        trials=trials,
        dscr_min_p10=1.20,
        dscr_min_p50=1.30,
    )


def test_mc_risk_surfaced_from_trials_and_snapshot_floor_fallback() -> None:
    """The real MC risk table is surfaced, JSON-safe; without a raw config the DSCR
    floor gracefully falls back to the ``debt_covenants.dscr_threshold`` snapshot (#639).
    """
    scenario = _bare_scenario(debt_covenants=_debt_covenants())  # dscr_threshold=1.20
    payload = build_casper_payload(
        scenario=scenario, monte_carlo=_monte_carlo_with_trials()
    )

    mc_risk = payload["mc_risk"]
    assert mc_risk is not None
    # Lender risk table has the DSCR (min) row plus covenant rows.
    metrics = {row["metric"] for row in mc_risk["lender_risk_table"]}
    assert "DSCR (min)" in metrics
    assert any(m.startswith("Prob(DSCR <") for m in metrics)
    # No ScenarioResult.config attached (empty default), so the floor fell back to
    # debt_covenants.dscr_threshold (1.20), not the CovenantSpec default (1.30).
    cov = mc_risk["covenant"]
    assert cov["dscr_floor"] == pytest.approx(1.20)
    assert 0.0 <= cov["prob_breach"] <= 1.0
    assert cov["n_trials"] == 10
    # Strict-JSON safe: numpy floats coerced to native, and the covenant-row NaN
    # placeholders mapped to None so a strict encoder does not raise (audit hardening).
    assert json.dumps(payload, allow_nan=False)
    # The covenant rows' numeric columns are None (not NaN tokens).
    prob_row = next(
        r for r in mc_risk["lender_risk_table"] if r["metric"].startswith("Prob(DSCR <")
    )
    assert prob_row["P50"] is None and prob_row["P90"] is None


def test_mc_risk_is_none_when_no_monte_carlo() -> None:
    payload = build_casper_payload(scenario=_bare_scenario())
    assert payload["mc_risk"] is None


def test_mc_risk_is_none_for_summary_only_result_no_crash() -> None:
    """A summary-only MonteCarloResult (no raw trials) degrades to None, not a crash."""
    payload = build_casper_payload(
        scenario=_bare_scenario(debt_covenants=_debt_covenants()),
        monte_carlo=_monte_carlo(),  # percentile scalars only, no .trials
    )
    assert payload["mc_risk"] is None


def test_mc_risk_floor_falls_back_to_default_without_covenants() -> None:
    """With no structured covenant, the surfaced floor is the CovenantSpec default (1.30)."""
    payload = build_casper_payload(
        scenario=_bare_scenario(),  # no debt_covenants
        monte_carlo=_monte_carlo_with_trials(),
    )
    assert payload["mc_risk"]["covenant"]["dscr_floor"] == pytest.approx(1.30)


def test_mc_risk_floor_prefers_engine_resolver_over_covenant_snapshot() -> None:
    """With a raw config attached, the floor is the ENGINE resolution (#639).

    The 4-path precedence (``constraints.min_dscr_covenant`` first) wins over the
    pipeline's ``debt_covenants.dscr_threshold`` snapshot (= ``Financing_Terms.
    target_dscr``). This mirrors the committed equitycase mixed-covenant shape
    (engine 1.30 vs snapshot 1.40); the breach probability is measured against
    the engine floor, so the CASPER table and the MC engine cannot disagree.
    """
    config: dict[str, Any] = {
        "constraints": {"min_dscr_covenant": 1.30},
        "Financing_Terms": {"target_dscr": 1.40, "min_dscr": 1.20},
        "monte_carlo": {"min_dscr_covenant": 1.20},
    }
    scenario = _bare_scenario(
        config=config, debt_covenants=_debt_covenants(dscr_threshold=1.40)
    )
    payload = build_casper_payload(
        scenario=scenario, monte_carlo=_monte_carlo_with_trials()
    )
    cov = payload["mc_risk"]["covenant"]
    assert cov["dscr_floor"] == pytest.approx(1.30)
    # 5 of the 10 dscr_min trials sit strictly below 1.30 (vs 8 below the
    # snapshot's 1.40): the breach probability follows the engine floor.
    assert cov["prob_breach"] == pytest.approx(0.5)


def test_mc_risk_floor_engine_precedence_walks_config_paths() -> None:
    """The shared resolver walks the engine's fallback paths within the config.

    Without ``constraints.min_dscr_covenant`` it lands on ``Financing_Terms.
    target_dscr``; a config carrying NO covenant path at all resolves to the
    engine default (1.30) — in both cases the attached config wins over the
    covenant snapshot (the snapshot is only a no-config fallback).
    """
    with_target = _bare_scenario(
        config={"Financing_Terms": {"target_dscr": 1.25}},
        debt_covenants=_debt_covenants(),  # snapshot 1.20 must NOT win
    )
    payload = build_casper_payload(
        scenario=with_target, monte_carlo=_monte_carlo_with_trials()
    )
    assert payload["mc_risk"]["covenant"]["dscr_floor"] == pytest.approx(1.25)

    no_covenant_paths = _bare_scenario(
        config={"project": {"name": "floorless"}},
        debt_covenants=_debt_covenants(),  # snapshot 1.20 must NOT win
    )
    payload = build_casper_payload(
        scenario=no_covenant_paths, monte_carlo=_monte_carlo_with_trials()
    )
    assert payload["mc_risk"]["covenant"]["dscr_floor"] == pytest.approx(1.30)


def test_mc_risk_floor_bare_string_scenario_uses_covenant_default() -> None:
    """A bare-string scenario has no config and no snapshot: CovenantSpec default."""
    payload = build_casper_payload(
        scenario="just_a_name", monte_carlo=_monte_carlo_with_trials()
    )
    assert payload["mc_risk"]["covenant"]["dscr_floor"] == pytest.approx(1.30)
