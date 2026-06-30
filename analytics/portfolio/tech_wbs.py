"""Per-technology cost/return work-breakdown for hybrid scenarios (ARCH-3, #475).

The keystone the deep-research audit flagged as ``ARCH-3`` and the #448 work
deliberately deferred: a per-technology CAPEX / OPEX / cost-of-capital breakdown for a
hybrid plant, **reconciled** against the authoritative financed totals.

Design — why this is additive and KPI-neutral
----------------------------------------------
The finance engine reads ONE financed CAPEX (``capex.usd_total``) and one project
OPEX. The per-tech ``generation.technologies.<tech>.capex_usd`` field is *reporting
only* by design — the "phantom-capex" decoupling that lets Monte-Carlo / sensitivity
perturb a single financed total (see
:mod:`analytics.portfolio.multi_tech_tornado`). This module **preserves** that design:
it performs no finance recomputation, so committed scenarios are byte-identical. What
it adds is the reconciliation #448 left open — it ties the per-tech split back to the
financed total and surfaces the gap honestly.

Reconciliation contract (CESSPIT — fail loud on a real error)
-------------------------------------------------------------
``capex_residual_usd = financed_capex - allocated_capex`` is the shared /
balance-of-plant / unallocated bucket (grid connection, the 220 kV line, development
cost — capex that is not attributable to a single technology). A **positive** residual
(financed > allocated) is expected and legitimate. Allocations that *exceed* the
financed total beyond ``reconcile_tolerance_pct`` are a real modelling error (you have
attributed more capex than is financed) and raise ``ValueError`` at build time. OPEX
reconciles the same way against the project OPEX.

Per-tech WACC is **disclosed only**
-----------------------------------
``cost_of_equity`` is populated when a technology block declares its own
``wacc.cost_of_equity`` (else ``None`` and ``wacc_basis == "blended"`` — the single
project WACC applies). It does NOT feed back into the financed economics: per-tech-WACC
*financing* (a blended cost of capital weighted by per-tech capital) would move the
hybrid KPIs and is a separate, explicitly-authorized step (a decision point, not an
automatic change — mirrors the frozen-export re-baseline discipline).

The blended ``project_wacc_nominal`` on the aggregate is best supplied by the caller
from the *resolved* run WACC (``ScenarioResult.wacc``): every committed multi-tech
scenario uses ``wacc.mode: build_up``, whose WACC is computed in-pipeline from the sized
debt and is therefore NOT derivable from raw config. When the caller passes nothing, the
field falls back to :func:`finance.wacc_v14.compute_wacc_from_config`, which only resolves
``fixed`` / CAPM modes (``None`` for ``build_up``) — so direct config-only callers of a
build-up scenario will see ``None`` until they pass the resolved value.

CCCDIR single-source resolvers (lazy-imported at call time, mirroring
:mod:`analytics.core.metrics` / :mod:`analytics.cost.mc_capex`, to keep this analytics
module free of module-scope ``finance`` imports):

* financed CAPEX → :func:`finance.debt_v14._extract_capex_usd` — the SAME total the debt
  engine sizes against, so the reconciliation is honest for ``capex.derive_from_breakdown``
  (bottom-up) and AACE QRA contingency, not just a flat ``capex.usd_total``.
* technology discovery → :mod:`analytics.portfolio.multi_tech_tornado`.
"""

from __future__ import annotations

import logging
import math
from typing import Any, List, Mapping, Optional, Tuple

from analytics.contracts_v14 import MultiTechWBS, TechnologyCostReturn
from analytics.portfolio.multi_tech_tornado import (
    discover_generation_technologies,
    discover_storage_technologies,
)

logger = logging.getLogger(__name__)


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    """Walk a nested mapping by ``path``; return ``None`` on any miss."""
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _as_float(value: Any) -> Optional[float]:
    """Coerce a config scalar to ``float``; ``None`` for absent/non-numeric/bool/non-finite."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        coerced = float(value)
        return coerced if math.isfinite(coerced) else None
    return None


def _technology_blocks(
    config: Mapping[str, Any],
) -> List[Tuple[str, Mapping[str, Any]]]:
    """Every ``(name, block)`` under ``generation.technologies``, in declared order."""
    techs = _nested_get(config, "generation", "technologies")
    if not isinstance(techs, Mapping):
        return []
    return [
        (str(name), block)
        for name, block in techs.items()
        if isinstance(block, Mapping)
    ]


#: Default reconciliation tolerance (percent of the financed total). Allocations may
#: undershoot freely (the shortfall is the shared/BOP residual); they may only overshoot
#: the financed total by this much before it is treated as a real over-attribution error.
DEFAULT_RECONCILE_TOLERANCE_PCT: float = 1.0

#: Per-tech OPEX field paths under ``generation.technologies.<tech>``, first hit wins.
#: Unit-suffixed per FIN-02; ``opex_usd`` / ``opex_annual_usd`` are tolerated aliases.
_TECH_OPEX_KEYS: tuple[str, ...] = ("opex_usd_per_year", "opex_usd", "opex_annual_usd")

#: Project-level OPEX paths (mirrors finance.cashflow_v14_params resolution order).
_PROJECT_OPEX_PATHS: tuple[tuple[str, ...], ...] = (
    ("opex", "usd_per_year"),
    ("opex", "usd_annual"),
    ("opex", "annual_opex_usd"),
    ("costs", "opex_usd_per_year"),
    ("costs", "opex_annual_usd"),
    ("opex_usd_per_year",),
)


def _resolve_project_opex_usd(config: Mapping[str, Any]) -> Optional[float]:
    """Resolve the financed annual project OPEX (USD), config-first; ``None`` if absent."""
    for path in _PROJECT_OPEX_PATHS:
        value = _as_float(_nested_get(config, *path))
        if value is not None:
            return value
    return None


def _resolve_financed_capex_usd(config: Mapping[str, Any]) -> Optional[float]:
    """Financed CAPEX total via the debt engine's canonical resolver.

    Delegates to :func:`finance.debt_v14._extract_capex_usd` (lazy import — the same seam
    :mod:`analytics.core.metrics` and :mod:`analytics.cost.mc_capex` use) so the
    reconciliation matches what the debt engine actually finances: ``capex.usd_total``,
    ``capex.derive_from_breakdown`` (bottom-up line items) and AACE QRA contingency.
    Returns ``None`` when no CAPEX is resolvable (the resolver raises on an absent/empty
    CAPEX; the WBS is opportunistic and must not crash the run).
    """
    from finance.debt_v14 import _extract_capex_usd

    try:
        return float(_extract_capex_usd(dict(config)))
    except (ValueError, TypeError, KeyError):
        return None


def _nonneg_or_warn(
    value: Optional[float], field_name: str, tech: str
) -> Optional[float]:
    """Drop a negative per-tech amount with a warning (data-entry guard).

    A negative ``capex_usd`` / ``opex`` would corrupt the allocated sum (and could null
    every share via the ``allocated > 0`` guard with no signal). Treat it as absent and
    warn, so a malformed input is surfaced rather than silently degrading the report.
    """
    if value is not None and value < 0:
        logger.warning(
            "generation.technologies['%s'].%s is negative (%.0f); excluding it from the "
            "WBS allocation.",
            tech,
            field_name,
            value,
        )
        return None
    return value


def _tech_opex_usd(block: Mapping[str, Any]) -> Optional[float]:
    """Per-technology annual OPEX (USD) from the first present alias, else ``None``."""
    for key in _TECH_OPEX_KEYS:
        value = _as_float(block.get(key))
        if value is not None:
            return value
    return None


def resolve_tech_opex_usd(config: Mapping[str, Any], tech: str) -> Optional[float]:
    """Per-technology annual OPEX (USD) for ``tech`` from its ``generation.technologies``
    block, or ``None`` if absent.

    The single source of truth for per-tech OPEX (the same ``_TECH_OPEX_KEYS`` the WBS
    uses), exposed so consumers (e.g. the multi-tech generation aggregator's ARCH-2
    margin split) reuse it without building the full work-breakdown — no double work and
    no over-attribution raise.
    """
    block = _nested_get(config, "generation", "technologies", tech)
    return _tech_opex_usd(block) if isinstance(block, Mapping) else None


def _tech_cost_of_equity(block: Mapping[str, Any]) -> Optional[float]:
    """Per-technology cost of equity, if the block declares its own ``wacc`` override.

    Mirrors :func:`finance.wacc_v14.resolve_cost_of_equity` inputs
    (``wacc.cost_of_equity`` or ``wacc.target_equity_return``) but only the *direct*
    forms — a per-tech build-up WACC is out of scope for the disclosure surface.
    Returns ``None`` when the technology inherits the project (blended) WACC.
    """
    wacc = block.get("wacc")
    if not isinstance(wacc, Mapping):
        return None
    return _as_float(wacc.get("cost_of_equity", wacc.get("target_equity_return")))


def _tech_class(name: str, generation_names: set[str], storage_names: set[str]) -> str:
    """Classify a technology as ``"generation"`` / ``"storage"`` / ``"other"``.

    Uses the public discovery from :mod:`analytics.portfolio.multi_tech_tornado` (the
    single source of truth for technology classification) so this surface cannot drift
    from the tornado / generation aggregator.
    """
    if name in generation_names:
        return "generation"
    if name in storage_names:
        return "storage"
    return "other"


def build_multi_tech_wbs(
    config: Mapping[str, Any],
    *,
    project_wacc_nominal: Optional[float] = None,
    reconcile_tolerance_pct: float = DEFAULT_RECONCILE_TOLERANCE_PCT,
) -> Optional[MultiTechWBS]:
    """Build the per-technology cost/return work-breakdown for a scenario.

    Resolves each ``generation.technologies.<tech>`` block's reporting CAPEX / OPEX and
    its per-tech cost-of-equity disclosure, then reconciles the allocations against the
    financed CAPEX (the debt engine's resolved total) and project OPEX. Generation and
    storage technologies are both included (a BESS carries CAPEX even though it earns a
    capacity charge, not generation revenue).

    Args:
        config: A loaded scenario config mapping.
        project_wacc_nominal: The *resolved* blended project WACC (e.g.
            ``ScenarioResult.wacc.base.wacc_nominal`` from the run). Pass this for
            ``build_up``-mode scenarios — their WACC is computed in-pipeline from sized
            debt and is not config-derivable. When ``None``, falls back to
            :func:`finance.wacc_v14.compute_wacc_from_config` (resolves ``fixed`` / CAPM
            only; yields ``None`` for ``build_up``).
        reconcile_tolerance_pct: Percent of the financed total an allocation may exceed
            before it is treated as an over-attribution error.

    Returns:
        A :class:`~analytics.contracts_v14.MultiTechWBS`, or ``None`` for a legacy
        single-tech scenario with no ``generation.technologies`` block (so callers can
        attach the view opportunistically, exactly like the generation aggregator).

    Raises:
        ValueError: A per-tech CAPEX or OPEX allocation exceeds the financed total
            beyond ``reconcile_tolerance_pct`` (CESSPIT — a real over-attribution).
    """
    blocks = _technology_blocks(config)
    if not blocks:
        return None

    financed_capex = _resolve_financed_capex_usd(config)
    financed_opex = _resolve_project_opex_usd(config)
    project_wacc = project_wacc_nominal
    if project_wacc is None:
        from finance.wacc_v14 import compute_wacc_from_config

        project_wacc = compute_wacc_from_config(dict(config)).get("wacc_nominal")
    generation_names = set(discover_generation_technologies(config))
    storage_names = set(discover_storage_technologies(config))

    rows: dict[str, TechnologyCostReturn] = {}
    allocated_capex = 0.0
    allocated_opex = 0.0
    for name, block in blocks:
        capex = _nonneg_or_warn(_as_float(block.get("capex_usd")), "capex_usd", name)
        opex = _nonneg_or_warn(_tech_opex_usd(block), "opex", name)
        coe = _tech_cost_of_equity(block)
        if capex is not None:
            allocated_capex += capex
        if opex is not None:
            allocated_opex += opex
        rows[name] = TechnologyCostReturn(
            technology=name,
            capex_usd=capex,
            opex_usd_per_year=opex,
            cost_of_equity=coe,
            wacc_basis="tech-specific" if coe is not None else "blended",
            notes=_tech_class(name, generation_names, storage_names),
        )

    capex_reconciled, capex_residual = _reconcile(
        "CAPEX", financed_capex, allocated_capex, reconcile_tolerance_pct
    )
    opex_reconciled, opex_residual = _reconcile(
        "OPEX", financed_opex, allocated_opex, reconcile_tolerance_pct
    )

    # Per-tech shares are of the ALLOCATED (attributed) total, so attributed techs sum to
    # 100%; the unallocated residual is reported separately on the aggregate.
    for name, row in rows.items():
        rows[name] = TechnologyCostReturn(
            technology=row.technology,
            capex_usd=row.capex_usd,
            opex_usd_per_year=row.opex_usd_per_year,
            cost_of_equity=row.cost_of_equity,
            wacc_basis=row.wacc_basis,
            share_of_capex_pct=(
                100.0 * row.capex_usd / allocated_capex
                if row.capex_usd is not None and allocated_capex > 0
                else None
            ),
            share_of_opex_pct=(
                100.0 * row.opex_usd_per_year / allocated_opex
                if row.opex_usd_per_year is not None and allocated_opex > 0
                else None
            ),
            notes=row.notes,
        )

    return MultiTechWBS(
        technologies=rows,
        financed_capex_usd=financed_capex,
        allocated_capex_usd=allocated_capex,
        capex_residual_usd=capex_residual,
        capex_reconciled=capex_reconciled,
        financed_opex_usd_per_year=financed_opex,
        allocated_opex_usd_per_year=allocated_opex,
        opex_residual_usd_per_year=opex_residual,
        opex_reconciled=opex_reconciled,
        project_wacc_nominal=_as_float(project_wacc),
        reconcile_tolerance_pct=reconcile_tolerance_pct,
        notes=(
            "Per-tech CAPEX/OPEX are reporting-only (financed totals unchanged); per-tech "
            "cost_of_equity is disclosure-only and does not feed the financed WACC."
        ),
    )


def _reconcile(
    label: str,
    financed: Optional[float],
    allocated: float,
    tolerance_pct: float,
) -> tuple[bool, Optional[float]]:
    """Reconcile an allocated sum against a financed total.

    Returns ``(reconciled, residual)`` where ``residual = financed - allocated`` (the
    shared/unallocated bucket) and ``reconciled`` is True iff a financed total is present
    and the allocation does not exceed it beyond tolerance. A positive residual is fine
    (under-allocation = shared/BOP cost); an allocation overshooting the financed total
    beyond tolerance raises.

    Raises:
        ValueError: ``allocated`` exceeds ``financed`` by more than ``tolerance_pct``.
    """
    # A non-positive financed total cannot be reconciled against: it has no economic
    # meaning as a denominator, and ``abs(financed) * tol`` would INVERT the
    # over-attribution test (a negative financed total makes any non-negative allocation
    # spuriously "exceed" it). Treat <=0 like an absent total.
    if financed is None or financed <= 0:
        if allocated > 0:
            logger.warning(
                "Per-tech %s allocates %.0f USD but the financed total is %s; "
                "cannot reconcile.",
                label,
                allocated,
                "absent" if financed is None else f"non-positive ({financed:,.0f})",
            )
        return False, None
    residual = financed - allocated
    tolerance_abs = abs(financed) * (tolerance_pct / 100.0)
    if allocated - financed > tolerance_abs:
        raise ValueError(
            f"Per-tech {label} over-attribution: allocated {allocated:,.0f} USD exceeds "
            f"the financed total {financed:,.0f} USD by more than {tolerance_pct:g}% "
            f"({allocated - financed:,.0f} USD over). The per-tech split must not exceed "
            f"the financed total — correct the per-tech values or the financed total."
        )
    return True, residual


__all__ = [
    "DEFAULT_RECONCILE_TOLERANCE_PCT",
    "build_multi_tech_wbs",
    "resolve_tech_opex_usd",
]
