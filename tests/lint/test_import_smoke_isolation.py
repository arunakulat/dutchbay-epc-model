"""Regression guard for #937 — the import-smoke suite must not poison later tests.

tests/lint/test_import_smoke.py used to purge ``analytics*`` entries from
``sys.modules`` and re-import in-process ("clear the cache to test fresh").
That creates a SECOND generation of module/class objects while
already-collected test modules keep first-generation references, with two
proven victim families:

  1. Class-identity split: analytics/fx/fx_integration.py's call-time
     ``from analytics.contracts_v14 import ScenarioResult`` resolves to the
     gen-2 class, so isinstance() rejects gen-1 instances held by
     tests/analytics/test_fx_integration_coverage.py (TypeError).
  2. Patch-target split: ``@patch("analytics.fx_sensitivity_real...")``
     patches the gen-2 module while the gen-1 class under test reads gen-1
     module globals, so the mock never lands and the real pipeline runs
     (FileNotFoundError in tests/analytics_layer/test_fx_sensitivity_real.py).

The smoke tests are now fresh-interpreter subprocess probes (see
``_cold_probe`` in test_import_smoke.py), which cannot leak. This guard
re-runs the historical poisoner file together with one victim from each
family IN ONE child pytest process — single worker, deterministic order,
poisoner first (the sequencing xdist sharding never reproduces in CI, which
is why #937 stayed invisible there). It fails if the in-process purge, or
any equivalent module-cache mutation, ever returns to the smoke suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_POISONER = "tests/lint/test_import_smoke.py"
_VICTIMS = (
    # Family 1 — class-identity split (isinstance against contracts_v14).
    "tests/analytics/test_fx_integration_coverage.py"
    "::test_fx_builder_failure_is_wrapped_as_valueerror",
    # Family 2 — patch-target split (mock lands on the wrong module object).
    "tests/analytics_layer/test_fx_sensitivity_real.py"
    "::TestFXSensitivityAnalyzer::test_run_fx_rate_sensitivity",
)


def test_import_smoke_suite_does_not_poison_fx_tests() -> None:
    """The minimal #937 poisoner+victim pairing must stay green in-process."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            _POISONER,
            *_VICTIMS,
            "--no-cov",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        "#937 regression: running the import-smoke suite before the fx tests "
        "in one process broke the fx tests — a module-cache mutation "
        "(sys.modules purge + re-import) is leaking split module/class "
        f"generations again.\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
