"""An undefined equity IRR reaches the KPI surface as undefined, never as 0.0 (#1436).

When no discount rate solves the equity cashflows, ``finance.irr`` returns ``None`` and the
equity waterfall reports ``equity_irr: None``. ``analytics.core.metrics`` seeds the KPI
surface with a 0.0 sentinel before the waterfall runs, and the merge into the KPI surface
copied only non-None values, so the sentinel survived: the worst cases (a long balloon
refinance on the lender case) reported 0.0, which the report reads as break-even (#782).

Negative control: ``test_lender_case_undefined_equity_irr_reaches_the_kpis_as_none`` reports
0.0 on ``main`` before this change. Positive controls: a defined IRR is merged unchanged,
and the canonical vector itself is pinned by
``tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, cast

import pytest

from analytics.pipeline_v14_enhanced import _update_kpis_with_equity_distribution
from app.reports.report_config import Covenants, KpiSpec, ReportConfig, ReportMeta
from app.reports.report_model import _build_kpi_rows, _build_verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _distribution(equity_irr: Any, status: str = "computed") -> Dict[str, Any]:
    return {
        "status": status,
        "equity_summary": {"equity_irr": equity_irr, "equity_npv": -1.0},
    }


def test_undefined_waterfall_irr_overwrites_the_zero_sentinel() -> None:
    kpis: Dict[str, Any] = {"equity_irr": 0.0}
    perf = _update_kpis_with_equity_distribution(kpis, _distribution(None))
    assert kpis["equity_irr"] is None
    assert perf is not None and perf.equity_irr is None


@pytest.mark.parametrize("status", ["computed", "defaulted"])
def test_defined_waterfall_irr_is_merged_unchanged(status: str) -> None:
    kpis: Dict[str, Any] = {"equity_irr": 0.0}
    _update_kpis_with_equity_distribution(
        kpis, _distribution(-0.07853839579881439, status)
    )
    assert kpis["equity_irr"] == -0.07853839579881439


def test_a_waterfall_that_did_not_run_leaves_the_kpis_alone() -> None:
    """Out of scope here: a failed waterfall is "not computed", not "undefined"."""
    kpis: Dict[str, Any] = {"equity_irr": 0.0}
    assert (
        _update_kpis_with_equity_distribution(kpis, _distribution(None, "failed"))
        is None
    )
    assert kpis["equity_irr"] == 0.0


def test_lender_case_undefined_equity_irr_reaches_the_kpis_as_none() -> None:
    """A 6-year balloon refinance leaves equity cashflows with no IRR root."""
    from analytics.evaluation_v14 import evaluate_with_overrides

    result = cast(
        Dict[str, Any],
        evaluate_with_overrides(
            LENDER_CONFIG,
            overrides={
                "Financing_Terms.balloon_treatment": "refinance",
                "constraints.refinancing.refinance_tenor_years": 6,
            },
            return_full_result=True,
        ),
    )
    assert result["equity_distribution"]["equity_summary"]["equity_irr"] is None
    assert result["kpis"]["equity_irr"] is None
    assert result["scenario_result"]["kpis"]["equity_irr"] is None


def _report_config() -> ReportConfig:
    return ReportConfig(
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
        kpi_table=[KpiSpec(key="equity_irr", label="Equity IRR", kind="pct")],
        risk_register=[],
    )


def test_report_kpi_table_shows_undefined_not_zero() -> None:
    rows = _build_kpi_rows({"equity_irr": None}, _report_config())  # type: ignore[dict-item]
    assert [(r.key, r.value, r.display) for r in rows] == [
        ("equity_irr", None, "undefined")
    ]


def test_report_kpi_table_still_formats_a_defined_irr() -> None:
    rows = _build_kpi_rows({"equity_irr": -0.0785}, _report_config())
    assert [(r.value, r.display) for r in rows] == [(-0.0785, "-7.85%")]


def test_report_verdict_says_undefined_and_never_break_even() -> None:
    covenants = _report_config().covenants
    verdict = _build_verdict({"equity_irr": None}, covenants)  # type: ignore[dict-item]
    assert any("Equity IRR is undefined" in note for note in verdict.notes)
    assert not any("break-even" in note for note in verdict.notes)
    assert _build_verdict({}, covenants).notes == []


def test_capex_mc_refuses_an_undefined_equity_irr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analytics.pipeline_v14_enhanced as pipeline
    from analytics.cost import mc_capex

    def _fake_run(config: Any) -> Dict[str, Any]:
        return {
            "kpis": {
                "project_irr": 0.01,
                "equity_irr": None,
                "project_npv": -1.0,
                "min_dscr": 1.3,
            }
        }

    monkeypatch.setattr(pipeline, "run_v14_pipeline", _fake_run)
    with pytest.raises(ValueError, match="equity IRR is undefined"):
        mc_capex.run_capex_mc(
            {"capex": {"usd_total": 100.0}}, n_samples=3, sigma_pct=10.0
        )


def test_wacc_sweep_carries_an_undefined_equity_irr_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from analytics import wacc_sensitivity

    monkeypatch.setattr(
        wacc_sensitivity,
        "evaluate_with_overrides",
        lambda path, overrides: {"equity_irr": None, "project_irr": 0.01},
    )
    rows = wacc_sensitivity.ke_band_npv("unused.yaml", [0.12])
    assert rows[0]["equity_irr"] is None
