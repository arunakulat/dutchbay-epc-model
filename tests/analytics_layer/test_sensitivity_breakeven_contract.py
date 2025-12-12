from __future__ import annotations

from typing import Any, Dict, List

import pytest

from analytics.contracts_v14 import BreakevenResult
from analytics.sensitivity_v14 import run_breakeven_parameter


def test_run_breakeven_parameter_uses_absolute_overrides_and_converges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Contract test for run_breakeven_parameter.

    Guarantees:
    - Uses _get_base_param_value(...) to derive base scalar.
    - Calls evaluate_with_overrides(config_path, overrides) with ABSOLUTE
      parameter values (no fractional multipliers).
    - Converges to the correct root for a simple monotonic toy function.
    """

    import analytics.sensitivity_v14 as mod

    # ── 1) Stub base param lookup ─────────────────────────────────────────
    def fake_get_base_param_value(config_path: str, variable_name: str) -> float:
        assert config_path == "dummy.yaml"
        assert variable_name == "tariff.tariff_lkr_per_kwh"
        # Base value = 10.0 (arbitrary but convenient)
        return 10.0

    monkeypatch.setattr(mod, "_get_base_param_value", fake_get_base_param_value)

    # ── 2) Stub evaluation gateway and record overrides ───────────────────
    calls: List[Dict[str, Any]] = []

    def fake_evaluate_with_overrides(
        config_path: str,
        overrides: Dict[str, Any] | None,
    ) -> Dict[str, float]:
        assert config_path == "dummy.yaml"

        # Base call: None → provide base KPI dict
        if overrides is None:
            return {"project_irr": 0.05}

        # Record override structure for later inspection
        calls.append(overrides)

        # Toy monotonic mapping:
        # project_irr = (tariff - 8.0) / 100
        tariff_block = overrides.get("tariff", {})
        tariff_val = float(tariff_block["tariff_lkr_per_kwh"])
        irr = (tariff_val - 8.0) / 100.0
        return {"project_irr": irr}

    monkeypatch.setattr(mod, "evaluate_with_overrides", fake_evaluate_with_overrides)

    # Target: project_irr = 0.02  ⇒  (x - 8) / 100 = 0.02  ⇒  x = 10
    result = run_breakeven_parameter(
        base_config_path="dummy.yaml",
        variable_name="tariff.tariff_lkr_per_kwh",
        target_metric="project_irr",
        target_value=0.02,
        low_pct=-0.5,   # -50% ⇒ 5.0
        high_pct=0.5,   # +50% ⇒ 15.0
        tol=1e-6,
        max_iter=30,
    )

    # ── 3) Contract: result shape and convergence ─────────────────────────
    assert isinstance(result, BreakevenResult)
    assert result.variable == "tariff.tariff_lkr_per_kwh"
    assert result.status == "success"
    assert result.bracket[0] < result.breakeven_value < result.bracket[1]
    assert abs(result.breakeven_value - 10.0) < 1e-3

    # ── 4) Contract: overrides use ABSOLUTE values within bracket ─────────
    assert calls, "Expected evaluate_with_overrides to be called with overrides"

    shocked_values = {
        overrides["tariff"]["tariff_lkr_per_kwh"]
        for overrides in calls
        if "tariff" in overrides
    }
    # Bracket should be [5.0, 15.0] from ±50% of base=10
    assert min(shocked_values) >= 5.0 - 1e-9
    assert max(shocked_values) <= 15.0 + 1e-9

