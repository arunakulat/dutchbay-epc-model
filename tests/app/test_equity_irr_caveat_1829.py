"""Regression tests for Issue #1829: #1456 equity IRR ranking caveat on remaining surfaces.

Covers the surfaces listed in #1829:
1. Web wizard ``_results.html.j2`` and ``app.api.surface.CaseSurface.from_report_context``
2. Lender report IRR bridge (``report.html.j2``)
3. Segregated synthetic QSTS finance counterfactual report (``synthetic_qsts_finance_report.html.j2``)
4. Solar assessment per-point tariff sweep, gearing sweep, and DSCR target tables
7. ``api.pipeline_api.KpiBlock`` (``equity_irr_caveat``)
8. Lender report capital-risk sections (``report.html.j2`` & ``_what_if_lender_risk.html.j2``)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from analytics.equity_irr_caveat import equity_irr_ranking_caveat
from analytics.synthetic_qsts_finance_counterfactual import (
    SyntheticCounterfactualEvaluation,
)
from api.pipeline_api import KpiBlock, _extract_kpis
from app.api.responses import CaseResult
from app.api.surface import CapitalRiskMetric, CapitalRiskSurface, CaseSurface, KpiCard
from app.models.inputs import WindFarmInputs
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    CapitalRiskBlock,
    CapitalRiskMetricRow,
    CasperCovenantSummary,
    CasperLenderRiskBlock,
    CasperLenderRiskRow,
    IrrBridgeBlock,
    IrrBridgeLeg,
    WhatIfLenderRiskBlock,
    build_report_context,
)
from app.reports.solar_assessment import (
    _equity_irr_ranks_flag,
    _row_equity_irr_caveat_notes,
    as_dbpl_document,
)

_CAVEAT = equity_irr_ranking_caveat(False, 3)


def _sample_inputs() -> WindFarmInputs:
    return WindFarmInputs(
        site_name="DutchBay",
        capacity_mw=148.9,
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )


def _sample_capital_risk_block() -> CapitalRiskBlock:
    return CapitalRiskBlock(
        scenario="dutchbay_base",
        model_version="15.6.1",
        method="lhs",
        n_trials=10,
        dscr_breach_probability=0.0,
        llcr_breach_probability=0.0,
        plcr_breach_probability=0.0,
        dscr_floor=1.20,
        llcr_floor=1.25,
        plcr_floor=1.30,
        probability_below_hurdle=0.1,
        target_equity_irr=0.14,
        metrics=[
            CapitalRiskMetricRow(
                metric="equity_irr",
                unit="pct",
                mean=0.15,
                var=0.11,
                cvar=0.10,
                var_label="VaR 95%",
                cvar_label="CVaR 95%",
            ),
            CapitalRiskMetricRow(
                metric="equity_npv",
                unit="usd",
                mean=10_000_000.0,
                var=2_000_000.0,
                cvar=1_000_000.0,
                var_label="VaR 95%",
                cvar_label="CVaR 95%",
            ),
        ],
        npv_distribution_filename="npv_dist.png",
        npv_distribution_img=None,
    )


def _render_wizard_results(surface: CaseSurface) -> str:
    template_dir = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    return env.get_template("_results.html.j2").render(
        surface=surface, inputs=_sample_inputs()
    )


def test_case_surface_and_wizard_results_carry_caveat_when_flagged() -> None:
    assert _CAVEAT is not None
    ctx = build_report_context(
        CaseResult(
            status="ok",
            scenario_variant="test",
            kpis={"project_irr": 0.10, "equity_irr": 0.14, "equity_npv": 1.0e6},
        ),
        run_result={
            "equity_distribution": {
                "equity_summary": {
                    "equity_irr_ranks_reliably": False,
                    "equity_cashflow_sign_changes": 3,
                }
            }
        },
        capital_risk=None,
        generated_at="2026-11-27T00:00:00Z",
    )
    surface = CaseSurface.from_report_context(ctx)
    assert surface.equity_irr_caveat == _CAVEAT

    flagged_surface = surface.model_copy(
        update={
            "capital_risk": CapitalRiskSurface(
                scenario="dutchbay_base",
                model_version="15.6.1",
                method="lhs",
                n_trials=10,
                dscr_breach_probability=0.0,
                llcr_breach_probability=0.0,
                plcr_breach_probability=0.0,
                dscr_floor=1.2,
                llcr_floor=1.25,
                plcr_floor=1.3,
                probability_below_hurdle=0.1,
                target_equity_irr=0.14,
                metrics=[
                    CapitalRiskMetric(
                        metric="equity_irr",
                        unit="pct",
                        mean=0.15,
                        var=0.11,
                        cvar=0.10,
                        var_label="VaR 95%",
                        cvar_label="CVaR 95%",
                    )
                ],
                npv_distribution_filename="npv_dist.png",
            )
        }
    )
    html = _render_wizard_results(flagged_surface)
    assert "equity-irr-caveat" in html
    assert "equity-irr-caveat-capital-risk" in html
    assert _CAVEAT in html


def test_case_surface_and_wizard_results_omit_caveat_when_unflagged() -> None:
    surface = CaseSurface(
        status="ok",
        scenario_variant="test",
        site_name="DutchBay",
        generated_at="2026-11-27T00:00:00Z",
        kpi_cards=[
            KpiCard(key="equity_irr", label="Equity IRR", value=0.14, display="14.00%")
        ],
        equity_irr_caveat=None,
    )
    html = _render_wizard_results(surface)
    assert "equity-irr-caveat" not in html


def test_kpi_block_carries_optional_equity_irr_caveat() -> None:
    assert _CAVEAT is not None
    block: KpiBlock = _extract_kpis(
        {"project_irr": 0.10, "equity_irr": 0.14},
        equity_irr_caveat=_CAVEAT,
    )
    assert block.equity_irr_caveat == _CAVEAT
    assert _extract_kpis({"project_irr": 0.10}).equity_irr_caveat is None


def test_lender_report_irr_bridge_and_capital_risk_sections_show_caveat() -> None:
    assert _CAVEAT is not None
    ctx = build_report_context(
        CaseResult(
            status="ok",
            scenario_variant="test",
            kpis={"project_irr": 0.10, "equity_irr": 0.14, "equity_npv": 1.0e6},
        ),
        run_result={
            "equity_distribution": {
                "equity_summary": {
                    "equity_irr_ranks_reliably": False,
                    "equity_cashflow_sign_changes": 3,
                }
            }
        },
        capital_risk=None,
        generated_at="2026-11-27T00:00:00Z",
    )
    ctx_with_sections = ctx.model_copy(
        update={
            "capital_risk": _sample_capital_risk_block(),
            "irr_bridge": IrrBridgeBlock(
                currency="USD",
                project_irr=0.10,
                equity_irr=0.14,
                total_uplift=0.04,
                legs=[
                    IrrBridgeLeg(
                        name="leverage",
                        contribution=0.05,
                        irr_after=0.15,
                        detail="Leverage uplift",
                    )
                ],
                residual=-0.01,
                residual_label="cashflow_timing_and_interaction",
                reconciled=True,
            ),
            "what_if_lender_risk": WhatIfLenderRiskBlock(
                casper_lender_risk=CasperLenderRiskBlock(
                    n_trials=10,
                    method="lhs",
                    seed=42,
                    scenario="dutchbay_base",
                    allow_toy_fallback=False,
                    covenant=CasperCovenantSummary(
                        dscr_floor=1.2,
                        prob_breach=0.0,
                        worst_year_dscr_p95_downside=1.25,
                        floor_pinned=False,
                        n_trials=10,
                        n_total_trials=10,
                        unavailable_trials=0,
                    ),
                    rows=[
                        CasperLenderRiskRow(
                            metric="Equity IRR",
                            unit="pct",
                            defined_trials=10,
                            total_trials=10,
                            unavailable_trials=0,
                            p50=0.14,
                            p90=0.11,
                            p95=0.10,
                            mean=0.14,
                            std=0.02,
                        )
                    ],
                )
            ),
        }
    )
    html = render_report_html(ctx_with_sections)
    assert "equity-irr-caveat-capital-risk" in html
    assert "equity-irr-caveat-lender-risk" in html
    assert "equity-irr-caveat-bridge" in html
    assert _CAVEAT in html


def test_synthetic_qsts_finance_template_renders_caveat_when_present() -> None:
    assert _CAVEAT is not None
    template_dir = Path(__file__).resolve().parents[2] / "app" / "reports" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.globals.update(
        {
            "fmt_pct": lambda v: f"{v * 100:.2f}%",
            "fmt_pp": lambda v: f"{v * 100:+.2f} pp",
            "fmt_money": lambda v: f"${v:,.0f}",
            "fmt_money_delta": lambda v: f"${v:+,.0f}",
            "fmt_mwh": lambda v: f"{v:,.0f} MWh",
            "fmt_mwh_delta": lambda v: f"{v:+,.0f} MWh",
        }
    )
    kpis = SimpleNamespace(
        project_irr=0.10,
        equity_irr=0.14,
        project_npv_usd=1e6,
        minimum_dscr=1.25,
        year1_net_generation_mwh=1000.0,
        lifetime_net_generation_mwh=20000.0,
        year1_revenue_usd=100000.0,
        lifetime_revenue_usd=2000000.0,
    )
    evaluation = SyntheticCounterfactualEvaluation(
        baseline_project_curtailment_decimal=0.0,
        synthetic_self_curtailment_decimal=0.01,
        counterfactual_project_curtailment_decimal=0.01,
        deemed_paid_finance_haircut_decimal=0.0,
        override_items=(("project.curtailment_pct", 0.01),),
        kpis=SimpleNamespace(baseline=kpis, counterfactual=kpis, movement=kpis),  # type: ignore[arg-type]
        baseline_equity_irr_caveat=_CAVEAT,
        counterfactual_equity_irr_caveat=_CAVEAT,
    )
    qsts = SimpleNamespace(
        input_package_manifest_sha256="a" * 64,
        input_profile_sha256="b" * 64,
        input_profile_values_sha256="c" * 64,
        profile_start_utc="2026-01-01T00:00:00Z",
        profile_end_utc="2026-01-02T00:00:00Z",
        profile_row_count=24,
        profile_timestep_hours=1.0,
        profile_timezone="UTC",
        profile_unit="MW",
        synthetic_aep_gwh=10.0,
        synthetic_aep_mwh=10000.0,
        gross_energy_mwh=1000.0,
        delivered_energy_mwh=990.0,
        self_curtailed_energy_mwh=10.0,
        self_curtailed_pre_bess_mwh=10.0,
        bess_recovered_energy_mwh=0.0,
        deemed_paid_energy_mwh=0.0,
        energy_balance_residual_mwh=0.0,
        export_cap_breach_timesteps=0,
        solver_telemetry=SimpleNamespace(
            status="converged",
            converged_steps=24,
            total_steps=24,
            max_voltage_pu=1.02,
            min_voltage_pu=0.98,
        ),
    )
    ctx = {
        "title": "Synthetic QSTS Finance Report",
        "warning": "SYNTHETIC",
        "generated_at_utc": "2026-11-27T00:00:00Z",
        "repository_commit": "0" * 40,
        "handoff_sha256": "d" * 64,
        "qsts_sha256": "e" * 64,
        "manifest_sha256": "a" * 64,
        "profile_sha256": "b" * 64,
        "profile_values_sha256": "c" * 64,
        "qsts": qsts,
        "evaluation": evaluation,
        "baseline": kpis,
        "counterfactual": kpis,
        "movement": kpis,
    }
    html = env.get_template("synthetic_qsts_finance_report.html.j2").render(ctx=ctx)
    assert "equity-irr-caveat" in html
    assert _CAVEAT in html


def test_solar_assessment_per_point_tables_carry_row_flag_and_note() -> None:
    assert _CAVEAT is not None
    assert _equity_irr_ranks_flag({"equity_irr_caveat": _CAVEAT}) == "no (see note)"
    assert _equity_irr_ranks_flag({"equity_irr_caveat": None}) == "yes"
    assert _row_equity_irr_caveat_notes(
        [{"equity_irr_caveat": _CAVEAT}, {"equity_irr_caveat": _CAVEAT}]
    ) == [_CAVEAT]

    doc = as_dbpl_document(
        {
            "scenario_name": "solar_test",
            "scenario_path": "conf/scenarios/solar.yaml",
            "generated_utc": "2026-11-27T00:00:00Z",
            "run_manifest": {"git_sha": "0" * 40},
            "not_run": [],
            "tariff_sweep": [
                {
                    "tariff": 20.0,
                    "factor": 1.0,
                    "projIRR": 0.10,
                    "eqIRR": 0.14,
                    "equity_irr_caveat": _CAVEAT,
                    "npv": 1e6,
                    "dscr": 1.3,
                }
            ],
            "optimization": {
                "objective_key": "equity_npv",
                "covenant": 1.25,
                "debt_sizing": "dual_dscr",
                "cap_binds": False,
                "best": None,
                "curve": [
                    {
                        "x": 0.7,
                        "realised": 0.7,
                        "obj": 1e6,
                        "feasible": True,
                        "eqIRR": 0.14,
                        "equity_irr_caveat": _CAVEAT,
                        "cure": 0.0,
                    }
                ],
            },
            "dscr": {
                "objective_key": "equity_npv",
                "best": None,
                "lockup_covenant": 1.15,
                "lockup_declared": True,
                "sweep": [
                    {
                        "target_dscr": 1.25,
                        "gearing": 0.7,
                        "min_dscr": 1.25,
                        "projIRR": 0.10,
                        "eqIRR": 0.14,
                        "equity_irr_caveat": None,
                        "eqNPV": 1e6,
                        "locked_years": 0,
                    }
                ],
            },
        },
        figures={},
        issue_date="2026-11-27",
    )
    tables = {s["heading"]: s["table"] for s in doc["sections"] if "table" in s}
    assert "IRR ranks?" in tables["Tariff sweep and breakevens"]["columns"]
    assert (
        tables["Tariff sweep and breakevens"]["rows"][0]["cells"][4] == "no (see note)"
    )
    assert _CAVEAT in tables["Tariff sweep and breakevens"]["notes"]

    assert "IRR ranks?" in tables["Gearing optimisation"]["columns"]
    assert tables["Gearing optimisation"]["rows"][0]["cells"][4] == "no (see note)"
    assert _CAVEAT in tables["Gearing optimisation"]["notes"]

    assert "IRR ranks?" in tables["DSCR sizing target"]["columns"]
    assert tables["DSCR sizing target"]["rows"][0]["cells"][5] == "yes"
    assert tables["DSCR sizing target"]["notes"] is None
