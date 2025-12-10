from __future__ import annotations

from pathlib import Path

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.sensitivity_v14 import SensitivityRequest, run

SCENARIO_BASE = Path("scenarios")
TEST_BASE_SCENARIO = SCENARIO_BASE / "test_base_scenario.yaml"


@pytest.mark.skipif(
    not TEST_BASE_SCENARIO.is_file(),
    reason=f"Integration scenario not found: {TEST_BASE_SCENARIO}",
)
class TestSensitivityRunFacade:
    def test_run_facade_basic(self) -> None:
        req = SensitivityRequest(
            base_config_path=str(TEST_BASE_SCENARIO),
            parameters=[
                ParameterRangeConfig(
                    variable_name="project.capex_usd_per_kw",
                    base_value=1500.0,
                    low_pct=-0.1,
                    high_pct=0.1,
                )
            ],
            metric="project_irr",
        )

        suite = run(req)

        # Contract / type checks
        assert isinstance(suite, SensitivitySuite)
        assert suite.metric == "project_irr"
        assert suite.base_config_path == str(TEST_BASE_SCENARIO)
        assert len(suite.tornado_results) >= 1

    def test_run_rejects_legacy_call_style(self) -> None:
        with pytest.raises(TypeError):
            # type: ignore[arg-type] - deliberately wrong type to assert TypeError
            run("scenarios/test_base_scenario.yaml")
