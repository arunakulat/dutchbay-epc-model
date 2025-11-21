import pytest

# Legacy CLI smoke test for the old dutchbay_v13.scenario_runner-based pipeline.
# The v13 runner has been superseded by the v14 analytics/scenario_loader + v14chat stack.
# We keep this file for historical context but skip it in the current branch.
pytest.skip(
    "Legacy v13 CLI test (dutchbay_v13.cli + scenario_runner); superseded by v14 stack.",
    allow_module_level=True,
)

# Original import retained only as a hint of prior wiring.
from dutchbay_v13 import cli  # type: ignore  # noqa: F401

