"""#1403: ``project.first_year_grid_unavailable_months``, the partial-year grid lever.

The lever is the months of the first operating year in which the plant is ready but
cannot export because its grid connection is not. It scales operating-year-1 energy
by ``1 - months / 12`` and nothing else. It is default-off: absent, or present at 0,
every committed scenario's cash flows are byte-identical.
"""

from __future__ import annotations

import copy
import math
import warnings
from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.cashflow_v14_params import _build_cashflow_params
from finance.cashflow_v14_production import calculate_net_production_for_year

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
BESS = REPO_ROOT / "scenarios" / "ceb_bess_10mw_capacity_charge.yaml"


def _rows(config: Dict[str, Any]) -> List[Dict[str, float]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_annual_rows(copy.deepcopy(config))


@pytest.fixture(scope="module")
def lender() -> Dict[str, Any]:
    return load_scenario_config(LENDER)


@pytest.fixture(scope="module")
def lender_rows(lender: Dict[str, Any]) -> List[Dict[str, float]]:
    return _rows(lender)


def _with_months(config: Dict[str, Any], months: Any) -> Dict[str, Any]:
    out = copy.deepcopy(config)
    out["project"]["first_year_grid_unavailable_months"] = months
    return out


def test_explicit_zero_is_byte_identical_to_absent(
    lender: Dict[str, Any], lender_rows: List[Dict[str, float]]
) -> None:
    assert "first_year_grid_unavailable_months" not in lender["project"]
    rows = _rows(_with_months(lender, 0))
    assert [r["cfads_usd"].hex() for r in rows] == [
        r["cfads_usd"].hex() for r in lender_rows
    ]
    assert rows == lender_rows


def test_six_months_halves_year_one_energy_and_leaves_later_years_alone(
    lender: Dict[str, Any], lender_rows: List[Dict[str, float]]
) -> None:
    rows = _rows(_with_months(lender, 6))
    assert rows[0]["net_kwh"] == pytest.approx(
        0.5 * lender_rows[0]["net_kwh"], rel=1e-15
    )
    assert rows[0]["gross_kwh"] == pytest.approx(
        0.5 * lender_rows[0]["gross_kwh"], rel=1e-15
    )
    assert rows[0]["generation_revenue_lkr"] < lender_rows[0]["generation_revenue_lkr"]
    assert rows[0]["opex_lkr"] == lender_rows[0]["opex_lkr"]
    for new, old in zip(rows[1:], lender_rows[1:], strict=True):
        assert new["net_kwh"] == old["net_kwh"]
        assert new["generation_revenue_lkr"] == old["generation_revenue_lkr"]


@pytest.mark.parametrize("months", [3, 9, 11.5])
def test_production_scales_year_one_by_the_unavailable_share(
    lender: Dict[str, Any], months: float
) -> None:
    from dataclasses import asdict

    base = asdict(_build_cashflow_params(lender))
    delayed = asdict(_build_cashflow_params(_with_months(lender, months)))
    g0, n0 = calculate_net_production_for_year(base, 0)
    g1, n1 = calculate_net_production_for_year(delayed, 0)
    share = 1.0 - months / 12.0
    assert n1 == pytest.approx(n0 * share, rel=1e-15)
    assert g1 == pytest.approx(g0 * share, rel=1e-15)
    assert calculate_net_production_for_year(delayed, 1) == (
        calculate_net_production_for_year(base, 1)
    )


@pytest.mark.parametrize("months", [12, 13, -1, math.nan, math.inf, "6", True])
def test_a_value_outside_zero_to_twelve_is_refused(
    lender: Dict[str, Any], months: Any
) -> None:
    with pytest.raises(ValueError, match="first_year_grid_unavailable_months"):
        _build_cashflow_params(_with_months(lender, months))


def test_the_lever_is_refused_with_a_bess_capacity_charge() -> None:
    config = load_scenario_config(BESS)
    config.setdefault("project", {})["first_year_grid_unavailable_months"] = 6
    with pytest.raises(ValueError, match="type: bess"):
        _rows(config)
