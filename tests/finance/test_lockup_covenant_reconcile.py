"""A2b/#33 & #1429 E01: the distribution-lockup DSCR resolves to the scenario's AUTHORED covenant.

The equity waterfall traps distributions whenever a year's DSCR < the lockup
threshold. That threshold previously fell back to an orphan library default of
1.25 (matching no stated covenant). It reconciles to the scenario's
``constraints.min_dscr_covenant`` (1.30 for the canonical lender case), and
since #1429 E01 has no code default when neither an explicit equity threshold nor
a covenant is declared.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from finance.equity_distribution_v14_hydra import _build_distribution_config

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_canonical_lockup_reconciles_to_the_covenant() -> None:
    """The lender lockup threshold equals constraints.min_dscr_covenant (1.30), not 1.25."""
    cfg = yaml.safe_load(LENDER.read_text(encoding="utf-8"))
    covenant = float(cfg["constraints"]["min_dscr_covenant"])
    dc = _build_distribution_config(cfg)
    assert dc.min_dscr_threshold == pytest.approx(covenant)
    assert dc.min_dscr_threshold == pytest.approx(1.30)
    assert dc.min_dscr_threshold != pytest.approx(1.25)  # the retired orphan default


def test_explicit_equity_threshold_takes_precedence() -> None:
    """An explicit equity_distribution.min_dscr_threshold wins over the covenant."""
    cfg = {
        "constraints": {"min_dscr_covenant": 1.30},
        "equity_distribution": {"min_dscr_threshold": 1.10},
    }
    assert _build_distribution_config(cfg).min_dscr_threshold == pytest.approx(1.10)


def test_raises_when_neither_declared_no_code_default() -> None:
    """With no equity threshold and no covenant, no 1.25 code default applies (#1429 E01)."""
    cfg: dict = {"project": {"project_life_years": 20}}
    with pytest.raises(ValueError, match="no code default"):
        _build_distribution_config(cfg)


def test_reconcile_locks_no_scheduled_year_on_the_sculpted_canonical() -> None:
    """The 1.30 sculpt locks exactly one canonical year, and only through the year-1 fold.

    This asserted zero until #1397. Sizing on levered-tax CFADS buys nine 0.0025 gearing
    steps, and the extra service takes the conservative annual fold for operating year 1
    to 1.2196, under the 1.30 threshold the reconcile tests. Only that folded figure is
    under the target: every other operating year reads 1.30, and every individual period
    reads at or above it. The fold combines the stub/bridge period (1.3056) with the
    first full operating period (2.4392) and the orphaned bridge service drags the
    combination below both parts -- the artifact tracked at #1353,
    issuecomment-6433557550. Owner informed 2026-10-27.

    The point of the guard is unchanged: the reconcile must not lock years it has no
    reason to. The companion test below proves it still engages on a genuine breach.

    #1779: the refinanced balloon tranche's three years now lock on its own coverage
    (below the threshold in each), so the case locks four years in all, and the
    scheduled test still only the year-1 fold.

    #1845 (owner decision 2026-11-22) sizes the lender case to the annual covenant, so
    the year-1 fold reads 1.30 and the scheduled test locks no year: back to zero, as
    before #1397. Only the refinanced tranche's three years lock.
    """
    from analytics.evaluation_v14 import evaluate_with_overrides

    full = evaluate_with_overrides(str(LENDER), overrides={}, return_full_result=True)
    kpis = full["kpis"]
    # #1779: the lock-up also tests the refinanced balloon tranche, whose coverage is below
    # the threshold in all three of its years (15 to 17). The scheduled test still locks
    # only the year-1 fold, so the phase-bug guard reads the scheduled locks alone.
    rows = full["equity_distribution"]["annual_distributions"]
    locked = [int(r["year"]) for r in rows if r["covenant_locked"]]
    tranche = [int(r["year"]) for r in rows if r["refinance_tranche_locked"]]
    assert locked == [15, 16, 17]  # #1845: no scheduled year (was [1, 15, 16, 17])
    assert tranche == [15, 16, 17]
    assert kpis["equity_covenant_locked_years"] == len(locked)
    assert kpis["min_dscr_period"] == pytest.approx(1.30, abs=1e-6)


def test_reconcile_genuinely_engages_on_a_real_sub_covenant_breach() -> None:
    """The reconcile is NOT an inert lever: a genuine stress breach DOES lock.

    edge_extreme_stress drives some operating years MATERIALLY below the 1.30 covenant
    (beyond _DSCR_LOCKUP_EPS), so the reconciled lockup correctly traps those distributions
    — proving the 1.25->1.30 change moves the output exactly where a lender lockup should.
    """
    from analytics.evaluation_v14 import evaluate_with_overrides

    stress = str(REPO_ROOT / "scenarios" / "edge_extreme_stress.yaml")
    kpis = evaluate_with_overrides(stress, overrides={})
    assert kpis["equity_covenant_locked_years"] > 0
