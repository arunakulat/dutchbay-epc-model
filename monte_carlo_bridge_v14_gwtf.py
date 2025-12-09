from __future__ import annotations

"""
analytics.monte_carlo_bridge_v14

Skinny bridge between evaluation_v14 and Monte Carlo engine.

This module is intentionally small and opinionated:
- Single place where MC decides which KPIs it cares about
- No direct access to cashflow/debt/wacc modules
- Reuses evaluate_scenario from evaluation_v14 (single evaluation gateway)
- Returns simple, numeric-only snapshots for sampler/aggregator logic

Go-with-the-Flow Compliance
---------------------------
✓ TYPE-01: Fully type-annotated (frozen dataclass)
✓ R15: mypy strict-compatible
✓ R17: Google-style docstrings
✓ TEST-01: Regression test pins in test file
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from analytics.evaluation_v14 import evaluate_scenario

logger = logging.getLogger(__name__)


# ============================================================================
# Data Containers
# ============================================================================


@dataclass(frozen=True)
class MonteCarloKpiSnapshot:
    """
    Minimal KPI snapshot for a single Monte Carlo draw.

    These are the quantities the MC engine aggregates into distributions
    (mean, stdev, percentiles, tail risk, etc.).

    Frozen=True ensures immutability for use in aggregation pipelines.

    Attributes
    ----------
    project_irr : float
        Project-level internal rate of return
    equity_irr : float
        Equity internal rate of return
    min_dscr : float
        Minimum debt service coverage ratio
    avg_dscr : float
        Average debt service coverage ratio
    """

    project_irr: float
    equity_irr: float
    min_dscr: float
    avg_dscr: float


# ============================================================================
# Public API: MC Bridge
# ============================================================================


def evaluate_for_monte_carlo(
    config_path: Path | str,
    overrides: Optional[Mapping[str, Any]] = None,
) -> MonteCarloKpiSnapshot:
    """
    Evaluate a single Monte Carlo scenario draw via evaluation_v14.

    Entry point for MC engine. Accepts config path + override dict,
    returns immutable KPI snapshot ready for distribution aggregation.

    Args
    ----
    config_path:
        Path to base v14 scenario configuration file (YAML/JSON).
    overrides:
        Nested dict of parameter overrides for this draw.
        Matches the structure expected by v14 pipeline:

        Example:
            {
                "project": {"capex_usd_per_kw": 1250.0},
                "generation": {"capacity_factor_pct": 37.5},
            }

    Returns
    -------
    MonteCarloKpiSnapshot
        Numeric KPIs extracted from evaluation, ready for aggregation
        into distributions (mean, stdev, percentiles, tail risk, etc).

    Raises
    ------
    KeyError
        If required metrics missing from evaluation result.
    TypeError
        If metric values are non-numeric or cannot be converted to float.
    FileNotFoundError
        If config_path does not exist.

    Example
    -------
    >>> snapshot = evaluate_for_monte_carlo(
    ...     "scenarios/dutchbay_lendercase_2025Q4.yaml",
    ...     overrides={"project": {"capex_usd_per_kw": 1500}},
    ... )
    >>> snapshot.equity_irr
    0.142
    """
    cfg_path = Path(config_path)

    logger.debug(
        "MC bridge evaluating scenario: %s with overrides: %s",
        cfg_path,
        overrides,
    )

    # Evaluate via evaluation_v14 gateway
    result = evaluate_scenario(cfg_path, overrides)

    # Extract canonical KPIs and construct snapshot
    try:
        project_irr = float(result["project_irr"])
        equity_irr = float(result["equity_irr"])
        min_dscr = float(result["min_dscr"])
        avg_dscr = float(result["avg_dscr"])
    except KeyError as exc:
        msg = (
            "MC bridge expects evaluation_v14 to provide keys: "
            "'project_irr', 'equity_irr', 'min_dscr', 'avg_dscr'. "
            f"Missing: {exc}"
        )
        raise KeyError(msg) from exc
    except (TypeError, ValueError) as exc:
        msg = (
            "MC bridge expected numeric IRR/DSCR values, got: "
            f"{{project_irr: {result.get('project_irr')}, "
            f"equity_irr: {result.get('equity_irr')}, "
            f"min_dscr: {result.get('min_dscr')}, "
            f"avg_dscr: {result.get('avg_dscr')}}}"
        )
        raise TypeError(msg) from exc

    snapshot = MonteCarloKpiSnapshot(
        project_irr=project_irr,
        equity_irr=equity_irr,
        min_dscr=min_dscr,
        avg_dscr=avg_dscr,
    )

    logger.debug("MC bridge snapshot: %s", snapshot)
    return snapshot


def evaluate_for_monte_carlo_as_dict(
    config_path: Path | str,
    overrides: Optional[Mapping[str, Any]] = None,
) -> dict[str, float]:
    """
    Evaluate MC scenario, return as plain dict (legacy compatibility).

    Same as evaluate_for_monte_carlo(), but returns a plain dict instead
    of MonteCarloKpiSnapshot. Useful if existing MC engine expects
    mapping interface.

    Args
    ----
    config_path:
        Path to base v14 scenario configuration file.
    overrides:
        Nested dict of parameter overrides for this draw.

    Returns
    -------
    dict[str, float]
        Dict with keys:
            - project_irr
            - equity_irr
            - min_dscr
            - avg_dscr

    Note
    ----
    Prefer evaluate_for_monte_carlo() for type safety.
    Use this variant only for legacy MC engines expecting dicts.
    """
    snapshot = evaluate_for_monte_carlo(config_path, overrides)
    return {
        "project_irr": snapshot.project_irr,
        "equity_irr": snapshot.equity_irr,
        "min_dscr": snapshot.min_dscr,
        "avg_dscr": snapshot.avg_dscr,
    }
