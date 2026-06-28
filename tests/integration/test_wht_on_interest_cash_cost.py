"""WHT-on-interest gross-up as a real equity cash cost (Wave-1 A2 wiring).

tax.wht_gross_up was decorative config: parsed but never used, and the computed
wht_on_interest never reduced any cash line. It is now wired at the debt/equity layer:
the scheduled per-period interest (debt_result['interest_total']) is surfaced on each
operating row as interest_usd (same alignment as debt_service), and when wht_gross_up is
True the equity waterfall charges interest * tax.wht_on_interest_to_nonresidents against
cash to equity — senior to equity but OUT of the DSCR (covenant unaffected).

Every shipped scenario sets wht_gross_up: false, so the canonical economics are
byte-identical; the cost only bites once a scenario grosses up.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Canonical KPIs after the round-5 #5 interest-tax-shield re-baseline (the levered equity
# path now bears LEVERED tax), the 5.9% FX-drift re-baseline (fx.annual_depr 0.03 ->
# 0.0589, data-derived BIS 2005-2026 LKR depreciation), and the 2.0% pre-construction P50
# over-prediction haircut on the DutchBay wind resource (net AEP 473.8 -> 464.3 GWh, CF
# 0.339 -> 0.332), which lowers eqIRR and CFADS further:
# eqIRR ... -> -0.019289278896401862 (PR-A tax/levy) -> -0.048585780806075674 (PR-B: LKR debt
# rate 8% -> UIP-implied 13.39%; the costlier LKR tranche hits levered equity hard).
# CFADS is the UNLEVERED project series — unchanged by PR B (the debt rate is downstream of it),
# so _CANON_CFADS stays 202.33M (it rose from 199.10M only via PR-A's fabricated-levy removal).
_CANON_EQ_IRR = -0.048585780806075674
_CANON_CFADS = 202332872.38974944


def test_default_off_is_byte_identical() -> None:
    """Default (wht_gross_up: false everywhere) leaves the canonical economics unchanged."""
    k = evaluate_with_overrides(LENDER, overrides={})
    assert k["equity_irr"] == pytest.approx(_CANON_EQ_IRR, abs=1e-9)
    assert k["total_cfads_usd"] == pytest.approx(_CANON_CFADS, rel=1e-9)
    assert k["min_dscr"] == pytest.approx(1.30, abs=1e-6)


def test_gross_up_off_with_a_rate_is_still_a_no_op() -> None:
    """A non-zero non-resident rate but wht_gross_up: false -> lender bears it, no SPV cost."""
    k = evaluate_with_overrides(
        LENDER,
        overrides={
            "tax.wht_on_interest_to_nonresidents": 0.10,
            "tax.wht_gross_up": False,
        },
    )
    assert k["equity_irr"] == pytest.approx(_CANON_EQ_IRR, abs=1e-9)
    assert k["total_cfads_usd"] == pytest.approx(_CANON_CFADS, rel=1e-9)


def test_gross_up_charges_a_real_cash_cost_without_touching_dscr() -> None:
    """gross_up + a rate lowers equity IRR (real cash leakage) but NOT the DSCR/CFADS
    (the WHT is senior to equity yet out of scheduled debt service)."""
    off = evaluate_with_overrides(
        LENDER,
        overrides={"tax.wht_on_interest_to_nonresidents": 0.10, "tax.wht_gross_up": False},
    )
    on = evaluate_with_overrides(
        LENDER,
        overrides={"tax.wht_on_interest_to_nonresidents": 0.10, "tax.wht_gross_up": True},
    )
    assert on["equity_irr"] < off["equity_irr"] - 1e-4  # materially lower
    # DSCR and project-level CFADS are upstream of the equity WHT deduction.
    assert on["min_dscr"] == pytest.approx(off["min_dscr"], abs=1e-9)
    assert on["total_cfads_usd"] == pytest.approx(off["total_cfads_usd"], rel=1e-9)


def test_per_year_wht_equals_interest_times_rate_aligned() -> None:
    """Proves the period alignment: each year's charged WHT equals that year's scheduled
    interest * rate (including the bridge-period interest folded into operating year 1)."""
    rate = 0.10
    full = evaluate_with_overrides(
        LENDER,
        overrides={"tax.wht_on_interest_to_nonresidents": rate, "tax.wht_gross_up": True},
        return_full_result=True,
    )
    rows = full["annual_rows"]
    dist = full["equity_distribution"]["annual_distributions"]
    assert len(rows) == len(dist)
    # year 1 must carry real (bridge-inclusive) interest, not zero
    assert rows[0]["interest_usd"] > 0.0
    for row, d in zip(rows, dist):
        expected = float(row["interest_usd"]) * rate
        assert d["wht_on_interest_usd"] == pytest.approx(expected, abs=1.0)


def test_interest_deductibility_flag_is_live_on_the_equity_path() -> None:
    """Round-5 #5: tax.interest_deductibility was decorative (toggling it changed nothing
    because the live pipeline computed CFADS with interest_expense=0). The levered equity
    path now applies the interest tax shield, so True (default) yields the canonical
    -0.048586 and False recovers the unlevered -0.08473157279360188 (after the PR-B UIP LKR
    debt rate 13.39%; the off case still keeps the IDC depreciation shield + dividend WHT,
    only dropping the interest deduction — a bigger shield now that LKR interest is higher).
    The project IRR / DSCR / CFADS are upstream of the equity waterfall and are byte-identical
    either way — the shield is confined to the equity path (project captures it via after-tax kd)."""
    on = evaluate_with_overrides(LENDER, overrides={})  # default True
    off = evaluate_with_overrides(LENDER, overrides={"tax.interest_deductibility": False})
    assert on["equity_irr"] == pytest.approx(_CANON_EQ_IRR, abs=1e-9)
    assert off["equity_irr"] == pytest.approx(-0.08473157279360188, abs=1e-9)
    assert on["equity_irr"] > off["equity_irr"] + 0.02  # the shield is material (+408bps)
    # The shield is confined to the equity path: project KPIs identical both ways.
    assert on["project_irr"] == pytest.approx(off["project_irr"], abs=1e-12)
    assert on["min_dscr"] == pytest.approx(off["min_dscr"], abs=1e-12)
    assert on["total_cfads_usd"] == pytest.approx(off["total_cfads_usd"], rel=1e-12)
