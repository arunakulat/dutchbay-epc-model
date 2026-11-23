"""Cost and storage in the lender report (#1825 slice iii).

The CAPEX Monte Carlo and the base-point pipeline run are replaced by fakes through the
section's own seams, and the dispatch ledger through its module, so these tests check the
section's wiring, guards and wording. The analyses themselves have their own tests. LCOS runs
for real on a committed scenario that declares a battery.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional

import pytest

import analytics.storage_dispatch as storage_dispatch
from analytics.evaluation_v14 import evaluated_scenario_config
from analytics.scenario_loader import load_scenario_config
from app.models.inputs import WindFarmInputs
from app.reports.capital_risk_emit import LENDER_GRADE_MIN_TRIALS
from app.reports.cost_storage_section import (
    DEFAULT_COST_STORAGE_SETTINGS,
    SECTION_COST_STORAGE,
    CostStorageSettings,
    build_cost_storage_section,
    settings_from_config,
)
from app.reports.lender_report_emit import SECTION_CAPITAL_RISK, sections_not_run
from app.reports.renderer import render_report_html
from app.reports.report_model import CostStorageBlock
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
)
from finance.bess_lcos import compute_lcos_suite

ON = CostStorageSettings(enabled=True)
CAPEX = 100_000_000.0
COMMITTED = {
    "project_irr": 0.10,
    "equity_irr": 0.12,
    "project_npv": 5_000_000.0,
    "min_dscr": 1.30,
    "discount_rate_used": 0.08,
}
_REPO = Path(__file__).resolve().parents[2]
_HYBRID = _REPO / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"
_SOLAR_BESS = _REPO / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"


def _scenario(**capex: Any) -> Dict[str, Any]:
    block: Dict[str, Any] = {"usd_total": CAPEX}
    block.update(capex)
    return {"capex": {k: v for k, v in block.items() if v is not None}}


def _result(**extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kpis": dict(COMMITTED), "annual_rows": [{}] * 20}
    out.update(extra)
    return out


class _Fakes:
    """Records what the Monte Carlo and the base-point run were asked."""

    def __init__(self) -> None:
        self.mc_calls: List[Dict[str, Any]] = []
        self.pipeline_calls: List[Dict[str, Any]] = []
        self.base_point_kpis: Dict[str, Any] = dict(COMMITTED)
        self.n_samples: Optional[int] = None

    def capex_mc(self, cfg: Mapping[str, Any], **kwargs: Any) -> Any:
        self.mc_calls.append({"cfg": cfg, **kwargs})
        sigma = kwargs["sigma_pct"]
        if sigma is None:
            cont = cfg["capex"].get("contingency") or {}
            sigma = float(
                cont.get(
                    "base_cost_uncertainty_pct", cfg["capex"].get("uncertainty_pct")
                )
            )
            sigma = max(sigma, 9.25)  # the module's own class floor (Class 3 here)

        def pct(lo: float, mid: float, hi: float) -> Dict[str, float]:
            return {"p10": lo, "p50": mid, "p90": hi}

        return SimpleNamespace(
            n_samples=self.n_samples or kwargs["n_samples"],
            seed=kwargs["seed"],
            sigma_pct=sigma,
            base_capex_usd=CAPEX,
            capex_usd=pct(88e6, 100e6, 112e6),
            project_irr=pct(0.085, 0.10, 0.117),
            equity_irr=pct(0.09, 0.12, 0.15),
            project_npv_usd=pct(-2e6, 5e6, 12e6),
            min_dscr=pct(1.29, 1.30, 1.31),
        )

    def pipeline(self, **kwargs: Any) -> Mapping[str, Any]:
        self.pipeline_calls.append(kwargs)
        return {"kpis": dict(self.base_point_kpis)}

    def build(
        self,
        scenario: Mapping[str, Any],
        result: Optional[Mapping[str, Any]] = None,
        settings: CostStorageSettings = ON,
    ) -> Any:
        return build_cost_storage_section(
            "scenario.yaml",
            scenario,
            _result() if result is None else result,
            settings,
            capex_mc=self.capex_mc,
            pipeline=self.pipeline,
        )


@pytest.fixture
def fakes() -> _Fakes:
    return _Fakes()


# ── settings ─────────────────────────────────────────────────────────────────


def test_the_section_is_off_by_default_at_the_lender_floor() -> None:
    assert DEFAULT_COST_STORAGE_SETTINGS.enabled is False
    assert DEFAULT_COST_STORAGE_SETTINGS.capex_mc_trials == LENDER_GRADE_MIN_TRIALS
    assert settings_from_config(None) == DEFAULT_COST_STORAGE_SETTINGS
    assert settings_from_config({}) == DEFAULT_COST_STORAGE_SETTINGS


def test_settings_are_read_from_the_run_configuration() -> None:
    got = settings_from_config(
        {"enabled": True, "capex_mc": {"trials": 2000, "seed": 7}}
    )
    assert got == CostStorageSettings(
        enabled=True, capex_mc_trials=2000, capex_mc_seed=7
    )


@pytest.mark.parametrize(
    "raw, message",
    [
        ([], "lender_report.cost_storage must be a mapping"),
        (
            {"enabled": True, "lcos": {}},
            "lender_report.cost_storage: unknown key(s) ['lcos']",
        ),
        (
            {"capex_mc": {"trials": 1000, "sigma": 5}},
            "lender_report.cost_storage.capex_mc takes only trials and seed",
        ),
        (
            {"capex_mc": [1000]},
            "lender_report.cost_storage.capex_mc takes only trials and seed",
        ),
        (
            {"capex_mc": {"trials": 999}},
            "lender_report.cost_storage.capex_mc.trials must be at least 1000 "
            "(the lender-grade floor), not 999",
        ),
    ],
)
def test_bad_settings_fail_loud(raw: Any, message: str) -> None:
    with pytest.raises(ValueError) as err:
        settings_from_config(raw)
    assert str(err.value) == message


def test_the_shipped_run_configuration_keeps_the_section_off() -> None:
    import yaml

    cfg = yaml.safe_load(
        (_REPO / "conf" / "run_full_pipeline_v14.yaml").read_text(encoding="utf-8")
    )
    got = settings_from_config(cfg["lender_report"]["cost_storage"])
    assert got == DEFAULT_COST_STORAGE_SETTINGS


# ── switched off ─────────────────────────────────────────────────────────────


def test_switched_off_the_section_is_not_run_and_nothing_is_evaluated(
    fakes: _Fakes,
) -> None:
    out = fakes.build(
        _scenario(estimate_class=3), settings=DEFAULT_COST_STORAGE_SETTINGS
    )
    assert out == (
        "not run: switched off (lender_report.cost_storage.enabled is false; the section "
        "is opt-in, #1825)"
    )
    assert fakes.mc_calls == [] and fakes.pipeline_calls == []


# ── estimate class and the CAPEX Monte Carlo sigma ───────────────────────────


def test_a_declared_estimate_class_without_an_uncertainty_uses_its_implied_sigma(
    fakes: _Fakes,
) -> None:
    block = fakes.build(_scenario(estimate_class=5))
    assert isinstance(block, CostStorageBlock)
    assert block.estimate_class is not None
    assert block.estimate_class.estimate_class == 5
    assert block.estimate_class.declared is True
    assert fakes.mc_calls[0]["sigma_pct"] == pytest.approx(25.0)
    assert block.capex_mc is not None
    assert block.capex_mc.sigma_basis == (
        "no CAPEX uncertainty is declared, so the spread the scenario's declared AACE "
        "Class 5 implies (-35% to +65%, about 25.00% at one sigma)"
    )


def test_a_declared_uncertainty_is_passed_through_to_the_module(fakes: _Fakes) -> None:
    block = fakes.build(_scenario(estimate_class=3, uncertainty_pct=12.0))
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    # None: run_capex_mc reads the declared figure itself, and applies its own class floor.
    assert fakes.mc_calls[0]["sigma_pct"] is None
    assert block.capex_mc.sigma_pct == 12.0
    assert block.capex_mc.sigma_basis == (
        "the scenario's declared CAPEX uncertainty, 12.00%"
    )


def test_a_declared_uncertainty_under_the_class_spread_says_it_is_floored(
    fakes: _Fakes,
) -> None:
    block = fakes.build(
        _scenario(estimate_class=3, contingency={"base_cost_uncertainty_pct": 5.0})
    )
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    assert block.capex_mc.sigma_pct == 9.25
    assert block.capex_mc.sigma_basis == (
        "the scenario's declared CAPEX uncertainty, 5.00%, floored to the 9.25% that "
        "AACE Class 3 implies"
    )


def test_with_neither_an_uncertainty_nor_a_class_the_mc_is_not_run(
    fakes: _Fakes,
) -> None:
    block = fakes.build(_scenario())
    assert isinstance(block, CostStorageBlock)
    # The band still shows, marked as the repository default rather than the scenario's.
    assert block.estimate_class is not None and block.estimate_class.declared is False
    assert block.capex_mc is None
    assert fakes.mc_calls == []
    assert block.parts_not_run[0] == (
        "CAPEX Monte Carlo: not run: the scenario declares neither a CAPEX uncertainty "
        "(capex.contingency.base_cost_uncertainty_pct or capex.uncertainty_pct) nor "
        "capex.estimate_class"
    )


# ── the CAPEX Monte Carlo guards ─────────────────────────────────────────────


def test_the_mc_runs_under_the_lender_guards(fakes: _Fakes) -> None:
    scenario = _scenario(estimate_class=3)
    scenario["monte_carlo"] = {"allow_toy_fallback": True, "parameters": {"x": 1}}
    settings = CostStorageSettings(enabled=True, capex_mc_trials=1500, capex_mc_seed=99)
    block = fakes.build(scenario, settings=settings)
    call = fakes.mc_calls[0]
    assert call["n_samples"] == 1500 and call["seed"] == 99
    assert call["cfg"]["monte_carlo"] == {
        "allow_toy_fallback": False,
        "parameters": {"x": 1},
    }
    # The scenario the caller holds is never mutated.
    assert scenario["monte_carlo"]["allow_toy_fallback"] is True
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    assert (block.capex_mc.n_trials, block.capex_mc.seed) == (1500, 99)


def test_rows_sit_beside_the_committed_figures(fakes: _Fakes) -> None:
    block = fakes.build(_scenario(estimate_class=3))
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    rows = {r.label: r for r in block.capex_mc.rows}
    assert list(rows) == [
        "CAPEX (pre-levy base)",
        "Project IRR",
        "Equity IRR",
        "Project NPV",
        "Minimum DSCR",
    ]
    assert rows["CAPEX (pre-levy base)"].committed == CAPEX
    assert rows["Project IRR"].committed == COMMITTED["project_irr"]
    assert rows["Equity IRR"].committed == COMMITTED["equity_irr"]
    assert rows["Project NPV"].committed == COMMITTED["project_npv"]
    assert rows["Minimum DSCR"].committed == COMMITTED["min_dscr"]
    assert (rows["Project NPV"].p10, rows["Project NPV"].p90) == (-2e6, 12e6)


def test_fewer_trials_than_the_lender_floor_is_not_run(fakes: _Fakes) -> None:
    fakes.n_samples = LENDER_GRADE_MIN_TRIALS - 1
    block = fakes.build(_scenario(estimate_class=3))
    assert isinstance(block, CostStorageBlock)
    assert block.capex_mc is None
    assert block.parts_not_run[0] == (
        "CAPEX Monte Carlo: not run: 999 trials is under the lender floor of 1000"
    )


def test_a_factor_one_trial_that_reproduces_the_committed_case_says_so(
    fakes: _Fakes,
) -> None:
    block = fakes.build(
        _scenario(
            estimate_class=3,
            derive_from_breakdown=True,
            breakdown={"turbines_usd": 60e6, "civil_usd": 40e6},
        )
    )
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    assert block.capex_mc.base_point == (
        "A factor-1.0 trial reproduces the committed project IRR, project NPV and minimum "
        "DSCR, so the percentiles are a spread around the committed case."
    )
    # The base-point run writes the pre-levy base as the total, like one MC trial.
    capex = fakes.pipeline_calls[0]["config"]["capex"]
    assert capex["usd_total"] == CAPEX and "derive_from_breakdown" not in capex


def test_capex_mc_succeeds_with_price_basis(fakes: _Fakes) -> None:
    scenario = _scenario(
        estimate_class=3,
        derive_from_breakdown=True,
        breakdown={"turbines_usd": 60e6, "civil_usd": 40e6},
        price_basis={"price_year": 2026, "escalation_pct": 5.0},
    )
    scenario["project"] = {"cod_year": 2028}
    scenario["Financing_Terms"] = {"construction_periods": 1}
    block = fakes.build(scenario)
    assert isinstance(block, CostStorageBlock)
    assert block.capex_mc is not None
    assert not any(
        entry.startswith("CAPEX Monte Carlo:") for entry in block.parts_not_run
    )
    # The base-point run keeps price_basis and writes the un-escalated base, like one MC trial.
    capex = fakes.pipeline_calls[0]["config"]["capex"]
    assert capex["usd_total"] == CAPEX
    assert capex["price_basis"] == {"price_year": 2026, "escalation_pct": 5.0}
    assert "derive_from_breakdown" not in capex


def test_a_factor_one_trial_that_misses_the_committed_case_says_so(
    fakes: _Fakes,
) -> None:
    fakes.base_point_kpis["project_npv"] = 4_000_000.0
    fakes.base_point_kpis["min_dscr"] = None
    block = fakes.build(_scenario(estimate_class=3))
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    assert block.capex_mc.base_point == (
        "A factor-1.0 trial does NOT reproduce the committed case: project_npv "
        "(4e+06 against the committed 5e+06); min_dscr (None against the committed 1.3). "
        "Read the percentiles as a spread around that trial, not the committed case."
    )


def test_debt_resizing_is_stated_only_when_the_scenario_resizes(fakes: _Fakes) -> None:
    plain = fakes.build(_scenario(estimate_class=3))
    assert isinstance(plain, CostStorageBlock) and plain.capex_mc is not None
    assert plain.capex_mc.debt_sizing_note is None
    sized = _scenario(estimate_class=3)
    sized["Financing_Terms"] = {"debt_sizing": "dual_dscr"}
    block = fakes.build(sized)
    assert isinstance(block, CostStorageBlock) and block.capex_mc is not None
    assert block.capex_mc.debt_sizing_note == (
        "Each trial re-sizes the debt (Financing_Terms.debt_sizing: dual_dscr), so the "
        "minimum DSCR moves far less than CAPEX does: extra CAPEX is carried mostly by "
        "equity, and shows in the equity IRR and project NPV rows."
    )


# ── storage parts ────────────────────────────────────────────────────────────


def test_a_scenario_without_storage_lists_every_storage_part_with_its_reason(
    fakes: _Fakes,
) -> None:
    block = fakes.build(_scenario(estimate_class=3))
    assert isinstance(block, CostStorageBlock)
    assert block.parts_not_run == [
        "Storage dispatch: not run: the scenario declares no enabled "
        "chronological_dispatch block (its storage is not dispatched hour by hour)",
        "LCOS: not run: the scenario has no battery (no type: bess technology)",
        "Battery-project economics: not run: the scenario declares no bess_economics "
        "block",
        "EPC margin: not run: the scenario declares no epc block",
    ]
    assert (block.dispatch, block.lcos, block.bess_economics, block.epc_margin) == (
        None,
        [],
        [],
        None,
    )


def test_dispatch_totals_the_ledger(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = SimpleNamespace(
        wind_to_bess_mwh=1.0,
        solar_to_bess_mwh=2.0,
        grid_to_bess_mwh=0.5,
        bess_to_poc_mwh=3.0,
        wind_to_poc_mwh=10.0,
        solar_to_poc_mwh=4.0,
        wind_curtailed_mwh=0.25,
        solar_curtailed_mwh=0.75,
        charge_loss_mwh=0.1,
        discharge_loss_mwh=0.2,
        unmet_charge_mwh=0.0,
        unmet_discharge_mwh=0.4,
    )
    monkeypatch.setattr(
        storage_dispatch,
        "evaluate_chronological_dispatch",
        lambda _s: SimpleNamespace(steps=[step, step]),
    )
    block = fakes.build(_scenario(estimate_class=3))
    assert isinstance(block, CostStorageBlock) and block.dispatch is not None
    d = block.dispatch
    assert (d.hours, d.charged_mwh, d.discharged_mwh, d.exported_mwh) == (
        2,
        7.0,
        6.0,
        34.0,
    )
    assert (d.curtailed_mwh, d.losses_mwh, d.unmet_mwh) == (
        2.0,
        pytest.approx(0.6),
        0.8,
    )


def test_lcos_runs_at_the_runs_own_discount_rate_on_a_scenario_with_a_battery(
    fakes: _Fakes,
) -> None:
    scenario = dict(load_scenario_config(str(_HYBRID)))
    result = _result()
    block = fakes.build(scenario, result=result)
    assert isinstance(block, CostStorageBlock)
    direct = compute_lcos_suite(
        evaluated_scenario_config(scenario), wacc=0.08, project_years=20
    )
    assert direct, "the hybrid scenario declares a battery"
    assert block.lcos_discount_rate == 0.08
    assert [r.technology for r in block.lcos] == [r.technology for r in direct]
    assert [r.lcos_usd_per_mwh for r in block.lcos] == [
        r.lcos_usd_per_mwh for r in direct
    ]
    assert all(r.benchmark_note for r in block.lcos)
    assert not any(p.startswith("LCOS:") for p in block.parts_not_run)


def test_lcos_prices_the_battery_on_the_financed_capex(fakes: _Fakes) -> None:
    """A declared capex.price_basis is applied, as the run applied it (#1569, #1899)."""
    scenario = dict(load_scenario_config(str(_SOLAR_BESS)))
    assert "price_basis" in scenario["capex"], "the fixture must declare a price basis"
    block = fakes.build(scenario)
    assert isinstance(block, CostStorageBlock) and block.lcos
    financed = compute_lcos_suite(
        evaluated_scenario_config(scenario), wacc=0.08, project_years=20
    )
    stated_cfg = dict(scenario)
    stated_cfg["capex"] = {
        k: v for k, v in scenario["capex"].items() if k != "price_basis"
    }
    stated = compute_lcos_suite(stated_cfg, wacc=0.08, project_years=20)
    got = [r.lcos_usd_per_mwh for r in block.lcos]
    assert got == [r.lcos_usd_per_mwh for r in financed]
    # Non-vacuity: the stated (unescalated) CAPEX would give a different figure.
    assert got != [r.lcos_usd_per_mwh for r in stated]


def test_lcos_without_a_discount_rate_says_so(fakes: _Fakes) -> None:
    scenario = dict(load_scenario_config(str(_HYBRID)))
    result = _result()
    del result["kpis"]["discount_rate_used"]
    block = fakes.build(scenario, result=result)
    assert isinstance(block, CostStorageBlock)
    assert (
        "LCOS: not run: the run publishes no discount rate or no operating years"
        in block.parts_not_run
    )


_BESS_ENTRY = {
    "status": "run",
    "projects": [
        {
            "technology": "bess_1",
            "landed_capex": {"landed_capex_usd": 4_000_000.0},
            "npv_usd": 250_000.0,
            "irr_usd": 0.11,
            "discount_rate": 0.09,
            "horizon_years": 15,
            "currency_basis": "USD nominal",
        }
    ],
}
_EPC_ENTRY = {
    "status": "run",
    "contract_value": 120e6,
    "total_cost": 108e6,
    "gross_margin": 12e6,
    "gross_margin_pct": 0.10,
    "return_on_cost_pct": 12e6 / 108e6,
    "construction_months": 24,
    "peak_working_capital": 9e6,
    "annualized_irr": None,
    "irr_note": "cash never turns negative",
}


def test_published_battery_economics_and_epc_margin_are_carried(
    fakes: _Fakes,
) -> None:
    block = fakes.build(
        _scenario(estimate_class=3),
        result=_result(bess_project_economics=_BESS_ENTRY, epc_margin=_EPC_ENTRY),
    )
    assert isinstance(block, CostStorageBlock)
    assert [r.technology for r in block.bess_economics] == ["bess_1"]
    assert block.bess_economics[0].landed_capex_usd == 4_000_000.0
    assert block.epc_margin is not None
    assert block.epc_margin.gross_margin_pct == 0.10
    assert block.epc_margin.irr_note == "cash never turns negative"
    assert not any(
        p.startswith(("Battery-project economics:", "EPC margin:"))
        for p in block.parts_not_run
    )


def test_a_published_entry_that_did_not_run_carries_its_reason(fakes: _Fakes) -> None:
    block = fakes.build(
        _scenario(estimate_class=3),
        result=_result(
            bess_project_economics={"status": "not_run", "reason": "no BESS revenue"},
            epc_margin={"status": "error"},
        ),
    )
    assert isinstance(block, CostStorageBlock)
    assert "Battery-project economics: not run: no BESS revenue" in block.parts_not_run
    assert "EPC margin: not run: error" in block.parts_not_run


def test_a_part_that_raises_is_listed_and_the_others_still_run(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_s: Any) -> Any:
        raise RuntimeError("ledger broke")

    monkeypatch.setattr(storage_dispatch, "evaluate_chronological_dispatch", _boom)
    block = fakes.build(
        _scenario(estimate_class=3), result=_result(epc_margin=_EPC_ENTRY)
    )
    assert isinstance(block, CostStorageBlock)
    assert (
        "Storage dispatch: not run: RuntimeError: ledger broke" in block.parts_not_run
    )
    assert block.capex_mc is not None and block.epc_margin is not None


def test_the_section_is_listed_before_capital_risk_when_left_out() -> None:
    scenario = _scenario(estimate_class=3)
    rows = sections_not_run(
        _empty_bundle(scenario),
        scenario,
        capital_risk_not_run="not run: test",
        cost_storage_not_run="not run: switched off",
    )
    names = [r.section for r in rows]
    assert names.index(SECTION_COST_STORAGE) == names.index(SECTION_CAPITAL_RISK) - 1


# ── rendering ────────────────────────────────────────────────────────────────


def _empty_bundle(scenario: Mapping[str, Any]) -> Any:
    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )


@pytest.fixture(scope="module")
def api_case() -> Any:
    inputs = WindFarmInputs(
        site_name="Report seam",
        capacity_mw=148.9,
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )
    return run_report_case(inputs, generated_at="2026-11-22T00:00:00+00:00")


def _render(case: Any, block: Optional[CostStorageBlock]) -> str:
    bundle = _empty_bundle(case.scenario_config)
    return render_report_html(
        build_report_context_from_case(case, bundle, cost_storage=block)
    )


def _section(html: str) -> str:
    return html.split("<h2>Cost and Storage</h2>", 1)[1].split("</section>", 1)[0]


def test_the_section_renders_every_part_with_its_f5_caption(
    fakes: _Fakes, api_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = SimpleNamespace(
        **{
            k: 1.0
            for k in (
                "wind_to_bess_mwh",
                "solar_to_bess_mwh",
                "grid_to_bess_mwh",
                "bess_to_poc_mwh",
                "wind_to_poc_mwh",
                "solar_to_poc_mwh",
                "wind_curtailed_mwh",
                "solar_curtailed_mwh",
                "charge_loss_mwh",
                "discharge_loss_mwh",
                "unmet_charge_mwh",
                "unmet_discharge_mwh",
            )
        }
    )
    monkeypatch.setattr(
        storage_dispatch,
        "evaluate_chronological_dispatch",
        lambda _s: SimpleNamespace(steps=[step]),
    )
    scenario = dict(load_scenario_config(str(_HYBRID)))
    scenario["capex"] = {**scenario["capex"], "usd_total": CAPEX}
    scenario["Financing_Terms"] = {"debt_sizing": "dual_dscr"}
    block = fakes.build(
        scenario,
        result=_result(bess_project_economics=_BESS_ENTRY, epc_margin=_EPC_ENTRY),
    )
    assert isinstance(block, CostStorageBlock) and block.parts_not_run == []
    section = _section(_render(api_case, block))
    assert "Beside the committed case, not a revised case." in section
    for heading in (
        "Estimate class",
        "CAPEX Monte Carlo",
        "Storage dispatch",
        "Levelised cost of storage",
        "Battery as its own project",
        "EPC construction margin",
    ):
        assert f"<h3>{heading}</h3>" in section, heading
    assert "1000 trials, seed 12345" in section
    assert "For CAPEX the adverse case is P90" in section
    assert "Each trial re-sizes the debt" in section
    assert '<td>Project NPV</td><td class="num">$5,000,000</td>' in section
    assert "At the run's discount rate of 8.00%" in section
    assert "(10.00% of the contract" in section
    assert "annualised IRR\n      undefined (cash never turns negative)" in section
    assert "Parts not run" not in section
    assert "F-5:" in section


def test_parts_not_run_are_listed_in_the_section(fakes: _Fakes, api_case: Any) -> None:
    block = fakes.build(_scenario())
    assert isinstance(block, CostStorageBlock)
    section = _section(_render(api_case, block))
    assert (
        "(the repository default: the\n      scenario declares no capex.estimate_class)"
        in section
    )
    assert "<h3>CAPEX Monte Carlo</h3>" not in section
    assert section.count("<li>") == len(block.parts_not_run) == 5


def test_no_block_means_no_section(api_case: Any) -> None:
    assert "<h2>Cost and Storage</h2>" not in _render(api_case, None)
