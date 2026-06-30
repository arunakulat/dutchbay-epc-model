"""Tests for the report content model (pure presentation over a CaseResult)."""

from __future__ import annotations

from typing import Dict

import pytest

from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_config import Covenants, ReportConfig, ReportMeta
from app.reports.report_model import (
    ReportContext,
    Verdict,
    build_report_context,
    fmt_gwh,
    fmt_pct,
    fmt_ratio_pct,
    fmt_usd,
    fmt_x,
    format_kpi_value,
)

GENERATED_AT = "2026-06-22T12:00:00+00:00"

#: The frozen value-destructive economics (#280/#281): IRR below the WACC hurdle,
#: negative equity NPV, DSCR at the 1.30 sculpt target, balloon within ceiling.
_VALUE_DESTRUCTIVE_KPIS: Dict[str, float] = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "project_npv": -57994285.93,
    "equity_npv": -60926463.83,
    "min_dscr": 1.2999999,
    "avg_dscr": 1.3873,
    "llcr": 1.1277,
    "plcr": 1.1895,
    "equity_moic": 0.7554,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}


def _case(kpis: Dict[str, float], *, variant: str = "lendercase") -> CaseResult:
    return CaseResult(
        status="success", scenario_variant=variant, kpis=kpis, run_manifest=None
    )


def _inputs() -> WindFarmInputs:
    return WindFarmInputs(
        site_name="Dutch Bay",
        location="Kalpitiya",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def test_format_pct() -> None:
    assert format_kpi_value(0.0422, "pct") == "4.22%"
    assert format_kpi_value(-0.0246, "pct") == "-2.46%"


def test_format_multiple() -> None:
    assert format_kpi_value(1.2999999, "multiple") == "1.30x"


def test_format_usd_sign_handling() -> None:
    assert format_kpi_value(110662500.0, "usd") == "$110,662,500"
    assert format_kpi_value(-57994285.93, "usd") == "-$57,994,286"


# --------------------------------------------------------------------------- #
# Finance-table format helpers (RPT-1)
# --------------------------------------------------------------------------- #
def test_fmt_helpers_none_is_em_dash() -> None:
    assert fmt_usd(None) == "—"
    assert fmt_gwh(None) == "—"
    assert fmt_x(None) == "—"
    assert fmt_ratio_pct(None) == "—"
    assert fmt_pct(None) == "—"


def test_fmt_helpers_values() -> None:
    assert fmt_usd(159_600_000.0) == "$159,600,000"
    assert fmt_usd(-65_455_817.0) == "-$65,455,817"  # accounting-style negative
    assert fmt_gwh(464.34) == "464.3 GWh"
    assert fmt_x(1.308) == "1.31x"
    assert fmt_ratio_pct(0.4125) == "41.25%"  # ratio -> percent
    assert fmt_pct(13.39) == "13.39%"  # already a percent


# --------------------------------------------------------------------------- #
# Finance blocks wiring (RPT-1): production / sources-and-uses / DSCR profile
# --------------------------------------------------------------------------- #
_SCENARIO_CFG = {
    "resource": {
        "wind": {"aep_gwh": 464.3, "capacity_factor": 0.332, "source_id": "test-source"}
    },
    "project": {"capacity_mw": 159.6},
    "finance": {"capex_total_usd": 159_600_000.0},
}
_DEBT_RESULT = {
    "debt_total": 65_835_000.0,
    "total_idc": 10_287_933.22,
    "tenor_years": 15,
    "construction_years": 2,
    "min_dscr": 1.2999,
    "avg_debt_rate": 0.08,
    "balloon_pct": 0.36,
    "balloon_remaining": 23_700_000.0,
    "dual_dscr": {
        "solved_gearing": 0.4125,
        "binding_constraint": "dscr",
        "binding_production_case": "P50",
    },
    "principal_by_tranche": {"senior": 65_835_000.0},
    "idc_by_tranche": {"senior": 10_287_933.22},
    "raw_dscr_series": [None, None, 1.308, 1.31, 1.30],
    "debt_outstanding": [65_835_000.0, 65_835_000.0, 60_000_000.0, 55e6, 50e6],
    "debt_service_total": [0.0, 0.0, 8_000_000.0, 8_000_000.0, 8_000_000.0],
    "funding": {
        "sources_and_uses": {
            "uses": {"capex_usd": 159_600_000.0, "idc_usd": 10_287_933.22},
            "sources": {"senior_debt_usd": 76_122_933.22, "equity_usd": 93_765_000.0},
            "uses_total_usd": 169_887_933.22,
            "sources_total_usd": 169_887_933.22,
            "balanced": True,
        }
    },
}


def test_finance_blocks_populated_with_scenario_and_debt() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
    )
    assert ctx.finance is not None
    assert ctx.finance.aep.net_p50_gwh == 464.3
    assert ctx.finance.funding.balanced is True
    # A real sources-and-uses table balances.
    assert ctx.finance.funding.uses_total_usd == ctx.finance.funding.sources_total_usd
    assert ctx.finance.debt.tenor_years == 15
    # Full-timeline DSCR profile: construction years carry None, operating years a value.
    assert [r.dscr for r in ctx.finance.debt.schedule[:3]] == [None, None, 1.308]
    assert ctx.finance.kpis.project_irr == _VALUE_DESTRUCTIVE_KPIS["project_irr"]


def test_finance_blocks_none_without_debt_result() -> None:
    # scenario_config alone (no debt_result) -> no finance section (legacy-safe).
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
    )
    assert ctx.finance is None


def test_finance_blocks_none_without_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        debt_result=_DEBT_RESULT,
    )
    assert ctx.finance is None


def test_tornado_stored_when_supplied() -> None:
    # build_report_context only stores the pre-computed tornado (it stays pure).
    from app.services.report_tornado import TornadoBlock, TornadoRow

    tornado = TornadoBlock(
        metric="project_irr",
        rows=[TornadoRow(label="Tariff", base=0.0116, impact_abs=0.028)],
    )
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, tornado=tornado
    )
    assert ctx.tornado is not None and ctx.tornado.rows[0].label == "Tariff"


def test_tornado_none_by_default() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.tornado is None


# --------------------------------------------------------------------------- #
# Global sensitivity (Morris) wiring (MC-1)
# --------------------------------------------------------------------------- #
def test_global_sa_stored_when_supplied() -> None:
    # build_report_context only stores the pre-computed global-SA block (stays pure).
    from app.services.report_global_sa import GlobalSABlock, GlobalSADriver

    block = GlobalSABlock(
        method="morris",
        metric="project_irr",
        n_runs=112,
        drivers=[
            GlobalSADriver(name="tariff.lkr_per_kwh", mu_star=0.0493, sigma=0.005)
        ],
    )
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, global_sa=block
    )
    assert ctx.global_sa is not None
    assert ctx.global_sa.drivers[0].name == "tariff.lkr_per_kwh"


def test_global_sa_none_by_default() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.global_sa is None


# --------------------------------------------------------------------------- #
# Evidence register (#435 -> RPT-1)
# --------------------------------------------------------------------------- #
def test_evidence_register_projected_from_scenario_config() -> None:
    scenario = {
        "evidence_register": {
            "entries": {
                "capex": {
                    "source": "SINOHYDRO EPC quote",
                    "as_of": "2025-09",
                    "tier": "A",
                },
                "tariff": {
                    "source": "CEB SPPA",
                    "as_of": "2025-06",
                    "tier": "A",
                    "note": "flat LKR",
                },
            }
        }
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert ctx.evidence is not None
    assert ctx.evidence.covered == 2
    assert (
        ctx.evidence.total > ctx.evidence.covered
    )  # uncovered material assumptions remain
    labels = {r.assumption for r in ctx.evidence.rows}
    assert {"capex", "tariff"} <= labels
    tariff = next(r for r in ctx.evidence.rows if r.assumption == "tariff")
    assert (
        tariff.source == "CEB SPPA" and tariff.tier == "A" and tariff.note == "flat LKR"
    )
    assert (
        "capex" not in ctx.evidence.missing
    )  # capex has evidence; not in the gap list


def test_evidence_block_shows_gap_when_no_entries() -> None:
    # A scenario with no evidence block still gets a block: 0 covered, the gap listed.
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, scenario_config={}
    )
    assert ctx.evidence is not None
    assert ctx.evidence.covered == 0 and ctx.evidence.rows == []
    assert len(ctx.evidence.missing) == ctx.evidence.total > 0


def test_evidence_none_without_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.evidence is None


def test_evidence_none_on_malformed_register() -> None:
    # A structurally malformed entries container degrades to no section (not a 500).
    scenario = {"evidence_register": {"entries": 42}}
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert ctx.evidence is None


# --------------------------------------------------------------------------- #
# Context assembly
# --------------------------------------------------------------------------- #
def test_build_context_basic_shape() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=_inputs()
    )
    assert isinstance(ctx, ReportContext)
    assert ctx.generated_at == GENERATED_AT
    assert ctx.site_name == "Dutch Bay"
    assert ctx.status == "success"
    assert ctx.scenario_variant == "lendercase"


def test_risk_register_projected_from_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.risk_register, "the default config seeds risks"
    # Rows are faithful passthroughs with a renderable severity.
    for row in ctx.risk_register:
        assert row.category and row.risk and row.mitigation
        assert row.severity in {"low", "medium", "high"}
    assert any(r.severity == "high" for r in ctx.risk_register)


def test_readiness_projected_from_scenario_config() -> None:
    scenario = {
        "development_readiness": {
            "items": {
                "environmental_social": {"status": "green", "note": "ESIA done"},
                "financing": {"status": "red"},
            }
        }
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert {r.workstream for r in ctx.readiness} == {
        "environmental_social",
        "financing",
    }
    assert ctx.overall_readiness == "red"  # worst declared
    assert all(r.status in {"green", "amber", "red"} for r in ctx.readiness)


def test_readiness_empty_when_no_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.readiness == []
    assert ctx.overall_readiness is None


def test_risk_register_empty_when_config_has_none() -> None:
    cfg = ReportConfig(
        report=ReportMeta(
            title="t",
            subtitle="s",
            organization="o",
            version="1.0",
            confidentiality="c",
            disclaimer="d",
        ),
        covenants=Covenants(
            min_dscr_floor=1.2, min_dscr_target=1.3, max_balloon_pct=0.4
        ),
        kpi_table=[],
    )  # no risk_register -> defaults to []
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, config=cfg
    )
    assert ctx.risk_register == []


def test_kpi_rows_formatted_in_config_order() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    by_key = {row.key: row for row in ctx.kpi_rows}
    assert by_key["project_irr"].display == "4.22%"
    assert by_key["min_dscr"].display == "1.30x"
    assert by_key["project_npv"].display == "-$57,994,286"
    # Order follows the config table, not dict insertion.
    assert [r.key for r in ctx.kpi_rows][0] == "project_irr"


def test_missing_kpi_is_skipped() -> None:
    kpis = dict(_VALUE_DESTRUCTIVE_KPIS)
    del kpis["plcr"]
    ctx = build_report_context(_case(kpis), generated_at=GENERATED_AT)
    assert "plcr" not in {row.key for row in ctx.kpi_rows}


def test_verdict_value_destructive() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    v: Verdict = ctx.verdict
    assert v.project_viable is False
    assert v.equity_positive is False
    assert v.dscr_covenant_met is True  # 1.30 >= 1.20 floor
    assert v.balloon_within_limit is True  # 34.67% <= 40%
    assert v.headline == "Value-destructive at the modeled assumptions."
    assert any("below the" in n for n in v.notes)


def test_verdict_bankable() -> None:
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.20,
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.project_viable and v.equity_positive and v.dscr_covenant_met
    assert v.balloon_within_limit
    assert v.headline == "Bankable at the modeled assumptions."


def test_verdict_not_bankable_on_balloon_breach() -> None:
    # Returns and DSCR all pass, but the balloon covenant breaches: the headline
    # must NOT claim "Bankable" (it would contradict the covenant table).
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.55,  # > 0.40 ceiling
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.project_viable and v.equity_positive and v.dscr_covenant_met
    assert v.balloon_within_limit is False
    assert v.headline == "Not bankable — covenant breach at the modeled assumptions."


def test_verdict_honors_engine_balloon_breach_over_report_ceiling() -> None:
    # Round-9 fix: the report must honor the engine's published balloon_covenant_breach
    # (evaluated against the SCENARIO's own covenant, e.g. 10%) and NOT re-derive "within
    # limit" against its more lenient presentation default (40%). 37.96% is BELOW the report
    # 40% ceiling but the engine flagged a breach against the scenario's 10% covenant.
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.3796,  # < 0.40 report default, but...
        "balloon_covenant_breach": 1.0,  # ...the engine flagged a breach (vs scenario 10%)
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert (
        v.balloon_within_limit is False
    )  # honors the engine, not the 40% report default
    assert any("BREACHES the modeled refinance-risk covenant" in n for n in v.notes)
    assert v.headline == "Not bankable — covenant breach at the modeled assumptions."


def test_verdict_falls_back_to_report_ceiling_without_engine_flag() -> None:
    # When the engine did NOT publish a breach flag, the report-config ceiling still governs.
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.3467,  # <= 0.40, no engine flag -> within limit
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.balloon_within_limit is True
    assert any("within the 40% refinance-risk ceiling" in n for n in v.notes)


def test_equity_irr_note_reflects_irr_sign_not_npv_flag() -> None:
    """Round-11 fix: the equity-IRR note's sign word must follow the IRR's OWN sign, not the
    equity-NPV value flag. A positive IRR below the hurdle (NPV<0) was falsely printed as
    'negative to sponsors'. The basecase (equity IRR ~+5.8%, below the ~12% equity hurdle,
    NPV<0) is the real-world example; the synthetic fixture below uses +2.42%. (Post the 5.9%
    FX-drift re-baseline the canonical LENDER equity IRR is itself negative, ~-0.46%.)
    """

    def note(kpis):
        v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
        return next(n for n in v.notes if "Equity IRR" in n)

    # positive IRR, negative NPV (the basecase reality) -> NOT "negative"
    pos_below = note(
        {
            "project_irr": 0.05,
            "discount_rate_used": 0.078,
            "equity_irr": 0.0242,
            "equity_npv": -35_000_000.0,
            "min_dscr": 1.30,
        }
    )
    assert "2.42%" in pos_below
    assert "positive but below the equity hurdle" in pos_below
    assert "negative" not in pos_below  # the bug: it used to say "negative to sponsors"

    # genuinely negative IRR -> "negative to sponsors"
    neg = note(
        {
            "project_irr": -0.03,
            "discount_rate_used": 0.078,
            "equity_irr": -0.0862,
            "equity_npv": -43_000_000.0,
            "min_dscr": 1.30,
        }
    )
    assert "negative to sponsors" in neg

    # positive IRR clearing the hurdle (NPV>0) -> "positive to sponsors"
    pos_ok = note(
        {
            "project_irr": 0.12,
            "discount_rate_used": 0.08,
            "equity_irr": 0.15,
            "equity_npv": 25_000_000.0,
            "min_dscr": 1.55,
        }
    )
    assert "positive to sponsors" in pos_ok


def test_verdict_not_bankable_on_dscr_breach() -> None:
    # DSCR floor breached while returns are acceptable -> explicit covenant breach.
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "min_dscr": 1.05,  # < 1.20 floor
        "balloon_pct": 0.20,
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.dscr_covenant_met is False
    assert v.headline == "Not bankable — covenant breach at the modeled assumptions."


def test_verdict_marginal() -> None:
    # Project clears the hurdle but equity is negative -> marginal, not bankable.
    kpis = {
        "project_irr": 0.10,
        "discount_rate_used": 0.08,
        "equity_npv": -1_000_000.0,
        "min_dscr": 1.40,
        "balloon_pct": 0.30,
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.project_viable is True
    assert v.equity_positive is False
    assert v.headline == "Marginal — covenant-sensitive at the modeled assumptions."


def test_equity_positive_falls_back_to_irr_when_no_npv() -> None:
    kpis = {"project_irr": 0.10, "discount_rate_used": 0.08, "equity_irr": 0.05}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.equity_positive is True


def test_equity_positive_false_when_no_equity_metrics() -> None:
    kpis = {"project_irr": 0.10, "discount_rate_used": 0.08, "min_dscr": 1.4}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.equity_positive is False
    assert v.dscr_covenant_met is True


def test_balloon_absent_is_within_limit() -> None:
    kpis = {"project_irr": 0.10, "discount_rate_used": 0.08, "min_dscr": 1.4}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.balloon_within_limit is True
    assert v.dscr_covenant_met is True


def test_dscr_breach_flagged() -> None:
    kpis = {"project_irr": 0.05, "discount_rate_used": 0.08, "min_dscr": 1.05}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.dscr_covenant_met is False
    assert any("breaches" in n for n in v.notes)


# --------------------------------------------------------------------------- #
# Assumptions register
# --------------------------------------------------------------------------- #
def test_assumptions_from_inputs_include_location() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=_inputs()
    )
    labels = [a.label for a in ctx.assumptions]
    assert "Location" in labels
    assert "Total CAPEX" in labels
    capex = next(a for a in ctx.assumptions if a.label == "Total CAPEX")
    assert capex.display == "$195,000,000"


def test_no_inputs_yields_empty_assumptions_and_variant_sitename() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="basecase"), generated_at=GENERATED_AT
    )
    assert ctx.assumptions == []
    assert ctx.site_name == "basecase"


def test_assumptions_omit_location_when_absent() -> None:
    inp = _inputs()
    inp = inp.model_copy(update={"location": None})
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=inp
    )
    assert "Location" not in [a.label for a in ctx.assumptions]


# --------------------------------------------------------------------------- #
# Multi-technology breakdown (ARCH-4, #476)
# --------------------------------------------------------------------------- #
_HYBRID_SCENARIO = {
    "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.02},
    "revenue": {"tariff_lkr_per_kwh": 30.0},
    "capex": {"usd_total": 200_000_000.0},
    "opex": {"usd_per_year": 5_000_000.0},
    "generation": {
        "technologies": {
            "wind": {
                "type": "wind",
                "aep_gwh": 400.0,
                "capacity_factor": 0.34,
                "capex_usd": 150_000_000.0,
                "opex_usd_per_year": 3_500_000.0,
            },
            "solar": {
                "type": "solar",
                "aep_gwh": 100.0,
                "capacity_factor": 0.20,
                "capex_usd": 30_000_000.0,
                "opex_usd_per_year": 800_000.0,
            },
        }
    },
}
_HYBRID_KPIS = {**_VALUE_DESTRUCTIVE_KPIS, "mean_operational_cfads_usd": 20_000_000.0}


def test_multi_tech_block_populated_for_hybrid() -> None:
    ctx = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_HYBRID_SCENARIO,
    )
    assert ctx.multi_tech is not None
    techs = {r.technology for r in ctx.multi_tech.rows}
    assert techs == {"wind", "solar"}
    assert ctx.multi_tech.total_aep_gwh == 500.0
    wind = next(r for r in ctx.multi_tech.rows if r.technology == "wind")
    assert wind.capex_usd == 150_000_000.0
    assert wind.opex_usd_per_year == 3_500_000.0
    assert wind.share_of_aep_pct is not None
    # Reconciliation: 200M financed, 180M attributed, 20M shared/BOP residual.
    assert ctx.multi_tech.financed_capex_usd == 200_000_000.0
    assert ctx.multi_tech.allocated_capex_usd == 180_000_000.0
    assert ctx.multi_tech.capex_residual_usd == 20_000_000.0
    assert ctx.multi_tech.capex_reconciled is True


def test_multi_tech_none_for_single_tech() -> None:
    single = {
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.02},
        "generation": {
            "technologies": {
                "wind": {"type": "wind", "aep_gwh": 400.0, "capacity_factor": 0.34}
            }
        },
    }
    ctx = build_report_context(
        _case(_HYBRID_KPIS), generated_at=GENERATED_AT, scenario_config=single
    )
    assert ctx.multi_tech is None


def test_multi_tech_none_without_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.multi_tech is None


def test_multi_tech_section_renders_in_html() -> None:
    """The multi-tech section renders in the HTML (Jinja step; no weasyprint needed)."""
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_HYBRID_SCENARIO,
    )
    html = render_report_html(ctx)
    assert "Multi-Technology Breakdown" in html
    assert "wind" in html and "solar" in html

    # Single-tech omits the section entirely.
    ctx_single = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert "Multi-Technology Breakdown" not in render_report_html(ctx_single)


def test_multi_tech_block_surfaces_poi_curtailment_when_configured() -> None:
    """A hybrid declaring a shared-POI limit + per-tech hourly profiles surfaces the
    curtailment disclosure (ARCH-5); committed scenarios without them omit it."""
    cfg = {
        **_HYBRID_SCENARIO,
        "generation": {
            "shared_poi": {"limit_mw": 150.0},
            "technologies": {
                "wind": {
                    "type": "wind",
                    "aep_gwh": 400.0,
                    "capacity_factor": 0.34,
                    "capex_usd": 150_000_000.0,
                    "hourly_profile_mw": [120.0, 80.0, 130.0],
                },
                "solar": {
                    "type": "solar",
                    "aep_gwh": 100.0,
                    "capacity_factor": 0.20,
                    "capex_usd": 30_000_000.0,
                    "hourly_profile_mw": [50.0, 40.0, 40.0],
                },
            },
        },
    }
    ctx = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=cfg,
    )
    assert ctx.multi_tech is not None
    assert ctx.multi_tech.poi_limit_mw == 150.0
    assert ctx.multi_tech.poi_curtailment_pct is not None
    assert ctx.multi_tech.poi_curtailed_energy_mwh == pytest.approx(40.0)  # 20+0+20

    # The committed-style hybrid (no POI limit / hourly profiles) omits curtailment.
    ctx_plain = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_HYBRID_SCENARIO,
    )
    assert ctx_plain.multi_tech is not None
    assert ctx_plain.multi_tech.poi_curtailment_pct is None


# --------------------------------------------------------------------------- #
# Three-statement output + tie-outs (#479)
# --------------------------------------------------------------------------- #
def _annual_rows_3s(n: int = 3) -> list:
    # Enriched rows: LKR P&L + per-year USD debt columns. interest 10/8/6, service 30/28/26
    # -> principal 20 each, retiring the 60 drawn debt (debt_total 55 + IDC 5) to 0. The engine
    # CFADS columns (cf_pre_debt 40/38/36, deliberately distinct from the ~7 the P&L would
    # reconstruct) prove the waterfall reads the engine's published figure, not a reconstruction.
    interest = [10.0, 8.0, 6.0]
    service = [30.0, 28.0, 26.0]
    cf_pre_debt = [40.0, 38.0, 36.0]
    return [
        {
            "year": t + 1,
            "revenue_lkr": 1000.0,
            "opex_lkr": 200.0,
            "ebitda_lkr": 800.0,
            "total_depreciation_lkr": 500.0,
            "tax_lkr": 100.0,
            "fx_rate": 100.0,
            "interest_usd": interest[t],
            "debt_service_total": service[t],
            "balloon_resolution": 0.0,
            "cf_pre_debt": cf_pre_debt[t],
            "cf_after_debt": cf_pre_debt[t] - service[t],
        }
        for t in range(n)
    ]


_DEBT_RESULT_3S = {
    "debt_total": 55.0,
    "total_idc": 5.0,
    "balloon_residual": 0.0,
}
_SCEN_3S = {"capex": {"usd_total": 55.0}, "fx": {"start_lkr_per_usd": 100.0}}


def test_three_statement_block_populated_and_ties_out() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    assert ctx.three_statement is not None
    ts = ctx.three_statement
    assert ts.currency == "USD"
    assert ts.tie_outs_pass is True
    assert ts.balance_sheet_balances and ts.debt_retires_to_residual
    assert len(ts.income_statement) == 3 and len(ts.balance_sheet) == 3


def test_three_statement_none_without_annual_rows() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
    )
    assert ctx.three_statement is None


def test_three_statement_section_renders_in_html() -> None:
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    html = render_report_html(ctx)
    assert "Financial Statements" in html
    assert "All tie-outs pass" in html
    assert "Income statement" in html and "Balance sheet" in html


def test_cashflow_waterfall_block_populated() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    assert ctx.cashflow_waterfall is not None
    wf = ctx.cashflow_waterfall
    assert wf.currency == "USD"
    assert len(wf.rows) == 3
    # The waterfall sources the engine's published cf_pre_debt (40/38/36), NOT a P&L reconstruction.
    assert [r.cfads for r in wf.rows] == pytest.approx([40.0, 38.0, 36.0])
    # Scheduled debt service equals the engine's debt_service_total (ties to the DSCR section).
    assert [r.scheduled_debt_service for r in wf.rows] == pytest.approx(
        [30.0, 28.0, 26.0]
    )
    assert wf.total_cfads == pytest.approx(114.0)
    assert wf.total_scheduled_debt_service == pytest.approx(84.0)


def test_cashflow_waterfall_none_without_annual_rows() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
    )
    assert ctx.cashflow_waterfall is None


def test_cashflow_waterfall_section_renders_in_html() -> None:
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    html = render_report_html(ctx)
    assert "Cash-Flow Waterfall by Payment Priority" in html
    assert "Scheduled debt service" in html
    assert "Cash to equity" in html
