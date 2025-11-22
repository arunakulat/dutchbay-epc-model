import pytest

# Legacy cashflow smoke test for the old dutchbay_v13.scenario_runner API.
# The v13 runner has been superseded by the v14 analytics/scenario_loader + v14chat pipeline.
# We keep this file for historical reference but skip it in the current branch.
pytest.skip(
    "Legacy v13 scenario_runner-based cashflow smoke; superseded by v14 analytics/v14chat pipeline.",
    allow_module_level=True,
)

# Original import (kept only as a hint of prior wiring)
from dutchbay_v13.scenario_runner import run_dir  # type: ignore  # noqa: F401

