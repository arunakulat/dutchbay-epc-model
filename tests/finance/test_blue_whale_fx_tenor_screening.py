"""Tests for Blue Whale dual-currency financing, FX, and tenor-tail screening.

Includes exact reproduction of the 11 unit test cases from the 2026-11-14 research
handoff (BW-FIN-COST-20261114, v1.0), exact benchmark reproduction of the 15-year
and 10-year debt sizing calculations, fixed-debt FX shock stress tests, TEST-01
independent closed-form oracles, monotonicity invariants, and Hydra CLI smoke test.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.finance.blue_whale_fx_tenor_screening import (
    amortize_tranche,
    annuity,
    complete_total,
    compute_coverage_metrics,
    compute_fx_cagr,
    compute_fx_history_metrics,
    energy_scaled_price,
    evaluate_dual_currency_screening,
    run_comprehensive_screening,
    run_fixed_debt_stress,
    size_debt_screening,
    validate_debt_tenor_against_ppa,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "conf" / "blue_whale_fx_tenor_screening.yaml"


@pytest.fixture(scope="module")
def screening_cfg() -> Dict[str, Any]:
    """Load configuration from conf/blue_whale_fx_tenor_screening.yaml."""
    raw = yaml.safe_load(CONFIG_PATH.read_text())
    params = raw["screening_parameters"]
    case15 = raw["cases"]["15"]
    return {**params, **case15}


# ==============================================================================
# Part 1: Exact reproduction of the 11 unit tests from the research handoff
# ==============================================================================


def test_zero_rate() -> None:
    """Zero-interest repayment must equal principal divided by tenor."""
    assert annuity(100.0, 0.0, 10) == 10.0


def test_present_value_oracle() -> None:
    """Discounted payments independently recover original principal (TEST-01)."""
    p, r, n = 26_331_000.0, 0.084, 15
    a = annuity(p, r, n)
    pv = sum(a / (1.0 + r) ** t for t in range(1, n + 1))
    assert math.isclose(pv, p, rel_tol=1e-6)


def test_principal_conservation() -> None:
    """Each tranche fully repays with no negative balance or hidden balloon."""
    for p, r, n in [(1e6, 0.084, 15), (20e9, 0.1276, 10), (100.0, 0.0, 3)]:
        rows = amortize_tranche(p, r, n)
        assert math.isclose(sum(x["principal"] for x in rows), p, rel_tol=1e-11)
        assert rows[-1]["closing"] == 0.0
        assert all(x["closing"] >= 0.0 for x in rows)


def test_dual_currency_translation(screening_cfg: Dict[str, Any]) -> None:
    """With zero FX change, currency-normalized service equals tranche sums."""
    c = {**screening_cfg, "fx_depreciation_decimal": 0.0, "fx_shock_decimal": 0.0}
    d = 80e6
    first = evaluate_dual_currency_screening(c, d)[0]
    expected = annuity(d * 0.3, 0.084, 15) * 333.79 + annuity(
        d * 0.7 * 333.79, 0.1276, 10
    )
    assert math.isclose(first["debt_service_lkr"], expected, rel_tol=1e-5)


def test_cash_waterfall(screening_cfg: Dict[str, Any]) -> None:
    """CFADS reconciles to revenue minus expenses, fees, and cash tax."""
    for r in evaluate_dual_currency_screening(screening_cfg, 80e6):
        expected_cfads = (
            r["revenue_lkr"] - r["opex_lkr"] - r["credit_fee_lkr"] - r["tax_lkr"]
        )
        assert math.isclose(r["cfads_lkr"], expected_cfads, rel_tol=1e-5)


def test_sizing_boundary_and_response(screening_cfg: Dict[str, Any]) -> None:
    """Debt passes floors and a material increase fails a coverage or gearing bound."""
    result = size_debt_screening(screening_cfg)
    assert result["debt_usd"] > 0
    assert result["p50"]["min_dscr"] >= 1.3 - 1e-9
    assert result["p90"]["min_dscr"] >= 1.1 - 1e-9

    larger = result["debt_usd"] * 1.001
    m50 = compute_coverage_metrics(
        evaluate_dual_currency_screening(screening_cfg, larger), 10
    )
    m90 = compute_coverage_metrics(
        evaluate_dual_currency_screening(screening_cfg, larger, True), 10
    )
    assert (
        larger > screening_cfg["capex_usd"] * 0.7
        or m50["min_dscr"] < 1.3
        or m90["min_dscr"] < 1.1
        or m50["first_local_average_dscr"] < 1.5
    )


def test_fx_and_resource_response(screening_cfg: Dict[str, Any]) -> None:
    """Higher USD/LKR drift and lower generation reduce capacity in this test case."""
    base = size_debt_screening(screening_cfg)["debt_usd"]
    stressed_fx = size_debt_screening(
        {**screening_cfg, "fx_depreciation_decimal": 0.1068}
    )["debt_usd"]
    assert stressed_fx < base

    derated_gen = size_debt_screening(
        {
            **screening_cfg,
            "p50_gwh": screening_cfg["p50_gwh"] * 0.9,
            "p90_gwh": screening_cfg["p90_gwh"] * 0.9,
        }
    )["debt_usd"]
    assert derated_gen < base


def test_ppa_maturity_gate(screening_cfg: Dict[str, Any]) -> None:
    """Fifteen-year debt cannot pass a twelve-year contracted PPA gate."""
    with pytest.raises(
        ValueError, match="Debt maturity exceeds contracted revenue less lender tail"
    ):
        evaluate_dual_currency_screening({**screening_cfg, "ppa_years": 12}, 80e6)


def test_fx_reciprocal_and_cagr() -> None:
    """The quote increase and currency-value decrease are distinct measures."""
    q = 363.11 / 200.43 - 1.0
    depreciation = 1.0 - 200.43 / 363.11
    assert math.isclose(q, 0.81165494187497, rel_tol=1e-10)
    assert math.isclose((1.0 + q) * (1.0 - depreciation), 1.0, rel_tol=1e-12)
    assert math.isclose(
        compute_fx_cagr(100.0, 121.0, "2020-01-01", "2022-01-01"), 0.1, abs_tol=1e-4
    )


def test_unknown_costs_fail_closed() -> None:
    """Missing costs remain unknown and cannot create false zero-price totals."""
    assert complete_total({"oem": None, "marine": 100.0}) is None
    assert complete_total({"oem": 100.0, "marine": 20.0}) == 120.0
    with pytest.raises(
        ValueError, match="Costs must be finite nonnegative amounts or None"
    ):
        complete_total({"cost": -1.0})


def test_hypothetical_energy_scaling() -> None:
    """Shared life factors cancel; changing AEP does not validate a supplier price."""
    assert energy_scaled_price(100.0, 200.0, 80.0) == 40.0
    assert energy_scaled_price(100.0, 200.0 * 20.0, 80.0 * 20.0) == 40.0


# ==============================================================================
# Part 2: Exact benchmark reproduction of sized debt and coverage metrics
# ==============================================================================


def test_reconstructed_selected_15year_reproduction(
    screening_cfg: Dict[str, Any],
) -> None:
    """Verify exact sizing matching reconstructed_selected_15year.json."""
    c = {
        **screening_cfg,
        "dfi_share": 0.3,
        "fx_depreciation_decimal": 0.07,
        "tariff_om_escalation_decimal": 0.0,
    }
    result = size_debt_screening(c)
    # Expected: 80,770,761.78 USD, gearing 48.12%
    assert math.isclose(result["debt_usd"], 80_770_761.77699926, rel_tol=1e-5)
    assert math.isclose(result["gearing_decimal"], 0.4811793266829457, rel_tol=1e-5)
    assert math.isclose(result["p50"]["min_dscr"], 1.30, abs_tol=1e-6)
    assert result["p50"]["binding_year"] == 10
    assert math.isclose(result["p90"]["min_dscr"], 1.11189665, rel_tol=1e-4)


def test_reconstructed_selected_10year_reproduction(
    screening_cfg: Dict[str, Any],
) -> None:
    """Verify exact sizing matching reconstructed_selected_10year.json."""
    c = {
        **screening_cfg,
        "dfi_share": 0.3,
        "fx_depreciation_decimal": 0.07,
        "tariff_om_escalation_decimal": 0.0,
        "dfi_tenor_years": 10,
        "ppa_years": 12,
        "lender_tail_years": 2,
    }
    result = size_debt_screening(c)
    # Expected: 72,421,933.82 USD, gearing 43.14%
    assert math.isclose(result["debt_usd"], 72_421_933.82084577, rel_tol=1e-5)
    assert math.isclose(result["gearing_decimal"], 0.43144247480546744, rel_tol=1e-5)
    assert math.isclose(result["p50"]["min_dscr"], 1.30, abs_tol=1e-6)
    assert result["p50"]["binding_year"] == 10
    assert math.isclose(result["p90"]["min_dscr"], 1.10919058, rel_tol=1e-4)


def test_fixed_debt_fx_shock_binding_year_shift(screening_cfg: Dict[str, Any]) -> None:
    """At high FX depreciation (10.68%), USD tranche inflation shifts binding year from 10 to 15."""
    c = {
        **screening_cfg,
        "dfi_share": 0.3,
        "tariff_om_escalation_decimal": 0.0,
    }
    # At 7% drift, year 10 binds
    m_7pct = compute_coverage_metrics(
        evaluate_dual_currency_screening(
            {**c, "fx_depreciation_decimal": 0.07, "fx_shock_decimal": 0.0},
            87_770_000.0,
        ),
        10,
    )
    assert m_7pct["binding_year"] == 10
    assert math.isclose(m_7pct["min_dscr"], 1.19924099, rel_tol=1e-4)

    # At 10.68% drift, year 15 binds (DFI service inflated by compounded LKR/USD)
    m_1068pct = compute_coverage_metrics(
        evaluate_dual_currency_screening(
            {**c, "fx_depreciation_decimal": 0.1068, "fx_shock_decimal": 0.0},
            87_770_000.0,
        ),
        10,
    )
    assert m_1068pct["binding_year"] == 15
    assert math.isclose(m_1068pct["min_dscr"], 0.76100181, rel_tol=1e-4)


# ==============================================================================
# Part 3: Invariant & Guard Checks (TEST-01, CASPER, CCCDIR)
# ==============================================================================


def test_annuity_closed_form_independent_oracle() -> None:
    """Independent oracle: level payment formula P * r * (1+r)^n / ((1+r)^n - 1)."""
    p, r, n = 50_000_000.0, 0.065, 12
    expected = p * (r * (1.0 + r) ** n) / ((1.0 + r) ** n - 1.0)
    actual = annuity(p, r, n)
    assert math.isclose(actual, expected, rel_tol=1e-12)


def test_annuity_guard_rails() -> None:
    """Annuity strictly refuses invalid loan parameters."""
    with pytest.raises(ValueError, match="Nonfinite loan input"):
        annuity(float("nan"), 0.05, 10)
    with pytest.raises(ValueError, match="Nonfinite loan input"):
        annuity(100.0, float("inf"), 10)
    with pytest.raises(ValueError, match="Loan requires nonnegative"):
        annuity(-100.0, 0.05, 10)
    with pytest.raises(ValueError, match="Loan requires nonnegative"):
        annuity(100.0, -0.05, 10)
    with pytest.raises(ValueError, match="Loan requires nonnegative"):
        annuity(100.0, 0.05, 0)


def test_tenor_tail_guards() -> None:
    """validate_debt_tenor_against_ppa rejects tenor violations and invalid inputs."""
    # Valid: 15-year debt in 20-year PPA with 2-year tail (15 <= 20 - 2 = 18)
    assert validate_debt_tenor_against_ppa(15, 10, 20, 2) == 15

    # Boundary: 15-year debt in 20-year PPA with 5-year tail (15 <= 20 - 5 = 15)
    assert validate_debt_tenor_against_ppa(15, 10, 20, 5) == 15

    # Violation: 15-year debt in 20-year PPA with 6-year tail (15 > 20 - 6 = 14)
    with pytest.raises(ValueError, match="Debt maturity exceeds contracted revenue"):
        validate_debt_tenor_against_ppa(15, 10, 20, 6)

    # Violation: local tenor 12 > PPA 12 - tail 1 = 11
    with pytest.raises(ValueError, match="Debt maturity exceeds contracted revenue"):
        validate_debt_tenor_against_ppa(10, 12, 12, 1)

    # Invalid arguments
    with pytest.raises(ValueError, match="Tenor and PPA years must be positive"):
        validate_debt_tenor_against_ppa(0, 10, 20, 2)
    with pytest.raises(ValueError, match="Lender tail years must be non-negative"):
        validate_debt_tenor_against_ppa(10, 10, 20, -1)


def test_fx_cagr_guards() -> None:
    """compute_fx_cagr rejects non-positive rates and non-chronological dates."""
    with pytest.raises(ValueError, match="Positive FX observations"):
        compute_fx_cagr(0.0, 300.0, "2021-01-01", "2022-01-01")
    with pytest.raises(ValueError, match="Positive FX observations"):
        compute_fx_cagr(200.0, -300.0, "2021-01-01", "2022-01-01")
    with pytest.raises(ValueError, match="Positive FX observations"):
        compute_fx_cagr(200.0, 300.0, "2022-01-01", "2021-01-01")


def test_monotonicity_invariants(screening_cfg: Dict[str, Any]) -> None:
    """TEST-01 Monotonicity invariants: debt capacity and DSCR respond in the expected direction."""
    c = {**screening_cfg, "dfi_share": 0.3, "tariff_om_escalation_decimal": 0.0}

    # Invariant 1: Sized debt is strictly decreasing as FX depreciation rate increases
    rates = [0.0, 0.03, 0.07, 0.1068]
    debts = [
        size_debt_screening({**c, "fx_depreciation_decimal": r})["debt_usd"]
        for r in rates
    ]
    for i in range(len(debts) - 1):
        assert (
            debts[i] > debts[i + 1]
        ), f"Debt at rate {rates[i]} not > debt at {rates[i+1]}"

    # Invariant 2: DSCR at any given operating year is monotonically decreasing in FX shock
    shocks = [0.0, 0.1, 0.2, 0.3]
    fixed_debt = 80e6
    dscrs_yr5 = [
        evaluate_dual_currency_screening(
            {**c, "fx_shock_decimal": s, "shock_operating_year": 5}, fixed_debt
        )[4]["dscr"]
        for s in shocks
    ]
    for i in range(len(dscrs_yr5) - 1):
        assert (
            dscrs_yr5[i] > dscrs_yr5[i + 1]
        ), f"DSCR at shock {shocks[i]} not > DSCR at {shocks[i+1]}"


def test_unfinanceable_negative_cfads(screening_cfg: Dict[str, Any]) -> None:
    """size_debt_screening returns 0 debt and unfinanceable status when unlevered CFADS < 0."""
    # Drastically reduce tariff to make project unfinanceable
    unfinanceable_cfg = {
        **screening_cfg,
        "tariff_fixed_lkr_per_kwh": 1.0,
        "tariff_om_lkr_per_kwh": 0.1,
    }
    result = size_debt_screening(unfinanceable_cfg)
    assert result["debt_usd"] == 0.0
    assert result["gearing_decimal"] == 0.0
    assert result["status"] == "unfinanceable_negative_debt_life_unlevered_cfads"


def test_fx_history_enrichment() -> None:
    """compute_fx_history_metrics computes quote change and rupee depreciation."""
    obs = [
        {"date": "2021-12-31", "lkr_per_usd": 200.43},
        {"date": "2022-12-31", "lkr_per_usd": 363.11},
    ]
    enriched = compute_fx_history_metrics(obs)
    assert enriched[0]["quote_change_decimal"] is None
    assert math.isclose(enriched[1]["quote_change_decimal"], 363.11 / 200.43 - 1.0)
    assert math.isclose(
        enriched[1]["lkr_value_depreciation_decimal"], 1.0 - 200.43 / 363.11
    )


# ==============================================================================
# Part 4: Hydra CLI integration smoke test
# ==============================================================================


def test_run_comprehensive_screening_direct() -> None:
    """Directly test run_comprehensive_screening helper."""
    raw = yaml.safe_load(CONFIG_PATH.read_text())
    result = run_comprehensive_screening(raw)
    assert result["schema_version"] == "blue_whale_fx_tenor_screening_v1"
    assert result["status"] == "complete"
    assert len(result["fx_metrics"]) == 3
    assert result["fixed_debt_fx_stress_count"] == 21


def test_run_fixed_debt_stress_direct(screening_cfg: Dict[str, Any]) -> None:
    """Directly test run_fixed_debt_stress helper."""
    results = run_fixed_debt_stress(
        screening_cfg, 87_770_000.0, [0.0589, 0.07], [0.0, 0.2]
    )
    assert len(results) == 4
    assert all("min_dscr" in r for r in results)


def test_hydra_cli_smoke() -> None:
    """Invoke run_blue_whale_fx_tenor_screening_v14.py via subprocess and verify JSON stdout."""
    script_path = REPO_ROOT / "scripts" / "run_blue_whale_fx_tenor_screening_v14.py"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "blue_whale_fx_tenor_screening_v1"
    assert payload["status"] == "complete"
    assert "fx_metrics" in payload
    assert "selected_15year_screening" in payload
    assert "selected_10year_screening" in payload
    assert payload["fixed_debt_fx_stress_count"] == 21
    assert math.isclose(
        payload["selected_15year_screening"]["debt_usd"], 80_770_761.78, rel_tol=1e-5
    )
    assert math.isclose(
        payload["selected_10year_screening"]["debt_usd"], 72_421_933.82, rel_tol=1e-5
    )
