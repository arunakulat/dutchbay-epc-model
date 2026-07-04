"""Coverage tests for ``finance.debt_v14`` edge branches.

These exercise the helper/validation/alias paths the main suite skips:
CAPEX extractor alias chains and toy-fallback gates, the QRA-contingency
breakdown path, financing-term schema adaptation, the annuity interest-only
rows, fx/series cleaning fall-throughs, the gearing-solver and amortize-resize
non-dict branches, the dual-DSCR sizing failure path, and refinance/decorative
warnings.

All assertions are derived structurally or from first principles (no hardcoded
economic magic numbers). The module is the CANONICAL project-finance debt
engine, so every test asserts a documented behaviour: a raise, a sign/bound, a
conservation identity, or a monotonic relationship.

Author: Test engineering, June 2026
"""

from __future__ import annotations

import logging

import pytest

import finance.debt_v14 as debt_v14
from finance.debt_v14 import (
    _allow_toy_capex_fallback,
    _annuity_schedule,
    _balloon_resolution_stream,
    _clean_public_dscr_series,
    _extract_capex_usd,
    _extract_financing_terms,
    _get,
    _npv,
    _resize_for_amortization,
    _resolve_downside_ratio,
    _solve_gearing_for_dscr,
    _truthy_flag,
    _warn_if_decorative_tranches,
    apply_debt_layer,
    plan_debt,
    size_debt_with_dual_dscr,
)


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────
def test_get_delegates_to_get_nested() -> None:
    d = {"a": {"b": 7}}
    assert _get(d, ["a", "b"]) == 7
    assert _get(d, ["a", "missing"], default=99) == 99


def test_truthy_flag_string_aliases() -> None:
    assert _truthy_flag("yes") is True
    assert _truthy_flag("ON") is True
    assert _truthy_flag("no") is False
    assert _truthy_flag(True) is True
    assert _truthy_flag(0) is False


def test_npv_empty_and_degenerate_rate() -> None:
    assert _npv([], 0.08) == 0.0
    # rate <= -1.0 is a documented guard returning 0.0 (avoids divide blow-up).
    assert _npv([1.0, 2.0], -1.0) == 0.0
    assert _npv([1.0, 2.0], -2.0) == 0.0


def test_clean_public_dscr_series_drops_nonfinite_and_nonnumeric() -> None:
    cleaned = _clean_public_dscr_series(
        [None, "not-a-number", float("inf"), float("nan"), 0.0, -1.0, 1.30, 2.0]
    )
    # Only None / non-numeric / non-finite (inf, nan) are dropped. A FINITE value <= 0.0
    # is RETAINED — a 0.0 (CFADS=0 vs live debt service) or a negative DSCR is a real
    # total-coverage breach that must surface in the lender-facing min (Wave-1 fix).
    assert cleaned == [0.0, -1.0, 1.30, 2.0]


# ─────────────────────────────────────────────────────────────────────────────
# Toy-fallback gate (allow_toy_fallback at top, testing.*, debt.*)
# ─────────────────────────────────────────────────────────────────────────────
def test_allow_toy_fallback_top_level() -> None:
    assert _allow_toy_capex_fallback({"allow_toy_fallback": True}) is True


def test_allow_toy_fallback_via_testing_section() -> None:
    assert _allow_toy_capex_fallback({"testing": {"allow_toy_fallback": "yes"}}) is True


def test_allow_toy_fallback_via_debt_section() -> None:
    assert _allow_toy_capex_fallback({"debt": {"allow_toy_fallback": True}}) is True


def test_allow_toy_fallback_default_false() -> None:
    assert _allow_toy_capex_fallback({"testing": {"other": 1}, "debt": {}}) is False


def test_extract_capex_toy_fallback_value(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        capex = _extract_capex_usd({"allow_toy_fallback": True})
    assert capex == 100.0
    assert any("toy fallback" in r.message.lower() for r in caplog.records)


def test_extract_capex_no_key_raises() -> None:
    with pytest.raises(ValueError, match="no recognized CAPEX key"):
        _extract_capex_usd({"unrelated": {"foo": 1}})


# ─────────────────────────────────────────────────────────────────────────────
# CAPEX extractor — breakdown / QRA / alias paths
# ─────────────────────────────────────────────────────────────────────────────
def test_capex_derive_breakdown_not_mapping_raises() -> None:
    params = {"capex": {"derive_from_breakdown": True, "breakdown": [1, 2, 3]}}
    with pytest.raises(ValueError, match="breakdown is missing or"):
        _extract_capex_usd(params)


def test_capex_breakdown_nonpositive_sum_raises() -> None:
    params = {
        "capex": {"derive_from_breakdown": True, "breakdown": {"a_usd": 0, "b_usd": 0}}
    }
    with pytest.raises(ValueError, match="sums to <= 0"):
        _extract_capex_usd(params)


def test_capex_breakdown_bottom_up_sum() -> None:
    params = {
        "capex": {
            "derive_from_breakdown": True,
            "breakdown": {"turbines_usd": 60.0, "bop_usd": 40.0, "label": "ignored"},
        }
    }
    # Derived bottom-up == sum of numeric line items only.
    assert _extract_capex_usd(params) == pytest.approx(100.0)


def test_capex_breakdown_qra_recomputes_contingency() -> None:
    base = {"turbines_usd": 90.0, "bop_usd": 10.0, "contingency_usd": 5.0}
    fixed_params = {"capex": {"derive_from_breakdown": True, "breakdown": dict(base)}}
    fixed_total = _extract_capex_usd(fixed_params)
    assert fixed_total == pytest.approx(105.0)

    qra_params = {
        "capex": {
            "derive_from_breakdown": True,
            "breakdown": dict(base),
            "contingency": {
                "method": "qra",
                "base_cost_uncertainty_pct": 10.0,
                "confidence_level": 0.80,
            },
        }
    }
    qra_total = _extract_capex_usd(qra_params)
    # QRA recomputes contingency on the base cost (line total minus the fixed
    # contingency line = 100), so the result is base_cost + a POSITIVE QRA add-on.
    assert qra_total > 100.0
    # And it differs from the fixed 105 because the contingency was re-derived.
    assert qra_total != pytest.approx(fixed_total)


def test_capex_breakdown_qra_nonpositive_derived_raises() -> None:
    # A large negative non-contingency item keeps the line total positive (passing
    # the >0 guard) but drives the QRA base cost — and thus the derived CAPEX —
    # below zero, which the engine must reject rather than size debt off.
    params = {
        "capex": {
            "derive_from_breakdown": True,
            "breakdown": {
                "good_usd": 1000.0,
                "credit_usd": -1090.0,
                "contingency_usd": 100.0,
            },
            "contingency": {
                "method": "qra",
                "base_cost_uncertainty_pct": 10.0,
                "confidence_level": 0.80,
            },
        }
    }
    with pytest.raises(ValueError, match="QRA-derived CAPEX is <= 0"):
        _extract_capex_usd(params)


def test_capex_section_string_value_is_parsed() -> None:
    # A string CAPEX under capex.usd_total goes through the float() except-path.
    assert _extract_capex_usd({"capex": {"usd_total": "250.0"}}) == pytest.approx(250.0)


def test_capex_section_bad_string_falls_through_to_raise() -> None:
    # Non-numeric string in every recognized key -> all aliases continue -> raise.
    params = {"capex": {"usd_total": "not-a-number"}}
    with pytest.raises(ValueError, match="no recognized CAPEX key"):
        _extract_capex_usd(params)


def test_capex_top_level_alias_int() -> None:
    assert _extract_capex_usd({"capex_total_usd": 175}) == pytest.approx(175.0)


def test_capex_top_level_alias_string() -> None:
    assert _extract_capex_usd({"total_capex_usd": "300"}) == pytest.approx(300.0)


def test_capex_top_level_alias_bad_string_then_toy() -> None:
    # Bad string top-level alias hits the float() except-continue, then the toy
    # fallback resolves it to 100.0 (both the except-path AND the fallback).
    params = {"capex_usd_total": "junk", "allow_toy_fallback": True}
    assert _extract_capex_usd(params) == pytest.approx(100.0)


# ─────────────────────────────────────────────────────────────────────────────
# Financing-terms schema adaptation
# ─────────────────────────────────────────────────────────────────────────────
def test_financing_terms_leverage_pct_alias() -> None:
    # debt_pct absent -> falls back to leverage_pct; >1 is treated as a percent.
    terms = _extract_financing_terms({"Financing_Terms": {"leverage_pct": 65.0}})
    assert terms["debt_ratio"] == pytest.approx(0.65)


def test_financing_terms_financing_section() -> None:
    # No Financing_Terms -> the lowercase ``financing`` section is returned as-is.
    out = _extract_financing_terms({"financing": {"debt_ratio": 0.55, "tag": "x"}})
    assert out["debt_ratio"] == 0.55
    assert out["tag"] == "x"


def test_financing_terms_debt_section_leverage_over_one() -> None:
    # ``debt`` section with leverage_pct > 1 -> normalized to a fraction.
    out = _extract_financing_terms(
        {"debt": {"leverage_pct": 60.0, "interest_rate_pct": 8.0}}
    )
    assert out["debt_ratio"] == pytest.approx(0.60)
    assert out["rates"]["usd_nominal"] == pytest.approx(0.08)


def test_financing_terms_no_section_returns_params() -> None:
    # No recognized section at all -> the params dict itself is returned.
    params = {"some_other_key": 1}
    assert _extract_financing_terms(params) is params


# ─────────────────────────────────────────────────────────────────────────────
# #585 fail-loud: placeholder-substitution WARNs (A1/#91) on BOTH schema paths
# ─────────────────────────────────────────────────────────────────────────────
def test_financing_terms_placeholder_substitution_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing draw/capex schedules on the Financing_Terms path WARN, not silent."""
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        terms = _extract_financing_terms({"Financing_Terms": {"debt_ratio": 0.6}})
    # Values are the documented placeholders (unchanged — byte-identity).
    assert terms["debt_drawdown_pct"] == [0.5, 0.5]
    assert terms["construction_schedule"] == [40.0, 60.0]
    msgs = [r.message for r in caplog.records]
    assert any("debt_drawdown_pct" in m and "placeholder" in m for m in msgs)
    assert any("construction_schedule" in m and "placeholder" in m for m in msgs)


def test_compact_debt_schema_placeholder_substitution_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The compact ``debt:`` schema emits the SAME placeholder WARNs (#585).

    Previously this path substituted [0.5, 0.5] / [40, 60] silently while the
    Financing_Terms path warned — the two schemas must be equally loud.
    """
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        terms = _extract_financing_terms({"debt": {"debt_ratio": 0.6}})
    assert terms["debt_drawdown_pct"] == [0.5, 0.5]
    assert terms["construction_schedule"] == [40.0, 60.0]
    msgs = [r.message for r in caplog.records]
    assert any("debt.debt_drawdown_pct" in m and "placeholder" in m for m in msgs)
    assert any("debt.construction_schedule" in m and "placeholder" in m for m in msgs)


def test_compact_debt_schema_explicit_schedules_do_not_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicitly supplied schedules pass through untouched, with no WARN."""
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        terms = _extract_financing_terms(
            {
                "debt": {
                    "debt_ratio": 0.6,
                    "construction_schedule": [30.0, 70.0],
                    "debt_drawdown_pct": [0.4, 0.6],
                }
            }
        )
    assert terms["construction_schedule"] == [30.0, 70.0]
    assert terms["debt_drawdown_pct"] == [0.4, 0.6]
    assert not [r for r in caplog.records if "placeholder" in r.message]


# ─────────────────────────────────────────────────────────────────────────────
# Annuity schedule with interest-only years (lines 407-408)
# ─────────────────────────────────────────────────────────────────────────────
def test_annuity_schedule_interest_only_rows() -> None:
    tr = debt_v14.Tranche("USD", rate=0.10, principal=1000.0, years_io=2)
    rows = _annuity_schedule(tr, amort_years=3)
    # First years_io rows are pure interest: principal == 0, service == interest.
    io_rows = rows[:2]
    for interest, principal, service in io_rows:
        assert principal == 0.0
        assert service == pytest.approx(interest)
        assert interest == pytest.approx(1000.0 * 0.10)
    # Total rows = io + amort.
    assert len(rows) == 5


# ─────────────────────────────────────────────────────────────────────────────
# apply_debt_layer — zero-debt avg-rate branch (line 586) + fx parsing (614-615)
# ─────────────────────────────────────────────────────────────────────────────
def _rows(cfads: float, n: int = 5, **extra: object) -> list[dict[str, object]]:
    return [{"year": i + 1, "cfads_usd": cfads, **extra} for i in range(n)]


def test_apply_debt_layer_zero_debt_ratio_avg_rate_zero() -> None:
    # debt_ratio == 0 -> debt_principal_total == 0 -> avg_debt_rate falls to 0.0.
    params = {
        "Financing_Terms": {
            "debt_ratio": 0.0,
            "tenor_years": 5,
            "construction_periods": 1,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
        "capex": {"usd_total": 100.0},
    }
    core = apply_debt_layer(params=params, annual_rows=_rows(10.0))
    assert core["avg_debt_rate"] == 0.0
    assert core["debt_total"] == 0.0
    # No debt -> no LLCR/PLCR coverage.
    assert core["llcr"] == 0.0
    assert core["plcr"] == 0.0


def test_apply_debt_layer_fx_bad_value_skipped() -> None:
    rows = [
        {"year": 1, "cfads_usd": 10.0, "fx_rate": 300.0},
        {"year": 2, "cfads_usd": 10.0, "fx_rate": "not-a-number"},
        {"year": 3, "cfads_usd": 10.0, "fx_rate": 320.0},
        {"year": 4, "cfads_usd": 10.0, "fx_rate": None},
        {"year": 5, "cfads_usd": 10.0},
    ]
    params = {
        "Financing_Terms": {
            "debt_ratio": 0.6,
            "tenor_years": 5,
            "construction_periods": 1,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
        "capex": {"usd_total": 100.0},
    }
    core = apply_debt_layer(params=params, annual_rows=rows)
    # The bad string and the None are both skipped; only 300 and 320 count.
    assert core["fx_min"] == pytest.approx(300.0)
    assert core["fx_max"] == pytest.approx(320.0)
    assert core["fx_avg"] == pytest.approx(310.0)


# ─────────────────────────────────────────────────────────────────────────────
# #585 fail-loud: _pmt degenerate-nper guard
# ─────────────────────────────────────────────────────────────────────────────
def test_pmt_nonzero_rate_nonpositive_nper_fails_loud() -> None:
    """rate != 0 with nper <= 0 raises a clear ValueError, not ZeroDivisionError."""
    with pytest.raises(ValueError, match="nper"):
        debt_v14._pmt(0.08, 0, 100.0)
    with pytest.raises(ValueError, match="nper"):
        debt_v14._pmt(0.08, -1, 100.0)


def test_pmt_zero_rate_degenerate_contract_preserved() -> None:
    """The historical rate == 0 contract is untouched (byte-identity guard)."""
    # nper <= 0 at zero rate keeps its documented 0.0 return.
    assert debt_v14._pmt(0.0, 0, 100.0) == 0.0
    # Zero-rate annuity is straight-line: pv / nper.
    assert debt_v14._pmt(0.0, 4, 100.0) == pytest.approx(25.0)


# ─────────────────────────────────────────────────────────────────────────────
# #585 fail-loud: amortization_style whitelist ('auto' is an explicit alias)
# ─────────────────────────────────────────────────────────────────────────────
def _amort_params(style: str) -> dict[str, object]:
    return {
        "Financing_Terms": {
            "debt_ratio": 0.6,
            "tenor_years": 5,
            "construction_periods": 1,
            "construction_schedule": [40.0, 60.0],
            "debt_drawdown_pct": [0.5, 0.5],
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
            "amortization_style": style,
            "target_dscr": 1.30,
        },
        "capex": {"usd_total": 100.0},
    }


def test_amortization_style_auto_is_whitelisted_sculpted_alias(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """'auto' (used by committed scenarios) maps to sculpted with NO warning."""
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        core_auto = apply_debt_layer(
            params=_amort_params("auto"), annual_rows=_rows(20.0)
        )
    assert not any(
        "amortization_style" in r.message.lower() for r in caplog.records
    ), "whitelisted 'auto' must not warn"
    core_sculpted = apply_debt_layer(
        params=_amort_params("sculpted"), annual_rows=_rows(20.0)
    )
    # Identical schedule: 'auto' IS sculpted, not a fall-through accident.
    assert core_auto["debt_service_total"] == core_sculpted["debt_service_total"]


def test_amortization_style_unknown_warns_and_falls_back_sculpted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unknown style WARNs (like balloon_treatment) and keeps the sculpted result."""
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        core_bogus = apply_debt_layer(
            params=_amort_params("bullet-ish"), annual_rows=_rows(20.0)
        )
    assert any(
        "Unknown amortization_style" in r.message for r in caplog.records
    ), "non-whitelisted style must fail loud"
    core_sculpted = apply_debt_layer(
        params=_amort_params("sculpted"), annual_rows=_rows(20.0)
    )
    # Behaviour preserved: the fallback is exactly the old silent fall-through.
    assert core_bogus["debt_service_total"] == core_sculpted["debt_service_total"]


@pytest.mark.parametrize("bad_style", [5, True, 1.5, ["sculpted"]])
def test_amortization_style_non_string_rejected_loud(bad_style: object) -> None:
    """A present-but-non-string style (YAML `5`/`true`) raises, no fallback (#683).

    The #585 cluster turned the pre-existing AttributeError crash into a
    warn-fallback — the one spot it made the engine MORE tolerant. A non-string
    is a config error, not a stylistic typo: reject it loudly. Unknown STRING
    styles keep the warn-fallback pinned by the test above.
    """
    params = _amort_params("sculpted")
    financing = params["Financing_Terms"]
    assert isinstance(financing, dict)
    financing["amortization_style"] = bad_style
    with pytest.raises(ValueError, match=r"amortization_style .* must be a string"):
        apply_debt_layer(params=params, annual_rows=_rows(20.0))


# ─────────────────────────────────────────────────────────────────────────────
# _solve_gearing_for_dscr — non-dict Financing_Terms branch + fallthrough
# ─────────────────────────────────────────────────────────────────────────────
def _flat_config(debt_ratio: float = 0.7) -> dict[str, object]:
    # No Financing_Terms / financing / debt section -> _extract_financing_terms
    # returns the params dict itself, so the engine reads the TOP-LEVEL
    # debt_ratio. The gearing solver / amortize-resizer therefore exercise their
    # else-branches (top-level debt_ratio assignment) AND actually take effect.
    return {
        "capex": {"usd_total": 100.0},
        "debt_ratio": debt_ratio,
        "tenor_years": 8,
        "construction_periods": 1,
        "amortization_style": "sculpted",
        "target_dscr": 1.30,
        "mix": {"usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08},
    }


def test_solve_gearing_top_level_debt_ratio_branch() -> None:
    # Strong CFADS: even at max_ratio the schedule clears target -> returns max_ratio.
    rows = _rows(40.0, n=8)
    solved = _solve_gearing_for_dscr(
        _flat_config(), rows, target_dscr=1.30, max_ratio=0.7
    )
    assert solved == pytest.approx(0.7)


def test_solve_gearing_fallthrough_when_target_unmet(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Very weak CFADS: no gearing on the scan meets the target, so the loop exhausts.
    # Fix: it now fails LOUD and returns the conservative FLOOR (least debt = step), not
    # the old near-MAXIMUM leverage (max_ratio - step) that silently over-levered an
    # unbankable structure.
    rows = _rows(0.001, n=8)
    with caplog.at_level("WARNING"):
        solved = _solve_gearing_for_dscr(
            _flat_config(), rows, target_dscr=5.0, max_ratio=0.05, step=0.0025
        )
    assert solved == pytest.approx(0.0025, abs=1e-9)  # conservative floor, NOT 0.0475
    assert solved > 0.0
    assert any("did not converge" in r.message for r in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# _resolve_downside_ratio — flat-factor fallback (line 718)
# ─────────────────────────────────────────────────────────────────────────────
def test_resolve_downside_ratio_flat_factor_fallback() -> None:
    # p90 source selected but expected_results has no P50/P90 -> flat factor.
    config: dict[str, object] = {}
    fin = {"downside_aep_source": "p90", "dscr_p99_downside_factor": 0.75}
    ratio, source = _resolve_downside_ratio(config, fin)
    assert source == "flat_factor"
    assert ratio == pytest.approx(0.75)


def test_resolve_downside_ratio_explicit_override() -> None:
    ratio, source = _resolve_downside_ratio({}, {"downside_cfads_factor": 0.9})
    assert source == "explicit_factor"
    assert ratio == pytest.approx(0.9)


def test_resolve_downside_ratio_p90_aep() -> None:
    config = {"expected_results": {"net_aep_p50_gwh": 100.0, "net_aep_p90_gwh": 90.0}}
    ratio, source = _resolve_downside_ratio(config, {"downside_aep_source": "p90"})
    assert source == "p90_aep"
    assert ratio == pytest.approx(0.90)


# ─────────────────────────────────────────────────────────────────────────────
# _maybe_autosolve_dscr — dual-DSCR sizing failure path (lines 801-802)
# ─────────────────────────────────────────────────────────────────────────────
def test_autosolve_dual_dscr_detail_none_on_value_error() -> None:
    # debt_ratio == 0 makes the inner size_debt_with_dual_dscr cap arg invalid
    # (debt_ratio_max must be in (0,1]); the except swallows it -> detail is None.
    config = {
        "capex": {"usd_total": 100.0},
        "Financing_Terms": {
            "debt_sizing": "dual_dscr",
            "debt_ratio": 0.0,
            "target_dscr": 1.30,
            "tenor_years": 5,
            "construction_periods": 1,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
    }
    result = plan_debt(annual_rows=_rows(10.0), config=config)
    assert result["dual_dscr"] is None


def test_autosolve_dual_dscr_detail_present_when_active() -> None:
    config = {
        "capex": {"usd_total": 100.0},
        "Financing_Terms": {
            "debt_sizing": "dual_dscr",
            "debt_ratio": 0.7,
            "target_dscr": 1.30,
            "tenor_years": 8,
            "construction_periods": 1,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
    }
    result = plan_debt(annual_rows=_rows(20.0, n=8), config=config)
    detail = result["dual_dscr"]
    assert detail is not None
    assert detail["sizing_mode"] == "dual_dscr"
    assert detail["binding_production_case"] == "P50"
    assert detail["solved_gearing"] <= 0.7


# ─────────────────────────────────────────────────────────────────────────────
# _balloon_resolution_stream — refinance with zero rate (line 878)
# ─────────────────────────────────────────────────────────────────────────────
def test_refinance_zero_rate_amortizes_balloon_evenly() -> None:
    # avg_rate + premium == 0 -> straight-line refi annuity = balloon / periods.
    cfads_ext = [0.0, 0.0, 5.0, 5.0, 5.0, 5.0]
    debt_service = [0.0, 10.0, 10.0, 0.0, 0.0, 0.0]
    resolution, residual = _balloon_resolution_stream(
        treatment="refinance",
        balloon=300.0,
        cfads_ext=cfads_ext,
        debt_service_total=debt_service,
        construction_periods=1,
        timeline_periods=len(cfads_ext),
        avg_rate=0.0,
        refi_tenor_years=3,
        refi_rate_premium=0.0,
    )
    # Maturity is just after the last nonzero service (index 2). 3 equal payments.
    assert residual == 0.0
    paid = [x for x in resolution if x > 0.0]
    assert len(paid) == 3
    for amt in paid:
        assert amt == pytest.approx(100.0)
    assert sum(resolution) == pytest.approx(300.0)


def test_refinance_positive_rate_costs_more_than_principal() -> None:
    # With a positive rate the refi annuity stream exceeds the bare balloon.
    cfads_ext = [0.0, 0.0, 5.0, 5.0, 5.0, 5.0]
    debt_service = [0.0, 10.0, 10.0, 0.0, 0.0, 0.0]
    resolution, residual = _balloon_resolution_stream(
        treatment="refinance",
        balloon=300.0,
        cfads_ext=cfads_ext,
        debt_service_total=debt_service,
        construction_periods=1,
        timeline_periods=len(cfads_ext),
        avg_rate=0.08,
        refi_tenor_years=3,
        refi_rate_premium=0.02,
    )
    assert residual == 0.0
    # Interest makes total repayment strictly greater than the principal.
    assert sum(resolution) > 300.0


# ─────────────────────────────────────────────────────────────────────────────
# _resize_for_amortization — no-balloon no-op (line 908)
# ─────────────────────────────────────────────────────────────────────────────
def test_resize_for_amortization_noop_when_no_balloon() -> None:
    config = {"capex": {"usd_total": 100.0}, "Financing_Terms": {"debt_ratio": 0.5}}
    core = {"balloon_remaining": 0.0}
    out_cfg, out_core = _resize_for_amortization(config, [], core)
    # No balloon -> returned unchanged (identity).
    assert out_cfg is config
    assert out_core is core


def test_resize_for_amortization_reduces_balloon_nondict_terms() -> None:
    # No Financing_Terms mapping forces the _at_ratio else-branch (top-level
    # debt_ratio) AND _solve... else-branch. Heavy gearing -> a real balloon to
    # bisect away. The result has balloon ~0 and lower gearing than the input.
    rows = _rows(8.0, n=8)
    config = _flat_config(debt_ratio=0.7)
    core_high = apply_debt_layer(params=config, annual_rows=rows)
    assert core_high["balloon_remaining"] > debt_v14._BALLOON_TOL
    out_cfg, out_core = _resize_for_amortization(config, rows, core_high)
    assert out_core["balloon_remaining"] <= debt_v14._BALLOON_TOL
    # The resized top-level debt_ratio is below the original gearing.
    assert out_cfg["debt_ratio"] < 0.7


# ─────────────────────────────────────────────────────────────────────────────
# _warn_if_decorative_tranches — already-warned early return (line 942)
# ─────────────────────────────────────────────────────────────────────────────
def test_warn_decorative_tranches_warns_once_then_short_circuits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    debt_v14._warned_decorative_tranches = False
    cfg = {"Financing_Terms": {"debt_tranches": [{"name": "X", "rate_pct": 5.0}]}}
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        _warn_if_decorative_tranches(cfg)
    assert any(
        "debt_tranches is NOT an engine input" in r.message for r in caplog.records
    )
    assert debt_v14._warned_decorative_tranches is True

    # Second call short-circuits on the module flag (no new warning record).
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        _warn_if_decorative_tranches(cfg)
    assert not any(
        "debt_tranches is NOT an engine input" in r.message for r in caplog.records
    )
    debt_v14._warned_decorative_tranches = False


# ─────────────────────────────────────────────────────────────────────────────
# Dual-DSCR conservation sanity (first-principles, no magic numbers)
# ─────────────────────────────────────────────────────────────────────────────
def test_dual_dscr_capacity_equals_npv_of_service() -> None:
    cfads_p50 = [12.0] * 10
    cfads_p99 = [9.0] * 10
    rate = 0.08
    result = size_debt_with_dual_dscr(
        cfads_p50=cfads_p50,
        cfads_p99=cfads_p99,
        dscr_target_p50=1.30,
        dscr_target_p99=1.00,
        capex=200.0,
        debt_ratio_max=0.80,
        debt_rate=rate,
    )
    # Debt capacity == NPV of the sculpted service stream (definitional).
    npv_manual = sum(
        ds / (1 + rate) ** (i + 1) for i, ds in enumerate(result["debt_service_p50"])
    )
    assert result["debt_p50"] == pytest.approx(npv_manual, rel=1e-9)
    # Conservative sizing never exceeds either single-scenario capacity.
    assert result["debt_sized"] <= result["debt_p50"]
    assert result["debt_sized"] <= result["debt_p99"]
