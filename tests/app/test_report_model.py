"""Tests for the report content model (pure presentation over a CaseResult)."""

from __future__ import annotations

from typing import Dict


from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_model import (
    ReportContext,
    Verdict,
    build_report_context,
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


def test_kpi_rows_formatted_in_config_order() -> None:
    ctx = build_report_context(_case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT)
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
    ctx = build_report_context(_case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT)
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
