"""Regression: the WACC reporting surface must not contradict the rate used.

Two confirmed defects this guards against:
  * wacc-1: ``ScenarioResult.discount_rate_used`` was hardcoded to the legacy
    0.10 while the engine discounted the project NPV at the ~0.0819 build-up
    WACC — the dataclass contract disagreed with the KPI surface and reality.
  * wacc-2: KPI ``wacc_is_real`` / ``wacc_label`` were unconditionally
    ``False`` / ``"base"`` even when the build-up WACC drove the discount.

The lender scenario opts into a build-up WACC (``wacc.drives_discount_rate:
true``, ``mode: build_up``), so the reported discount basis must say so, and the
KPI dict and the ScenarioResult contract must agree on the rate.

GWTF: ARCH-02 (WACC sourced from finance/wacc_v14.py — only its *reporting* is
touched here), CCCDIR (one resolved truth feeds every surface).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from analytics.core.metrics import DEFAULT_DISCOUNT_RATE, calculate_scenario_kpis
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.pipeline_v14_enhanced import run_v14_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_build_up_wacc_drives_and_is_reported_consistently() -> None:
    """Lender scenario: every surface reports the real build-up WACC basis."""
    result = run_v14_pipeline(config=LENDER)
    kpis = result["kpis"]
    scenario_result = result["scenario_result"]

    drate = kpis["discount_rate_used"]
    # The build-up WACC, NOT the legacy 0.10 default. Since #737/#738 de-levered the
    # deal the build-up WACC (~0.1002 after #738's 0.41 levy-inclusive gearing put
    # more 12% equity in the stack) sits coincidentally close to the 0.10 default,
    # so a distance check no longer discriminates; pin the computed value instead
    # (the wacc_is_real/wacc_label assertions below prove the BASIS).
    assert math.isfinite(drate)
    assert drate == pytest.approx(0.1028583522632941, abs=1e-9)
    assert 0.05 < drate < 0.12

    # The flag/label no longer contradict the rate that was actually used.
    assert kpis["wacc_is_real"] is True
    assert kpis["wacc_label"] == "build_up"

    # The ScenarioResult contract agrees with the KPI surface on ALL three WACC
    # fields (discount_rate_used was the original bug; wacc_is_real was a second
    # blind spot — the dataclass field was never set by the pipeline, so the
    # CASPER payload read None).
    assert abs(scenario_result["discount_rate_used"] - drate) < 1e-12
    assert scenario_result["wacc_label"] == "build_up"
    assert scenario_result["wacc_is_real"] is True
    # The CASPER payload reads this field straight off the contract
    # (getattr(s, "wacc_is_real", None)); now that the pipeline sets it, the
    # lender-facing payload reports the real basis instead of None.


def test_disabling_drives_falls_back_to_legacy_and_says_so() -> None:
    """With drives_discount_rate off, the basis is the legacy default + labelled base."""
    kpis = evaluate_with_overrides(
        LENDER, overrides={"wacc.drives_discount_rate": False}
    )
    assert abs(kpis["discount_rate_used"] - DEFAULT_DISCOUNT_RATE) < 1e-9
    assert not kpis["wacc_is_real"]


def test_kpi_wacc_flags_are_config_derived_not_hardcoded() -> None:
    """Unit-level: the flag/label track config (and an explicit caller wins)."""
    base_kwargs = dict(annual_rows=[], debt_result=None, discount_rate=0.0819)

    real = calculate_scenario_kpis(
        config={"wacc": {"drives_discount_rate": True, "mode": "build_up"}},
        **base_kwargs,
    )
    assert real["wacc_is_real"] is True
    assert real["wacc_label"] == "build_up"

    legacy = calculate_scenario_kpis(config={}, **base_kwargs)
    assert legacy["wacc_is_real"] is False
    assert legacy["wacc_label"] == "base"

    # An explicit caller-resolved value overrides the config fallback.
    explicit = calculate_scenario_kpis(
        config={"wacc": {"drives_discount_rate": True, "mode": "build_up"}},
        wacc_is_real=False,
        wacc_label="base",
        **base_kwargs,
    )
    assert explicit["wacc_is_real"] is False
    assert explicit["wacc_label"] == "base"
