from __future__ import annotations

from pathlib import Path

import pytest

from analytics.contracts_v14 import (
    ParameterRangeConfig,
    MultiMetricSensitivitySuite,
    SensitivitySuite,
)
from analytics.sensitivity_v14 import (
    SensitivityRequest,
    _normalize_percentage,
    _sanitize_shocked_value,
    run,
    run_breakeven_parameter,
    run_multi_metric_tornado,
)

SCENARIO_PATH = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


@pytest.mark.smoke
def test_sensitivity_request_run_end_to_end() -> None:
    """
    CASPER front-door contract:

    SensitivityRequest → run(...) → SensitivitySuite

    Locks the canonical entry point for deterministic tornado:
    - Typed request object
    - Gateway-only evaluation
    - Successful SensitivitySuite result
    """
    req = SensitivityRequest(
        base_config_path=str(SCENARIO_PATH),
        parameters=[
            ParameterRangeConfig(
                variable_name="project.capex_usd_per_kw",
                base_value=1500.0,
                low_pct=-10.0,
                high_pct=10.0,
            ),
            ParameterRangeConfig(
                variable_name="generation.capacity_factor_pct",
                base_value=35.0,
                low_pct=-5.0,
                high_pct=5.0,
            ),
        ],
        metric="project_irr",
    )

    suite = run(req)

    # Basic surface checks
    assert isinstance(suite, SensitivitySuite)
    assert suite.base_config_path == str(SCENARIO_PATH)
    assert suite.metric == "project_irr"
    assert suite.base_metric is not None

    # We asked for two parameters → at least two tornado rows
    assert len(suite.tornado_results) >= 2

    # Each tornado row should have a label and finite impacts
    for row in suite.tornado_results:
        assert isinstance(row.variable, str)
        assert row.variable  # non-empty label
        assert row.base_irr == pytest.approx(suite.base_metric)
        assert isinstance(row.impact_abs, float)
        assert row.impact_abs >= 0.0


@pytest.mark.smoke
def test_run_multi_metric_tornado_end_to_end() -> None:
    """
    Contract test for run_multi_metric_tornado:

    - Accepts SensitivityRequest
    - Returns MultiMetricSensitivitySuite
    - Produces at least one row per parameter/metric combination.
    """
    req = SensitivityRequest(
        base_config_path=str(SCENARIO_PATH),
        parameters=[
            ParameterRangeConfig(
                variable_name="project.capex_usd_per_kw",
                base_value=1500.0,
                low_pct=-10.0,
                high_pct=10.0,
            ),
            ParameterRangeConfig(
                variable_name="generation.capacity_factor_pct",
                base_value=35.0,
                low_pct=-5.0,
                high_pct=5.0,
            ),
        ],
        metric="project_irr",  # still used by plain run(...)
    )

    metrics = ["project_irr", "equity_irr"]

    suite = run_multi_metric_tornado(req, metrics=metrics)

    assert isinstance(suite, MultiMetricSensitivitySuite)
    assert suite.base_config_path == str(SCENARIO_PATH)
    assert set(suite.metrics) == set(metrics)
    assert set(suite.base_metrics.keys()) >= set(metrics)

    # Expect at least as many rows as parameters
    assert len(suite.tornado_results) >= 2

    for row in suite.tornado_results:
        # variable + label should be non-empty strings
        assert isinstance(row.variable, str)
        assert row.variable
        assert isinstance(row.label, str)
        assert row.label

        # All requested metrics should be present in dicts
        for m in metrics:
            assert m in row.base_values
            assert m in row.low_values
            assert m in row.high_values
            assert m in row.impacts
            assert m in row.impact_dirs


@pytest.mark.smoke
def test_run_breakeven_parameter_smoke_tariff_irr() -> None:
    """
    Breakeven contract smoke test.

    Verifies that:
    - run_breakeven_parameter(...) executes successfully
    - returns a numeric breakeven_value
    - returns a valid bracket tuple
    - status is either 'success' or 'max_iter_exceeded'
    """
    result = run_breakeven_parameter(
        base_config_path=str(SCENARIO_PATH),
        variable_name="tariff.tariff_lkr_per_kwh",
        target_metric="project_irr",
        target_value=0.12,
        low_pct=-0.5,
        high_pct=0.5,
        tol=1e-4,
        max_iter=30,
    )

    assert result.variable == "tariff.tariff_lkr_per_kwh"
    assert isinstance(result.breakeven_value, float)
    assert isinstance(result.bracket, tuple)
    assert len(result.bracket) == 2
    assert result.status in {"success", "max_iter_exceeded"}

    # Breakeven value should be inside the final bracket
    a, b = result.bracket
    assert min(a, b) <= result.breakeven_value <= max(a, b)


def test_normalize_percentage_behaviour() -> None:
    """
    Contract test for _normalize_percentage:

    - Whole numbers are treated as percentages
      (5 → 5%, -10 → -10%)
    - Decimals <1 are treated as decimal fractions
      (0.05 → 0.05)
    - Ambiguous decimals (e.g., 0.075) are passed through
      as-is and explicitly documented in the module.
    """
    # Whole numbers → percentage
    assert _normalize_percentage(5.0) == pytest.approx(0.05)
    assert _normalize_percentage(-10.0) == pytest.approx(-0.10)

    # Decimals < 1 → left as-is
    assert _normalize_percentage(0.05) == pytest.approx(0.05)
    assert _normalize_percentage(-0.10) == pytest.approx(-0.10)

    # Ambiguous case: 0.075 → interpreted as 0.075 (0.075%)
    assert _normalize_percentage(0.075) == pytest.approx(0.075)


def test_sanitize_shocked_value_positive_only_rejects_negative() -> None:
    """
    Contract test for _sanitize_shocked_value:

    For positive-only parameters (tariff/capex/opex/price/cost/etc.):
    - Negative or zero shocked values must raise ValueError
    - Positive values pass through unchanged
    """
    variable = "tariff.tariff_lkr_per_kwh"
    base_value = 20.0

    # Positive value → allowed
    safe = _sanitize_shocked_value(
        variable_name=variable,
        shocked_value=22.0,
        base_value=base_value,
        shock_label="high",
    )
    assert safe == 22.0

    # Zero or negative values → rejected
    with pytest.raises(ValueError):
        _sanitize_shocked_value(
            variable_name=variable,
            shocked_value=0.0,
            base_value=base_value,
            shock_label="low",
        )

    with pytest.raises(ValueError):
        _sanitize_shocked_value(
            variable_name=variable,
            shocked_value=-5.0,
            base_value=base_value,
            shock_label="low",
        )


def test_sanitize_shocked_value_non_positive_only_param_allows_negative() -> None:
    """
    _sanitize_shocked_value should NOT globally forbid negatives.

    For parameters that don't match the positive-only patterns
    (e.g., a hypothetical 'equity.return_adjustment'), negative values
    are allowed to flow through – validation is expected elsewhere.
    """
    variable = "equity.return_adjustment"
    base_value = 0.0

    value = _sanitize_shocked_value(
        variable_name=variable,
        shocked_value=-0.05,
        base_value=base_value,
        shock_label="low",
    )
    assert value == -0.05
