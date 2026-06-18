"""Guards for dotted-key override expansion in the v14 evaluation gateway.

Regression coverage for the silent no-op where flat *dotted* overrides
(e.g. ``{"tax.corporate_tax_rate": 0.30}``) were dropped by ``_deep_merge_config``,
which made every nested-parameter one-way sensitivity report zero impact while the
underlying model in fact responds to the parameter.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from analytics.evaluation_v14 import _expand_dotted_overrides, evaluate_with_overrides

BASECASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")


# ── Pure unit tests (no scenario needed; always run) ─────────────────────────


def test_expand_dotted_overrides_builds_nested_paths() -> None:
    out = _expand_dotted_overrides(
        {"tax.corporate_tax_rate": 0.42, "tax.tax_holiday_years": 5, "capex": {"x": 1}}
    )
    assert out == {
        "tax": {"corporate_tax_rate": 0.42, "tax_holiday_years": 5},
        "capex": {"x": 1},
    }


def test_expand_dotted_overrides_recurses_into_nested_mappings() -> None:
    assert _expand_dotted_overrides({"a": {"b.c": 1}}) == {"a": {"b": {"c": 1}}}


def test_expand_dotted_overrides_passes_plain_keys_through() -> None:
    assert _expand_dotted_overrides({"tariff": 30.0}) == {"tariff": 30.0}


# ── End-to-end guards (skip if the canonical scenario is absent) ─────────────


@pytest.fixture
def basecase():
    if not BASECASE.is_file():
        pytest.skip(f"canonical scenario missing: {BASECASE}")
    from omegaconf import OmegaConf

    return OmegaConf.to_container(OmegaConf.load(BASECASE), resolve=True)


def _equity_irr(cfg, overrides):
    out = evaluate_with_overrides(
        config_path=None, raw_config=copy.deepcopy(cfg), overrides=overrides
    )
    kpis = out.get("kpis", out) if hasattr(out, "get") else out
    return kpis["equity_irr"]


def test_dotted_override_actually_applies(basecase):
    """A near-tripled corporate tax rate must move equity IRR (pre-fix: no-op)."""
    base = _equity_irr(basecase, {})
    shocked = _equity_irr(basecase, {"tax.corporate_tax_rate": 0.90})
    assert shocked != pytest.approx(base), "dotted override had no effect (regression)"
    assert shocked < base


def test_dotted_and_nested_overrides_are_equivalent(basecase):
    flat = _equity_irr(basecase, {"tax.corporate_tax_rate": 0.90})
    nested = _equity_irr(basecase, {"tax": {"corporate_tax_rate": 0.90}})
    assert flat == pytest.approx(nested)


def test_one_way_sensitivity_reports_nonzero_impact(basecase):
    """The contract-API one-way sensitivity must now register a real impact."""
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity.tax import TaxSensitivityConfig, run_tax_one_way

    suite = run_tax_one_way(
        base_config=basecase,
        parameter=ParameterRangeConfig(
            variable_name="tax.corporate_tax_rate",
            base_value=0.30,
            low_pct=-50.0,
            high_pct=50.0,
            points=3,
            label="corporate_tax_rate",
        ),
        cfg=TaxSensitivityConfig(metric_key="equity_irr"),
    )
    tornado = suite.tornado_results[0]
    assert tornado.impact_abs > 0.0, "one-way tax sensitivity still reports zero impact"
