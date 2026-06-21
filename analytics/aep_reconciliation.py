"""AEP ↔ capacity-factor reconciliation guard.

The finance engine bills revenue off ``capacity_mw × capacity_factor × 8760``
(``finance.cashflow_v14_production._calculate_net_production``). A scenario may *also*
carry a **bankable net AEP** — the IEC-density + PyWake-wake + IEC-61400-15-2-uncertainty
P50 export — in ``expected_results.net_aep_p50_gwh`` and/or the
``resource.aep_summary_path`` JSON (key ``net_site_aep_gwh``). These are two
representations of the same physical quantity and MUST agree, but nothing enforced it.

A stale ``capacity_mw`` or ``capacity_factor`` therefore silently diverged from the
bankable AEP: a 3×-inflated ``project.capacity_mw`` (159.6 vs the real 56 MW) made the
Mullikulam scenario book ~3× its real generation while the bankable export said
otherwise (PR #263; the same class as red-flag-register item #175, "financed P50 vs
auxiliary summary disagree, finance using the higher").

This guard reconciles them. When a scenario carries BOTH a bankable net-AEP reference
AND ``project.capacity_mw`` + ``project.capacity_factor`` it asserts::

    | capacity_mw · capacity_factor · 8.760  −  net_aep |  /  net_aep   ≤   tolerance

against every bankable reference present, and **fails loud** otherwise (CESSPIT).
Scenarios without a bankable AEP are unaffected — the ``capacity_factor`` path stands
alone. The guard changes no computed number, so it preserves byte-identical economics;
it only refuses configs whose two generation sources disagree.

Why a guard and not "have finance read the bankable AEP directly": the opt-in
wind→finance bridge (``analytics.wind.wind_integration``) already drives finance off the
bankable export when a project opts in, and most scenarios legitimately have only a
``capacity_factor``. The defect was the *silent* divergence, which this makes explicit.

The bankable net AEP is net of the wind-loss stack and the scenario ``capacity_factor``
is the *net* capacity factor, so ``capacity_mw · CF · 8.760 == net AEP`` by construction
when consistent (the engine then applies an additional ``grid_loss_pct`` to reach billed
energy — out of scope here).

Tolerance is config-first (CESSPIT / CCCDIR — never a Python literal)::

    scenario ``aep_reconciliation.tolerance_pct``  →  else
    ``config/defaults.yaml`` ``defaults.aep_reconciliation.tolerance_pct``

This mirrors ``analytics.cost.cost_basis`` and ``analytics.fx.fx_fetch``.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"

# GWh produced per (MW · net capacity factor): 8760 h / 1000 (kWh → GWh).
_GWH_PER_MW_AT_CF1 = 8.760


class AepReconciliationError(ValueError):
    """Raised when capacity_factor-implied generation diverges from the bankable AEP."""


@lru_cache(maxsize=1)
def default_tolerance_pct() -> float:
    """The single config-sourced reconciliation tolerance (``config/defaults.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        return float(data["defaults"]["aep_reconciliation"]["tolerance_pct"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "config/defaults.yaml missing defaults.aep_reconciliation.tolerance_pct "
            f"({_DEFAULTS_PATH})"
        ) from exc


def resolve_tolerance_pct(config: Mapping[str, Any]) -> float:
    """Resolve the reconciliation tolerance (%) for a scenario.

    Prefers the scenario's explicit ``aep_reconciliation.tolerance_pct``; falls back to
    the single config-sourced default. Raises if the explicit value is not numeric.
    """
    block = config.get("aep_reconciliation")
    if isinstance(block, Mapping):
        tol = block.get("tolerance_pct")
        if tol is not None:
            try:
                return float(tol)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"aep_reconciliation.tolerance_pct must be numeric; got {tol!r}"
                ) from exc
    return default_tolerance_pct()


def collect_bankable_net_aep_gwh(config: Mapping[str, Any]) -> dict[str, float]:
    """Collect available bankable net-AEP references (GWh), labelled by source.

    Reads ``expected_results.net_aep_p50_gwh`` and, if present and readable, the
    ``resource.aep_summary_path`` JSON's ``net_site_aep_gwh`` (falling back to
    ``net_aep_p50_gwh``). An unreadable/absent summary is skipped — surfacing that is a
    separate concern, not this guard's job.
    """
    refs: dict[str, float] = {}

    expected = config.get("expected_results")
    if isinstance(expected, Mapping):
        value = expected.get("net_aep_p50_gwh")
        if isinstance(value, (int, float)):
            refs["expected_results.net_aep_p50_gwh"] = float(value)

    resource = config.get("resource")
    if isinstance(resource, Mapping):
        path = resource.get("aep_summary_path")
        if isinstance(path, str) and path:
            summary_path = Path(path)
            if summary_path.exists():
                try:
                    data = json.loads(summary_path.read_text())
                except (OSError, ValueError):
                    data = None
                if isinstance(data, Mapping):
                    value = data.get("net_site_aep_gwh")
                    if value is None:
                        value = data.get("net_aep_p50_gwh")
                    if isinstance(value, (int, float)):
                        refs[f"{path}:net_site_aep_gwh"] = float(value)
    return refs


def reconcile_capacity_factor_with_bankable_aep(
    config: Mapping[str, Any], config_path: str | None = None
) -> None:
    """Fail loud if ``capacity_mw · CF · 8.760`` diverges from any bankable net AEP.

    No-op when the scenario lacks ``project.capacity_mw``, ``project.capacity_factor``,
    or any bankable net-AEP reference. Raises :class:`AepReconciliationError` when an
    implied generation diverges from a bankable reference beyond the configured
    tolerance.
    """
    project = config.get("project")
    if not isinstance(project, Mapping):
        return
    capacity_mw = project.get("capacity_mw")
    capacity_factor = project.get("capacity_factor")
    if not isinstance(capacity_mw, (int, float)) or not isinstance(
        capacity_factor, (int, float)
    ):
        return

    references = collect_bankable_net_aep_gwh(config)
    if not references:
        return

    implied_gwh = float(capacity_mw) * float(capacity_factor) * _GWH_PER_MW_AT_CF1
    tolerance = resolve_tolerance_pct(config) / 100.0

    problems: list[str] = []
    for label, reference_gwh in references.items():
        if reference_gwh <= 0:
            continue
        relative = abs(implied_gwh - reference_gwh) / reference_gwh
        if relative > tolerance:
            problems.append(
                f"{label}={reference_gwh:.2f} GWh vs "
                f"capacity_mw*capacity_factor*8.760={implied_gwh:.2f} GWh "
                f"({relative * 100:.1f}% > {tolerance * 100:.1f}% tolerance)"
            )

    if problems:
        where = f" in '{config_path}'" if config_path else ""
        raise AepReconciliationError(
            f"Bankable AEP does not reconcile with capacity_mw x capacity_factor{where}: "
            + "; ".join(problems)
            + ". The finance engine bills revenue off capacity_mw*capacity_factor, so a "
            "mismatch means a stale capacity_mw/capacity_factor is silently over- or "
            "under-stating generation versus the bankable AEP export. Fix capacity_mw/"
            "capacity_factor (or the AEP export) so they agree, or set "
            "aep_reconciliation.tolerance_pct if the gap is intentional."
        )

    logger.debug(
        "AEP reconciliation OK: implied %.2f GWh within %.1f%% of %d bankable ref(s)",
        implied_gwh,
        tolerance * 100,
        len(references),
    )


__all__ = [
    "AepReconciliationError",
    "default_tolerance_pct",
    "resolve_tolerance_pct",
    "collect_bankable_net_aep_gwh",
    "reconcile_capacity_factor_with_bankable_aep",
]
