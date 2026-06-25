#!/usr/bin/env python
"""Coverage-raising tests for finance.equity_distribution_v14_hydra.

These tests target the equity waterfall / distribution module directly with
deterministic, first-principles assertions. No economic magic numbers are
hardcoded: every expected value is either derived from the inputs inside the
test (conservation/sign/monotonicity invariants) or computed via the engine's
own delegated helpers. Source files are never modified.

The canonical lender scenario is used where a real config is required; all
other cases build explicit, fully-deterministic payloads so each waterfall
branch is exercised in isolation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from omegaconf import OmegaConf
from pydantic_core import ValidationError

from finance import equity_distribution_v14_hydra as mod
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    EquityDistributionEngine,
    build_equity_distribution_schedule,
    calculate_equity_distribution_from_pipeline,
    load_config,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


# ---------------------------------------------------------------------------
# Pydantic field validators (lines 91, 99, 107, 115, 123)
# ---------------------------------------------------------------------------
def test_validate_project_life_rejects_out_of_range() -> None:
    """project_life_years outside 1..50 must raise with a clear message.

    The Field(ge=1, le=50) bound fires first during construction, so to
    exercise the validator's own raise we also invoke the classmethod
    directly (its documented contract: 1..50 inclusive).
    """
    with pytest.raises(ValidationError) as exc:
        EquityDistributionConfig(project_life_years=0)
    assert "project_life_years" in str(exc.value)
    with pytest.raises(ValidationError):
        EquityDistributionConfig(project_life_years=51)
    # in-bound value passes the validator and is returned unchanged
    assert EquityDistributionConfig.validate_project_life(25) == 25
    with pytest.raises(ValueError, match="Project life must be 1-50"):
        EquityDistributionConfig.validate_project_life(0)


def test_validate_equity_stake_custom_validator() -> None:
    """equity_stake_pct above 100 trips the explicit validator path."""
    with pytest.raises(ValidationError) as exc:
        EquityDistributionConfig(equity_stake_pct=150.0)
    assert "equity_stake" in str(exc.value).lower()
    assert EquityDistributionConfig.validate_equity_stake(25.0) == 25.0
    with pytest.raises(ValueError, match="Equity stake"):
        EquityDistributionConfig.validate_equity_stake(150.0)


def test_validate_dscr_threshold_rejects_above_five() -> None:
    """min_dscr_threshold above 5.0 must be rejected."""
    with pytest.raises(ValidationError) as exc:
        EquityDistributionConfig(min_dscr_threshold=9.0)
    assert "dscr" in str(exc.value).lower()
    assert EquityDistributionConfig.validate_dscr_threshold(1.25) == 1.25
    with pytest.raises(ValueError, match="DSCR threshold"):
        EquityDistributionConfig.validate_dscr_threshold(9.0)


def test_validate_discount_rate_rejects_above_one() -> None:
    """discount_rate above 1.0 (a decimal) must be rejected."""
    with pytest.raises(ValidationError) as exc:
        EquityDistributionConfig(discount_rate=2.0)
    assert "discount_rate" in str(exc.value)
    assert EquityDistributionConfig.validate_discount_rate(0.10) == 0.10
    with pytest.raises(ValueError, match="discount_rate must be"):
        EquityDistributionConfig.validate_discount_rate(2.0)


# ---------------------------------------------------------------------------
# Numeric coercion helpers (lines 152-153, 221)
# ---------------------------------------------------------------------------
def test_as_float_handles_bad_text_with_default() -> None:
    """Non-numeric text falls back to the supplied default, not an exception."""
    assert mod._as_float("not-a-number", default=3.5) == 3.5
    assert mod._as_float(None, default=None) is None
    assert mod._as_float("12.5") == 12.5


def test_normalise_percent_none_returns_default() -> None:
    """An un-coercible value yields the default (the None branch)."""
    assert mod._normalise_percent("garbage", 42.0) == 42.0
    # decimal fraction is scaled to percent points
    assert mod._normalise_percent(0.25, 10.0) == 25.0
    # already-percent value is passed through
    assert mod._normalise_percent(73.0, 10.0) == 73.0


# ---------------------------------------------------------------------------
# CAPEX extraction (lines 179-183) and scenario-name extraction (197, 205)
# ---------------------------------------------------------------------------
def test_extract_capex_top_level_fallback() -> None:
    """Top-level capex keys are used when no known section carries it."""
    assert mod._extract_capex_usd({"capex_total_usd": 1.0e8}) == 1.0e8


def test_extract_capex_returns_none_when_absent() -> None:
    """Absent CAPEX anywhere returns None (the final return)."""
    assert mod._extract_capex_usd({"unrelated": {"x": 1}}) is None


def test_extract_scenario_name_from_meta_section() -> None:
    """Scenario name resolves from the nested meta section."""
    assert mod._extract_scenario_name({"meta": {"name": "meta-case"}}) == "meta-case"


def test_extract_scenario_name_defaults_when_missing() -> None:
    """With no name anywhere, the default sentinel is returned."""
    assert mod._extract_scenario_name({"irrelevant": 1}) == "default"


def test_extract_scenario_name_from_project_section() -> None:
    """Scenario name resolves from a Project/project section name field."""
    assert mod._extract_scenario_name({"project": {"name": "proj-case"}}) == "proj-case"


# ---------------------------------------------------------------------------
# CFADS / debt-service / DSCR row extractors (338-344, 358, 362-366, 373)
# ---------------------------------------------------------------------------
def test_extract_cf_pre_debt_lkr_fallback() -> None:
    """LKR CFADS divided by FX rate yields USD when no USD field present."""
    row = {"cfads_final_lkr": 3.0e9, "fx_rate": 300.0}
    assert mod._extract_cf_pre_debt(row) == pytest.approx(1.0e7)
    # zero/None fx -> 0.0 fallback (defensive)
    assert mod._extract_cf_pre_debt({"cfads_lkr": 1.0, "fx_rate": 0.0}) == 0.0
    assert mod._extract_cf_pre_debt({}) == 0.0


def test_extract_debt_service_total_service_key() -> None:
    """The alternate 'total_service' key is honoured when present."""
    assert mod._extract_debt_service({"total_service": 5.0e6}, [], 0) == 5.0e6


def test_extract_debt_service_falls_back_to_series() -> None:
    """When the row carries no service, the aligned positional series is used."""
    series = [1.0e6, 2.0e6, 3.0e6]
    assert mod._extract_debt_service({}, series, 1) == 2.0e6
    # index past the series end -> 0.0
    assert mod._extract_debt_service({}, series, 9) == 0.0


def test_extract_dscr_prefers_row_value() -> None:
    """A positive row dscr is returned verbatim without recomputation."""
    assert mod._extract_dscr({"dscr": 1.42}, cf_pre_debt=10.0, debt_service=5.0) == 1.42
    # non-positive row dscr -> compute from cash / service
    assert mod._extract_dscr({"dscr": 0.0}, cf_pre_debt=10.0, debt_service=5.0) == 2.0
    # no service -> None
    assert mod._extract_dscr({}, cf_pre_debt=10.0, debt_service=0.0) is None


# ---------------------------------------------------------------------------
# Equity investment derivation (305, 325-328)
# ---------------------------------------------------------------------------
def test_derive_equity_investment_explicit() -> None:
    """An explicit equity_investment_usd is returned with 'explicit' source."""
    cfg = EquityDistributionConfig(equity_investment_usd=42.0e6)
    amount, source = mod._derive_equity_investment_usd(
        config={}, debt_result={}, distribution_config=cfg
    )
    assert amount == 42.0e6
    assert source == "explicit"


def test_derive_equity_investment_defaulted() -> None:
    """When CAPEX/debt are absent but defaults allowed, the default is used."""
    cfg = EquityDistributionConfig(
        allow_default_equity_investment=True,
        default_equity_investment_usd=7.0e6,
    )
    amount, source = mod._derive_equity_investment_usd(
        config={}, debt_result={}, distribution_config=cfg
    )
    assert amount == 7.0e6
    assert source == "defaulted"


def test_derive_equity_investment_failed() -> None:
    """No explicit value, no CAPEX/debt, defaults off -> (None, 'failed')."""
    cfg = EquityDistributionConfig()
    amount, source = mod._derive_equity_investment_usd(
        config={}, debt_result={}, distribution_config=cfg
    )
    assert amount is None
    assert source == "failed"


def test_derive_equity_investment_capex_less_debt() -> None:
    """CAPEX minus debt gives the residual equity; conservation holds."""
    cfg = EquityDistributionConfig()
    capex, debt = 200.0e6, 120.0e6
    amount, source = mod._derive_equity_investment_usd(
        config={"capex": {"usd_total": capex}},
        debt_result={"debt_total": debt},
        distribution_config=cfg,
    )
    assert amount == pytest.approx(capex - debt)
    assert source == "capex_less_debt"


def test_derive_equity_investment_plus_dsra_at_close() -> None:
    """fund_at_close adds the initial DSRA as an extra equity use at t0."""
    cfg = EquityDistributionConfig()
    capex, debt, dsra = 200.0e6, 120.0e6, 4.0e6
    amount, source = mod._derive_equity_investment_usd(
        config={"capex": {"usd_total": capex}},
        debt_result={
            "debt_total": debt,
            "funding": {"fund_at_close": True, "initial_dsra_usd": dsra},
        },
        distribution_config=cfg,
    )
    assert amount == pytest.approx(capex - debt + dsra)
    assert source == "capex_less_debt_plus_dsra"


# ---------------------------------------------------------------------------
# Pipeline early-exit branches (486, 496, 512)
# ---------------------------------------------------------------------------
def test_pipeline_disabled_short_circuits() -> None:
    """A disabled equity section returns the 'disabled' status payload."""
    result = calculate_equity_distribution_from_pipeline(
        config={"equity_distribution": {"enabled": False, "scenario_name": "off"}},
        annual_rows=[{"year": 1, "cf_pre_debt": 1.0e6}],
        debt_result={},
    )
    assert result["success"] is True
    assert result["status"] == "disabled"
    assert result["scenario_name"] == "off"
    assert result["annual_distributions"] == []


def test_pipeline_empty_rows_fails() -> None:
    """Empty annual_rows is a hard failure (cannot build a schedule)."""
    result = calculate_equity_distribution_from_pipeline(
        config={"capex": {"usd_total": 2.0e8}},
        annual_rows=[],
        debt_result={"debt_total": 1.2e8},
    )
    assert result["success"] is False
    assert result["status"] == "failed"
    assert "annual_rows is empty" in result["error"]


def test_pipeline_undefivable_equity_fails() -> None:
    """No equity investment derivable -> failed with source metadata."""
    result = calculate_equity_distribution_from_pipeline(
        config={},
        annual_rows=[{"year": 1, "cf_pre_debt": 1.0e6}],
        debt_result={},
    )
    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["metadata"]["equity_investment_source"] == "failed"


# ---------------------------------------------------------------------------
# Terminal value branch (535-539) + full pipeline invariants
# ---------------------------------------------------------------------------
def _simple_rows(n: int, cf: float, ds: float) -> List[Dict[str, Any]]:
    return [
        {"year": i + 1, "cf_pre_debt": cf, "debt_service_total": ds} for i in range(n)
    ]


def test_pipeline_terminal_value_added_to_last_year() -> None:
    """terminal_value_usd is added to the final-year distribution exactly once."""
    tv = 9.0e6
    config = {
        "equity_distribution": {
            "scenario_name": "tv-case",
            "equity_investment_usd": 30.0e6,
            "terminal_value_usd": tv,
            "min_dscr_threshold": 0.0,  # never covenant-lock
            "discount_rate": 0.10,
        },
    }
    rows = _simple_rows(5, cf=10.0e6, ds=4.0e6)
    with_tv = calculate_equity_distribution_from_pipeline(
        config=config, annual_rows=rows, debt_result={}
    )

    # Same scenario without terminal value, to isolate the delta.
    cfg_no_tv = {
        "equity_distribution": {
            **config["equity_distribution"],
            "terminal_value_usd": 0.0,
        }
    }
    no_tv = calculate_equity_distribution_from_pipeline(
        config=cfg_no_tv, annual_rows=rows, debt_result={}
    )

    last_with = with_tv["annual_distributions"][-1]
    last_without = no_tv["annual_distributions"][-1]
    assert last_with["terminal_value_usd"] == tv
    # the only change is +tv on the last year's distribution
    assert last_with["equity_distribution_usd"] == pytest.approx(
        last_without["equity_distribution_usd"] + tv
    )
    # total distributed differs by exactly the terminal value
    assert with_tv["equity_summary"]["total_equity_distributed_usd"] == pytest.approx(
        no_tv["equity_summary"]["total_equity_distributed_usd"] + tv
    )


def test_pipeline_waterfall_invariants_hold() -> None:
    """Distributions are non-negative and never exceed CFADS-less-debt-service."""
    config = {
        "equity_distribution": {
            "scenario_name": "inv-case",
            "equity_investment_usd": 30.0e6,
            "min_dscr_threshold": 0.0,
            "discount_rate": 0.08,
        }
    }
    rows = _simple_rows(6, cf=12.0e6, ds=5.0e6)
    result = calculate_equity_distribution_from_pipeline(
        config=config, annual_rows=rows, debt_result={}
    )
    assert result["success"] is True
    assert result["status"] == "computed"
    cf_after_debt = 12.0e6 - 5.0e6
    total_distributed = 0.0
    for row in result["annual_distributions"]:
        # cash flow after debt is conserved
        assert row["cf_after_debt_usd"] == pytest.approx(cf_after_debt)
        # distribution is non-negative
        assert row["equity_distribution_usd"] >= 0.0
        # the terminal release returns reserves built up over PRIOR years and sits on top of
        # this year's operating cash; the OPERATING distribution is still bounded by, and
        # conserves, that year's cash after debt service.
        operating_dist = row["equity_distribution_usd"] - row["terminal_release_usd"]
        assert operating_dist <= cf_after_debt + 1e-6
        assert (
            row["reserve_funded_usd"] + row["retained_cash_usd"] + operating_dist
        ) == pytest.approx(cf_after_debt)
        total_distributed += row["equity_distribution_usd"]
    # Schedule-level conservation: with no seeded DSRA, every dollar of cash-after-debt is
    # ultimately distributed — reserves built up during operations are released at maturity.
    n_years = len(result["annual_distributions"])
    assert total_distributed == pytest.approx(cf_after_debt * n_years)
    # IRR sign: positive distributions on a positive investment -> finite IRR
    summary = result["equity_summary"]
    assert summary["equity_investment_usd"] == 30.0e6
    assert summary["total_equity_distributed_usd"] > 0.0


def test_pipeline_covenant_lock_blocks_distribution() -> None:
    """A DSCR below the threshold locks the covenant and blocks distributions."""
    config = {
        "equity_distribution": {
            "scenario_name": "lock-case",
            "equity_investment_usd": 20.0e6,
            "min_dscr_threshold": 1.50,
            "discount_rate": 0.10,
        }
    }
    # cf/ds = 1.10 < 1.50 -> locked every year
    rows = _simple_rows(4, cf=5.5e6, ds=5.0e6)
    result = calculate_equity_distribution_from_pipeline(
        config=config, annual_rows=rows, debt_result={}
    )
    assert result["equity_summary"]["covenant_locked_years"] == 4
    for row in result["annual_distributions"]:
        assert row["covenant_locked"] is True
        # locked + no balloon shortfall -> zero OPERATING distribution. At the terminal
        # period the reserve built up over the locked years is released to the sponsor, so
        # net the terminal release out before asserting the lock blocked the distribution.
        assert (row["equity_distribution_usd"] - row["terminal_release_usd"]) == 0.0


def test_pipeline_defaulted_status_propagates() -> None:
    """A defaulted equity investment surfaces status='defaulted'."""
    config = {
        "equity_distribution": {
            "scenario_name": "def-case",
            "allow_default_equity_investment": True,
            "default_equity_investment_usd": 15.0e6,
            "min_dscr_threshold": 0.0,
        }
    }
    rows = _simple_rows(3, cf=8.0e6, ds=3.0e6)
    result = calculate_equity_distribution_from_pipeline(
        config=config, annual_rows=rows, debt_result={}
    )
    assert result["status"] == "defaulted"
    assert result["equity_summary"]["equity_investment_source"] == "defaulted"


# ---------------------------------------------------------------------------
# load_config (612-630) + canonical scenario integration
# ---------------------------------------------------------------------------
def test_load_config_canonical_scenario() -> None:
    """The canonical lender YAML loads and passes v14 schema validation."""
    cfg = load_config(LENDER)
    container = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(container, dict)
    assert "project" in container


def test_load_config_rejects_non_mapping_root(tmp_path: Path) -> None:
    """A YAML whose root is a list is rejected with a TypeError."""
    bad = tmp_path / "list_root.yaml"
    bad.write_text("- a\n- b\n")
    with pytest.raises(TypeError):
        load_config(str(bad))


def test_pipeline_from_canonical_scenario_capex_less_debt() -> None:
    """End-to-end on the canonical scenario: equity = CAPEX - debt, distributions valid."""
    from analytics.scenario_loader import load_scenario_config

    cfg = dict(load_scenario_config(LENDER))
    capex = mod._extract_capex_usd(cfg)
    assert capex is not None and capex > 0.0
    debt_total = 0.6 * capex
    rows = _simple_rows(4, cf=20.0e6, ds=8.0e6)
    result = calculate_equity_distribution_from_pipeline(
        config=cfg,
        annual_rows=rows,
        debt_result={"debt_total": debt_total},
    )
    assert result["success"] is True
    summary = result["equity_summary"]
    # equity derived purely from CAPEX less debt
    assert summary["equity_investment_usd"] == pytest.approx(capex - debt_total)
    assert summary["equity_investment_source"] == "capex_less_debt"
    # the result must be JSON-safe
    json.dumps(result)


# ---------------------------------------------------------------------------
# build_equity_distribution_schedule fund-at-close seeding + balloon paths
# ---------------------------------------------------------------------------
def test_schedule_balloon_shortfall_is_cash_call() -> None:
    """A balloon larger than available cash becomes a negative equity CF (cash call)."""
    cfg = EquityDistributionConfig(min_dscr_threshold=0.0, min_reserve_months=0)
    rows = [{"year": 1, "cf_pre_debt": 6.0e6, "debt_service_total": 5.0e6,
             "balloon_resolution": 4.0e6}]
    schedule = build_equity_distribution_schedule(
        annual_rows=rows, debt_result={}, distribution_config=cfg
    )
    row = schedule[0]
    # cash after debt = 1.0M, balloon = 4.0M -> shortfall of 3.0M
    assert row["equity_distribution_usd"] == pytest.approx(-3.0e6)
    assert row["retained_cash_usd"] == 0.0


def test_schedule_fund_at_close_seeds_reserve() -> None:
    """fund_at_close seeds the reserve (no operating top-up when full); it is held during
    operations and RELEASED to the sponsor at the terminal period (Wave-1 fix)."""
    cfg = EquityDistributionConfig(min_dscr_threshold=0.0, min_reserve_months=6)
    rows = [
        {"year": 1, "cf_pre_debt": 10.0e6, "debt_service_total": 4.0e6},
        {"year": 2, "cf_pre_debt": 10.0e6, "debt_service_total": 4.0e6},
    ]
    # reserve required = ds * 6/12 = 2.0M; seed it fully at close
    debt_result = {"funding": {"fund_at_close": True, "initial_dsra_usd": 2.0e6}}
    schedule = build_equity_distribution_schedule(
        annual_rows=rows, debt_result=debt_result, distribution_config=cfg
    )
    # Operating year: reserve already full -> no top-up, balance held at 2.0M, nothing released.
    assert schedule[0]["reserve_funded_usd"] == 0.0
    assert schedule[0]["reserve_balance_usd"] == pytest.approx(2.0e6)
    assert schedule[0]["terminal_release_usd"] == 0.0
    assert schedule[0]["equity_distribution_usd"] == pytest.approx(6.0e6)
    # Terminal year: the seeded DSRA is released to the sponsor, not destroyed.
    assert schedule[-1]["reserve_balance_usd"] == pytest.approx(0.0)
    assert schedule[-1]["terminal_release_usd"] == pytest.approx(2.0e6)
    assert schedule[-1]["equity_distribution_usd"] == pytest.approx(8.0e6)  # 6M op + 2M DSRA


def test_schedule_holdback_retains_cash() -> None:
    """A non-zero holdback moves cash from distribution to retained DURING operations; the
    accumulated retention is released to the sponsor at the terminal period (Wave-1 fix)."""
    cfg = EquityDistributionConfig(
        min_dscr_threshold=0.0,
        min_reserve_months=0,
        distribution_sweep_pct=100.0,
        holdback_pct=20.0,
    )
    rows = [
        {"year": 1, "cf_pre_debt": 10.0e6, "debt_service_total": 4.0e6},
        {"year": 2, "cf_pre_debt": 10.0e6, "debt_service_total": 4.0e6},
    ]
    schedule = build_equity_distribution_schedule(
        annual_rows=rows, debt_result={}, distribution_config=cfg
    )
    cash_for_equity = 6.0e6  # 10 - 4, no reserve
    # Operating year: 20% held back from the distribution, retained in the SPV.
    assert schedule[0]["equity_distribution_usd"] == pytest.approx(cash_for_equity * 0.80)
    assert schedule[0]["retained_cash_usd"] == pytest.approx(cash_for_equity * 0.20)
    assert schedule[0]["terminal_release_usd"] == 0.0
    # Terminal year: both years' holdbacks (2 x 1.2M) are released to the sponsor; nothing lost.
    assert schedule[-1]["terminal_release_usd"] == pytest.approx(2 * cash_for_equity * 0.20)
    assert schedule[-1]["equity_distribution_usd"] == pytest.approx(
        cash_for_equity * 0.80 + 2 * cash_for_equity * 0.20
    )
    # Conservation: every dollar of cash-for-equity reaches the sponsor across the schedule.
    total_dist = sum(r["equity_distribution_usd"] for r in schedule)
    assert total_dist == pytest.approx(2 * cash_for_equity)


# ---------------------------------------------------------------------------
# EquityDistributionEngine.run exception path (773-775)
# ---------------------------------------------------------------------------
def test_engine_run_handles_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """If calculate_distributions blows up, run() returns a failed payload."""
    cfg = OmegaConf.create(
        {"equity": {"scenario_name": "boom", "project_life_years": 3}}
    )
    engine = EquityDistributionEngine(cfg)

    def _boom(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(engine, "calculate_distributions", _boom)
    result = engine.run()
    assert result["success"] is False
    assert result["status"] == "failed"
    assert "synthetic failure" in result["error"]
    assert result["scenario_name"] == "boom"


def test_engine_run_succeeds_and_conserves() -> None:
    """run() builds per-year distributions; senior debt is paid before equity."""
    cfg = OmegaConf.create(
        {
            "equity": {
                "scenario_name": "legacy",
                "project_life_years": 2,
                "annual_distributable_cash_usd": 10.0e6,
                "priority_senior_debt_usd": 5.0e6,
                "priority_mezzanine_usd": 0.0,
                "reserve_fund_pct": 10.0,
            }
        }
    )
    engine = EquityDistributionEngine(cfg)
    result = engine.run()
    assert result["success"] is True
    dists = result["distributions"]["annual_distributions"]
    assert len(dists) == 2
    # year 1: 5M to senior, reserve 10% of 10M = 1M, equity = 4M
    first = dists[0]
    assert first["senior_debt_dist_usd"] == 5.0e6
    assert first["reserve_fund_usd"] == 1.0e6
    assert first["equity_distribution_usd"] == 4.0e6
    # year 2: senior fully repaid -> more equity than year 1
    second = dists[1]
    assert second["senior_debt_dist_usd"] == 0.0
    assert second["equity_distribution_usd"] >= first["equity_distribution_usd"]


# ---------------------------------------------------------------------------
# main() CLI entry point (792-816)
# ---------------------------------------------------------------------------
def _write_equity_yaml(tmp_path: Path, *, life: int = 2) -> str:
    cfg = {
        "project": {"name": "cli-case", "life_years": life},
        "capex": {"usd_total": 2.0e8},
        "cashflow": {"enabled": True},
        "debt": {"principal_usd": 1.2e8},
        "equity": {
            "scenario_name": "cli-case",
            "project_life_years": life,
            "annual_distributable_cash_usd": 10.0e6,
            "priority_senior_debt_usd": 5.0e6,
            "priority_mezzanine_usd": 0.0,
            "reserve_fund_pct": 10.0,
        },
    }
    path = tmp_path / "equity_cli.yaml"
    OmegaConf.save(OmegaConf.create(cfg), str(path))
    return str(path)


def test_main_writes_json_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """main() loads a config, runs the engine, and emits valid JSON to stdout."""
    # Bypass v14 schema validation for this minimal standalone equity config.
    monkeypatch.setattr(mod, "validate_config_for_v14", lambda **_kwargs: None)
    path = _write_equity_yaml(tmp_path)
    main(path)
    out = capsys.readouterr().out
    payload = json.loads(out.strip())
    assert payload["success"] is True
    assert payload["scenario_name"] == "cli-case"


def test_main_reraises_and_reports_on_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing config path makes main() emit an error payload and re-raise."""
    missing = str(tmp_path / "does_not_exist.yaml")
    with pytest.raises(Exception):
        main(missing)
    out = capsys.readouterr().out
    payload = json.loads(out.strip())
    assert payload["success"] is False
    assert payload["status"] == "failed"
    assert "error" in payload
