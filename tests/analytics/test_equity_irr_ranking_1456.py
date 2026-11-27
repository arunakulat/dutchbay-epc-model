#!/usr/bin/env python
"""Equity IRR ranking caveat and the equity-NPV optimiser default (#1456).

Owner decision, 2026-11-01: the optimisers default to equity NPV, and equity IRR stays
reported with a caveat when the equity cashflows change sign more than once.

The fast tests pin the sign-change counter, the defaults of every optimiser entry point
the issue lists, the warning on an explicit ``equity_irr`` objective, and that a default
run ranks on NPV where IRR and NPV disagree. One test reads the committed lender case,
whose refinanced tail calls equity back in operating years 17-19, and checks that its
equity summary carries the caveat while the IRR itself is still reported.
"""

from __future__ import annotations

import inspect
import logging
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pytest
import yaml

import analytics.capital_structure_optimizer_v14 as opt_mod
from analytics.capital_structure_optimizer_v14 import (
    DEFAULT_OBJECTIVE_KEY,
    optimize_capex_contingency,
    optimize_debt_mix,
)
from finance.equity_v14 import (
    count_cashflow_sign_changes,
    equity_irr_ranks_reliably,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")
CLI_YAML = REPO_ROOT / "conf" / "cli_capital_structure_optimize.yaml"
CLI_MODULE = REPO_ROOT / "analytics" / "cli" / "cli_capital_structure_optimize_hydra.py"

_MIX_LKR_PATH = "Financing_Terms.mix.lkr_max"
_MIX_DFI_PATH = "Financing_Terms.mix.dfi_max"
_CAPEX_TOTAL_PATH = "capex.usd_total"

# The equity cashflows (USD m) the issue records for the refinance canon: invest,
# distribute, inject in years 17-19, distribute again. Three sign changes.
_ISSUE_1456_EQUITY_CF = [
    -104.49,
    0,
    0,
    0,
    0.8,
    3.56,
    3.31,
    3.07,
    2.85,
    2.64,
    2.45,
    2.26,
    2.09,
    1.93,
    2.1,
    1.48,
    1.37,
    -5.63,
    -8.09,
    -8.47,
    2.65,
    2.36,
    2.09,
]


# ---------------------------------------------------------------------------
# Sign-change counter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cashflows", "expected"),
    [
        ([], 0),
        ([-100.0], 0),
        ([-100.0, -5.0], 0),
        ([-100.0, 10.0, 10.0, 120.0], 1),
        ([-100.0, 0.0, 0.0, 50.0, 60.0], 1),  # construction zeros are ignored
        ([-100.0, 50.0, -20.0, 80.0], 3),
        ([-100.0, 150.0, -40.0], 2),
        ([-100.0, 50.0, 0.0, 60.0], 1),  # a zero year between positives is skipped
        ([100.0, -50.0], 1),
        ([-100.0, float("nan"), 50.0], 1),  # non-finite entries are ignored
        ([-100.0, math.inf, 50.0], 1),
        (_ISSUE_1456_EQUITY_CF, 3),
    ],
)
def test_count_cashflow_sign_changes(cashflows: list, expected: int) -> None:
    assert count_cashflow_sign_changes(cashflows) == expected


@pytest.mark.parametrize(
    ("cashflows", "expected"),
    [
        ([-100.0, 30.0, 30.0, 60.0], True),
        ([-100.0, 50.0, 0.0, 60.0], True),  # the zero year does not add a change
        ([], False),  # no IRR exists (#1522 D-1)
        ([-100.0], False),
        ([-100.0, -5.0, 0.0], False),
        ([-100.0, 150.0, -40.0], False),  # exactly two changes is the boundary
        (_ISSUE_1456_EQUITY_CF, False),
    ],
)
def test_ranks_reliably_only_with_exactly_one_sign_change(
    cashflows: list, expected: bool
) -> None:
    assert equity_irr_ranks_reliably(cashflows) is expected


@pytest.mark.parametrize(
    ("operating_cf", "changes", "flag", "warns"),
    [
        ([1.5e8], 1, True, False),
        ([5.0e7, 0.0, 6.0e7], 1, True, False),
        (
            [0.0, 0.0],
            0,
            False,
            False,
        ),  # no IRR: not rankable, and no multi-root warning
        ([1.5e8, -4.0e7], 2, False, True),
    ],
)
def test_pipeline_flag_is_the_helper_predicate(
    caplog: pytest.LogCaptureFixture,
    operating_cf: list,
    changes: int,
    flag: bool,
    warns: bool,
) -> None:
    """The equity summary uses the helper, including at 0 and at exactly 2 changes."""
    from finance.equity_distribution_v14_hydra import (
        calculate_equity_distribution_from_pipeline,
    )

    with caplog.at_level(
        logging.WARNING, logger="finance.equity_distribution_v14_hydra"
    ):
        result = calculate_equity_distribution_from_pipeline(
            config={
                "capex": {"usd_total": 2.0e8},
                "constraints": {"min_dscr_covenant": 1.25},
            },
            annual_rows=[
                {"year": i + 1, "cf_pre_debt": v} for i, v in enumerate(operating_cf)
            ],
            debt_result={"debt_total": 1.2e8},
        )
    summary = result["equity_summary"]
    cashflows = result["equity_cashflows_usd"]
    assert summary["equity_cashflow_sign_changes"] == changes
    assert summary["equity_irr_ranks_reliably"] is flag
    assert equity_irr_ranks_reliably(cashflows) is flag
    multi_root = [r for r in caplog.records if "change sign" in r.getMessage()]
    assert bool(multi_root) is warns


# ---------------------------------------------------------------------------
# Every listed consumer defaults to equity NPV (issuecomment-6475341924)
# ---------------------------------------------------------------------------


def test_default_objective_key_is_equity_npv() -> None:
    assert DEFAULT_OBJECTIVE_KEY == "equity_npv"


@pytest.mark.parametrize("fn", [optimize_debt_mix, optimize_capex_contingency])
def test_optimiser_signature_defaults_to_npv_max(fn: Any) -> None:
    params = inspect.signature(fn).parameters
    assert params["objective_key"].default == "equity_npv"
    # A less negative equity NPV is better, so NPV is maximised.
    assert params["direction"].default == "max"


def test_cli_yaml_defaults_to_npv_max() -> None:
    cfg = yaml.safe_load(CLI_YAML.read_text(encoding="utf-8"))
    assert cfg["objective_key"] == "equity_npv"
    assert cfg["direction"] == "max"


def test_cli_fallback_uses_the_shared_default() -> None:
    source = CLI_MODULE.read_text(encoding="utf-8")
    assert 'cfg.get("objective_key", DEFAULT_OBJECTIVE_KEY)' in source
    assert 'cfg.get("objective_key", "equity_irr")' not in source


# ---------------------------------------------------------------------------
# A default run ranks on NPV where IRR and NPV disagree
# ---------------------------------------------------------------------------


def _mix_fake(
    config_path: str,
    *,
    overrides: Optional[Mapping[str, Any]] = None,
    **_kwargs: Any,
) -> Dict[str, Any]:
    """IRR prefers dear LKR debt, NPV prefers cheap DFI debt: the #1456 shape."""
    ov = overrides or {}
    lkr = float(ov[_MIX_LKR_PATH])
    dfi = float(ov[_MIX_DFI_PATH])
    return {"equity_irr": lkr - dfi, "equity_npv": dfi - lkr}


def _contingency_fake(
    config_path: str,
    *,
    overrides: Optional[Mapping[str, Any]] = None,
    **_kwargs: Any,
) -> Dict[str, Any]:
    total = float((overrides or {})[_CAPEX_TOTAL_PATH])
    frac = total / 100.0 - 1.0
    # NPV falls with contingency; IRR (perversely) peaks at the top of the range.
    return {"equity_irr": frac, "equity_npv": -frac}


def test_default_debt_mix_ranks_on_npv(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", _mix_fake)
    with caplog.at_level(logging.WARNING, logger=opt_mod.__name__):
        res = optimize_debt_mix(
            LENDER_CONFIG, lkr_bounds=(0.0, 0.6), dfi_bounds=(0.0, 0.4), n_steps=4
        )
    assert res.objective_key == "equity_npv"
    assert res.direction == "max"
    assert res.best is not None and res.best.mix is not None
    assert res.best.mix.lkr_share == pytest.approx(0.0)
    assert res.best.mix.dfi_share == pytest.approx(0.4)
    assert not [r for r in caplog.records if "#1456" in r.getMessage()]


def test_default_contingency_ranks_on_npv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", _contingency_fake)
    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=100.0,
        contingency_bounds=(0.0, 0.15),
        n_steps=4,
    )
    assert res.objective_key == "equity_npv"
    assert res.best is not None
    assert res.best.value[0] == pytest.approx(0.0)


@pytest.mark.parametrize("mode", ["debt_mix", "capex_contingency"])
def test_explicit_equity_irr_is_honoured_with_a_warning(
    mode: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=opt_mod.__name__):
        if mode == "debt_mix":
            monkeypatch.setattr(opt_mod, "evaluate_with_overrides", _mix_fake)
            res = optimize_debt_mix(
                LENDER_CONFIG,
                objective_key="equity_irr",
                lkr_bounds=(0.0, 0.6),
                dfi_bounds=(0.0, 0.4),
                n_steps=4,
            )
            assert res.best is not None and res.best.mix is not None
            # The caller asked for IRR, so IRR's (perverse) choice is returned.
            assert res.best.mix.lkr_share == pytest.approx(0.6)
        else:
            monkeypatch.setattr(opt_mod, "evaluate_with_overrides", _contingency_fake)
            res = optimize_capex_contingency(
                LENDER_CONFIG,
                base_capex_usd=100.0,
                objective_key="equity_irr",
                contingency_bounds=(0.0, 0.15),
                n_steps=4,
            )
            assert res.best is not None
            assert res.best.value[0] == pytest.approx(0.15)
    assert res.objective_key == "equity_irr"
    warnings_1456 = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "#1456" in r.getMessage()
    ]
    assert len(warnings_1456) == 1
    assert mode in warnings_1456[0].getMessage()


# ---------------------------------------------------------------------------
# The caveat on the committed lender case (refinance canon)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_lender_case_equity_summary_carries_the_caveat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The refinanced tail calls equity back, so the IRR is caveated, not hidden.

    #1845 sizes the committed lender case to the annual covenant: its balloon falls to
    USD 11.05M, the cash trapped in year 15 meets the refinance shortfall, and no year
    calls the sponsor, so its equity cash flow changes sign once and the IRR ranks
    reliably. This runs the lender case on the per-period basis, whose larger refinanced
    balloon still calls equity back, to keep the caveat path covered.
    """
    from analytics.evaluation_v14 import evaluate_with_overrides

    with caplog.at_level(
        logging.WARNING, logger="finance.equity_distribution_v14_hydra"
    ):
        result = evaluate_with_overrides(
            LENDER_CONFIG,
            overrides={"Financing_Terms.sizing_dscr_basis": "period"},
            return_full_result=True,
        )
    equity = result["equity_distribution"]
    summary = equity["equity_summary"]
    cashflows = equity["equity_cashflows_usd"]

    assert summary["equity_cashflow_sign_changes"] == count_cashflow_sign_changes(
        cashflows
    )
    assert summary["equity_cashflow_sign_changes"] > 1
    assert summary["equity_irr_ranks_reliably"] is False
    # Option "suppress" was not chosen: the IRR is still computed and reported.
    assert summary["equity_irr"] is not None
    assert result["kpis"]["equity_irr"] == summary["equity_irr"]
    assert any(
        "change sign" in r.getMessage() and "#1456" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.slow
def test_lender_case_default_debt_mix_picks_cheap_debt() -> None:
    """With no objective given, the debt-mix optimiser no longer picks the dearest mix.

    Before #1456 the default (equity IRR, max) chose 60% LKR / 0% DFI on this grid. The
    oracle is the tranche pricing in the committed case (DFI is the cheapest tranche),
    as in the pre-existing ``test_real_debt_mix_favours_cheap_dfi``.
    """
    res = optimize_debt_mix(
        LENDER_CONFIG, lkr_bounds=(0.0, 0.6), dfi_bounds=(0.0, 0.4), n_steps=4
    )
    assert res.objective_key == "equity_npv"
    assert res.feasible and res.best is not None and res.best.mix is not None
    assert res.best.mix.dfi_share == pytest.approx(0.4, abs=1e-9)
    assert res.best.mix.lkr_share == pytest.approx(0.0, abs=1e-9)
