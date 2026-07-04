"""A2b/#33: the distribution-lockup DSCR resolves to the scenario's AUTHORED covenant.

The equity waterfall traps distributions whenever a year's DSCR < the lockup
threshold. That threshold previously fell back to an orphan library default of
1.25 (matching no stated covenant). It now reconciles to the scenario's
``constraints.min_dscr_covenant`` (1.30 for the canonical lender case), with the
hardcoded 1.25 retained only when neither an explicit equity threshold nor a
covenant is declared.
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


def test_falls_back_to_125_when_neither_declared() -> None:
    """With no equity threshold and no covenant, the 1.25 library default stands."""
    cfg: dict = {"project": {"project_life_years": 20}}
    assert _build_distribution_config(cfg).min_dscr_threshold == pytest.approx(1.25)


def test_reconcile_is_kpi_neutral_on_the_sculpted_canonical() -> None:
    """The 1.30 lockup engages ONLY on the one honest sub-covenant year (#737).

    The dual-DSCR sculpt lands every per-period floor year AT the covenant
    (1.2999999999999998 in FP), which the FP-tolerant lockup treats as meeting the
    covenant. With the #737 credit-support fees, operating year 1's per-YEAR covenant
    value — its own service PLUS the orphaned half-year bridge service, out of
    fee-netted CFADS — reads ~1.288, a genuine (small) breach beyond _DSCR_LOCKUP_EPS,
    so exactly ONE year locks. Pre-fee it cleared at ~1.306 on slack and zero years
    locked. A phantom (misalignment) lockup would trap many years, not one.
    """
    from analytics.evaluation_v14 import evaluate_with_overrides

    kpis = evaluate_with_overrides(str(LENDER), overrides={})
    assert kpis["equity_covenant_locked_years"] == 1


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
