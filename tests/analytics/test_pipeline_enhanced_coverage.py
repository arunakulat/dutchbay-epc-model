"""Coverage hardening for ``analytics.pipeline_v14_enhanced``.

Targets the validation-failure, FX/degradation, missing-block, and adapter
edge branches that the golden integration tests never exercise. Each test
asserts against the LIVE engine helpers (documented raises, structure, and
sign/conservation invariants) rather than hardcoding any IRR/NPV/DSCR number.

The private helpers are part of the module's internal contract: the public
gateway is a thin orchestrator over them, so unit-testing the helpers with
crafted bad inputs is the precise way to pin the error branches.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

import analytics.pipeline_v14_enhanced as mod
from analytics.pipeline_v14_enhanced import (
    PipelineConfigError,
    PipelineValidationError,
    _build_debt_covenant_snapshot,
    _build_tranche_debt_profile,
    _build_wacc_contract,
    _debt_fee_rate,
    _enrich_annual_rows_with_debt,
    _update_kpis_with_equity_distribution,
    _validate_annual_rows_structure,
    _validate_config_type_and_structure,
    _validate_debt_result_structure,
    run_v14_pipeline_enhanced,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# _validate_config_type_and_structure
# ---------------------------------------------------------------------------


def test_config_loaded_from_path_returns_dict() -> None:
    """A real scenario path loads into a non-empty dict (happy path of the loader branch)."""
    cfg = _validate_config_type_and_structure(LENDER_SCENARIO)
    assert isinstance(cfg, dict)
    assert cfg


def test_config_load_failure_wrapped_as_config_error() -> None:
    """A missing path raises PipelineConfigError wrapping the loader exception (line 104)."""
    missing = REPO_ROOT / "scenarios" / "does_not_exist_xyz.yaml"
    with pytest.raises(PipelineConfigError, match="Failed to load config"):
        _validate_config_type_and_structure(str(missing))


def test_config_loader_returns_non_dict_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the loader yields a non-dict, the gateway rejects it (line 99).

    ``load_scenario_config`` normally always returns a dict; we patch it to
    return a list so the defensive ``not isinstance(cfg, dict)`` guard fires
    and surfaces as the documented PipelineConfigError.
    """
    monkeypatch.setattr(mod, "load_scenario_config", lambda _p: ["not", "a", "dict"])
    with pytest.raises(PipelineConfigError, match="is not a dict"):
        _validate_config_type_and_structure(str(LENDER_SCENARIO))


def test_config_empty_mapping_raises(  ) -> None:
    """An empty mapping is rejected (line 111)."""
    with pytest.raises(PipelineConfigError, match="empty"):
        _validate_config_type_and_structure({})


def test_config_non_empty_mapping_passes() -> None:
    """A non-empty mapping is copied and returned (line 112)."""
    out = _validate_config_type_and_structure({"a": 1})
    assert out == {"a": 1}


def test_config_wrong_type_raises() -> None:
    """Neither str/Path nor Mapping -> PipelineConfigError (line 114)."""
    with pytest.raises(PipelineConfigError, match="must be str, Path, or Mapping"):
        _validate_config_type_and_structure(12345)


# ---------------------------------------------------------------------------
# _validate_annual_rows_structure
# ---------------------------------------------------------------------------


def test_annual_rows_not_list_raises() -> None:
    """Non-list annual_rows -> PipelineValidationError (line 124)."""
    with pytest.raises(PipelineValidationError, match="must be list"):
        _validate_annual_rows_structure({"year": 1})


def test_annual_rows_empty_raises() -> None:
    """Empty list -> PipelineValidationError (line 129)."""
    with pytest.raises(PipelineValidationError, match="cannot be empty"):
        _validate_annual_rows_structure([])


def test_annual_rows_first_row_not_dict_raises() -> None:
    """First row not a dict -> PipelineValidationError (line 133)."""
    with pytest.raises(PipelineValidationError, match=r"annual_rows\[0\] must be dict"):
        _validate_annual_rows_structure([42])


def test_annual_rows_missing_required_keys_raises() -> None:
    """Missing 'year' (and debt fields when required) -> raises (line 143)."""
    with pytest.raises(PipelineValidationError, match="missing required keys"):
        _validate_annual_rows_structure([{"not_year": 1}])


def test_annual_rows_missing_debt_fields_when_required() -> None:
    """require_debt_fields surfaces the debt keys in the missing set (line 143)."""
    with pytest.raises(PipelineValidationError, match="cf_pre_debt|debt_service_total"):
        _validate_annual_rows_structure([{"year": 1}], require_debt_fields=True)


def test_annual_rows_non_floatable_value_raises() -> None:
    """A present-but-non-floatable required key -> raises (lines 149,152-153)."""
    with pytest.raises(PipelineValidationError, match="not convertible to float"):
        _validate_annual_rows_structure([{"year": "not-a-number"}])


def test_annual_rows_valid_returns_same_list() -> None:
    """A well-formed list is returned unchanged."""
    rows = [{"year": 1, "cf_pre_debt": 1.0, "debt_service_total": 0.5}]
    assert _validate_annual_rows_structure(rows, require_debt_fields=True) is rows


# ---------------------------------------------------------------------------
# _validate_debt_result_structure
# ---------------------------------------------------------------------------


def test_debt_result_not_dict_raises() -> None:
    """Non-dict debt_result -> raises (line 168)."""
    with pytest.raises(PipelineValidationError, match="debt_result must be dict"):
        _validate_debt_result_structure([1, 2, 3])


def test_debt_result_missing_keys_raises() -> None:
    """Missing min_dscr/dscr_series/balloon_remaining -> raises (line 175)."""
    with pytest.raises(PipelineValidationError, match="missing required keys"):
        _validate_debt_result_structure({"min_dscr": 1.3})


def test_debt_result_bad_field_type_raises() -> None:
    """A present key with a non-coercible critical value -> raises (lines 183-184)."""
    bad = {
        "min_dscr": "not-a-float",
        "dscr_series": [1.3, 1.4],
        "balloon_remaining": 0.0,
    }
    with pytest.raises(PipelineValidationError, match="critical field type validation"):
        _validate_debt_result_structure(bad)


def test_debt_result_valid_passes() -> None:
    """Well-formed debt_result is returned as-is."""
    good = {"min_dscr": 1.3, "dscr_series": [1.3, 1.5], "balloon_remaining": 0.0}
    assert _validate_debt_result_structure(good) is good


# ---------------------------------------------------------------------------
# _enrich_annual_rows_with_debt  (defensive coercion + bridge folding)
# ---------------------------------------------------------------------------


def test_enrich_bad_period_map_entries_skipped() -> None:
    """Malformed period-map entries are skipped (lines 218-219) and rows still enrich."""
    annual_rows = [
        {"year": 1, "cf_pre_debt": 100.0},
        {"year": 2, "cf_pre_debt": 110.0},
    ]
    debt_result = {
        "debt_service_total": [10.0, 20.0],
        "balloon_resolution": [0.0, 0.0],
        # one valid mapping, several malformed (missing key / bad types)
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "debt_period": 0},
            {"annual_row_index": "x", "debt_period": 1},
            {"no_index": 1},
            {"annual_row_index": 1, "debt_period": None},
        ],
    }
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result)
    # Row 0 mapped to period 0; row 1's malformed mapping fell back to positional.
    assert enriched[0]["debt_service_total"] == 10.0
    # Conservation: cf_after_debt == cf_pre_debt - service - balloon for every row.
    for row in enriched:
        assert math.isclose(
            row["cf_after_debt"],
            row["cf_pre_debt"] - row["debt_service_total"] - row["balloon_resolution"],
            rel_tol=1e-9,
            abs_tol=1e-9,
        )


def test_enrich_non_numeric_values_coerced_to_zero() -> None:
    """Non-numeric cfads/service/resolution coerce to 0.0 (lines 247-248, 258-259, 272-273)."""
    annual_rows = [{"year": 1, "cfads_usd": "junk"}]
    debt_result = {
        "debt_service_total": ["bad-service"],
        "balloon_resolution": ["bad-resolution"],
        "annual_row_debt_period_map": [{"annual_row_index": 0, "debt_period": 0}],
    }
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result)
    out = enriched[0]
    assert out["cf_pre_debt"] == 0.0
    assert out["debt_service_total"] == 0.0
    assert out["balloon_resolution"] == 0.0
    assert out["cf_after_debt"] == 0.0


def test_enrich_bridge_service_non_numeric_coerced() -> None:
    """A non-numeric bridge service entry coerces to 0.0 (lines 237-238)."""
    annual_rows = [{"year": 1, "cfads_usd": 100.0}]
    debt_result = {
        # index 1 is the (unmapped) bridge period and is non-numeric.
        "debt_service_total": [10.0, "not-a-number"],
        "balloon_resolution": [0.0, 0.0],
        "annual_row_debt_period_map": [{"annual_row_index": 0, "debt_period": 0}],
        "cfads_bridge_debt_period": 1,
    }
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result)
    # Bridge service coerced to 0, so year-1 service is just its own period service.
    assert enriched[0]["debt_service_total"] == 10.0


def test_enrich_bridge_service_folds_into_year_one() -> None:
    """A real unmapped bridge period adds its service onto operating year 1."""
    annual_rows = [
        {"year": 1, "cfads_usd": 100.0},
        {"year": 2, "cfads_usd": 100.0},
    ]
    debt_result = {
        # period 2 (bridge) is unmapped; periods 0,1 map to the two rows.
        "debt_service_total": [10.0, 12.0, 5.0],
        "balloon_resolution": [0.0, 0.0, 0.0],
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "debt_period": 0},
            {"annual_row_index": 1, "debt_period": 1},
        ],
        "cfads_bridge_debt_period": 2,
    }
    enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result)
    # Year 1 bears its own (10) plus the orphaned bridge service (5).
    assert math.isclose(enriched[0]["debt_service_total"], 15.0)
    assert math.isclose(enriched[1]["debt_service_total"], 12.0)


# ---------------------------------------------------------------------------
# _debt_fee_rate
# ---------------------------------------------------------------------------


def test_debt_fee_rate_non_mapping_financing_returns_zero() -> None:
    """Financing_Terms that is not a Mapping -> 0.0 (line 288)."""
    assert _debt_fee_rate({"Financing_Terms": ["not", "a", "mapping"]}) == 0.0


def test_debt_fee_rate_guarantee_gated_on_flag() -> None:
    """Fee load = upfront/tenor always; the guarantee premium loads ONLY when
    use_revenue_guarantee is true (round-9 gate). Without the flag the 75bps is NOT charged."""
    base = {
        "Financing_Terms": {
            "guarantee_revenue_pct": 0.01,
            "fees": {"upfront_pct": 0.03},
            "tenor_years": 15.0,
        }
    }
    # Flag absent / false -> guarantee gated OFF, only upfront/tenor loads.
    assert math.isclose(_debt_fee_rate(base), 0.03 / 15.0, rel_tol=1e-12)
    off = {"Financing_Terms": {**base["Financing_Terms"], "use_revenue_guarantee": False}}
    assert math.isclose(_debt_fee_rate(off), 0.03 / 15.0, rel_tol=1e-12)
    # Flag true -> guarantee premium loads alongside the amortised upfront.
    on = {"Financing_Terms": {**base["Financing_Terms"], "use_revenue_guarantee": True}}
    assert math.isclose(_debt_fee_rate(on), 0.01 + 0.03 / 15.0, rel_tol=1e-12)


def test_debt_fee_rate_zero_tenor_falls_back_to_default() -> None:
    """A zero tenor must not divide-by-zero; falls back to 15.0 (line 293 guard)."""
    cfg = {"Financing_Terms": {"fees": {"upfront_pct": 0.03}, "tenor_years": 0}}
    assert math.isclose(_debt_fee_rate(cfg), 0.03 / 15.0, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# _build_wacc_contract
# ---------------------------------------------------------------------------


def test_wacc_contract_none_for_empty_dict() -> None:
    """Empty/None WACC dict -> None (line 335 branch)."""
    assert _build_wacc_contract(None) is None
    assert _build_wacc_contract({}) is None


def test_wacc_contract_invalid_values_return_none() -> None:
    """A non-coercible WACC field is caught and yields None (lines 360-362)."""
    bad = {"mode": "capm", "wacc_nominal": "not-a-number"}
    assert _build_wacc_contract(bad) is None


def test_wacc_contract_valid_dict_builds_result() -> None:
    """A minimal valid WACC dict produces a WaccResult whose prudential mirrors nominal."""
    out = _build_wacc_contract({"mode": "capm", "wacc_nominal": 0.08})
    assert out is not None
    assert math.isclose(out.base.wacc_nominal, 0.08)
    # prudential defaults to nominal when not supplied
    assert math.isclose(out.prudential_rate, 0.08)


# ---------------------------------------------------------------------------
# _build_tranche_debt_profile
# ---------------------------------------------------------------------------


def test_tranche_profile_bad_target_dscr_uses_none() -> None:
    """A non-floatable target_dscr is caught and stored as None (lines 406-408)."""
    config: dict[str, Any] = {"Financing_Terms": {"target_dscr": "bad"}}
    debt_result: dict[str, Any] = {
        "principal_by_tranche": {"usd": 1_000.0},
        "total_idc": 0.0,
    }
    profile = _build_tranche_debt_profile(config, debt_result)
    assert profile.dscr_target is None
    # total_debt is the sum of principals (conservation of the tranche split).
    assert math.isclose(profile.total_debt, 1_000.0)


# ---------------------------------------------------------------------------
# _build_debt_covenant_snapshot
# ---------------------------------------------------------------------------


def test_covenant_bad_threshold_falls_back_to_default() -> None:
    """A non-floatable target_dscr threshold falls back to 1.30 (lines 444-449)."""
    config: dict[str, Any] = {"Financing_Terms": {"target_dscr": "garbage"}}
    debt_result: dict[str, Any] = {
        "dscr_series": [1.5, 1.6, 2.0],
        "min_dscr": 1.5,
        "balloon_remaining": 0.0,
    }
    snap = _build_debt_covenant_snapshot(config, debt_result)
    assert math.isclose(snap.dscr_threshold, 1.30)
    assert snap.audit_status == "PASS"
    assert snap.years_below_threshold == 0


def test_covenant_skips_none_and_nonnumeric_and_inf() -> None:
    """None, non-numeric, and inf DSCRs are skipped (lines 457, 460-466, 468)."""
    config: dict[str, Any] = {"Financing_Terms": {"target_dscr": 1.30}}
    debt_result: dict[str, Any] = {
        # mix of None, non-numeric, inf, and one genuine breach (< 1.30)
        "dscr_series": [None, "n/a", float("inf"), 1.10],
        "min_dscr": 1.10,
        "balloon_remaining": 0.0,
    }
    snap = _build_debt_covenant_snapshot(config, debt_result)
    # Only the single 1.10 entry counts as a breach.
    assert snap.years_below_threshold == 1
    assert snap.audit_status == "REVIEW"
    assert snap.first_breach_year == snap.last_breach_year


def test_covenant_balloon_breach_appends_notes() -> None:
    """A flagged balloon breach extends the covenant notes (balloon branch)."""
    config: dict[str, Any] = {"Financing_Terms": {"target_dscr": 1.30}}
    debt_result: dict[str, Any] = {
        "dscr_series": [1.0, 1.1, 1.2, 1.25],
        "min_dscr": 1.0,
        "balloon_remaining": 5_000_000.0,
        "balloon_pct": 0.36,
        "balloon_treatment": "refinance",
        "balloon_covenant_breach": True,
        "max_balloon_pct": 0.10,
    }
    snap = _build_debt_covenant_snapshot(config, debt_result)
    assert snap.balloon_flag is True
    assert "Balloon" in snap.notes
    assert "BREACHES" in snap.notes
    # Four sub-1.30 years -> FAIL.
    assert snap.audit_status == "FAIL"


# ---------------------------------------------------------------------------
# _update_kpis_with_equity_distribution
# ---------------------------------------------------------------------------


def test_equity_update_failed_status_returns_none() -> None:
    """A non-computed/defaulted status -> None and only status recorded (line 520)."""
    kpis: dict[str, Any] = {}
    out = _update_kpis_with_equity_distribution(kpis, {"status": "failed"})
    assert out is None
    assert kpis["equity_distribution_status"] == "failed"


def test_equity_update_missing_summary_returns_none() -> None:
    """A 'computed' status with no summary mapping -> None (line 524)."""
    kpis: dict[str, Any] = {}
    out = _update_kpis_with_equity_distribution(
        kpis, {"status": "computed", "equity_summary": None}
    )
    assert out is None
    assert kpis["equity_distribution_status"] == "computed"


def test_equity_update_computed_merges_summary() -> None:
    """A full computed summary populates KPIs and returns an EquityPerformance."""
    kpis: dict[str, Any] = {}
    equity = {
        "status": "computed",
        "equity_summary": {
            "equity_irr": 0.12,
            "equity_npv": 1_000_000.0,
            "equity_multiple": 1.5,
            "moic": 1.5,
            "payback_period_years": 7.0,
            "total_equity_distributed_usd": 90_000_000.0,
            "average_cash_on_cash": 0.08,
            "covenant_locked_years": 0,
            "equity_investment_source": "config",
        },
    }
    perf = _update_kpis_with_equity_distribution(kpis, equity)
    assert perf is not None
    assert math.isclose(kpis["equity_irr"], 0.12)
    assert math.isclose(kpis["equity_moic"], 1.5)
    assert kpis["equity_distribution_status"] == "computed"
    assert perf.metadata["status"] == "computed"


# ---------------------------------------------------------------------------
# run_v14_pipeline_enhanced  (gateway-level branches)
# ---------------------------------------------------------------------------


def test_pipeline_invalid_validation_mode_raises() -> None:
    """An unknown validation_mode raises ValueError before any work (line 577)."""
    with pytest.raises(ValueError, match="validation_mode must be"):
        run_v14_pipeline_enhanced({"a": 1}, validation_mode="bogus")


def test_pipeline_config_error_propagates_unwrapped() -> None:
    """An empty inline config surfaces as PipelineConfigError, not wrapped (line 778)."""
    with pytest.raises(PipelineConfigError):
        run_v14_pipeline_enhanced({}, validation_mode="off")


def test_pipeline_internal_failure_wrapped_as_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-pipeline exception inside the body is wrapped as PipelineValidationError (line 781)."""

    def _boom(_cfg: Any) -> Any:
        raise RuntimeError("synthetic cashflow blowup")

    # Patch the lazily-imported cashflow builder at its source module so the
    # gateway's generic except-block fires.
    import finance.cashflow_v14 as cashflow_mod

    monkeypatch.setattr(cashflow_mod, "build_annual_rows", _boom)
    with pytest.raises(PipelineValidationError, match="Pipeline execution failed"):
        run_v14_pipeline_enhanced(str(LENDER_SCENARIO), validation_mode="off")


def test_pipeline_success_monitoring_disabled_emits_no_metrics() -> None:
    """With monitoring off the metrics block is empty but the run still succeeds."""
    result = run_v14_pipeline_enhanced(
        str(LENDER_SCENARIO),
        validation_mode="off",
        enable_monitoring=False,
    )
    assert result["status"] == "success"
    assert result["metrics"] == {}
    # Conservation/sign invariants on the headline numbers from the LIVE engine.
    sr = result["scenario_result"]
    assert isinstance(sr["min_dscr"], (int, float))
    assert sr["max_debt_usd"] >= 0.0


def test_pipeline_strict_validation_runs_modules() -> None:
    """Strict mode drives schema validation and still produces a lender result."""
    result = run_v14_pipeline_enhanced(
        str(LENDER_SCENARIO),
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )
    assert result["status"] == "success"
    assert result["validation_mode"] == "strict"
    assert result["annual_rows"]
    assert "dscr_series" in result["debt_result"]


def test_run_v14_pipeline_alias_is_enhanced() -> None:
    """The public alias points at the enhanced gateway (module-level binding)."""
    assert mod.run_v14_pipeline is run_v14_pipeline_enhanced
