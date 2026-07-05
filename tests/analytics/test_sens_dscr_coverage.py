"""Coverage for analytics.sensitivity.dscr.

The module is a thin, deterministic DSCR-focused wrapper around the engine's
``build_one_way_sensitivity_suite``. These tests assert real behaviour:

- the ``DscrSensitivityConfig`` defaults and frozen-dataclass contract;
- one real-config integration sweep that returns a populated ``SensitivitySuite``
  whose tornado metric is the DSCR(min) metric;
- pass-through of ``cfg`` (metric key) and ``run_cfg`` into the engine call,
  verified by patching the engine seam (no network, no plotting involved).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity.dscr import DscrSensitivityConfig, run_dscr_one_way
from analytics.sensitivity.engine import SensitivityRunConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _param(name: str = "project.capacity_factor") -> ParameterRangeConfig:
    return ParameterRangeConfig(
        variable_name=name, base_value=1.0, low_pct=-10.0, high_pct=10.0, label=name
    )


def test_dscr_config_defaults() -> None:
    cfg = DscrSensitivityConfig()
    assert cfg.dscr_metric_key == "dscr_min"
    assert cfg.dscr_floor == pytest.approx(1.30)


def test_dscr_config_is_frozen() -> None:
    cfg = DscrSensitivityConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.dscr_floor = 1.40  # type: ignore[misc]


def test_dscr_config_custom_values() -> None:
    cfg = DscrSensitivityConfig(dscr_metric_key="dscr_mean", dscr_floor=1.10)
    assert cfg.dscr_metric_key == "dscr_mean"
    assert cfg.dscr_floor == pytest.approx(1.10)


def test_run_dscr_one_way_real_config() -> None:
    """End-to-end against the canonical lender scenario (deterministic)."""
    base_cfg = load_scenario_config(LENDER)
    suite = run_dscr_one_way(base_config=base_cfg, parameter=_param())

    assert isinstance(suite, SensitivitySuite)
    # The DSCR(min) metric must be the suite metric.
    assert suite.metric == "dscr_min"
    assert len(suite.tornado_results) == 1
    # Base case DSCR(min) headline is the #790 fold-corrected covenant minimum
    # (the per-period sculpt floor 1.30 lives in min_dscr_period). #738: the
    # levy-inclusive year-1 fold eases 1.2884 -> 1.2857.
    assert suite.base_kpis["dscr_min"] == pytest.approx(1.285740985294611, abs=1e-6)
    assert suite.base_kpis["min_dscr_period"] == pytest.approx(1.30, abs=1e-6)


def test_run_dscr_one_way_unknown_parameter_raises() -> None:
    """Strict mode (engine default) rejects a non-resolving config path."""
    base_cfg = load_scenario_config(LENDER)
    with pytest.raises(ValueError, match="does not resolve"):
        run_dscr_one_way(base_config=base_cfg, parameter=_param("opex_annual"))


def test_run_dscr_one_way_passes_metric_and_runcfg() -> None:
    """cfg.dscr_metric_key and run_cfg are forwarded verbatim to the engine."""
    sentinel = SensitivitySuite(metric="dscr_mean")
    base_cfg: Mapping[str, Any] = {"project": {"capacity_factor": 0.34}}
    param = _param()
    dscr_cfg = DscrSensitivityConfig(dscr_metric_key="dscr_mean")
    run_cfg = SensitivityRunConfig(strict=False, attach_trial_metadata=False)

    with mock.patch(
        "analytics.sensitivity.dscr.build_one_way_sensitivity_suite",
        return_value=sentinel,
    ) as built:
        out = run_dscr_one_way(
            base_config=base_cfg,
            parameter=param,
            cfg=dscr_cfg,
            run_cfg=run_cfg,
        )

    assert out is sentinel
    built.assert_called_once_with(
        base_config=base_cfg,
        parameter=param,
        metric_key="dscr_mean",
        run_cfg=run_cfg,
    )


def test_run_dscr_one_way_default_metric_forwarded() -> None:
    """With the default cfg, the engine is called with metric_key='dscr_min'."""
    sentinel = SensitivitySuite(metric="dscr_min")
    base_cfg: Mapping[str, Any] = {"project": {"capacity_factor": 0.34}}
    param = _param()

    with mock.patch(
        "analytics.sensitivity.dscr.build_one_way_sensitivity_suite",
        return_value=sentinel,
    ) as built:
        run_dscr_one_way(base_config=base_cfg, parameter=param)

    _, kwargs = built.call_args
    assert kwargs["metric_key"] == "dscr_min"
    # Default run_cfg is the engine's frozen default.
    assert kwargs["run_cfg"] == SensitivityRunConfig()
