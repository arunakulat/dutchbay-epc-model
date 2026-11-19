"""Monte Carlo IRR statistics say how many trials they leave out (#1746 step 1, #1763).

A trial whose cash flow changes sign more than once has no unique IRR (#1525). Each IRR
statistic is taken over that metric's defined trials only, so every surface that shows
one states the count it leaves out, and says the excluded trials may be the worst
outcomes. The capital-risk report shows each IRR metric with that coverage instead of
refusing (owner ruling 2026-11-16, "Report with coverage"); NPV, DSCR, LLCR and PLCR keep
the complete-cohort contract. No statistic changes for a run whose trials are all defined.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest

from analytics.capital_risk_layer_v14 import (
    _risk_config_from_scenario,
    build_capital_risk_report_from_trials,
)
from analytics.mc.aggregate import (
    aggregate_trials,
    irr_exclusion_note,
    irr_ranked_note,
)
from analytics.mc.exports import build_lender_risk_table
from app.api.responses import CaseResult
from app.api.surface import _project_capital_risk
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")
GENERATED_AT = "2026-11-17T00:00:00+00:00"
N = 40
UNDEFINED = (
    0,
    3,
    7,
    11,
    19,
)  # equity IRR undefined on these trials; project on 0 and 3


def _trials(*, undefined: bool) -> dict[str, list[float | None]]:
    rng = np.random.default_rng(7)
    out: dict[str, list[float | None]] = {
        "equity_irr": list(rng.normal(0.08, 0.03, N)),
        "project_irr": list(rng.normal(0.07, 0.02, N)),
        "equity_npv": list(rng.normal(-5e6, 4e6, N)),
        "project_npv": list(rng.normal(-3e6, 4e6, N)),
        "dscr_min": list(rng.normal(1.35, 0.05, N)),
        "llcr": list(rng.normal(1.40, 0.04, N)),
        "plcr": list(rng.normal(1.50, 0.04, N)),
    }
    if undefined:
        for i in UNDEFINED:
            out["equity_irr"][i] = None
        for i in UNDEFINED[:2]:
            out["project_irr"][i] = None
    return out


def _rows(*, undefined: bool) -> list[dict[str, float | None]]:
    trials = _trials(undefined=undefined)
    rows = []
    for i in range(N):
        row = {key: values[i] for key, values in trials.items()}
        # The evaluation gateway drops a KPI it cannot convert (normalize_kpi_dict),
        # so a real undefined IRR reaches the aggregate as an absent key.
        rows.append({k: v for k, v in row.items() if v is not None})
    return rows


def _aggregate(*, undefined: bool):
    rows = _rows(undefined=undefined)
    return aggregate_trials(
        trial_metrics=rows,
        base_config={},
        param_names=["capex.usd_total"],
        samples=np.zeros((len(rows), 1)),
        meta={"seed": 1, "n_trials": len(rows)},
    )


def _report(tmp_path: Path, *, undefined: bool):
    return build_capital_risk_report_from_trials(
        _trials(undefined=undefined),
        tmp_path,
        risk_config=_risk_config_from_scenario(LENDER_CONFIG),
        scenario="synthetic",
    )


def test_summary_states_the_excluded_trials_beside_each_irr(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="analytics.mc.aggregate"):
        result = _aggregate(undefined=True)
    equity = result.summary["equity_irr"]
    assert equity["defined_count"] == N - 5 and equity["excluded_count"] == 5
    # #1746 step 2: the summary ranks the excluded trials worst and says so.
    assert equity["coverage_note"] == irr_ranked_note("equity_irr", 5, N)
    assert "ranked below every defined trial" in equity["coverage_note"]
    assert result.summary["project_irr"]["excluded_count"] == 2
    assert result.project_irr_excluded_count == 2
    assert set(result.metadata["irr_coverage_notes"]) == {"equity_irr", "project_irr"}
    # NPV and DSCR carry their counts too, with no note: they cover every trial.
    assert result.summary["equity_npv"]["excluded_count"] == 0
    assert "coverage_note" not in result.summary["equity_npv"]
    assert sum("no defined equity_irr" in r.message for r in caplog.records) == 1
    # The mean stays over the defined trials, and says so (#1746 step 2).
    defined = [v for v in _trials(undefined=True)["equity_irr"] if v is not None]
    assert equity["mean"] == pytest.approx(float(np.mean(defined)))
    assert equity["mean_basis"] == "defined_trials"


def test_a_run_with_every_irr_defined_carries_no_note(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="analytics.mc.aggregate"):
        result = _aggregate(undefined=False)
    for key in ("equity_irr", "project_irr"):
        assert result.summary[key]["excluded_count"] == 0
        assert "coverage_note" not in result.summary[key]
    assert result.metadata["irr_coverage_notes"] == {}
    assert result.project_irr_excluded_count == 0
    assert not [r for r in caplog.records if "no defined" in r.message]


def test_lender_risk_table_notes_only_an_irr_that_leaves_trials_out() -> None:
    frame = build_lender_risk_table(_aggregate(undefined=True))
    irr = frame[frame["metric"] == "Project IRR"].iloc[0]
    assert irr["unavailable_trials"] == 2
    assert irr["coverage_note"] == irr_ranked_note("project_irr", 2, N)
    npv = frame[frame["metric"] == "Project NPV"].iloc[0]
    assert not isinstance(npv["coverage_note"], str)
    clean = build_lender_risk_table(_aggregate(undefined=False))
    assert "coverage_note" not in clean.columns


def test_capital_risk_report_shows_each_irr_with_its_coverage(tmp_path) -> None:
    """#1763: built, not refused; each IRR over its own defined trials."""
    report = _report(tmp_path, undefined=True)
    assert report.n_trials == N
    equity = report.irr_coverage["equity_irr"]
    assert (equity["defined_count"], equity["excluded_count"]) == (N - 5, 5)
    assert equity["note"] == irr_exclusion_note("equity_irr", 5, N)
    assert report.irr_coverage["project_irr"]["excluded_count"] == 2
    trials = _trials(undefined=True)
    defined = np.array([v for v in trials["equity_irr"] if v is not None])
    assert report.tail_report.equity_irr.mean == pytest.approx(defined.mean())
    target = report.tail_report.target_equity_irr
    assert report.tail_report.probability_below_hurdle == pytest.approx(
        float((defined < target).mean())
    )
    # NPV keeps every trial.
    assert report.tail_report.equity_npv.mean == pytest.approx(
        float(np.mean(trials["equity_npv"]))
    )
    rows = {row["metric"]: row for row in report.snapshot["rows"]}
    assert rows["equity_irr"]["excluded_count"] == 5
    assert np.isfinite(rows["equity_irr"]["p10"])
    assert "excluded_count" not in rows["equity_npv"]


def test_capital_risk_report_still_refuses_an_incomplete_npv(tmp_path) -> None:
    trials = _trials(undefined=True)
    trials["equity_npv"][4] = None
    with pytest.raises(ValueError, match="complete aligned metric observations"):
        build_capital_risk_report_from_trials(
            trials,
            tmp_path,
            risk_config=_risk_config_from_scenario(LENDER_CONFIG),
            scenario="synthetic",
        )


def test_a_complete_report_has_full_coverage_and_no_note(tmp_path) -> None:
    report = _report(tmp_path, undefined=False)
    for facts in report.irr_coverage.values():
        assert facts["excluded_count"] == 0 and facts["note"] is None


def _case() -> CaseResult:
    return CaseResult(
        status="success",
        scenario_variant="lendercase",
        kpis={"project_irr": 0.05, "equity_irr": 0.06, "min_dscr": 1.3},
        run_manifest=None,
    )


def test_report_block_api_surface_and_html_state_the_coverage(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    report = _report(tmp_path, undefined=True)
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, capital_risk=report)
    block = ctx.capital_risk
    assert block is not None
    assert block.irr_coverage_notes == [
        irr_exclusion_note("project_irr", 2, N),
        irr_exclusion_note("equity_irr", 5, N),
    ]
    assert block.hurdle_defined_count == N - 5
    rows = {m.metric: m for m in block.metrics}
    assert (rows["equity_irr"].defined_count, rows["equity_irr"].total_count) == (
        N - 5,
        N,
    )
    assert (
        rows["equity_npv"].defined_count == N
        and rows["equity_npv"].coverage_note is None
    )
    surface = _project_capital_risk(block)
    assert surface is not None
    assert surface.irr_coverage_notes == block.irr_coverage_notes
    assert {m.metric: m.defined_count for m in surface.metrics}["equity_irr"] == N - 5
    html = render_report_html(ctx)
    assert html.count("IRR coverage:") == 2
    assert irr_exclusion_note("equity_irr", 5, N) in html
    assert f"over the {N - 5} of {N} trials with a defined equity IRR" in html
    assert f"{N - 5} of {N}" in html


def test_report_html_without_undefined_irr_has_no_coverage_note(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    report = _report(tmp_path, undefined=False)
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, capital_risk=report)
    assert ctx.capital_risk is not None and ctx.capital_risk.irr_coverage_notes == []
    html = render_report_html(ctx)
    assert "IRR coverage:" not in html
    assert "with a defined equity IRR" not in html
