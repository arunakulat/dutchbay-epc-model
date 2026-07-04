"""Report wiring for the capital-risk (Monte-Carlo) block (#776, surfacing #657).

Pins that build_report_context surfaces a pre-computed CapitalRiskReport as a
CapitalRiskBlock and that the existing renderer renders the section (render-when-present),
and that a caller supplying none omits it (byte-identical to the pre-#776 report). The MC
runs out-of-band; this is pure presentation of its result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pytest

from analytics.capital_risk_layer_v14 import (
    _risk_config_from_scenario,
    build_capital_risk_report_from_trials,
)
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

GENERATED_AT = "2026-07-03T12:00:00+00:00"
REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

_KPIS: Dict[str, float] = {
    "project_irr": 0.0268,
    "equity_irr": -0.0486,
    "equity_npv": -65_460_000.0,
    "min_dscr": 1.30,
    "discount_rate_used": 0.0983,
    "balloon_pct": 0.10,
}


def _case() -> CaseResult:
    return CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )


def _synthetic_trials(n: int = 60) -> dict:
    rng = np.random.default_rng(0)
    return {
        "equity_irr": rng.normal(-0.048, 0.01, n),
        "project_irr": rng.normal(0.027, 0.01, n),
        "equity_npv": rng.normal(-65e6, 5e6, n),
        "project_npv": rng.normal(-48e6, 5e6, n),
        "dscr_min": np.full(n, 1.30),
        "llcr": rng.normal(1.30, 0.002, n),
        "plcr": rng.normal(1.35, 0.002, n),
    }


def _capital_risk_report(tmp_path):
    return build_capital_risk_report_from_trials(
        _synthetic_trials(60),
        tmp_path,
        risk_config=_risk_config_from_scenario(LENDER_CONFIG),
        scenario="lendercase",
    )


def test_capital_risk_block_renders_when_supplied(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    report = _capital_risk_report(tmp_path)
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, capital_risk=report)
    assert ctx.capital_risk is not None
    block = ctx.capital_risk
    assert block.scenario == "lendercase" and block.n_trials == 60
    # the breach probabilities + the four VaR/CVaR metric rows are projected
    assert block.dscr_breach_probability == pytest.approx(0.0)
    assert {m.metric for m in block.metrics} == {
        "equity_irr",
        "project_irr",
        "equity_npv",
        "project_npv",
    }
    assert block.dscr_floor > 0.0
    # per-metric units: IRR rows are ratios, NPV rows are dollars (no mixed-unit column)
    units = {m.metric: m.unit for m in block.metrics}
    assert units["equity_irr"] == "pct" and units["equity_npv"] == "usd"
    html = render_report_html(ctx)
    assert "Capital Risk — Monte-Carlo Distribution" in html
    assert "Covenant-breach probability" in html
    assert "Value at Risk" in html
    # the NPV chart is embedded as a self-contained data URI (no absolute path leak)
    assert 'src="data:image/png;base64,' in html
    assert str(tmp_path) not in html  # the server filesystem path is NOT leaked
    # the methodology string is the report's actual method, not a hardcoded claim
    assert block.method in html


def test_capital_risk_method_is_the_actual_mc_provenance(tmp_path) -> None:
    # #776 Fable: the method must reflect the REAL MC source, not a hardcoded
    # "LHS + rank correlation". A synthetic (non-canonical) report carries the generic
    # default and must NOT claim rank correlation it never applied.
    report = _capital_risk_report(tmp_path)
    assert report.method == "monte_carlo"
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, capital_risk=report)
    html = render_report_html(ctx)
    assert (
        "rank correlation" not in html
    )  # not claimed for a source without correlation


def test_canonical_mc_result_method_label_is_derived(tmp_path) -> None:
    # from a canonical MonteCarloResult, the method is derived from its metadata
    # (sampler + correlation_enabled) — a faithful provenance, not a hardcoded string.
    pytest.importorskip("matplotlib")
    from analytics.capital_risk_layer_v14 import (
        build_capital_risk_report_from_mc_result,
    )
    from analytics.contracts_v14 import MonteCarloResult

    result = MonteCarloResult(
        trials={k: list(v) for k, v in _synthetic_trials(50).items()},
        metadata={"sampler": "lhs", "correlation_enabled": True},
    )
    rep = build_capital_risk_report_from_mc_result(
        result, tmp_path, risk_config=_risk_config_from_scenario(LENDER_CONFIG)
    )
    assert rep.method == "lhs sampling, rank correlation"


def test_capital_risk_block_omitted_when_absent() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT)
    assert ctx.capital_risk is None
    assert "Capital Risk — Monte-Carlo Distribution" not in render_report_html(ctx)


def test_capital_risk_projection_is_read_only(tmp_path) -> None:
    # the block reflects the report's own numbers (no recomputation): breach probs and the
    # target hurdle come straight from the tail_report / covenant thresholds.
    pytest.importorskip("matplotlib")
    report = _capital_risk_report(tmp_path)
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, capital_risk=report)
    cb = report.tail_report.covenant_breaches
    assert ctx.capital_risk.llcr_breach_probability == cb.llcr_breach_probability
    assert (
        ctx.capital_risk.probability_below_hurdle
        == report.tail_report.probability_below_hurdle
    )
    # only the basename is carried (no absolute-path leak); the img is a data URI
    assert (
        ctx.capital_risk.npv_distribution_filename == report.npv_distribution_png.name
    )
    assert ctx.capital_risk.npv_distribution_img.startswith("data:image/png;base64,")
