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
from tests._canon import LENDER_EQUITY_IRR as _CANON_EQ_IRR
from tests._canon import LENDER_MIN_DSCR as _CANON_MIN_DSCR
from tests._canon import LENDER_MIN_DSCR_PERIOD as _CANON_MIN_DSCR_PERIOD
from tests._canon import LENDER_TOTAL_CFADS_USD as _CANON_CFADS

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Canonical KPIs after the round-5 #5 interest-tax-shield re-baseline (the levered equity
# path now bears LEVERED tax), the 5.9% FX-drift re-baseline (fx.annual_depr 0.03 ->
# 0.0589, data-derived BIS 2005-2026 LKR depreciation), and the 2.0% pre-construction P50
# over-prediction haircut on the DutchBay wind resource (net AEP 473.8 -> 464.3 GWh, CF
# 0.339 -> 0.332), which lowers eqIRR and CFADS further:
# eqIRR ... -> -0.019289278896401862 (PR-A tax/levy) -> -0.048585780806075674 (PR-B: LKR debt
# rate 8% -> UIP-implied 13.39%; the costlier LKR tranche hits levered equity hard).
# CFADS was unchanged by PR B (the debt rate was downstream of it), but #737's credit-support
# fees ARE in the unlevered CFADS (senior fee at the EBITDA line, sized off the debt structure):
# _CANON_CFADS 202.33M -> 191.22M. #738 (2026-07-05) re-baselines again: import levies ON
# (PRUDENT posture — duties on the imported capex share capitalized, 18% opex VAT) net of the
# revenue-SSCL statutory-exemption reversal: eqIRR -0.049921 -> -0.058413, CFADS 191.22M ->
# 191.11M (the SSCL removal nearly offsets the opex VAT at the CFADS line; the capex-side
# levies bite through depreciation/tax, debt sizing and the equity base instead).
# The canonical values (_CANON_EQ_IRR, _CANON_CFADS) are imported above from
# tests/_canon.py (#955, single source of truth).


def test_default_off_is_byte_identical() -> None:
    """Default (wht_gross_up: false everywhere) leaves the canonical economics unchanged."""
    k = evaluate_with_overrides(LENDER, overrides={})
    assert k["equity_irr"] == pytest.approx(_CANON_EQ_IRR, abs=1e-9)
    assert k["total_cfads_usd"] == pytest.approx(_CANON_CFADS, rel=1e-9)
    # #790: headline = fold-corrected covenant minimum; per-period floor 1.30.
    # (#738: the levy-inclusive year-1 fold eases 1.2884 -> 1.2857.)
    assert k["min_dscr"] == pytest.approx(_CANON_MIN_DSCR, abs=1e-6)
    assert k["min_dscr_period"] == pytest.approx(_CANON_MIN_DSCR_PERIOD, abs=1e-6)


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
        overrides={
            "tax.wht_on_interest_to_nonresidents": 0.10,
            "tax.wht_gross_up": False,
        },
    )
    on = evaluate_with_overrides(
        LENDER,
        overrides={
            "tax.wht_on_interest_to_nonresidents": 0.10,
            "tax.wht_gross_up": True,
        },
    )
    assert on["equity_irr"] < off["equity_irr"] - 1e-4  # materially lower
    # DSCR and project-level CFADS are upstream of the equity WHT deduction.
    assert on["min_dscr"] == pytest.approx(off["min_dscr"], abs=1e-9)
    assert on["total_cfads_usd"] == pytest.approx(off["total_cfads_usd"], rel=1e-9)


def test_per_year_wht_equals_interest_times_rate_aligned() -> None:
    """Proves the period alignment: each year's charged WHT equals that year's scheduled
    interest * rate (including the bridge-period interest folded into operating year 1).
    """
    rate = 0.10
    full = evaluate_with_overrides(
        LENDER,
        overrides={
            "tax.wht_on_interest_to_nonresidents": rate,
            "tax.wht_gross_up": True,
        },
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
    path applied the shield; the rest of the engine did not.

    #1397 made the flag live on the SIZING path too, and this test is the clearest place
    to see what that did, so it now records both halves.

    The off case is the control. It is byte-identical to the pre-#1397 engine -- the pin
    below is the literal that was already here, unchanged -- because with no interest to
    deduct the fixed point settles on the first pass, which is the old sizing pass.

    The on case now differs from the off case everywhere, where before it differed only
    in equity IRR:

    * coverage rises (LLCR 1.2810 -> 1.2875), which is the whole point: the facility is
      sized and covenanted on CFADS the SPV can actually pay from;
    * the headline min_dscr falls 1.30 -> 1.2196, the year-1 fold the extra gearing
      steps push under the target (#1353, issuecomment-6433557550);
    * project IRR and total CFADS fall slightly, through the larger facility's senior
      credit-support fee rather than through tax -- the project pass still computes its
      own tax with no interest deducted;
    * and the shield's benefit to EQUITY is now much smaller, +44bps rather than +272bps,
      because most of it is absorbed by the extra leverage it finances. That is a real
      consequence of the change and is asserted, not hidden.

    #1396 part B widened the equity gap again, to +537bps, without touching the sizing
    half. The committed case now refinances its balloon, and the off case's smaller
    facility leaves a LARGER balloon (USD 31.55m vs 28.63m) whose refinance service
    equity must fund (tranche coverage 0.25x vs 0.28x). So the band's upper bound moves
    from 0.02 to 0.08; the lower bound still catches the flag going decorative.
    """
    on = evaluate_with_overrides(LENDER, overrides={})  # default True
    off = evaluate_with_overrides(
        LENDER, overrides={"tax.interest_deductibility": False}
    )
    assert on["equity_irr"] == pytest.approx(_CANON_EQ_IRR, abs=1e-9)
    # #1504 (2026-10-31): both cases now charge the post-maturity senior fee on the
    # refinanced balance actually outstanding; off moves -35.90% -> -32.30% and the
    # gap stays inside the band (+586bps).
    assert off["equity_irr"] == pytest.approx(-0.32300741810736144, abs=1e-9)
    # Still material to equity. Both bounds matter: the lower one catches the flag going
    # decorative again, the upper one catches the refinance gap between the two cases
    # growing beyond what the balloon difference explains.
    assert 0.001 < on["equity_irr"] - off["equity_irr"] < 0.08
    # The shield now reaches the sizing path as well, in these directions.
    assert on["llcr"] > off["llcr"]
    assert on["min_dscr"] < off["min_dscr"]
    assert on["project_irr"] < off["project_irr"]
    assert on["total_cfads_usd"] < off["total_cfads_usd"]
