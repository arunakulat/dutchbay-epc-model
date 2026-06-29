"""Compute the lender report's sensitivity tornado (RPT-1).

The report embeds a one-at-a-time (OAT) tornado over the standard financial drivers
(tariff, CAPEX, OPEX, capacity factor, tax, …). The canonical sweep engine
``analytics.core.sensitivity_runner.run_sensitivity_analysis`` is **path-based** (it
re-reads the scenario from disk per shock), so this adapter writes the in-memory
wizard scenario to a private temp file, runs the canonical sweep — building its
default driver library from the config — and maps the resulting ``SensitivitySuite``
to a small render-ready block. No tornado logic is reimplemented here (CCCDIR).

CASPER — the tornado is a *supplementary* visualisation that costs N extra pipeline
runs; a failure in it must never sink the core report, so the compute is best-effort:
it returns ``None`` (and logs) on any error. The CORE report blocks stay fail-loud.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Callable, List, Mapping, Optional

import yaml
from pydantic import BaseModel

from analytics.contracts_v14 import SensitivitySuite
from analytics.core.sensitivity_runner import run_sensitivity_analysis

logger = logging.getLogger(__name__)

#: ``(config_path, *, metric) -> SensitivitySuite`` — the sweep engine, injectable so
#: tests exercise this adapter without running the real (slow) multi-shock pipeline.
SweepRunner = Callable[..., SensitivitySuite]


class TornadoRow(BaseModel):
    """One driver's one-at-a-time impact on the target metric."""

    label: str
    base: Optional[float] = None
    low_case: Optional[float] = None
    high_case: Optional[float] = None
    impact_abs: Optional[float] = None  # |swing| = how far the metric moves


class TornadoBlock(BaseModel):
    """The report tornado: the target metric and its drivers, widest swing first."""

    metric: str
    rows: List[TornadoRow]


def _to_row(tornado: Any) -> Optional[TornadoRow]:
    """Map one canonical ``TornadoResult`` to a render row (None if unlabelled)."""
    shocks = tornado.shock_results or []
    first = shocks[0] if shocks else None
    label = (
        (
            (getattr(first, "label", None) or getattr(first, "variable_name", None))
            if first is not None
            else None
        )
        or tornado.label
        or tornado.metric_name
    )
    if not label:
        return None
    return TornadoRow(
        label=str(label),
        base=tornado.base_metric,
        low_case=getattr(first, "low_case", None),
        high_case=getattr(first, "high_case", None),
        impact_abs=tornado.impact_abs,
    )


def compute_report_tornado(
    scenario_config: Mapping[str, Any],
    *,
    metric: str = "project_irr",
    runner: SweepRunner = run_sensitivity_analysis,
) -> Optional[TornadoBlock]:
    """Run an OAT tornado over the standard drivers, or ``None`` on failure.

    Args:
        scenario_config: The resolved scenario to sweep (written to a private temp
            file because the canonical runner is path-based).
        metric: The target KPI to sweep (default ``"project_irr"``).
        runner: The sweep engine; injectable so tests need not run the real pipeline.

    Returns:
        A render-ready :class:`TornadoBlock` with drivers sorted widest-swing first, or
        ``None`` if the sweep raised or produced no usable rows — the supplementary
        tornado never sinks the core report (CASPER).
    """
    path: Optional[str] = None
    try:
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="dutchbay_tornado_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(dict(scenario_config), fh)
        suite = runner(path, metric=metric)
    except (
        Exception
    ):  # noqa: BLE001 - supplementary section: log + degrade, never 500 the report
        logger.exception("Report tornado sweep failed; rendering report without it")
        return None
    finally:
        if path is not None and os.path.exists(path):
            os.unlink(path)

    rows = [r for r in (_to_row(tr) for tr in suite.tornado_results) if r is not None]
    rows.sort(
        key=lambda r: r.impact_abs if r.impact_abs is not None else 0.0, reverse=True
    )
    if not rows:
        return None
    return TornadoBlock(metric=metric, rows=rows)
