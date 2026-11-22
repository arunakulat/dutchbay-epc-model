"""The #1456 equity IRR ranking caveat on every surface that prints equity IRR (#1688).

#1522 put the flag (``equity_irr_ranks_reliably``) and the sign-change count in the waterfall's
opaque equity summary, outside ``kpis``. These tests pin that each rendered surface shows the
caveat, with equity NPV beside equity IRR, when the flag is False, and shows nothing new when it
is True. The pessimistic case is flagged (two sign changes); the base case and, since #1892
(#1845) sized it to the annual covenant DSCR, the lender case are not.
"""

from __future__ import annotations

from html import unescape
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.casper.casper_payload import build_casper_payload
from analytics.contracts_v14 import EquityPerformance, ScenarioResult
from analytics.equity_irr_caveat import (
    equity_irr_caveat_from_run,
    equity_irr_caveat_from_summary,
    equity_irr_ranking_caveat,
)
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.executive_workbook import (
    EQUITY_IRR_CAVEAT_LABEL,
    frames_from_pipeline_result,
)
from analytics.pipeline_v14_enhanced import _update_kpis_with_equity_distribution
from app.api.responses import CaseResult
from app.reports import solar_assessment
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context, fmt_usd

GENERATED_AT = "2026-11-17T00:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]
#: The committed case whose equity IRR does not rank it. The lender case motivated #1688 with
#: three sign changes until #1892 (#1845) sized it to the annual covenant DSCR; it now has one.
_FLAGGED_CFG = _REPO_ROOT / "scenarios" / "dutchbay_pessimistic_2025Q4.yaml"
FLAGGED_SIGN_CHANGES = 2
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
_BASE_CFG = _REPO_ROOT / "scenarios" / "dutchbay_basecase_2025Q4.yaml"


@pytest.fixture(scope="module")
def flagged_run() -> Dict[str, Any]:
    return evaluate_with_overrides(str(_FLAGGED_CFG), return_full_result=True)


@pytest.fixture(scope="module")
def lender_run() -> Dict[str, Any]:
    return evaluate_with_overrides(str(_LENDER_CFG), return_full_result=True)


@pytest.fixture(scope="module")
def base_run() -> Dict[str, Any]:
    return evaluate_with_overrides(str(_BASE_CFG), return_full_result=True)


def _summary(run: Dict[str, Any]) -> Dict[str, Any]:
    return run["equity_distribution"]["equity_summary"]


# ── the wording ────────────────────────────────────────────────────────────────


def test_no_caveat_unless_the_flag_is_exactly_false() -> None:
    assert equity_irr_ranking_caveat(True, 1) is None
    assert equity_irr_ranking_caveat(None, 3) is None
    assert equity_irr_ranking_caveat(0, 3) is None  # falsy is not False
    assert equity_irr_caveat_from_summary({}) is None
    assert equity_irr_caveat_from_summary(None) is None
    assert equity_irr_caveat_from_run(None) is None
    assert equity_irr_caveat_from_run({"equity_distribution": "x"}) is None


@pytest.mark.parametrize(
    ("sign_changes", "reason"),
    [
        # Descartes' rule of signs (#1821 review D-1): an odd count always leaves a rate,
        # so only an even count may say "or none".
        (
            3,
            "its equity cash flows change sign 3 times, so more than one rate can solve them.",
        ),
        (
            5,
            "its equity cash flows change sign 5 times, so more than one rate can solve them.",
        ),
        (
            2,
            "its equity cash flows change sign 2 times, "
            "so more than one rate, or none, can solve them.",
        ),
        (
            4,
            "its equity cash flows change sign 4 times, "
            "so more than one rate, or none, can solve them.",
        ),
        (0, "its equity cash flows never change sign, so no rate solves them."),
        (None, "its equity cash flows do not change sign exactly once."),
        (True, "its equity cash flows do not change sign exactly once."),
        (False, "its equity cash flows do not change sign exactly once."),
        (-1, "its equity cash flows do not change sign exactly once."),
    ],
)
def test_the_caveat_names_why_and_points_to_equity_npv(
    sign_changes: Any, reason: str
) -> None:
    caveat = equity_irr_ranking_caveat(False, sign_changes)
    assert caveat is not None
    assert caveat.startswith("Equity IRR does not rank this case: ")
    assert reason in caveat
    if isinstance(sign_changes, int) and not isinstance(sign_changes, bool):
        assert ("or none" in caveat) == (sign_changes >= 2 and sign_changes % 2 == 0)
    assert caveat.endswith(
        "Read equity NPV beside it, and rank cases on NPV, not equity IRR (#1456)."
    )
    # #1821 domain review DM-1: the solar + BESS sizing ranks on project NPV, so the caveat
    # must not say that every optimiser ranks on equity NPV.
    assert "optimisers" not in caveat
    assert "rank on equity NPV" not in caveat


# ── the engine side: the flag rides in metadata, never in kpis ──────────────────


def test_the_flag_rides_in_equity_metadata_and_stays_out_of_kpis() -> None:
    kpis: Dict[str, Any] = {}
    perf = _update_kpis_with_equity_distribution(
        kpis,
        {
            "status": "computed",
            "equity_summary": {
                "equity_irr": 0.05,
                "equity_npv": -1.0,
                "equity_irr_ranks_reliably": False,
                "equity_cashflow_sign_changes": 3,
            },
        },
    )
    assert perf is not None
    assert perf.metadata["equity_irr_ranks_reliably"] is False
    assert perf.metadata["equity_cashflow_sign_changes"] == 3
    assert not any("ranks_reliably" in key or "sign_changes" in key for key in kpis)


def test_the_committed_cases_carry_the_flag(
    flagged_run: Dict[str, Any],
    lender_run: Dict[str, Any],
    base_run: Dict[str, Any],
) -> None:
    assert _summary(flagged_run)["equity_irr_ranks_reliably"] is False
    assert _summary(flagged_run)["equity_cashflow_sign_changes"] == FLAGGED_SIGN_CHANGES
    assert _summary(base_run)["equity_irr_ranks_reliably"] is True
    # #1892 (#1845): the lender case's equity cash flows now change sign once.
    assert _summary(lender_run)["equity_irr_ranks_reliably"] is True
    assert _summary(lender_run)["equity_cashflow_sign_changes"] == 1
    meta = flagged_run["scenario_result"]["equity_performance"]["metadata"]
    assert meta["equity_irr_ranks_reliably"] is False
    assert meta["equity_cashflow_sign_changes"] == FLAGGED_SIGN_CHANGES
    assert "equity_irr_caveat" not in flagged_run["kpis"]


# ── the lender report ──────────────────────────────────────────────────────────


def _report_html(run: Dict[str, Any], cfg: Path) -> tuple[Any, str]:
    scenario = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    case = CaseResult.from_pipeline_result(run, scenario_variant=cfg.stem)
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        scenario_config=scenario,
        debt_result=run["debt_result"],
        run_result=run,
    )
    return ctx, unescape(render_report_html(ctx))


def test_the_lender_report_shows_the_caveat_and_equity_npv(
    flagged_run: Dict[str, Any],
) -> None:
    ctx, html = _report_html(flagged_run, _FLAGGED_CFG)
    assert ctx.equity_irr_caveat == equity_irr_ranking_caveat(
        False, FLAGGED_SIGN_CHANGES
    )
    summary = html.split("<h2>Executive Summary</h2>", 1)[1].split("</table>", 1)[0]
    irr_row = summary.index("<td>Equity IRR</td>")
    npv_row = summary.index("<td>Equity NPV</td>")
    caveat_row = summary.index('<tr class="equity-irr-caveat">')
    assert irr_row < npv_row < caveat_row, "equity NPV and the caveat follow equity IRR"
    # The Equity NPV row prints the run's own equity NPV, not a placeholder.
    equity_npv = flagged_run["kpis"]["equity_npv"]
    assert isinstance(equity_npv, float)
    assert f'<td>Equity NPV</td><td class="num">{fmt_usd(equity_npv)}</td>' in summary
    assert ctx.equity_irr_caveat in summary
    # #1821 review D-2: the Key Financial Indicators table prints equity IRR too.
    kfi = html.split("<h2>Key Financial Indicators</h2>", 1)[1].split("</section>", 1)[
        0
    ]
    assert kfi.index("</table>") < kfi.index('class="muted equity-irr-caveat-kpi"')
    assert ctx.equity_irr_caveat in kfi


def test_the_kpi_only_report_still_shows_the_caveat(
    flagged_run: Dict[str, Any],
) -> None:
    """#1821 review D-4: without scenario_config or debt_result there is no Executive
    Summary finance block, but the Key Financial Indicators table still prints equity IRR.
    """
    case = CaseResult.from_pipeline_result(
        flagged_run, scenario_variant=_FLAGGED_CFG.stem
    )
    ctx = build_report_context(case, generated_at=GENERATED_AT, run_result=flagged_run)
    html = unescape(render_report_html(ctx))
    kfi = html.split("<h2>Key Financial Indicators</h2>", 1)[1].split("</section>", 1)[
        0
    ]
    assert equity_irr_ranking_caveat(False, FLAGGED_SIGN_CHANGES) in kfi


def test_a_case_whose_irr_ranks_gets_no_caveat_or_extra_row(
    base_run: Dict[str, Any],
) -> None:
    ctx, html = _report_html(base_run, _BASE_CFG)
    assert ctx.equity_irr_caveat is None
    assert "equity-irr-caveat" not in html
    assert "<td>Equity NPV</td>" not in html.split("</table>", 1)[0]


# ── the executive workbook ─────────────────────────────────────────────────────


def test_the_workbook_puts_the_caveat_after_equity_irr(
    flagged_run: Dict[str, Any],
) -> None:
    frames = frames_from_pipeline_result(flagged_run)
    caveat = equity_irr_ranking_caveat(False, FLAGGED_SIGN_CHANGES)
    metrics = list(frames["summary"]["Metric"])
    at = metrics.index("equity_irr")
    assert metrics[at + 1] == EQUITY_IRR_CAVEAT_LABEL
    assert frames["summary"]["Value"].iloc[at + 1] == caveat
    columns = list(frames["scenario_summary"].columns)
    assert columns[columns.index("equity_irr") + 1] == EQUITY_IRR_CAVEAT_LABEL
    assert frames["scenario_summary"].iloc[0][EQUITY_IRR_CAVEAT_LABEL] == caveat
    assert "equity_npv" in columns


def test_the_workbook_keeps_its_columns_when_the_irr_ranks(
    base_run: Dict[str, Any],
) -> None:
    frames = frames_from_pipeline_result(base_run)
    assert EQUITY_IRR_CAVEAT_LABEL not in list(frames["summary"]["Metric"])
    scenario_summary = frames["scenario_summary"]
    assert EQUITY_IRR_CAVEAT_LABEL in scenario_summary.columns
    assert scenario_summary.iloc[0][EQUITY_IRR_CAVEAT_LABEL] is None


# ── the CASPER payload ─────────────────────────────────────────────────────────


def _scenario(meta: Dict[str, Any]) -> ScenarioResult:
    return ScenarioResult(
        scenario_name="caveat",
        config_path="<inline>",
        project_npv=1.0,
        project_irr=0.05,
        dscr_series=[1.3],
        min_dscr=1.3,
        max_debt_usd=1.0,
        equity_performance=EquityPerformance(
            equity_irr=0.02, equity_npv=-5.0, equity_multiple=1.0, metadata=meta
        ),
    )


def test_the_casper_payload_carries_the_caveat_beside_equity_npv(
    flagged_run: Dict[str, Any], base_run: Dict[str, Any]
) -> None:
    lender_meta = flagged_run["scenario_result"]["equity_performance"]["metadata"]
    block = build_casper_payload(scenario=_scenario(lender_meta))["scenario"][
        "equity_performance"
    ]
    assert block["equity_irr_caveat"] == equity_irr_ranking_caveat(
        False, FLAGGED_SIGN_CHANGES
    )
    assert block["equity_npv"] == -5.0
    base_meta = base_run["scenario_result"]["equity_performance"]["metadata"]
    block = build_casper_payload(scenario=_scenario(base_meta))["scenario"][
        "equity_performance"
    ]
    assert block["equity_irr_caveat"] is None


def test_the_casper_payload_reads_a_mapping_equity_block() -> None:
    scenario = _scenario({})
    object.__setattr__(
        scenario,
        "equity_performance",
        {
            "equity_irr": 0.02,
            "equity_npv": -5.0,
            "metadata": {
                "equity_irr_ranks_reliably": False,
                "equity_cashflow_sign_changes": 2,
            },
        },
    )
    block = build_casper_payload(scenario=scenario)["scenario"]["equity_performance"]
    assert block["equity_irr_caveat"] == equity_irr_ranking_caveat(False, 2)


# ── the solar assessment report ────────────────────────────────────────────────


def _finance_table(base: Dict[str, Any]) -> Dict[str, Any]:
    doc = solar_assessment.as_dbpl_document(
        {
            "scenario_name": "Any",
            "scenario_path": "x.yaml",
            "not_run": [],
            "base": base,
        },
        {},
        issue_date="2026-11-17",
    )
    section = next(
        s for s in doc["sections"] if s["heading"] == "Deterministic finance"
    )
    table: Dict[str, Any] = section["table"]
    return table


_BASE_KPIS = {
    "project_irr": 0.05,
    "equity_irr": 0.02,
    "project_npv": 1.0,
    "equity_npv": -5.0,
    "min_dscr": 1.3,
    "avg_dscr": 1.5,
    "max_debt_usd": 1.0,
    "discount_rate_used": 0.08,
}


def test_the_solar_assessment_finance_table_notes_the_caveat(
    flagged_run: Dict[str, Any],
) -> None:
    caveat = equity_irr_caveat_from_summary(_summary(flagged_run))
    assert caveat is not None
    table = _finance_table({**_BASE_KPIS, "equity_irr_caveat": caveat})
    assert table["notes"] == [caveat]
    labels = [row["cells"][0] for row in table["rows"]]
    assert "Equity NPV" in labels


def test_the_solar_assessment_table_has_no_note_when_the_irr_ranks() -> None:
    assert _finance_table({**_BASE_KPIS, "equity_irr_caveat": None})["notes"] is None
    assert _finance_table(dict(_BASE_KPIS))["notes"] is None


def test_the_solar_assessment_kpis_carry_the_caveat() -> None:
    out = solar_assessment.kpis(solar_assessment.load_scenario(_FLAGGED_CFG))
    assert out["equity_irr_caveat"] == equity_irr_ranking_caveat(
        False, FLAGGED_SIGN_CHANGES
    )
    assert out["equity_sign_changes"] == FLAGGED_SIGN_CHANGES
