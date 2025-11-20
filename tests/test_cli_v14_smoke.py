import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "run_full_pipeline.py"
LENDERCASE_CONFIG = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_cli_v14_pipeline_invocation():
    assert SCRIPT.exists(), f"Pipeline script not found: {SCRIPT}"
    assert LENDERCASE_CONFIG.exists(), f"Missing lendercase config: {LENDERCASE_CONFIG}"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(LENDERCASE_CONFIG)],
        capture_output=True,
        text=True,
        check=True,
    )

    # Process completed successfully
    assert result.returncode == 0

    # Basic output sanity checks
    stdout = result.stdout
    assert "Core KPIs" in stdout
    assert "npv" in stdout.lower()
    assert "irr" in stdout.lower()
