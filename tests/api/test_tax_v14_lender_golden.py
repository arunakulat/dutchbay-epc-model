from pathlib import Path

import pytest

from analytics.evaluationv14 import evaluatewithoverrides
from analytics.scenarioloader import loadscenarioconfig

SCENARIO_PATH = Path("scenarios/dutchbaylendercase2025Q4.yaml")


def test_tax_v14_lender_golden_surface(tmp_path):
    if not SCENARIO_PATH.is_file():
        pytest.skip(f"Missing canonical lender-case scenario at {SCENARIO_PATH}")

    cfg = loadscenarioconfig(str(SCENARIO_PATH))
    assert isinstance(cfg, dict)

    kpis = evaluatewithoverrides(str(SCENARIO_PATH), overrides=None)

    assert "projectirr" in kpis
    assert "projectnpv" in kpis
    assert "mindscr" in kpis
