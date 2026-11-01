"""The project discount rate is a required scenario input, never a code default (#1429).

The engine used to discount every scenario that did not opt its WACC in
(``wacc.drives_discount_rate``) at a hard-coded ``DEFAULT_DISCOUNT_RATE = 0.10``. It did so
whatever the scenario declared: ``scenarios/edge_extreme_stress.yaml`` says
``returns.project_discount_rate: 0.12`` and was discounted at 0.10. The programme in #1429
moves every project-specific figure into YAML, so these tests pin:

* the code default is gone from ``analytics.core.metrics`` and from the pipeline;
* ``returns.project_discount_rate`` is required and validated by one resolver, which the
  v14 pre-flight and the KPI pass share, and a refusal names the path;
* the pipeline discounts at the declared rate when the WACC does not drive, and falls back
  to it, not to 0.10, when a driving WACC resolves no ``wacc_nominal``;
* the KPI surface refuses a call that gives neither a rate nor a config that declares one.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict

import pytest

import analytics.core.metrics as metrics
import analytics.pipeline_v14_enhanced as pipeline
from analytics.core.metrics import (
    PROJECT_DISCOUNT_RATE_PATH,
    calculate_scenario_kpis,
    resolve_project_discount_rate,
)
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
STRESS_CONFIG = REPO_ROOT / "scenarios" / "edge_extreme_stress.yaml"


def _raw(path: Path) -> Dict[str, Any]:
    from analytics.scenario_loader import load_scenario_config

    return copy.deepcopy(dict(load_scenario_config(str(path))))


def _returns(value: Any) -> Dict[str, Any]:
    return {"returns": {"project_discount_rate": value}}


# --------------------------------------------------------------------------- #
# No code default
# --------------------------------------------------------------------------- #
def test_the_code_default_is_gone() -> None:
    assert not hasattr(metrics, "DEFAULT_DISCOUNT_RATE")
    assert not hasattr(pipeline, "DEFAULT_DISCOUNT_RATE")
    assert PROJECT_DISCOUNT_RATE_PATH == "returns.project_discount_rate"


# --------------------------------------------------------------------------- #
# The resolver: YAML or refusal
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", [0.0, 0.07, 0.10, 0.12, "0.12", 0.999])
def test_a_declared_rate_is_read_as_a_fraction(value: Any) -> None:
    assert resolve_project_discount_rate(_returns(value)) == float(value)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (None, "is required"),
        ({}, "is required"),
        ({"returns": None}, "is required"),
        ({"returns": {}}, "is required"),
        (_returns(None), "is required"),
        (_returns(True), "not a boolean"),
        (_returns("ten percent"), "must be a number"),
        (_returns([0.1]), "must be a number"),
        (_returns(math.nan), r"finite fraction in \[0, 1\)"),
        (_returns(math.inf), r"finite fraction in \[0, 1\)"),
        (_returns(-0.01), r"finite fraction in \[0, 1\)"),
        (_returns(1.0), r"finite fraction in \[0, 1\)"),
        # A percentage written where a fraction belongs is refused, not divided by 100.
        (_returns(10), r"finite fraction in \[0, 1\)"),
    ],
)
def test_a_missing_or_invalid_rate_is_refused_by_path(
    config: Any, message: str
) -> None:
    with pytest.raises(ValueError, match=message) as excinfo:
        resolve_project_discount_rate(config)
    assert "returns.project_discount_rate" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Pre-flight
# --------------------------------------------------------------------------- #
def test_preflight_passes_the_committed_lender_case() -> None:
    validate_config_for_v14(_raw(LENDER_CONFIG), "lendercase", ["cashflow", "debt"])


def test_preflight_refuses_a_scenario_without_a_rate() -> None:
    """Negative control: delete the field from the committed lender case."""
    raw = _raw(LENDER_CONFIG)
    del raw["returns"]["project_discount_rate"]
    with pytest.raises(
        ConfigValidationError, match=r"returns\.project_discount_rate is required"
    ):
        validate_config_for_v14(raw, "lendercase", ["cashflow", "debt"])


def test_preflight_refuses_a_rate_even_when_the_wacc_drives() -> None:
    """The field is required on every scenario, not only on those whose WACC is
    informational: a driving WACC falls back to it when it resolves no rate."""
    raw = _raw(LENDER_CONFIG)
    assert raw["wacc"]["drives_discount_rate"] is True
    raw["returns"]["project_discount_rate"] = 12
    with pytest.raises(ConfigValidationError, match=r"returns\.project_discount_rate"):
        validate_config_for_v14(raw, "lendercase", ["cashflow", "debt"])


def test_a_validation_that_computes_no_cashflow_does_not_ask_for_a_rate() -> None:
    """Scope: only a ``cashflow`` validation discounts. An FX-only check (no modules)
    is not asked for a rate, so the guard does not leak into unrelated validators."""
    raw = _raw(LENDER_CONFIG)
    del raw["returns"]["project_discount_rate"]
    validate_config_for_v14(raw, "lendercase", [])


def test_the_pipeline_refuses_a_scenario_without_a_rate() -> None:
    raw = _raw(LENDER_CONFIG)
    del raw["returns"]["project_discount_rate"]
    with pytest.raises(Exception, match=r"returns\.project_discount_rate is required"):
        pipeline.run_v14_pipeline(config=raw)


# --------------------------------------------------------------------------- #
# The pipeline discounts at the declared rate
# --------------------------------------------------------------------------- #
def test_a_non_driving_scenario_is_discounted_at_its_declared_rate() -> None:
    """edge_extreme_stress declares 0.12 and does not opt its WACC in. Before #1429 it
    was discounted at 0.10."""
    kpis = evaluate_with_overrides(str(STRESS_CONFIG), overrides={})
    assert kpis["discount_rate_used"] == 0.12
    assert not kpis["wacc_is_real"]


@pytest.mark.parametrize("declared", [0.07, 0.135])
def test_the_declared_rate_moves_the_npv(declared: float) -> None:
    """Responsiveness: the lender case with its WACC switched off follows whatever rate
    it declares, so no constant can be standing in for the input."""
    overrides = {
        "wacc.drives_discount_rate": False,
        "returns.project_discount_rate": declared,
    }
    kpis = evaluate_with_overrides(str(LENDER_CONFIG), overrides=overrides)
    assert kpis["discount_rate_used"] == declared
    at_ten = evaluate_with_overrides(
        str(LENDER_CONFIG),
        overrides={**overrides, "returns.project_discount_rate": 0.10},
    )
    # A higher rate discounts the same positive operating CFADS harder.
    if declared > 0.10:
        assert kpis["project_npv"] < at_ten["project_npv"]
    else:
        assert kpis["project_npv"] > at_ten["project_npv"]


def test_a_driving_wacc_without_a_rate_falls_back_to_the_declared_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "compute_wacc_from_config",
        lambda cfg: {"mode": "capm", "wacc_nominal": None, "cost_of_equity": None},
    )
    config = {
        "wacc": {"drives_discount_rate": True, "mode": "capm"},
        "returns": {"project_discount_rate": 0.0875},
    }
    _, project_discount, equity_discount = pipeline._resolve_wacc_and_discounts(
        config, {}
    )
    assert project_discount == 0.0875
    assert equity_discount is None


def test_a_driving_wacc_with_a_rate_still_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "compute_wacc_from_config",
        lambda cfg: {"mode": "capm", "wacc_nominal": 0.1111, "cost_of_equity": 0.15},
    )
    config = {
        "wacc": {"drives_discount_rate": True, "mode": "capm"},
        "returns": {"project_discount_rate": 0.0875},
    }
    _, project_discount, equity_discount = pipeline._resolve_wacc_and_discounts(
        config, {}
    )
    assert project_discount == 0.1111
    assert equity_discount == 0.15


# --------------------------------------------------------------------------- #
# The KPI surface
# --------------------------------------------------------------------------- #
def test_the_kpi_surface_refuses_to_assume_a_rate() -> None:
    with pytest.raises(ValueError, match=r"returns\.project_discount_rate is required"):
        calculate_scenario_kpis(cfads_series_usd=[1.0])


def test_the_kpi_surface_reads_the_rate_from_config() -> None:
    kpis = calculate_scenario_kpis(config=_returns(0.083), cfads_series_usd=[1.0])
    assert kpis["discount_rate_used"] == 0.083


def test_an_explicit_rate_wins_over_the_config() -> None:
    kpis = calculate_scenario_kpis(
        config=_returns(0.083), cfads_series_usd=[1.0], discount_rate=0.05
    )
    assert kpis["discount_rate_used"] == 0.05
