#!/usr/bin/env python3
"""Coverage tests for analytics.core.metrics — the canonical v14 KPI engine.

This module aggregates scenario-level KPIs: project NPV/IRR (delegated to the
finance.irr singleton), DSCR statistics, CFADS aggregates and the lender KPI
surface. The tests here drive the PUBLIC surface (calculate_scenario_kpis /
compute_kpis) and the private derivation helpers with synthetic configs and
DSCR/CFADS series, then assert against the LIVE finance.irr engine and against
documented invariants (signs, bounds, conservation, key stability) — never
against hardcoded IRR/NPV/DSCR magic numbers.

The goal is to exercise the schema-tolerant fallback branches (case-insensitive
lookups, legacy/compact CAPEX schemas, LKR->USD CFADS conversion, construction
lag resolution, WACC-basis derivation and the llcr/plcr fallbacks) that a
happy-path pipeline run does not reach.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from analytics.core import metrics
from analytics.core.metrics import (
    DEFAULT_DISCOUNT_RATE,
    _clean_dscr_series,
    _derive_capex_usd,
    _derive_cfads_series,
    _derive_scenario_name,
    _summary_stats,
    calculate_scenario_kpis,
    compute_kpis,
)
from finance.irr import approx_project_irr, project_npv_from_cfads


# ---------------------------------------------------------------------------
# _summary_stats
# ---------------------------------------------------------------------------
def test_summary_stats_empty_returns_zero_skeleton() -> None:
    stats = _summary_stats([])
    assert stats["n"] == 0.0
    assert set(stats) == {"n", "mean", "std", "min", "p10", "median", "p90", "max"}
    assert all(v == 0.0 for v in stats.values())


def test_summary_stats_filters_non_finite_and_non_numeric() -> None:
    # NaN, inf, None and a string are all dropped; only the two floats survive.
    stats = _summary_stats([1.0, float("nan"), float("inf"), None, "x", 3.0])  # type: ignore[list-item]
    assert stats["n"] == 2.0
    assert stats["min"] == 1.0
    assert stats["max"] == 3.0
    assert stats["mean"] == 2.0


def test_summary_stats_single_value_zero_std() -> None:
    # n == 1 branch: std is 0.0 (not NaN).
    stats = _summary_stats([5.0])
    assert stats["n"] == 1.0
    assert stats["std"] == 0.0
    assert stats["min"] == stats["max"] == 5.0


def test_summary_stats_percentile_edges_hit_min_and_max() -> None:
    # p10 with q just above 0 and p90 below 1 still bracket within [min,max];
    # min/max keys directly exercise the q<=0 and q>=1 percentile branches.
    vals = [float(i) for i in range(1, 11)]
    stats = _summary_stats(vals)
    assert stats["min"] == 1.0
    assert stats["max"] == 10.0
    assert (
        stats["min"] <= stats["p10"] <= stats["median"] <= stats["p90"] <= stats["max"]
    )


def test_summary_stats_percentile_is_linear_interpolated() -> None:
    # _percentile now uses linear interpolation between order statistics (the same
    # convention statistics.median uses), not nearest-rank rounding. For [2, 4]:
    #   p10 -> pos = 0.10*(2-1) = 0.10 -> 2*(0.90) + 4*(0.10) = 2.2
    #   p90 -> pos = 0.90*(2-1) = 0.90 -> 2*(0.10) + 4*(0.90) = 3.8
    stats = _summary_stats([2.0, 4.0])
    assert math.isclose(stats["p10"], 2.2, rel_tol=1e-12)
    assert math.isclose(stats["p90"], 3.8, rel_tol=1e-12)


def test_summary_stats_p50_equals_median() -> None:
    # The whole point of aligning _percentile to interpolation: an interpolated p50
    # equals the reported median for an even-length series (was 2.0 vs 2.5 under the
    # old nearest-rank convention).
    vals = [1.0, 2.0, 3.0, 4.0]
    stats = _summary_stats(vals)
    # reconstruct p50 the same way _percentile does (pos = 0.5*(n-1) = 1.5 -> 2.5)
    interp_p50 = (vals[1] + vals[2]) / 2.0
    assert math.isclose(stats["median"], interp_p50, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# _clean_dscr_series
# ---------------------------------------------------------------------------
def test_clean_dscr_series_none_and_empty() -> None:
    assert list(_clean_dscr_series(None)) == []
    assert list(_clean_dscr_series([])) == []


def test_clean_dscr_series_drops_invalid_entries() -> None:
    raw = [None, "not-a-number", float("nan"), float("inf"), -1.0, 0.0, "1.5", 2.0]
    cleaned = list(_clean_dscr_series(raw))
    # Drop ONLY None / non-coercible / non-finite. A finite DSCR <= 0.0 is a REAL
    # coverage BREACH and is RETAINED (Wave-2 fix: align with the debt engine's
    # _clean_public_dscr_series so the KPI min_dscr cannot hide a breach year).
    assert cleaned == [-1.0, 0.0, 1.5, 2.0]


def test_clean_dscr_series_retains_finite_breach_so_min_matches_debt_engine() -> None:
    """A breaching series' KPI min must equal the worst finite year, not an optimistic
    positive value (the bug: 0.0 / negative breaches were silently dropped)."""
    cleaned = list(_clean_dscr_series([1.5, 1.4, 0.0, -0.3, 1.2]))
    assert cleaned == [1.5, 1.4, 0.0, -0.3, 1.2]
    assert min(cleaned) == -0.3


# ---------------------------------------------------------------------------
# _derive_scenario_name
# ---------------------------------------------------------------------------
def test_derive_scenario_name_empty_config() -> None:
    assert _derive_scenario_name(None) == ""
    assert _derive_scenario_name({}) == ""


def test_derive_scenario_name_top_level_case_insensitive() -> None:
    assert _derive_scenario_name({"Scenario_Name": "Top"}) == "Top"
    assert _derive_scenario_name({"ID": 42}) == "42"


def test_derive_scenario_name_from_meta_section() -> None:
    cfg = {"meta": {"NAME": "FromMeta"}}
    assert _derive_scenario_name(cfg) == "FromMeta"


def test_derive_scenario_name_from_project_section() -> None:
    cfg = {"project": {"name": "FromProject"}}
    assert _derive_scenario_name(cfg) == "FromProject"


def test_derive_scenario_name_no_match_returns_empty() -> None:
    # meta/project present but nameless -> falls through to final "".
    cfg = {"meta": {"foo": "bar"}, "project": {"capacity_mw": 150}}
    assert _derive_scenario_name(cfg) == ""


# ---------------------------------------------------------------------------
# _derive_capex_usd
# ---------------------------------------------------------------------------
def test_derive_capex_usd_empty_config() -> None:
    assert _derive_capex_usd(None) == 0.0
    assert _derive_capex_usd({}) == 0.0


def test_derive_capex_usd_finance_section() -> None:
    assert _derive_capex_usd({"finance": {"capex_total_usd": 1_000.0}}) == 1_000.0


def test_derive_capex_usd_legacy_capex_section_case_insensitive() -> None:
    cfg = {"CAPEX": {"usd_total": 250_000_000.0}}
    assert _derive_capex_usd(cfg) == 250_000_000.0


def test_derive_capex_usd_skips_none_and_uncoercible_then_top_level() -> None:
    # finance section present but its keys are None / non-numeric -> the loop
    # `continue`s (lines 149 + 152-153), then the flat top-level key is used.
    cfg = {
        "finance": {"capex_total_usd": None, "capex_usd": "not-a-number"},
        "capex_total_usd": 500.0,
    }
    assert _derive_capex_usd(cfg) == 500.0


def test_derive_capex_usd_top_level_uncoercible_returns_zero() -> None:
    # Every candidate is non-numeric -> the final return 0.0 (line 164).
    cfg: Dict[str, Any] = {"capex_total_usd": "abc", "total_capex_usd": object()}
    assert _derive_capex_usd(cfg) == 0.0


def test_derive_capex_usd_costs_section() -> None:
    assert _derive_capex_usd({"costs": {"total_capex": 9_999.0}}) == 9_999.0


# ---------------------------------------------------------------------------
# _derive_cfads_series
# ---------------------------------------------------------------------------
def test_derive_cfads_series_empty() -> None:
    assert _derive_cfads_series(None) == []
    assert _derive_cfads_series([]) == []


def test_derive_cfads_series_usd_direct() -> None:
    rows = [{"cfads_usd": 10.0}, {"cfads_usd": 20.0}]
    assert _derive_cfads_series(rows) == [10.0, 20.0]


def test_derive_cfads_series_lkr_fallback_variants() -> None:
    # Three LKR key variants, all with an fx rate, convert to USD.
    rows = [
        {"cfads_final_lkr": 300.0, "fx_rate": 3.0},
        {"cfads_lkr": 600.0, "start_lkr_per_usd": 3.0},
        {"cfads": 900.0, "fx_rate": 3.0},
    ]
    assert _derive_cfads_series(rows) == [100.0, 200.0, 300.0]


def test_derive_cfads_series_missing_fx_or_lkr_yields_zero() -> None:
    # No fx, or LKR present but fx zero, or neither -> 0.0 appended.
    rows = [
        {"cfads_lkr": 300.0},  # no fx
        {"fx_rate": 3.0},  # no lkr
        {},  # nothing
    ]
    assert _derive_cfads_series(rows) == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# calculate_scenario_kpis — CFADS aggregates & defaults
# ---------------------------------------------------------------------------
def test_calculate_kpis_minimal_no_inputs_stable_surface() -> None:
    # With no config/rows/debt the function must still return the stable lender
    # KPI surface with zero defaults (API stability, not economic substitution).
    result = calculate_scenario_kpis()
    for key in (
        "project_npv",
        "npv",
        "project_irr",
        "irr",
        "equity_irr",
        "avg_dscr",
        "llcr",
        "plcr",
        "min_dscr",
        "discount_rate_used",
        "wacc_label",
        "wacc_is_real",
    ):
        assert key in result
    assert result["project_npv"] == 0.0
    assert result["irr"] == 0.0
    assert result["discount_rate_used"] == DEFAULT_DISCOUNT_RATE
    # No debt -> llcr/plcr fall back to dscr_mean (here 0.0).
    assert result["llcr"] == 0.0
    assert result["plcr"] == 0.0


def test_calculate_kpis_cfads_aggregates_conserve() -> None:
    cfads = [100.0, 200.0, 300.0]
    result = calculate_scenario_kpis(cfads_series_usd=cfads)
    assert result["total_cfads_usd"] == sum(cfads)
    assert result["final_cfads_usd"] == cfads[-1]
    assert math.isclose(result["mean_operational_cfads_usd"], sum(cfads) / len(cfads))


def test_calculate_kpis_explicit_discount_rate_used() -> None:
    result = calculate_scenario_kpis(cfads_series_usd=[1.0], discount_rate=0.07)
    assert result["discount_rate_used"] == 0.07


def test_calculate_kpis_scenario_name_override_skips_derivation() -> None:
    result = calculate_scenario_kpis(scenario_name="Explicit", config={"name": "Cfg"})
    assert result["scenario_name"] == "Explicit"


# ---------------------------------------------------------------------------
# calculate_scenario_kpis — NPV/IRR against the LIVE engine
# ---------------------------------------------------------------------------
def test_calculate_kpis_npv_irr_match_finance_engine() -> None:
    # A profitable project: capex recovered by a flat CFADS stream. The metrics
    # engine must reproduce exactly what finance.irr returns for the same inputs.
    capex = 1_000.0
    cfads = [300.0] * 6
    config = {"capex_total_usd": capex}
    drate = 0.08

    result = calculate_scenario_kpis(
        config=config, cfads_series_usd=cfads, discount_rate=drate
    )

    expected_npv = project_npv_from_cfads(drate, cfads, capex, construction_years=0)
    expected_irr = approx_project_irr(cfads, capex, construction_years=0)

    assert math.isclose(result["project_npv"], expected_npv, rel_tol=1e-9)
    assert math.isclose(result["npv"], expected_npv, rel_tol=1e-9)
    assert math.isclose(result["project_irr"], expected_irr, rel_tol=1e-9)
    assert math.isclose(result["irr"], expected_irr, rel_tol=1e-9)
    # Profitable: total CFADS exceeds capex, so NPV at this rate is positive and
    # equity_irr does NOT mirror the (unlevered) project_irr when no equity-distribution
    # value is supplied — that would present one metric as another. It defaults to the
    # neutral 0.0 sentinel (Wave-2 fix); the live pipeline overwrites it with the real
    # levered waterfall equity IRR.
    assert result["project_npv"] > 0.0
    assert result["project_irr"] > 0.0
    assert result["equity_irr"] == 0.0


def test_calculate_kpis_construction_lag_lowers_npv() -> None:
    # The construction lag must push operating cash later -> strictly lower NPV
    # than the un-lagged case (monotonic in the lag), matching the engine.
    capex = 1_000.0
    cfads = [300.0] * 8
    drate = 0.08

    no_lag = calculate_scenario_kpis(
        config={"capex_total_usd": capex},
        cfads_series_usd=cfads,
        discount_rate=drate,
        debt_result={"construction_years": 0},
    )
    with_lag = calculate_scenario_kpis(
        config={"capex_total_usd": capex},
        cfads_series_usd=cfads,
        discount_rate=drate,
        debt_result={"construction_years": 2},
    )
    assert with_lag["project_npv"] < no_lag["project_npv"]
    # The lagged value must equal the engine computed with the same lag.
    assert math.isclose(
        with_lag["project_npv"],
        project_npv_from_cfads(drate, cfads, capex, construction_years=2),
        rel_tol=1e-9,
    )


def test_calculate_kpis_construction_years_from_config() -> None:
    # No debt_result construction_years -> resolved from config instead.
    capex = 1_000.0
    cfads = [300.0] * 8
    drate = 0.08
    result = calculate_scenario_kpis(
        config={"capex_total_usd": capex, "construction_years": 2},
        cfads_series_usd=cfads,
        discount_rate=drate,
    )
    assert math.isclose(
        result["project_npv"],
        project_npv_from_cfads(drate, cfads, capex, construction_years=2),
        rel_tol=1e-9,
    )


def test_calculate_kpis_construction_years_bad_values_default_zero() -> None:
    # Non-coercible construction_years in BOTH debt_result and config must be
    # swallowed (TypeError/ValueError branches) and fall back to lag 0.
    capex = 1_000.0
    cfads = [300.0] * 6
    drate = 0.08
    result = calculate_scenario_kpis(
        config={"capex_total_usd": capex, "construction_years": "oops"},
        cfads_series_usd=cfads,
        discount_rate=drate,
        debt_result={"construction_years": object()},
    )
    # Lag fell back to 0 -> equals the no-lag engine result.
    assert math.isclose(
        result["project_npv"],
        project_npv_from_cfads(drate, cfads, capex, construction_years=0),
        rel_tol=1e-9,
    )


def test_calculate_kpis_valuation_overrides_npv_irr() -> None:
    # When a valuation block is supplied, its npv/irr win over engine derivation.
    result = calculate_scenario_kpis(
        config={"capex_total_usd": 1_000.0},
        cfads_series_usd=[300.0] * 6,
        valuation={"npv": -123.0, "irr": 0.042},
    )
    assert result["project_npv"] == -123.0
    assert result["npv"] == -123.0
    assert result["project_irr"] == 0.042
    assert result["irr"] == 0.042


def test_calculate_kpis_valuation_uncoercible_falls_back_to_engine() -> None:
    # Non-numeric valuation entries are ignored (TypeError/ValueError) -> engine
    # derivation still fills project_npv/irr from CFADS+capex.
    capex = 1_000.0
    cfads = [300.0] * 6
    result = calculate_scenario_kpis(
        config={"capex_total_usd": capex},
        cfads_series_usd=cfads,
        valuation={"npv": "bad", "irr": None},
    )
    assert math.isclose(
        result["project_npv"],
        project_npv_from_cfads(DEFAULT_DISCOUNT_RATE, cfads, capex),
        rel_tol=1e-9,
    )


def test_calculate_kpis_no_capex_keeps_zero_npv_default() -> None:
    # CFADS present but capex == 0 -> engine NPV branch skipped, stable zero.
    result = calculate_scenario_kpis(cfads_series_usd=[300.0] * 6)
    assert result["project_npv"] == 0.0
    assert result["project_irr"] == 0.0


# ---------------------------------------------------------------------------
# calculate_scenario_kpis — debt_result / DSCR / debt magnitudes
# ---------------------------------------------------------------------------
def test_calculate_kpis_dscr_stats_and_debt_magnitudes() -> None:
    dscr = [1.30, 1.45, 1.60, 1.50]
    debt = {
        "dscr_series": dscr,
        "max_debt_usd": 100_000_000.0,
        "final_debt_usd": 36_000_000.0,
        "total_idc_usd": 5_000_000.0,
    }
    result = calculate_scenario_kpis(debt_result=debt)
    # DSCR stats reduce over the cleaned series.
    assert result["min_dscr"] == min(dscr)
    assert result["dscr_min"] == min(dscr)
    assert result["dscr_max"] == max(dscr)
    assert math.isclose(result["dscr_mean"], sum(dscr) / len(dscr))
    assert result["avg_dscr"] == result["dscr_mean"]
    assert result["max_debt_usd"] == 100_000_000.0
    assert result["final_debt_usd"] == 36_000_000.0
    assert result["total_idc_usd"] == 5_000_000.0


def test_calculate_kpis_debt_total_alias_and_idc_alias() -> None:
    # `debt_total` aliases max_debt_usd; `total_idc` aliases total_idc_usd.
    debt = {
        "dscr_series": [1.4],
        "debt_total": 80_000_000.0,
        "total_idc": 2_000_000.0,
    }
    result = calculate_scenario_kpis(debt_result=debt)
    assert result["max_debt_usd"] == 80_000_000.0
    assert result["total_idc_usd"] == 2_000_000.0


def test_calculate_kpis_debt_magnitudes_uncoercible_skipped() -> None:
    # Non-numeric debt magnitudes hit the TypeError/ValueError continue and are
    # simply absent from the result (no key emitted).
    debt = {"dscr_series": [1.4], "max_debt_usd": "NaNish", "final_debt_usd": object()}
    result = calculate_scenario_kpis(debt_result=debt)
    assert "max_debt_usd" not in result
    assert "final_debt_usd" not in result


def test_calculate_kpis_dscr_series_not_a_sequence() -> None:
    # A non-Sequence dscr_series collapses to empty -> zeroed DSCR stats.
    result = calculate_scenario_kpis(debt_result={"dscr_series": 1234})
    assert result["dscr_series"] == []
    assert result["min_dscr"] == 0.0


# ---------------------------------------------------------------------------
# calculate_scenario_kpis — llcr / plcr / balloon surface
# ---------------------------------------------------------------------------
def test_calculate_kpis_llcr_plcr_from_debt_result() -> None:
    debt = {"dscr_series": [1.4, 1.5], "llcr": 1.8, "plcr": 1.9}
    result = calculate_scenario_kpis(debt_result=debt)
    assert result["llcr"] == 1.8
    assert result["plcr"] == 1.9


def test_calculate_kpis_llcr_plcr_uncoercible_fall_back_to_dscr_mean() -> None:
    # Non-numeric llcr/plcr -> fall back to dscr_mean (lines 368-370).
    debt = {"dscr_series": [1.4, 1.6], "llcr": "bad", "plcr": object()}
    result = calculate_scenario_kpis(debt_result=debt)
    assert result["llcr"] == result["dscr_mean"]
    assert result["plcr"] == result["dscr_mean"]


def test_calculate_kpis_no_debt_result_llcr_plcr_branch() -> None:
    # Without a debt_result the explicit else-branch sets llcr/plcr = dscr_mean.
    result = calculate_scenario_kpis(cfads_series_usd=[1.0])
    assert result["llcr"] == result["dscr_mean"]
    assert result["plcr"] == result["dscr_mean"]


def test_calculate_kpis_balloon_surface_numeric() -> None:
    debt = {
        "dscr_series": [1.4],
        "balloon_pct": 0.36,
        "balloon_residual": 36_000_000.0,
        "balloon_covenant_breach": True,
    }
    result = calculate_scenario_kpis(debt_result=debt)
    assert result["balloon_pct"] == 0.36
    assert result["balloon_residual"] == 36_000_000.0
    # Breach flag normalised to numeric 1.0.
    assert result["balloon_covenant_breach"] == 1.0


def test_calculate_kpis_balloon_no_breach_zero() -> None:
    result = calculate_scenario_kpis(debt_result={"dscr_series": [1.4]})
    assert result["balloon_covenant_breach"] == 0.0
    assert result["balloon_pct"] == 0.0


# ---------------------------------------------------------------------------
# calculate_scenario_kpis — WACC reporting basis
# ---------------------------------------------------------------------------
def test_calculate_kpis_wacc_explicit_args_passthrough() -> None:
    result = calculate_scenario_kpis(
        cfads_series_usd=[1.0], wacc_is_real=True, wacc_label="real_buildup"
    )
    assert result["wacc_is_real"] is True
    assert result["wacc_label"] == "real_buildup"


def test_calculate_kpis_wacc_derived_from_config_drives_discount() -> None:
    # wacc.drives_discount_rate + mode -> wacc_is_real True, label == mode.
    cfg = {"wacc": {"drives_discount_rate": True, "mode": "nominal"}}
    result = calculate_scenario_kpis(config=cfg, cfads_series_usd=[1.0])
    assert result["wacc_is_real"] is True
    assert result["wacc_label"] == "nominal"


def test_calculate_kpis_wacc_default_label_when_not_driving() -> None:
    # No driving flag -> wacc_is_real False, label falls back to "base".
    cfg = {"wacc": {"drives_discount_rate": False, "mode": "nominal"}}
    result = calculate_scenario_kpis(config=cfg, cfads_series_usd=[1.0])
    assert result["wacc_is_real"] is False
    assert result["wacc_label"] == "base"


def test_calculate_kpis_wacc_no_config_section() -> None:
    # No wacc section at all -> still safe defaults.
    result = calculate_scenario_kpis(config={}, cfads_series_usd=[1.0])
    assert result["wacc_is_real"] is False
    assert result["wacc_label"] == "base"


# ---------------------------------------------------------------------------
# CFADS derivation via annual_rows path (no explicit cfads_series_usd)
# ---------------------------------------------------------------------------
def test_calculate_kpis_uses_annual_rows_when_no_series() -> None:
    rows = [{"cfads_usd": 100.0}, {"cfads_usd": 200.0}]
    result = calculate_scenario_kpis(annual_rows=rows)
    assert result["total_cfads_usd"] == 300.0
    assert result["final_cfads_usd"] == 200.0


# ---------------------------------------------------------------------------
# compute_kpis thin adapter
# ---------------------------------------------------------------------------
def test_compute_kpis_adapter_matches_calculate() -> None:
    capex = 1_000.0
    config = {"capex_total_usd": capex}
    rows = [{"cfads_usd": 300.0} for _ in range(6)]
    debt = {"dscr_series": [1.4, 1.5, 1.6]}

    via_adapter = compute_kpis(
        config=config, annual_rows=rows, debt_result=debt, discount_rate=0.08
    )
    via_direct = calculate_scenario_kpis(
        config=config,
        annual_rows=rows,
        debt_result=debt,
        discount_rate=0.08,
    )
    # The adapter is a pure pass-through, so the two surfaces must agree.
    assert via_adapter["project_npv"] == via_direct["project_npv"]
    assert via_adapter["project_irr"] == via_direct["project_irr"]
    assert via_adapter["dscr_mean"] == via_direct["dscr_mean"]


# ---------------------------------------------------------------------------
# End-to-end against the canonical lender scenario (sanity / invariants)
# ---------------------------------------------------------------------------
def test_module_exports_public_surface() -> None:
    # __all__ documents the supported entry points.
    assert set(metrics.__all__) == {
        "_summary_stats",
        "calculate_scenario_kpis",
        "compute_kpis",
    }


def test_derive_capex_matches_debt_engine_for_breakdown() -> None:
    """When capex.derive_from_breakdown is set, the NPV capex base must EQUAL the debt
    engine's basis (one shared resolver) so the two cannot diverge (Wave-2 fix). A
    flat-total config (no derive) stays on the metrics flat path, unchanged."""
    from finance.debt_v14 import _extract_capex_usd

    # bottom-up breakdown: NPV capex == debt capex == the breakdown sum (100M)
    cfg_breakdown = {
        "capex": {
            "derive_from_breakdown": True,
            "usd_total": 100_000_000,
            "breakdown": {
                "epc_usd": 80_000_000,
                "grid_usd": 18_500_000,
                "contingency_usd": 1_500_000,
            },
        }
    }
    assert _derive_capex_usd(cfg_breakdown) == _extract_capex_usd(dict(cfg_breakdown))
    assert _derive_capex_usd(cfg_breakdown) == 100_000_000.0

    # No derive_from_breakdown -> flat-total path, unchanged.
    assert _derive_capex_usd({"capex": {"usd_total": 250_000_000}}) == 250_000_000.0


def test_prudential_rate_surfaces_a_distinct_prudential_npv() -> None:
    """A supplied prudential_rate now yields a prudential-basis NPV under a distinct key
    (it was previously accepted but never consumed — decorative). Additive: the base
    project_npv is unchanged and the key is absent when no prudential rate is given."""
    capex = 1_000.0
    cfads = [300.0] * 6
    base = calculate_scenario_kpis(
        config={"capex_total_usd": capex}, cfads_series_usd=cfads, discount_rate=0.08
    )
    prud = calculate_scenario_kpis(
        config={"capex_total_usd": capex},
        cfads_series_usd=cfads,
        discount_rate=0.08,
        prudential_rate=0.12,
    )
    assert (
        "project_npv_prudential" not in base
    )  # not computed without a prudential rate
    assert prud["prudential_rate_used"] == 0.12
    assert (
        prud["project_npv_prudential"] < prud["project_npv"]
    )  # higher discount -> lower
    assert prud["project_npv"] == base["project_npv"]  # base unchanged (additive)
