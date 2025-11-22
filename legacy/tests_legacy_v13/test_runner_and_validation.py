import pytest

# Legacy smoke test for the old dutchbay_v13.scenario_runner API.
# The v13 runner has been superseded by the v14 analytics/scenario_loader path.
# We keep this file for historical reference but skip it in the current branch.
pytest.skip(
    "Legacy v13 scenario_runner has been superseded by analytics.scenario_loader/v14 pipeline; "
    "smoke retained only for history.",
    allow_module_level=True,
)

# Original contents below (kept for reference)
from dutchbay_v13.scenario_runner import run_dir  # type: ignore  # noqa: F401

