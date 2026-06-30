"""Integration check: the report's cash-flow waterfall (RPT-2) ties to the engine (#481).

The waterfall must not become a second source of truth. This runs the canonical lender case
end-to-end — which carries a 10% CFADS risk haircut AND a real balloon, the exact configuration
that exposed the original reconstruction's divergence — and asserts that:

* the waterfall's total CFADS equals the headline ``total_cfads_usd`` KPI (haircut included), and
* its per-year scheduled debt service equals the engine's ``debt_service_total`` (the DSCR
  denominator the Debt Structure & DSCR Profile section renders),

so the report never presents two contradictory coverage numbers (CCCDIR — one source of truth).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.three_statement import build_cashflow_waterfall

_LENDERCASE = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def test_waterfall_ties_to_headline_cfads_and_dscr_debt_service() -> None:
    res = run_v14_pipeline(config=str(_LENDERCASE))
    rows = res["annual_rows"]
    kpis = res["kpis"]
    wf = build_cashflow_waterfall(rows)

    # CFADS ties to the headline KPI — one source of truth, the lender risk haircut included.
    assert wf.total_cfads == pytest.approx(kpis["total_cfads_usd"], rel=1e-9)

    # Scheduled debt service is the engine's debt_service_total (the DSCR denominator), per row.
    assert all(
        math.isclose(
            w.scheduled_debt_service,
            float(r.get("debt_service_total", 0.0)),
            rel_tol=1e-9,
            abs_tol=1e-6,
        )
        for w, r in zip(wf.rows, rows)
    )

    # The lender case carries a real balloon, shown SEPARATELY (not folded into scheduled service).
    assert wf.total_balloon_sweep > 0.0

    # Cascade identity: cash to equity = CFADS − scheduled debt service − balloon sweep.
    assert wf.total_cash_to_equity == pytest.approx(
        wf.total_cfads - wf.total_scheduled_debt_service - wf.total_balloon_sweep,
        rel=1e-9,
    )
