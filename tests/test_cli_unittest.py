import unittest
import subprocess
import sys
import os
import json


class TestCLI(unittest.TestCase):
    def test_cli_runs_text(self):
        cfg = os.path.join(
            os.path.dirname(__file__),
            "..",
            "inputs",
            "full_model_variables_updated.yaml",
        )
        out = subprocess.check_output(
            [
                sys.executable,
                "-m",
                "dutchbay_v13.cli",
                "--config",
                cfg,
                "--mode",
                "irr",
            ],
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertIn("IRR / NPV / DSCR RESULTS", out)

    def test_cli_runs_json(self):
        cfg = os.path.join(
            os.path.dirname(__file__),
            "..",
            "inputs",
            "full_model_variables_updated.yaml",
        )
        out = subprocess.check_output(
            [
                sys.executable,
                "-m",
                "dutchbay_v13.cli",
                "--config",
                cfg,
                "--mode",
                "irr",
                "--format",
                "json",
            ],
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        obj = json.loads(out)
        self.assertIn("equity_irr_pct", obj)
        self.assertIn("project_irr_pct", obj)


if __name__ == "__main__":
    unittest.main()
