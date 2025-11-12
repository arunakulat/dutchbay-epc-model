from dutchbay_v13.scenario_runner import load_config, run_single_scenario
import os


def test_run_single_scenario():
    cfgp = os.path.join(
        os.path.dirname(__file__), "..", "inputs", "full_model_variables_updated.yaml"
    )
    cfg = load_config(cfgp)
    res = run_single_scenario(cfg)
    assert res["equity_irr_pct"] is not None
    assert res["avg_dscr"] > 0.0
