"""Compute the lender report's global sensitivity analysis (MC-1 / #468).

The report embeds a GLOBAL sensitivity screening — **Morris** elementary effects — as
the variance-aware complement to the local one-at-a-time tornado. ``mu_star`` ranks
each driver's overall importance (including its interactions); a high ``sigma`` flags
a non-linear / interactive effect.

Like the tornado adapter, the canonical engine
``analytics.sensitivity.global_sa.run_morris`` is **path-based** (it re-reads the
scenario per model evaluation), so this writes the in-memory scenario to a private temp
file, runs the canonical screening over the scenario's ``monte_carlo.parameters``, and
maps the result to a small render-ready block. No SA logic is reimplemented (CCCDIR).

Morris on the lender scenario is ~8s (``n_trajectories·(D+1)`` evaluations). The full
Sobol S1/ST variance decomposition is ~3 min and stays on the on-demand CLI
(``scripts/run_global_sensitivity.py --method sobol``), not inline. CASPER — best-effort:
a failure (no ``monte_carlo.parameters``, SALib absent, …) returns ``None`` and the
section is omitted; the core report stays fail-loud.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Callable, List, Mapping, Optional

import yaml
from pydantic import BaseModel

from analytics.sensitivity.global_sa import run_morris

logger = logging.getLogger(__name__)

#: Morris trajectories for the report screening (``n·(D+1)`` model runs; 16 ≈ 8s at D=6).
_REPORT_MORRIS_TRAJECTORIES = 16

#: ``(config_path, *, metrics, n_trajectories) -> result_dict`` — injectable so tests
#: exercise this adapter without running the real (slow) multi-evaluation screening.
GlobalSARunner = Callable[..., Mapping[str, Any]]


class GlobalSADriver(BaseModel):
    """One driver's global-screening result for the target metric."""

    name: str
    mu_star: Optional[float] = None  # overall importance (incl. interactions)
    sigma: Optional[float] = None  # spread → non-linear / interactive effect


class GlobalSABlock(BaseModel):
    """The report's global sensitivity block: drivers ranked most-important first."""

    method: str  # "morris"
    metric: str  # e.g. "project_irr"
    n_runs: Optional[int] = None
    drivers: List[GlobalSADriver]


def compute_report_global_sa(
    scenario_config: Mapping[str, Any],
    *,
    metric: str = "project_irr",
    n_trajectories: int = _REPORT_MORRIS_TRAJECTORIES,
    runner: GlobalSARunner = run_morris,
) -> Optional[GlobalSABlock]:
    """Run a Morris global-SA screening for the report, or ``None`` on failure.

    Args:
        scenario_config: The resolved scenario to screen (written to a private temp
            file because the canonical runner is path-based). Its
            ``monte_carlo.parameters`` define the drivers.
        metric: The target KPI to screen (default ``"project_irr"``).
        n_trajectories: Morris trajectories (cost is ``n·(D+1)`` model evaluations).
        runner: The screening engine; injectable so tests need not run the real
            pipeline.

    Returns:
        A render-ready :class:`GlobalSABlock` with drivers ranked by ``mu_star``, or
        ``None`` if the screening raised or produced no usable rows — the supplementary
        section never sinks the core report (CASPER).
    """
    path: Optional[str] = None
    try:
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="dutchbay_globalsa_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(dict(scenario_config), fh)
        result = runner(path, metrics=[metric], n_trajectories=n_trajectories)
    except Exception:  # noqa: BLE001 - supplementary section: log + degrade, never 500
        logger.exception(
            "Report global-SA screening failed; rendering report without it"
        )
        return None
    finally:
        if path is not None and os.path.exists(path):
            os.unlink(path)

    per_metric = (result.get("metrics") or {}).get(metric) or {}
    raw = per_metric.get("drivers") or {}
    ranking = per_metric.get("ranking") or sorted(
        raw, key=lambda k: (raw[k] or {}).get("mu_star") or 0.0, reverse=True
    )
    drivers = [
        GlobalSADriver(
            name=str(name),
            mu_star=(raw[name] or {}).get("mu_star"),
            sigma=(raw[name] or {}).get("sigma"),
        )
        for name in ranking
        if name in raw
    ]
    if not drivers:
        return None
    return GlobalSABlock(
        method=str(result.get("method", "morris")),
        metric=metric,
        n_runs=result.get("n_runs"),
        drivers=drivers,
    )
