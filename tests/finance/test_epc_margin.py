"""Tests for ``finance.epc_margin`` — EPC construction-margin economics.

Pins the Kolonnawa-style EPC supply model: a construction margin (price − cost) over a
construction period, with the contractor's working-capital need and (when defined) an
annualised construction IRR — a SEPARATE model from the operational v14 cashflow engine.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from finance.epc_margin import EpcMarginResult, compute_epc_margin

_REPO = Path(__file__).resolve().parents[2]
_SCENARIO = _REPO / "scenarios" / "kolonnawa_epc_100mw.yaml"


def _epc(**overrides) -> dict:
    epc = {
        "contract_value_usd": 100.0,
        "cost": {"a": 50.0, "b": 30.0},  # total 80
        "construction_months": 12,
    }
    epc.update(overrides)
    return {"epc": epc}


# ── margin maths ────────────────────────────────────────────────────────────────


def test_margin_and_returns():
    r = compute_epc_margin(_epc())
    assert isinstance(r, EpcMarginResult)
    assert r.contract_value == 100.0
    assert r.total_cost == 80.0
    assert r.gross_margin == pytest.approx(20.0)
    assert r.gross_margin_pct == pytest.approx(0.20)  # 20 / 100
    assert r.return_on_cost_pct == pytest.approx(0.25)  # 20 / 80


def test_cost_sums_every_category():
    r = compute_epc_margin(_epc(cost={"x": 10.0, "y": 20.0, "z": 5.0}))
    assert r.total_cost == pytest.approx(35.0)


def test_even_spread_when_no_schedules():
    # With no payment_schedule AND no cost_schedule, BOTH spread evenly over months
    # 1..12; net per month is (value - cost)/months, and month 0 (signing) is 0.
    r = compute_epc_margin(_epc())
    assert r.monthly_net_cashflow[0] == pytest.approx(0.0)
    assert len(r.monthly_net_cashflow) == 13  # month 0..12
    assert r.monthly_net_cashflow[1] == pytest.approx((100.0 - 80.0) / 12)
    assert sum(r.monthly_net_cashflow) == pytest.approx(r.gross_margin)


def test_peak_working_capital_with_back_loaded_payment():
    # all payment at month 12, cost even over 1..12 -> contractor funds the whole cost
    r = compute_epc_margin(_epc(payment_schedule=[{"month": 12, "pct": 1.0}]))
    assert r.peak_working_capital == pytest.approx(80.0 * 11 / 12)  # cumulative cost by month 11


def test_construction_irr_defined_when_investment_first():
    # cost-first then a single back-loaded receipt -> a real IRR exists
    r = compute_epc_margin(_epc(payment_schedule=[{"month": 12, "pct": 1.0}]))
    assert r.annualized_irr is not None
    assert r.annualized_irr > 0  # margin positive over the build


def test_full_advance_is_fully_prefunded():
    # a 100% advance at month 0 means the contractor never funds working capital
    r = compute_epc_margin(_epc(payment_schedule=[{"month": 0, "pct": 1.0}]))
    assert r.peak_working_capital == pytest.approx(0.0)
    assert r.gross_margin == pytest.approx(20.0)  # margin is timing-independent


# ── fail-loud validation ──────────────────────────────────────────────────────


def test_missing_epc_block_raises():
    with pytest.raises(ValueError, match="no 'epc' block"):
        compute_epc_margin({"project": {}})


@pytest.mark.parametrize("bad", [0, -10, float("nan"), float("inf"), "x"])
def test_non_positive_contract_value_raises(bad):
    with pytest.raises(ValueError, match="contract_value_usd"):
        compute_epc_margin(_epc(contract_value_usd=bad))


def test_empty_cost_raises():
    with pytest.raises(ValueError, match="epc.cost"):
        compute_epc_margin(_epc(cost={}))


@pytest.mark.parametrize("months", [0, -3, 1.5, "x"])
def test_bad_construction_months_raises(months):
    with pytest.raises(ValueError, match="construction_months"):
        compute_epc_margin(_epc(construction_months=months))


def test_payment_schedule_must_sum_to_one():
    with pytest.raises(ValueError, match="sum to"):
        compute_epc_margin(_epc(payment_schedule=[{"month": 0, "pct": 0.5}]))  # 0.5 != 1


def test_payment_month_out_of_range_raises():
    with pytest.raises(ValueError, match="month"):
        compute_epc_margin(_epc(payment_schedule=[{"month": 99, "pct": 1.0}]))  # > 12


# ── scenario + CLI ─────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _SCENARIO.exists(), reason="Kolonnawa EPC scenario not present")
def test_kolonnawa_scenario():
    import yaml

    config = yaml.safe_load(_SCENARIO.read_text())
    r = compute_epc_margin(config)
    assert r.total_cost == pytest.approx(48_000_000)
    assert r.gross_margin == pytest.approx(6_000_000)
    assert r.peak_working_capital > 0  # the contractor funds working capital mid-build


@pytest.mark.skipif(not _SCENARIO.exists(), reason="Kolonnawa EPC scenario not present")
def test_cli_runs(capsys):
    spec = importlib.util.spec_from_file_location(
        "run_epc_margin", _REPO / "scripts" / "run_epc_margin.py"
    )
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    spec.loader.exec_module(cli)
    rc = cli.main(["--config", str(_SCENARIO)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Gross margin" in out
    assert "Peak working capital" in out
