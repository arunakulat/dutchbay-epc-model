from __future__ import annotations

from typing import Any, Dict, List

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.sensitivity_v14 import SensitivityRequest, run


def test_run_with_sensitivity_request_uses_gateway_and_returns_suite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Contract test for analytics.sensitivity_v14.run(...).

    Guarantees:
    - Accepts a SensitivityRequest as the canonical CASPER entry point.
    - Delegates to the tornado engine and returns a SensitivitySuite.
    - Uses evaluate_with_overrides(config_path, overrides) for shocked runs.
    - Produces exactly one tornado row per ParameterRangeConfig.
    """

    import analytics.sensitivity_v14 as mod

    base_config_path = "dummy_sensitivity.yaml"

    # ── 1) Stub base KPI evaluation (via _evaluate_base_kpis) ─────────────
    def fake_evaluate_base_kpis(config_path: str) -> Dict[str, float]:
        # Ensure the correct config path flows through
        assert config_path == base_config_path
        # Single KPI for this contract test
        return {"project_irr": 0.10}

    monkeypatch.setattr(mod, "_evaluate_base_kpis", fake_evaluate_base_kpis)

    # ── 2) Stub evaluation gateway for shocked runs ──────────────────────
    calls: List[Dict[str, Any] | None] = []

    def fake_evaluate_with_overrides(
        config_path: str,
        overrides: Dict[str, Any] | None,
    ) -> Dict[str, float]:
        # All calls must use the same config path
        assert config_path == base_config_path

        # Record every call for contract assertions
        calls.append(overrides)

        # This stub is used only for shocked evaluations in this test.
        # We return a simple deterministic mapping that shifts IRR based on
        # the shocked parameter value, but the exact formula is not critical.
        if overrides is None:
            # Not expected here because base KPIs are from _evaluate_base_kpis.
            return {"project_irr": 0.10}

        # Pull *some* scalar out of the nested override for determinism
        val: float | None = None
        if "tariff" in overrides:
            val = float(overrides["tariff"]["tariff_lkr_per_kwh"])
        elif "project" in overrides:
            val = float(overrides["project"]["capex_usd_per_kw"])
        else:
            # Fallback for unexpected paths; still deterministic
            (first_key,) = overrides.keys()
            inner = overrides[first_key]
            (leaf_key,) = inner.keys()
            val = float(inner[leaf_key])

        # Toy IRR mapping: base 0.10 plus a small bump scaled by val
        irr = 0.10 + (val - 10.0) / 10_000.0
        return {"project_irr": irr}

    monkeypatch.setattr(mod, "evaluate_with_overrides", fake_evaluate_with_overrides)

    # ── 3) Build SensitivityRequest with 2 parameters ─────────────────────
    params = [
        ParameterRangeConfig(
            variable_name="tariff.tariff_lkr_per_kwh",
            base_value=10.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=1_000.0,
            low_pct=-5.0,
            high_pct=5.0,
        ),
    ]

    request = SensitivityRequest(
        base_config_path=base_config_path,
        parameters=params,
        override_labels={
            "tariff.tariff_lkr_per_kwh": "Tariff (LKR/kWh)",
            "project.capex_usd_per_kw": "CAPEX (USD/kW)",
        },
        metric="project_irr",
    )

    # ── 4) Run the canonical CASPER entry point ───────────────────────────
    suite = run(request)

    # ── 5) Contract assertions on the returned suite ──────────────────────
    assert isinstance(suite, SensitivitySuite)
    assert suite.metric == "project_irr"
    assert suite.base_config_path == base_config_path
    assert suite.base_metric == pytest.approx(0.10)

    # One tornado row per parameter
    assert len(suite.tornado_results) == len(params)

    # Variables should be the human-readable labels we passed in
    variables = {row.variable for row in suite.tornado_results}
    assert variables == {"Tariff (LKR/kWh)", "CAPEX (USD/kW)"}

    # Tornado rows must have consistent numeric fields
    for row in suite.tornado_results:
        assert isinstance(row.base_irr, float)
        assert isinstance(row.low_irr, float)
        assert isinstance(row.high_irr, float)

    # ── 6) Contract on gateway usage ──────────────────────────────────────
    # We expect at least one shocked evaluation via evaluate_with_overrides.
    assert calls, "Expected evaluate_with_overrides to be called for shocks"

    # All recorded calls from this test should be shocked (non-None) overrides.
    assert all(ovr is not None for ovr in calls)
