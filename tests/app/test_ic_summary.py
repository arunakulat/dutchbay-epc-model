"""IC executive summary + red-flag block — app/reports/report_model.py (#706).

Covers the presence-gated red-flag derivations (covenant breach, negative sponsor
returns, below-hurdle project IRR, CP-outstanding, readiness reds), the single-source
consistency with the Verdict (incl. the engine-published ``balloon_covenant_breach``
precedent), and the render-when-present template section. KPI-neutral: pure surfacing
over engine-published outputs — no assertion here recomputes a finance metric.

The load-bearing guarantee: an ABSENT KPI or register never fabricates a flag. The
verdict's booleans read "absent" as "not met" for the headline; the red-flag section
must only report breaches it has evidence for (the #657 fabricated-breach lesson).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import pytest
from pydantic import ValidationError

from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    IcSummaryBlock,
    ReadinessRow,
    RedFlag,
    _build_ic_summary,
    _build_verdict,
    build_report_context,
    load_report_config,
)

GENERATED_AT = "2026-07-03T12:00:00+00:00"

#: The frozen value-destructive economics (mirrors test_report_model): project IRR below
#: the hurdle, negative equity IRR/NPV, DSCR at the 1.30 sculpt target (meets the floor),
#: balloon within the report ceiling.
_VALUE_DESTRUCTIVE_KPIS: Dict[str, float] = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "project_npv": -57994285.93,
    "equity_npv": -60926463.83,
    "min_dscr": 1.2999999,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}

#: A healthy run: everything the red-flag section watches is green.
_HEALTHY_KPIS: Dict[str, float] = {
    "project_irr": 0.1200,
    "equity_irr": 0.1500,
    "equity_npv": 25_000_000.0,
    "min_dscr": 1.45,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.10,
}


def _case(kpis: Dict[str, float]) -> CaseResult:
    return CaseResult(
        status="success", scenario_variant="lendercase", kpis=kpis, run_manifest=None
    )


def _ic(
    kpis: Dict[str, float],
    scenario_config: Optional[Mapping[str, Any]] = None,
    readiness_rows: tuple = (),
) -> IcSummaryBlock:
    covenants = load_report_config().covenants
    verdict = _build_verdict(kpis, covenants)
    return _build_ic_summary(kpis, verdict, scenario_config, list(readiness_rows))


def _kinds(block: IcSummaryBlock) -> set[str]:
    return {f.kind for f in block.red_flags}


# ── clean path ───────────────────────────────────────────────────────────────────
def test_healthy_run_is_clean() -> None:
    block = _ic(_HEALTHY_KPIS)
    assert block.is_clean
    assert block.red_flags == []
    assert block.cp_outstanding == 0
    assert block.readiness_reds == []


def test_headline_is_the_verdict_headline_single_source() -> None:
    covenants = load_report_config().covenants
    verdict = _build_verdict(_VALUE_DESTRUCTIVE_KPIS, covenants)
    block = _build_ic_summary(_VALUE_DESTRUCTIVE_KPIS, verdict, None, [])
    assert block.headline == verdict.headline


# ── value/covenant flags ─────────────────────────────────────────────────────────
def test_value_destructive_run_flags_returns_not_covenants() -> None:
    block = _ic(_VALUE_DESTRUCTIVE_KPIS)
    kinds = _kinds(block)
    # DSCR 1.30 meets the floor and the balloon is within ceiling: no covenant flag.
    assert kinds == {"negative_equity", "below_hurdle"}
    assert all(f.severity == "high" for f in block.red_flags)


def test_dscr_breach_raises_covenant_flag() -> None:
    kpis = dict(_HEALTHY_KPIS, min_dscr=1.05)
    block = _ic(kpis)
    covenant = [f for f in block.red_flags if f.kind == "covenant_breach"]
    assert len(covenant) == 1
    assert "1.05x" in covenant[0].detail
    assert covenant[0].severity == "high"


def test_absent_min_dscr_never_fabricates_a_breach() -> None:
    kpis = {k: v for k, v in _HEALTHY_KPIS.items() if k != "min_dscr"}
    covenants = load_report_config().covenants
    verdict = _build_verdict(kpis, covenants)
    assert verdict.dscr_covenant_met is False  # the verdict reads absent as not-met…
    block = _build_ic_summary(kpis, verdict, None, [])
    assert "covenant_breach" not in _kinds(block)  # …but the red flag must NOT fire


def test_engine_balloon_breach_flag_is_honored_true() -> None:
    kpis = dict(_HEALTHY_KPIS, balloon_covenant_breach=1.0)
    block = _ic(kpis)
    covenant = [f for f in block.red_flags if f.kind == "covenant_breach"]
    assert len(covenant) == 1
    assert "modeled refinance-risk covenant" in covenant[0].detail
    assert "balloon_covenant_breach" in covenant[0].source


def test_engine_balloon_ok_flag_suppresses_report_ceiling_judgment() -> None:
    # The engine explicitly judged the balloon OK: even a share above the report's
    # presentation ceiling must NOT be re-judged into a flag (CCCDIR single source).
    kpis = dict(_HEALTHY_KPIS, balloon_pct=0.90, balloon_covenant_breach=0.0)
    block = _ic(kpis)
    assert "covenant_breach" not in _kinds(block)


def test_balloon_fallback_to_report_ceiling_when_engine_silent() -> None:
    kpis = dict(_HEALTHY_KPIS, balloon_pct=0.90)  # no engine flag published
    block = _ic(kpis)
    covenant = [f for f in block.red_flags if f.kind == "covenant_breach"]
    assert len(covenant) == 1
    assert "report refinance-risk ceiling" in covenant[0].detail


# ── sponsor-return flags (literal-truth guard) ───────────────────────────────────
def test_negative_equity_details_only_state_what_is_negative() -> None:
    # Positive IRR, negative NPV: the flag must mention the NPV and NOT call the
    # IRR negative (the round-11 literally-false-statement lesson).
    kpis = dict(_HEALTHY_KPIS, equity_irr=0.03, equity_npv=-5_000_000.0)
    block = _ic(kpis)
    neg = [f for f in block.red_flags if f.kind == "negative_equity"]
    assert len(neg) == 1
    assert "NPV" in neg[0].detail and "-$5,000,000" in neg[0].detail
    assert "IRR" not in neg[0].detail


def test_negative_equity_irr_and_npv_both_stated() -> None:
    block = _ic(_VALUE_DESTRUCTIVE_KPIS)
    (neg,) = [f for f in block.red_flags if f.kind == "negative_equity"]
    assert "equity IRR -2.46% is negative" in neg.detail
    assert "equity NPV -$60,926,464 is negative" in neg.detail


def test_absent_equity_kpis_raise_no_flag() -> None:
    kpis = {
        k: v for k, v in _HEALTHY_KPIS.items() if k not in ("equity_irr", "equity_npv")
    }
    block = _ic(kpis)
    assert "negative_equity" not in _kinds(block)


def test_break_even_equity_irr_zero_is_not_called_negative() -> None:
    # equity_irr EXACTLY 0.0 (a reachable break-even waterfall / no-waterfall sentinel)
    # is not negative: with a non-negative NPV the negative_equity flag must not fire,
    # and it must never print "equity IRR 0.00% is negative" (literal falsehood that
    # could co-render under a Bankable headline). Regression for the #706 Fable BLOCK.
    kpis = dict(_HEALTHY_KPIS, equity_irr=0.0, equity_npv=1.0)
    block = _ic(kpis)
    assert "negative_equity" not in _kinds(block)
    assert all("0.00% is negative" not in f.detail for f in block.red_flags)


def test_zero_equity_irr_with_negative_npv_flags_only_the_npv() -> None:
    # A genuinely value-destructive run whose equity_irr rounds to break-even: only the
    # NPV part is negative, so the flag states the NPV and does NOT call the IRR negative.
    kpis = dict(_HEALTHY_KPIS, equity_irr=0.0, equity_npv=-3_000_000.0)
    block = _ic(kpis)
    (neg,) = [f for f in block.red_flags if f.kind == "negative_equity"]
    assert "NPV" in neg.detail and "-$3,000,000" in neg.detail
    assert "IRR" not in neg.detail


# ── hurdle flag ──────────────────────────────────────────────────────────────────
def test_below_hurdle_flag_states_both_numbers() -> None:
    block = _ic(_VALUE_DESTRUCTIVE_KPIS)
    (hurdle,) = [f for f in block.red_flags if f.kind == "below_hurdle"]
    assert "4.22%" in hurdle.detail and "8.54%" in hurdle.detail


def test_absent_hurdle_raises_no_flag() -> None:
    kpis = {
        k: v for k, v in _VALUE_DESTRUCTIVE_KPIS.items() if k != "discount_rate_used"
    }
    block = _ic(kpis)
    assert "below_hurdle" not in _kinds(block)


# ── CP-outstanding flag ──────────────────────────────────────────────────────────
def test_outstanding_cps_flag_with_workstream_counts() -> None:
    scenario = {
        "conditions_precedent": {
            "items": {
                "ppa_executed": {"status": "pending"},
                "esia_approved": {"status": "pending"},
                "epc_contract_signed": {"status": "satisfied"},
            }
        }
    }
    block = _ic(_HEALTHY_KPIS, scenario_config=scenario)
    assert block.cp_outstanding == 2
    assert block.cp_outstanding_by_workstream == {
        "ppa": 1,
        "environmental_social": 1,
    }
    (cp,) = [f for f in block.red_flags if f.kind == "cp_outstanding"]
    assert cp.severity == "medium"
    assert "2 condition(s) precedent outstanding" in cp.detail
    assert "first drawdown is gated" in cp.detail


def test_all_satisfied_cps_raise_no_flag() -> None:
    scenario = {
        "conditions_precedent": {
            "items": {
                "ppa_executed": {"status": "satisfied"},
                "esia_approved": {"status": "waived", "waived_reason": "bridged"},
            }
        }
    }
    block = _ic(_HEALTHY_KPIS, scenario_config=scenario)
    assert block.cp_outstanding == 0
    assert "cp_outstanding" not in _kinds(block)


def test_no_scenario_config_raises_no_cp_flag() -> None:
    block = _ic(_HEALTHY_KPIS, scenario_config=None)
    assert block.cp_outstanding == 0
    assert block.cp_outstanding_by_workstream == {}
    assert "cp_outstanding" not in _kinds(block)


def test_malformed_cp_block_degrades_instead_of_breaking_the_report() -> None:
    # A structurally malformed conditions_precedent.items raises in build_cp_report;
    # the IC summary must degrade to "no CP block" (like the other best-effort report
    # inputs) rather than propagate and break the whole report.
    scenario = {"conditions_precedent": {"items": 7}}  # not a mapping/list -> raises
    block = _ic(_HEALTHY_KPIS, scenario_config=scenario)
    assert block.cp_outstanding == 0
    assert "cp_outstanding" not in _kinds(block)


# ── readiness-red flag ───────────────────────────────────────────────────────────
def test_readiness_reds_are_aggregated_into_one_flag() -> None:
    rows = (
        ReadinessRow(workstream="land", status="red"),
        ReadinessRow(workstream="grid_connection", status="red"),
        ReadinessRow(workstream="ppa", status="green"),
    )
    block = _ic(_HEALTHY_KPIS, readiness_rows=rows)
    assert block.readiness_reds == ["land", "grid_connection"]
    (flag,) = [f for f in block.red_flags if f.kind == "readiness_red"]
    assert flag.severity == "medium"
    assert "land, grid_connection" in flag.detail


def test_amber_readiness_raises_no_flag() -> None:
    rows = (ReadinessRow(workstream="permits", status="amber"),)
    block = _ic(_HEALTHY_KPIS, readiness_rows=rows)
    assert block.readiness_reds == []
    assert "readiness_red" not in _kinds(block)


# ── integration: build_report_context + template ─────────────────────────────────
def test_context_carries_ic_summary_and_template_renders_it() -> None:
    scenario = {
        "conditions_precedent": {"items": {"ppa_executed": {"status": "pending"}}},
        "development_readiness": {"items": {"financing": {"status": "red"}}},
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert ctx.ic_summary is not None
    kinds = _kinds(ctx.ic_summary)
    assert kinds == {
        "negative_equity",
        "below_hurdle",
        "cp_outstanding",
        "readiness_red",
    }
    assert ctx.ic_summary.headline == ctx.verdict.headline
    html = render_report_html(ctx)
    assert "Investment Committee — Red Flags" in html or (
        "Investment Committee &mdash; Red Flags" in html
    )
    assert "first drawdown is gated" in html


def test_clean_run_renders_no_red_flags_badge() -> None:
    ctx = build_report_context(_case(_HEALTHY_KPIS), generated_at=GENERATED_AT)
    assert ctx.ic_summary is not None
    assert ctx.ic_summary.is_clean
    html = render_report_html(ctx)
    assert "No red flags" in html


# ── model contracts ──────────────────────────────────────────────────────────────
def test_models_are_frozen_and_extra_forbid() -> None:
    flag = RedFlag(kind="covenant_breach", severity="high", detail="x", source="y")
    with pytest.raises(ValidationError):
        flag.detail = "mutated"
    with pytest.raises(ValidationError):
        RedFlag(kind="k", severity="s", detail="d", source="s", bogus="nope")
    block = IcSummaryBlock(headline="h")
    with pytest.raises(ValidationError):
        block.headline = "mutated"
