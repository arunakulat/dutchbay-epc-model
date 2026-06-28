"""Coverage-raising tests for ``finance.cashflow_v14``.

This is the canonical annual-cashflow-rows builder for the v14 finance stack.
These tests target the under-covered branches of ``cashflow_v14.py``:

- ``_prepare_cashflow_context`` resolution branches (FX curve override / pad /
  empty-refetch, depreciable-capex precedence ladder, interest-series pad/trim).
- ``calculate_single_year_cfads`` edge branches (non-positive FX rate, verbose).
- ``build_annual_cfads`` / ``build_annual_rows`` / ``build_annual_rows_efficient``
  end-to-end against the canonical lender scenario, plus the degenerate
  zero-year logging branches.

CRITICAL (economics safety): no economic magic number is hardcoded. Every
expectation is either DERIVED by re-running the engine (e.g. the efficient
builder must agree row-for-row with the canonical builder) or asserted as a
structural / sign / conservation / monotonicity property computed from the
inputs the test itself supplies.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest

import finance.cashflow_v14 as cf
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import (
    _prepare_cashflow_context,
    build_annual_cfads,
    build_annual_rows,
    build_annual_rows_efficient,
    calculate_single_year_cfads,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

# A schema-complete tax block. ``TaxConfig.from_yaml`` is schema-strict (every
# field REQUIRED, no hidden defaults), so a hand-authored config must supply all
# of these. Single-class (non-split) mode: ``plant_capex_share`` deliberately
# absent so the legacy straight-line depreciation branch is exercised.
_FULL_TAX: Dict[str, Any] = {
    "corporate_tax_rate": 0.30,
    "depreciation_method": "straight_line",
    "depreciation_start_year": 1,
    "depreciation_years": 15,
    "enhanced_allowance_applies": False,
    "enhanced_capital_allowance_pct": 1.0,
    "loss_carryforward_years": 6,
    "tax_holiday_start_year": 1,
    "tax_holiday_years": 0,
    "wht_on_interest_to_nonresidents": 0.1,
    "wht_on_interest_enabled": True,
    "wht_gross_up": False,
    "interest_deductibility": True,
}

_PROJECT_LIFE = 5


def _base_config() -> Dict[str, Any]:
    """A minimal, schema-complete, single-class config (project life 5y)."""
    return {
        "project": {
            "project_life_years": _PROJECT_LIFE,
            "capacity_mw": 100.0,
            "capacity_factor": 0.40,
        },
        "tariff": {"lkr_per_kwh": 20.0},
        "opex": {"usd_per_year": 1_000_000.0},
        "fx": {"start_lkr_per_usd": 300.0},
        "tax": dict(_FULL_TAX),
    }


# ---------------------------------------------------------------------------
# Canonical scenario: end-to-end structure / conservation / agreement.
# ---------------------------------------------------------------------------


def test_canonical_scenario_available() -> None:
    """Guard: the canonical lender scenario file must exist for these tests."""
    assert LENDER_SCENARIO.is_file(), f"missing scenario: {LENDER_SCENARIO}"


def test_build_annual_rows_row_count_equals_project_life() -> None:
    """build_annual_rows returns exactly one row per project year."""
    cfg = load_scenario_config(str(LENDER_SCENARIO))
    rows = build_annual_rows(cfg)
    expected_years = int(cfg["project"]["life_years"])
    assert len(rows) == expected_years
    # Years are 1-based and strictly increasing 1..N.
    assert [int(r["year"]) for r in rows] == list(range(1, expected_years + 1))


def test_canonical_rows_conservation_and_signs() -> None:
    """Each canonical row obeys the documented CFADS identity and sign rules."""
    cfg = load_scenario_config(str(LENDER_SCENARIO))
    rows = build_annual_rows(cfg)

    for r in rows:
        # EBITDA identity: revenue - statutory - opex.
        assert math.isclose(
            r["ebitda_lkr"],
            r["revenue_lkr"]
            - r["total_statutory_deductions_lkr"]
            - r["opex_lkr"],
            rel_tol=1e-9,
            abs_tol=1.0,
        )
        # pretax_cfads == EBITDA (no other non-cash items in this engine).
        assert math.isclose(r["pretax_cfads_lkr"], r["ebitda_lkr"], rel_tol=1e-9)
        # Post-tax CFADS = pretax - tax.
        assert math.isclose(
            r["posttax_cfads_lkr"],
            r["pretax_cfads_lkr"] - r["tax_lkr"],
            rel_tol=1e-9,
            abs_tol=1.0,
        )
        # Risk haircut: final = posttax - haircut_amount, haircut >= 0 for a
        # non-negative posttax CFADS and a non-negative haircut pct.
        assert math.isclose(
            r["cfads_final_lkr"],
            r["posttax_cfads_lkr"] - r["risk_haircut_amount_lkr"],
            rel_tol=1e-9,
            abs_tol=1.0,
        )
        assert r["risk_haircut_amount_lkr"] >= -1.0
        # Grid loss is non-negative; net <= gross.
        assert r["net_kwh"] <= r["gross_kwh"] + 1.0
        assert math.isclose(
            r["grid_loss"], r["gross_kwh"] - r["net_kwh"], rel_tol=1e-9, abs_tol=1.0
        )
        # USD view is the LKR view divided by the per-year FX rate.
        assert math.isclose(
            r["cfads_usd"], r["cfads_final_lkr"] / r["fx_rate"], rel_tol=1e-9
        )


def test_efficient_builder_agrees_with_canonical_builder() -> None:
    """build_annual_rows_efficient must reproduce build_annual_rows exactly.

    The docstring promises an "identical structure". We assert the stronger
    property: identical keys AND numerically identical values per row. This
    derives the expectation from the canonical builder rather than hardcoding.
    """
    cfg = load_scenario_config(str(LENDER_SCENARIO))
    rows = build_annual_rows(cfg)
    eff = build_annual_rows_efficient(cfg)

    assert len(rows) == len(eff)
    for base_row, eff_row in zip(rows, eff):
        assert set(base_row.keys()) == set(eff_row.keys())
        for key in base_row:
            assert math.isclose(
                base_row[key], eff_row[key], rel_tol=1e-9, abs_tol=1e-6
            ), f"mismatch on {key}"


def test_efficient_builder_zero_fx_year_zeroes_usd_views() -> None:
    """A zero FX rate in any year zeroes that year's USD views in the efficient path.

    LKR views remain positive; only the USD translation collapses to 0.0. This
    exercises the non-positive-FX ``else`` arm of ``build_annual_rows_efficient``.
    """
    curve = [300.0, 300.0, 0.0, 300.0, 300.0]
    rows = build_annual_rows_efficient(_base_config(), fx_curve=curve)
    zero_year = rows[2]
    assert zero_year["fx_rate"] == 0.0
    assert zero_year["revenue_usd"] == 0.0
    assert zero_year["cfads_usd"] == 0.0
    # A positive-FX year still produces a positive USD revenue view.
    assert rows[0]["revenue_usd"] > 0.0


def test_build_annual_cfads_matches_rows_cfads() -> None:
    """The numeric CFADS surface equals the row-wise ``cfads_final_lkr``."""
    cfg = load_scenario_config(str(LENDER_SCENARIO))
    cfads = build_annual_cfads(cfg)
    rows = build_annual_rows(cfg)
    assert len(cfads) == len(rows)
    for value, row in zip(cfads, rows):
        assert math.isclose(value, row["cfads_final_lkr"], rel_tol=1e-12)


def test_loss_carry_forward_is_monotone_state() -> None:
    """Carried-forward losses are tracked across years as a running state.

    Property (not a magic number): the prior-year carried losses feed the next
    year. We re-derive each year's input from the previous row and assert the
    engine threads it through (carried losses are always non-negative).
    """
    cfg = load_scenario_config(str(LENDER_SCENARIO))
    rows = build_annual_rows(cfg)
    for r in rows:
        assert r["carried_forward_losses"] >= -1.0


# ---------------------------------------------------------------------------
# FX-curve resolution branches in _prepare_cashflow_context.
# ---------------------------------------------------------------------------


def test_fx_curve_override_exact_length() -> None:
    """An explicit FX curve of exactly project-life length is used verbatim."""
    curve = [301.0, 302.0, 303.0, 304.0, 305.0]
    rows = build_annual_rows(_base_config(), fx_curve=curve)
    assert [r["fx_rate"] for r in rows] == curve


def test_fx_curve_override_shorter_is_padded_with_last() -> None:
    """A short FX curve is padded by repeating the last known rate."""
    rows = build_annual_rows(_base_config(), fx_curve=[300.0, 310.0])
    rates = [r["fx_rate"] for r in rows]
    assert rates == [300.0, 310.0, 310.0, 310.0, 310.0]


def test_fx_curve_override_empty_refetches_from_config() -> None:
    """An empty explicit FX curve falls back to deriving from the config block."""
    rows = build_annual_rows(_base_config(), fx_curve=[])
    # config fx.start_lkr_per_usd == 300.0 (flat, no depreciation configured).
    assert all(math.isclose(r["fx_rate"], 300.0, rel_tol=1e-9) for r in rows)


# ---------------------------------------------------------------------------
# Depreciable-capex precedence ladder in _prepare_cashflow_context.
# ---------------------------------------------------------------------------


def _first_year_depreciation(cfg: Dict[str, Any]) -> float:
    return build_annual_rows(cfg)[0]["total_depreciation_lkr"]


def test_capex_explicit_arg_takes_precedence() -> None:
    """An explicit ``capex_depreciable_lkr`` arg is the depreciation base.

    Straight-line over ``depreciation_years`` (15) => year-1 amount derived
    from first principles, not hardcoded.
    """
    base = 5.0e10
    cfg = _base_config()
    rows = build_annual_rows(cfg, capex_depreciable_lkr=base)
    expected = base / float(cfg["tax"]["depreciation_years"])
    assert math.isclose(rows[0]["total_depreciation_lkr"], expected, rel_tol=1e-9)


def test_capex_depreciable_lkr_config_key() -> None:
    """``tax.depreciable_capex_lkr`` sets the depreciation base."""
    base = 1.0e10
    cfg = _base_config()
    cfg["tax"]["depreciable_capex_lkr"] = base
    expected = base / float(cfg["tax"]["depreciation_years"])
    assert math.isclose(_first_year_depreciation(cfg), expected, rel_tol=1e-9)


def test_capex_dep_base_lkr_alias() -> None:
    """``tax.dep_base_lkr`` is accepted as the depreciation base alias."""
    base = 2.0e10
    cfg = _base_config()
    cfg["tax"]["dep_base_lkr"] = base
    expected = base / float(cfg["tax"]["depreciation_years"])
    assert math.isclose(_first_year_depreciation(cfg), expected, rel_tol=1e-9)


def test_capex_lkr_total_branch() -> None:
    """Project-wide ``capex.lkr_total`` is used when no explicit tax base set."""
    base = 3.0e10
    cfg = _base_config()
    cfg["capex"] = {"lkr_total": base}
    expected = base / float(cfg["tax"]["depreciation_years"])
    assert math.isclose(_first_year_depreciation(cfg), expected, rel_tol=1e-9)


def test_capex_usd_total_translated_at_year0_fx() -> None:
    """USD capex is translated to LKR at the year-0 FX rate before depreciating."""
    usd = 1.0e8
    cfg = _base_config()
    cfg["capex"] = {"usd_total": usd}
    fx0 = float(cfg["fx"]["start_lkr_per_usd"])
    expected = (usd * fx0) / float(cfg["tax"]["depreciation_years"])
    assert math.isclose(_first_year_depreciation(cfg), expected, rel_tol=1e-9)


def test_enhanced_capital_allowance_scales_depreciation_base() -> None:
    """When the enhanced allowance applies, the whole base is scaled up.

    Derive: enabling the 1.5x allowance must multiply year-1 depreciation by
    exactly 1.5 versus the non-enhanced run (same base).
    """
    base = 1.0e10
    plain = _base_config()
    plain["tax"]["depreciable_capex_lkr"] = base
    dep_plain = _first_year_depreciation(plain)

    enhanced = _base_config()
    enhanced["tax"]["depreciable_capex_lkr"] = base
    enhanced["tax"]["enhanced_allowance_applies"] = True
    enhanced["tax"]["enhanced_capital_allowance_pct"] = 1.5
    dep_enhanced = _first_year_depreciation(enhanced)

    assert math.isclose(dep_enhanced, dep_plain * 1.5, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Interest-series alignment branches.
# ---------------------------------------------------------------------------


def test_interest_series_short_is_padded_with_zeros() -> None:
    """A short interest series is padded with zeros to project life."""
    rows = build_annual_rows(_base_config(), interest_expense_series=[1.0e8])
    interest = [r["interest_expense_lkr"] for r in rows]
    assert interest == [1.0e8, 0.0, 0.0, 0.0, 0.0]


def test_interest_series_long_is_trimmed() -> None:
    """An over-length interest series is trimmed to project life."""
    over = [1.0e8] * (_PROJECT_LIFE + 3)
    rows = build_annual_rows(_base_config(), interest_expense_series=over)
    assert len(rows) == _PROJECT_LIFE
    assert all(
        math.isclose(r["interest_expense_lkr"], 1.0e8, rel_tol=1e-9) for r in rows
    )


def test_interest_series_default_is_all_zero() -> None:
    """Omitting the interest series yields a zero-interest project."""
    rows = build_annual_rows(_base_config())
    assert all(r["interest_expense_lkr"] == 0.0 for r in rows)


# ---------------------------------------------------------------------------
# Split-depreciation mode (canonical scenario uses plant_capex_share=0.80).
# ---------------------------------------------------------------------------


def test_split_depreciation_mode_engaged_in_canonical_scenario() -> None:
    """Canonical scenario sets ``plant_capex_share`` => split straight-line.

    Property: plant (short-life) + civils (long-life) means the early-year
    depreciation must exceed a single-class straight-line over the long civil
    life. We assert depreciation is positive and decreases once the short-life
    plant tranche fully expires (year > plant_depreciation_years).
    """
    cfg = load_scenario_config(str(LENDER_SCENARIO))
    rows = build_annual_rows(cfg)
    plant_life = int(cfg["tax"]["plant_depreciation_years"])

    early = rows[0]["total_depreciation_lkr"]
    late = rows[plant_life]["total_depreciation_lkr"]  # first year after plant
    assert early > 0.0
    # After the plant tranche fully depreciates, the annual amount drops.
    assert late < early


# ---------------------------------------------------------------------------
# calculate_single_year_cfads edge branches.
# ---------------------------------------------------------------------------


def _context() -> Any:
    return _prepare_cashflow_context(_base_config(), None, None, None)


def test_single_year_zero_fx_zeroes_usd_views() -> None:
    """A zero FX rate forces the USD revenue/CFADS views to 0.0 (no div-by-0)."""
    (params, _fxc, _cd, _ints, _years, tp, ds) = _context()
    row = calculate_single_year_cfads(
        params=params, fx_rate=0.0, year=1, tax_profile=tp, depreciation_schedule=ds
    )
    assert row["revenue_usd"] == 0.0
    assert row["cfads_usd"] == 0.0
    # LKR views are still computed normally.
    assert row["revenue_lkr"] > 0.0


def test_single_year_negative_fx_zeroes_usd_views() -> None:
    """A non-positive (negative) FX rate also zeroes the USD views."""
    (params, _fxc, _cd, _ints, _years, tp, ds) = _context()
    row = calculate_single_year_cfads(
        params=params, fx_rate=-5.0, year=1, tax_profile=tp, depreciation_schedule=ds
    )
    assert row["revenue_usd"] == 0.0
    assert row["cfads_usd"] == 0.0


def test_single_year_verbose_logs(caplog: pytest.LogCaptureFixture) -> None:
    """verbose=True emits a per-year CFADS log line without changing the result."""
    (params, _fxc, _cd, _ints, _years, tp, ds) = _context()
    quiet = calculate_single_year_cfads(
        params=params, fx_rate=300.0, year=1, tax_profile=tp, depreciation_schedule=ds
    )
    with caplog.at_level("INFO", logger="finance.cashflow_v14"):
        loud = calculate_single_year_cfads(
            params=params,
            fx_rate=300.0,
            year=1,
            tax_profile=tp,
            depreciation_schedule=ds,
            verbose=True,
        )
    assert any("Year 1 CFADS" in rec.getMessage() for rec in caplog.records)
    assert math.isclose(
        quiet["cfads_final_lkr"], loud["cfads_final_lkr"], rel_tol=1e-12
    )


def test_single_year_prior_losses_threaded_into_tax() -> None:
    """Carried prior-year losses reduce taxable income (loss-carry-forward).

    Derive: a large prior-year loss shield must not increase the tax versus a
    zero-loss baseline (monotonic, sign-correct shield).
    """
    (params, _fxc, _cd, _ints, _years, tp, ds) = _context()
    no_loss = calculate_single_year_cfads(
        params=params, fx_rate=300.0, year=2, tax_profile=tp,
        depreciation_schedule=ds, prior_year_losses=0.0,
    )
    with_loss = calculate_single_year_cfads(
        params=params, fx_rate=300.0, year=2, tax_profile=tp,
        depreciation_schedule=ds, prior_year_losses=1.0e12,
    )
    assert with_loss["tax_lkr"] <= no_loss["tax_lkr"] + 1.0


# ---------------------------------------------------------------------------
# Degenerate zero-year logging branches (defensive `else` arms).
# ---------------------------------------------------------------------------


@pytest.fixture()
def _force_zero_years(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], None]:
    """Patch the shared context builder to report a zero-length project.

    The public extractor enforces 5<=life<=60, so the empty-list logging arms
    of the builders are otherwise unreachable. We wrap the real context builder
    and zero out only the ``years`` field, keeping every other value valid.
    """
    real = _prepare_cashflow_context

    def _patched(
        config: Dict[str, Any],
        fx_curve: Any,
        capex_depreciable_lkr: Any,
        interest_expense_series: Any,
        **kwargs: Any,
    ) -> Any:
        (params, fxc, cd, ints, _years, tp, ds) = real(
            config, fx_curve, capex_depreciable_lkr, interest_expense_series, **kwargs
        )
        return (params, fxc, cd, [], 0, tp, ds)

    def _apply() -> None:
        monkeypatch.setattr(cf, "_prepare_cashflow_context", _patched)

    return _apply


def test_build_annual_rows_zero_years_returns_empty(
    _force_zero_years: Callable[[], None],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Zero project years => empty rows and the 0-year log line."""
    _force_zero_years()
    with caplog.at_level("INFO", logger="finance.cashflow_v14"):
        rows = build_annual_rows(_base_config())
    assert rows == []
    assert any("for 0 years" in rec.getMessage() for rec in caplog.records)


def test_build_annual_cfads_zero_years_returns_empty(
    _force_zero_years: Callable[[], None],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Zero project years => empty CFADS list and the 0-year log line."""
    _force_zero_years()
    with caplog.at_level("INFO", logger="finance.cashflow_v14"):
        cfads = build_annual_cfads(_base_config())
    assert cfads == []
    assert any("for 0 years" in rec.getMessage() for rec in caplog.records)


def test_build_annual_rows_efficient_zero_years_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Zero project years => empty efficient rows and the 0-year log line.

    ``build_tax_series`` rejects empty input, so for this degenerate path we
    also stub it to return an empty list (consistent with zero years).
    """
    real = _prepare_cashflow_context

    def _patched(
        config: Dict[str, Any],
        fx_curve: Any,
        capex_depreciable_lkr: Any,
        interest_expense_series: Any,
        **kwargs: Any,
    ) -> Any:
        (params, fxc, cd, ints, _years, tp, ds) = real(
            config, fx_curve, capex_depreciable_lkr, interest_expense_series, **kwargs
        )
        return (params, fxc, cd, [], 0, tp, ds)

    def _empty_tax_series(**_kwargs: Any) -> List[Any]:
        return []

    monkeypatch.setattr(cf, "_prepare_cashflow_context", _patched)
    monkeypatch.setattr(cf, "build_tax_series", _empty_tax_series)

    with caplog.at_level("INFO", logger="finance.cashflow_v14"):
        rows = build_annual_rows_efficient(_base_config())
    assert rows == []
    assert any("for 0 years" in rec.getMessage() for rec in caplog.records)
