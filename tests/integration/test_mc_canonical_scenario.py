"""Integration guard: the canonical MC engine must run the canonical scenario.

Regression cover for the contract break where ``analytics.mc.engine`` expected
``monte_carlo.parameters`` as a list of ``{name, low, high}`` mappings while the
lender scenario shipped a dict of per-driver scalars — so the canonical Hydra
MC CLI (which loads the scenario and calls
``run_monte_carlo_analysis(base_config=...)``) crashed with an opaque
``TypeError`` on the canonical scenario, and *no* test exercised that path
(every MC test fed the engine a hand-shaped list fixture, hiding the break).

These tests run the **real** lender scenario through the **functional
entrypoint the CLI wraps**, plus a CESSPIT schema-guard failure test that a
dict-shaped ``parameters`` block raises a clear, typed error.

GWTF:
    - CESSPIT: schema strict (the failure test asserts a raise on a bad shape).
    - CCCDIR: the engine consumes the scenario's declared MC parameter list.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

import yaml

from analytics.mc.engine import MonteCarloConfigError, run_monte_carlo_analysis

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _load_lender_scenario() -> Dict[str, Any]:
    """Load the canonical lender scenario YAML into a plain dict."""
    with LENDER_SCENARIO.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


def test_canonical_mc_engine_runs_on_canonical_scenario() -> None:
    """The canonical scenario must drive the canonical MC engine to completion.

    This is the gate that was missing: a real run of the lender scenario through
    ``run_monte_carlo_analysis`` (the functional entrypoint the Hydra CLI calls),
    asserting every trial evaluated for real (no silent toy-fallback) and the
    flat-scalar result surface is populated with a sane IRR distribution.
    """
    base_config = _load_lender_scenario()

    result = run_monte_carlo_analysis(base_config=base_config, n_trials=24, seed=42)

    # Every trial ran the real pipeline (toy-fallback would inflate failures or
    # collapse the distribution to a constant).
    assert result.iterations == 24
    assert result.failed_iterations == 0
    assert result.success_rate() == 100.0

    # Flat-scalar surface (#203) is populated and ordered.
    p10, p50, p90 = (
        result.project_irr_p10,
        result.project_irr_p50,
        result.project_irr_p90,
    )
    for v in (p10, p50, p90):
        assert isinstance(v, float) and math.isfinite(v)
    assert p10 <= p50 <= p90
    # Sane economic range for this project (single-digit-to-low-double-digit IRR).
    assert -0.10 < p10 and p90 < 0.30
    # A genuine distribution, not a collapsed constant.
    assert p90 - p10 > 1e-4


def test_dict_shaped_parameters_raises_clear_error() -> None:
    """CESSPIT schema-guard: a dict-shaped ``parameters`` must fail loudly.

    The pre-fix failure mode was a cryptic ``TypeError: string indices must be
    integers`` from inside the sampler. The engine now rejects the wrong shape
    up-front with a typed, actionable :class:`MonteCarloConfigError`.
    """
    base_config = _load_lender_scenario()
    base_config["monte_carlo"] = dict(base_config["monte_carlo"])
    base_config["monte_carlo"]["parameters"] = {
        "capacity_factor_std": 0.05,
        "tariff_lkr_std": 0.10,
    }

    try:
        run_monte_carlo_analysis(base_config=base_config, n_trials=4, seed=1)
    except MonteCarloConfigError as exc:
        assert "must be a LIST" in str(exc)
        assert "capacity_factor_std" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("dict-shaped monte_carlo.parameters did not raise")
