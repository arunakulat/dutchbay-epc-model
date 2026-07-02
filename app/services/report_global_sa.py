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

The same degrade path covers an engine-FLAGGED metric (#644): when the screening marks
the target metric ``nan_poisoned`` (too many non-finite outputs) or ``flat_metric``
(structurally invariant), its ``drivers`` are zeroed placeholders, not results — rendering
them would print every driver at 0.00% with no caveat, a confident false claim (e.g. "FX
does not influence the IRR"). The section is omitted (``None``) instead, with the engine's
reason logged.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Callable, List, Mapping, Optional

import yaml
from pydantic import BaseModel

from analytics.sensitivity.global_sa import run_morris, run_pawn

logger = logging.getLogger(__name__)

#: Morris trajectories for the report screening (``n·(D+1)`` model runs; 16 ≈ 8s at D=6).
_REPORT_MORRIS_TRAJECTORIES = 16

#: PAWN sample size / conditioning slices for the report block (given-data KS; #645).
#: ``n=256`` / ``s=10`` are the engine defaults; at these the inert-driver median-KS noise
#: floor is ~0.15, disclosed in the report copy so low-end ranks are not read as influence.
_REPORT_PAWN_N = 256
_REPORT_PAWN_S = 10

#: ``(config_path, *, metrics, **kwargs) -> result_dict`` — injectable so tests exercise
#: these adapters without running the real (slow) multi-evaluation screening.
GlobalSARunner = Callable[..., Mapping[str, Any]]


class GlobalSADriver(BaseModel):
    """One driver's global-screening result for the target metric.

    Carries BOTH method families' indices as optional fields (the template renders whichever
    the block's ``method`` populated): Morris ``mu_star`` / ``sigma`` and PAWN ``median_ks`` /
    ``ks_cv`` (median Kolmogorov-Smirnov statistic + its across-slice coefficient of variation).
    """

    name: str
    mu_star: Optional[float] = None  # Morris: overall importance (incl. interactions)
    sigma: Optional[float] = None  # Morris: spread → non-linear / interactive effect
    median_ks: Optional[float] = (
        None  # PAWN: median KS distance → distributional influence
    )
    ks_cv: Optional[float] = None  # PAWN: CV of the KS across conditioning slices


class GlobalSABlock(BaseModel):
    """The report's global sensitivity block: drivers ranked most-important first."""

    method: str  # "morris" | "pawn"
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
        ``None`` if the screening raised, produced no usable rows, or flagged the metric
        (``nan_poisoned`` / ``flat_metric`` — zeroed placeholder drivers that would render
        as an uncaveated all-0.00% table) — the supplementary section never sinks the
        core report, and never renders a flagged placeholder as a result (CASPER).
    """
    screened = _screen_and_check(
        scenario_config, metric=metric, runner=runner, n_trajectories=n_trajectories
    )
    if screened is None:
        return None
    result, per_metric = screened
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


def compute_report_global_sa_pawn(
    scenario_config: Mapping[str, Any],
    *,
    metric: str = "project_irr",
    n: int = _REPORT_PAWN_N,
    s: int = _REPORT_PAWN_S,
    runner: GlobalSARunner = run_pawn,
) -> Optional[GlobalSABlock]:
    """Run a PAWN global-SA block for the report, or ``None`` on failure (#645).

    PAWN's median Kolmogorov-Smirnov index is a *distribution*-based measure that stays
    bounded in [0, 1] and is robust on the skewed / covenant-pinned KPIs where variance-based
    Sobol misbehaves, so it is the natural complement to the Morris screening in the lender SA
    section. This adapter mirrors :func:`compute_report_global_sa`: it writes the in-memory
    scenario to a private temp file (the canonical ``run_pawn`` is path-based), screens the
    scenario's ``monte_carlo.parameters``, and maps the result to a render-ready block — no SA
    logic is reimplemented here (CCCDIR).

    Args:
        scenario_config: The resolved scenario to screen. Its ``monte_carlo.parameters``
            define the drivers.
        metric: The target KPI to screen (default ``"project_irr"``).
        n: PAWN LHS sample size (given-data KS; cost is ``n`` model evaluations).
        s: PAWN conditioning slices.
        runner: The screening engine; injectable so tests need not run the real pipeline.

    Returns:
        A render-ready :class:`GlobalSABlock` with drivers ranked by median KS, or ``None``
        if the screening raised, produced no usable rows, or flagged the metric
        (``nan_poisoned`` / ``flat_metric``) — best-effort per CASPER, never sinking the core
        report and never rendering a zeroed placeholder as a result.
    """
    screened = _screen_and_check(
        scenario_config, metric=metric, runner=runner, n=n, s=s
    )
    if screened is None:
        return None
    result, per_metric = screened
    raw = per_metric.get("drivers") or {}
    ranking = per_metric.get("ranking") or sorted(
        raw, key=lambda k: (raw[k] or {}).get("median") or 0.0, reverse=True
    )
    drivers = [
        GlobalSADriver(
            name=str(name),
            median_ks=(raw[name] or {}).get("median"),
            ks_cv=(raw[name] or {}).get("cv"),
        )
        for name in ranking
        if name in raw
    ]
    if not drivers:
        return None
    return GlobalSABlock(
        method=str(result.get("method", "pawn")),
        metric=metric,
        n_runs=result.get("n_runs"),
        drivers=drivers,
    )


def _screen_and_check(
    scenario_config: Mapping[str, Any],
    *,
    metric: str,
    runner: GlobalSARunner,
    **runner_kwargs: Any,
) -> Optional[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Run a path-based screening runner and apply the shared CASPER degrade path.

    Writes the in-memory scenario to a private temp file, invokes ``runner(path,
    metrics=[metric], **runner_kwargs)``, and returns ``(result, per_metric)`` — or ``None``
    when the screening raised, produced no metric entry, or FLAGGED the metric
    (``nan_poisoned`` / ``flat_metric``: zeroed placeholder drivers that would render as an
    uncaveated all-0.00% table). Shared by the Morris and PAWN adapters so both take exactly
    the same best-effort omission and temp-file lifecycle (CASPER, DRY).
    """
    path: Optional[str] = None
    try:
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="dutchbay_globalsa_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(dict(scenario_config), fh)
        result = runner(path, metrics=[metric], **runner_kwargs)
    except Exception:  # noqa: BLE001 - supplementary section: log + degrade, never 500
        logger.exception(
            "Report global-SA screening failed; rendering report without it"
        )
        return None
    finally:
        if path is not None and os.path.exists(path):
            os.unlink(path)

    per_metric = (result.get("metrics") or {}).get(metric) or {}
    for flag, reason_key in (
        ("nan_poisoned", "nan_poisoned_reason"),
        ("flat_metric", "flat_metric_reason"),
    ):
        if per_metric.get(flag):
            logger.warning(
                "Report global-SA metric '%s' is flagged %s (%s); its zeroed placeholder "
                "drivers would render as an uncaveated all-0.00%% table — omitting the "
                "Global Sensitivity section from the report.",
                metric,
                flag,
                per_metric.get(reason_key) or "no reason attached",
            )
            return None
    return result, per_metric
