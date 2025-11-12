import unittest
import os
from dutchbay_v13.scenario_runner import load_config, run_single_scenario


class TestScenario(unittest.TestCase):
    def test_run_single_scenario(self):
        cfgp = os.path.join(
            os.path.dirname(__file__),
            "..",
            "inputs",
            "full_model_variables_updated.yaml",
        )
        cfg = load_config(cfgp)
        res = run_single_scenario(cfg)
        self.assertIsNotNone(res["equity_irr_pct"])
        self.assertIn("avg_dscr", res)


if __name__ == "__main__":
    unittest.main()
