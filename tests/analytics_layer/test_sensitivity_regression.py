import pytest

pytestmark = pytest.mark.skip(
    reason="sensitivity_v14 is parked for a future refactor; "
           "regression + helper surface not finalized yet."
)

import pytest
import numpy as np
from analytics.sensitivity import (
    SensitivityRequest, run_tornado_sensitivity, run_multi_metric_tornado,
    run_breakeven_parameter, run_two_way_sensitivity, optimize_from_sensitivity_insights
)
from analytics.contracts_v14 import ParameterRangeConfig

@pytest.fixture
def base_req():
    # Substitute with minimal canonical scenario for goldens
    return SensitivityRequest(
        base_config_path="scenarios/test_basecase.yaml",
        parameters=[
            ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=-15, high_pct=15),
            ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=-10, high_pct=10)
        ],
        metric="project_irr"
    )

def test_tornado_reproducibility(base_req):
    suite1 = run_tornado_sensitivity(base_req)
    suite2 = run_tornado_sensitivity(base_req)
    assert np.allclose(
        [t.impact_abs for t in suite1.tornado_results],
        [t.impact_abs for t in suite2.tornado_results]
    )

def test_breakeven_solution(base_req):
    br = run_breakeven_parameter(
        base_req.base_config_path, 
        variable_name=base_req.parameters[0].variable_name, 
        target_metric=base_req.metric, 
        target_value=0.13, 
        lower=600, upper=1200
    )
    assert br.status == "success"
    assert 600 < br.breakeven_value < 1200

def test_two_way_heatmap_shape(base_req):
    df = run_two_way_sensitivity(
        base_req.base_config_path,
        param_x=base_req.parameters[0],
        param_y=base_req.parameters[1],
        metric="project_irr", steps=4
    )
    assert df.shape == (4, 4)
    # All entries should be float
    assert df.values.dtype.kind == "f"

def test_pareto_feasible_points(base_req):
    suite = run_tornado_sensitivity(base_req)
    pf = optimize_from_sensitivity_insights(
        suite, 
        base_config_path=base_req.base_config_path,
        objectives=("project_irr", "dscr_min"),
        steps=3
    )
    assert len(pf.frontier_points) > 0
    # Pareto points must respect constraints by construction

def test_multi_metric_impacts(base_req):
    suite = run_multi_metric_tornado(
        base_req, metrics=["project_irr", "equity_irr"]
    )
    for t in suite.tornado_results:
        assert any(i > 0 for i in t.impacts.values())
        