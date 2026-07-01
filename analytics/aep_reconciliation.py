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
otherwise (PR #263; the same class as red-flag-register item #175).

**This is a DETECTOR, not a single-source-of-truth fix.** It makes the contradiction
fail loud; it does not make the bankable AEP authoritative (``capacity_mw × CF`` remains
the billed quantity). A scenario with a stale capacity and *no* bankable AEP still sails
through, and widening ``aep_reconciliation.tolerance_pct`` is an *audited override*, not
a fix — a non-default tolerance is logged at WARNING so it is visible in run output.

When a scenario carries BOTH a bankable net-AEP reference AND a resolvable capacity +
capacity_factor it asserts::

    | capacity_mw · capacity_factor · 8.760  −  net_aep |  /  net_aep   ≤   tolerance

against every bankable reference present, and **fails loud** otherwise (CESSPIT). It
changes no computed number, so it preserves byte-identical economics.

Crucially, capacity_mw and capacity_factor are resolved through the **same path lists and
the same ``pct_to_decimal`` normalization the finance engine uses** (the shared
``finance.cashflow_v14_utils.CAPACITY_MW_PATHS`` / ``CAPACITY_FACTOR_PATHS``), so the
guard reconciles *exactly* the values the engine bills off — including percent-form CF
(``project.capacity_factor: 33.9`` → 0.339) and the ``capacity_factor_pct`` / nested
authoring forms — rather than one of several aliases.

Why a guard and not "have finance read the bankable AEP directly": the opt-in
wind→finance bridge (``analytics.wind.wind_integration``) already drives finance off the
bankable export when a project opts in, and most scenarios legitimately carry only a
``capacity_factor``. The bankable summary's net is net-of-*wind*-losses only, while the
engine applies an additional ``grid_loss_pct`` downstream — so wiring finance straight
off the summary would double-count grid loss. The defect was the *silent* divergence,
which this makes explicit.

Tolerance is config-first (CESSPIT / CCCDIR — never a Python literal)::

    scenario ``aep_reconciliation.tolerance_pct``  →  else
    ``config/defaults.yaml`` ``defaults.aep_reconciliation.tolerance_pct``

This mirrors ``analytics.cost.cost_basis`` and ``analytics.fx.fx_fetch``. The guard runs
at AUTHORED-scenario LOAD time (``analytics.scenario_loader``) and on authored configs at
the API boundary, NOT on every derived run — so deliberate sensitivity/Monte-Carlo
perturbations of capacity_factor (in-memory dicts, never re-loaded) are unaffected.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional, TypeGuard

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


def _is_number(value: Any) -> TypeGuard[float]:
    """True for a real numeric (bool is a subclass of int — explicitly excluded)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def resolve_billed_capacity_and_factor(
    config: dict[str, Any],
) -> tuple[Optional[float], Optional[float]]:
    """Resolve the (capacity_mw, capacity_factor) the finance engine bills off.

    Uses the SAME path-precedence lists and the SAME ``pct_to_decimal`` normalization as
    ``finance.cashflow_v14_params._build_cashflow_params`` (imported lazily to avoid any
    load-order cycle), so the guard tracks the engine's actual revenue basis — including
    percent-form CF and the ``capacity_factor_pct`` / nested authoring forms — rather than
    one of several aliases. Returns ``(None, None)`` components when unresolved.
    """
    from finance.cashflow_v14_utils import (
        CAPACITY_FACTOR_PATHS,
        CAPACITY_MW_PATHS,
        as_float_or_none,
        pct_to_decimal,
        resolve_first,
    )

    capacity_mw = as_float_or_none(resolve_first(config, *CAPACITY_MW_PATHS))
    capacity_factor = pct_to_decimal(
        as_float_or_none(resolve_first(config, *CAPACITY_FACTOR_PATHS))
    )
    return capacity_mw, capacity_factor


def collect_bankable_net_aep_gwh(config: Mapping[str, Any]) -> dict[str, float]:
    """Collect available bankable net-AEP references (GWh), labelled by source.

    Reads ``expected_results.net_aep_p50_gwh`` and, if present and readable, the
    ``resource.aep_summary_path`` JSON's ``net_site_aep_gwh`` (falling back to
    ``net_aep_p50_gwh``). A declared-but-unreadable summary is *logged at WARNING* (a
    silently-disarmed reference would itself be the silent-divergence failure mode this
    guard exists to kill) and then skipped.
    """
    refs: dict[str, float] = {}

    expected = config.get("expected_results")
    if isinstance(expected, Mapping):
        value = expected.get("net_aep_p50_gwh")
        if _is_number(value):
            refs["expected_results.net_aep_p50_gwh"] = float(value)

    resource = config.get("resource")
    if isinstance(resource, Mapping):
        path = resource.get("aep_summary_path")
        if isinstance(path, str) and path:
            summary_path = Path(path)
            # WIND-7 / CESSPIT: a DECLARED aep_summary_path commits the scenario to it.
            # A missing/unreadable/unparseable summary must FAIL LOUD — silently skipping
            # it disarms the AEP<->CF reconciliation this guard exists to perform, which is
            # exactly the silent-divergence failure mode it is meant to prevent.
            if not summary_path.exists():
                raise AepReconciliationError(
                    f"resource.aep_summary_path {path!r} is declared but not readable "
                    f"from cwd ({Path.cwd()}). A bankable-AEP reference must resolve to a "
                    f"committed production artifact (e.g. scenarios/aep_summary_*.json); "
                    f"refusing to silently skip it (WIND-7)."
                )
            try:
                data = json.loads(summary_path.read_text())
            except (OSError, ValueError) as exc:
                raise AepReconciliationError(
                    f"resource.aep_summary_path {path!r} could not be read/parsed as "
                    f"JSON: {exc}. Refusing to silently skip the bankable-AEP reference "
                    f"(WIND-7)."
                ) from exc
            if isinstance(data, Mapping):
                value = data.get("net_site_aep_gwh")
                if value is None:
                    value = data.get("net_aep_p50_gwh")
                if _is_number(value):
                    refs[f"{path}:net_site_aep_gwh"] = float(value)
    return refs


def collect_bankable_net_aep_p90_gwh(config: Mapping[str, Any]) -> dict[str, float]:
    """Collect available bankable net-AEP **P90** references (GWh), labelled by source.

    The P90 analogue of :func:`collect_bankable_net_aep_gwh`. Reads the frozen
    ``expected_results.net_aep_p90_gwh`` and, when the ``resource.aep_summary_path`` export
    exists, parses, and carries it, the authoritative ``exceedance.net_aep_p90_1yr_gwh``.

    Unlike the P50 collector this does NOT re-raise on a missing/unparseable summary — that
    fail-loud contract is owned by :func:`collect_bankable_net_aep_gwh` (which runs first in
    :func:`reconcile_capacity_factor_with_bankable_aep`); and a summary that simply does not
    export a P90 is not an error (not every bankable export computes exceedance).
    """
    refs: dict[str, float] = {}

    expected = config.get("expected_results")
    if isinstance(expected, Mapping):
        value = expected.get("net_aep_p90_gwh")
        if _is_number(value):
            refs["expected_results.net_aep_p90_gwh"] = float(value)

    resource = config.get("resource")
    if isinstance(resource, Mapping):
        path = resource.get("aep_summary_path")
        if isinstance(path, str) and path:
            summary_path = Path(path)
            if summary_path.exists():
                try:
                    data: Any = json.loads(summary_path.read_text())
                except (OSError, ValueError):
                    data = None
                if isinstance(data, Mapping):
                    exceed = data.get("exceedance")
                    value = (
                        exceed.get("net_aep_p90_1yr_gwh")
                        if isinstance(exceed, Mapping)
                        else None
                    )
                    if value is None:
                        value = data.get("net_aep_p90_1yr_gwh")
                    if _is_number(value):
                        refs[f"{path}:exceedance.net_aep_p90_1yr_gwh"] = float(value)
    return refs


def reconcile_frozen_p90_with_bankable_summary(
    config: dict[str, Any], config_path: str | None = None
) -> None:
    """Fail loud if the frozen ``expected_results.net_aep_p90_gwh`` diverges from the
    bankable P90 in the ``resource.aep_summary_path`` export.

    No-op unless the scenario declares BOTH a frozen ``net_aep_p90_gwh`` AND a summary that
    exports ``exceedance.net_aep_p90_1yr_gwh``. The frozen P90 drives the hybrid
    P90-binds-gearing (``finance.debt_v14._resolve_downside_ratio`` reads the P90/P50 ratio to
    size the ``min(P50, P90)`` gearing), so a stale value silently moves committed hybrid
    economics. The P50 side is guarded by
    :func:`reconcile_capacity_factor_with_bankable_aep` against ``capacity_mw · CF · 8.760``;
    this restores the P50<->P90 symmetry (round-2 audit).
    """
    refs = collect_bankable_net_aep_p90_gwh(config)
    scenario_p90 = refs.get("expected_results.net_aep_p90_gwh")
    summary_key = next(
        (k for k in refs if k.endswith(":exceedance.net_aep_p90_1yr_gwh")), None
    )
    if scenario_p90 is None or summary_key is None:
        return

    summary_p90 = refs[summary_key]
    where = f" in '{config_path}'" if config_path else ""
    if scenario_p90 <= 0 or summary_p90 <= 0:
        raise AepReconciliationError(
            f"Bankable net-AEP P90 is non-positive{where}: "
            f"expected_results.net_aep_p90_gwh={scenario_p90}, {summary_key}={summary_p90} "
            "— a zero/negative P90 is nonsensical; fix the export or expected_results."
        )

    tolerance = resolve_tolerance_pct(config) / 100.0
    relative = abs(scenario_p90 - summary_p90) / summary_p90
    if relative > tolerance:
        raise AepReconciliationError(
            f"Frozen expected_results.net_aep_p90_gwh={scenario_p90:.2f} GWh does not "
            f"reconcile with the bankable P90 export {summary_key}={summary_p90:.2f} GWh "
            f"({relative * 100:.1f}% > {tolerance * 100:.1f}% tolerance){where}. This P90 "
            "drives the hybrid P90-binds-gearing (finance.debt_v14._resolve_downside_ratio "
            "reads the P90/P50 ratio to size the min(P50, P90) gearing), so a stale value "
            "silently moves committed hybrid economics. Regenerate the aep_summary export or "
            "fix expected_results.net_aep_p90_gwh so they agree, or set "
            "aep_reconciliation.tolerance_pct if the gap is intentional."
        )


def reconcile_capacity_factor_with_bankable_aep(
    config: dict[str, Any], config_path: str | None = None
) -> None:
    """Fail loud if ``capacity_mw · CF · 8.760`` diverges from any bankable net AEP.

    No-op when the scenario lacks a resolvable capacity_mw / capacity_factor or any
    bankable net-AEP reference. Raises :class:`AepReconciliationError` when an implied
    generation diverges from a bankable reference beyond the configured tolerance, or when
    a declared bankable reference is non-positive.

    Also reconciles the frozen P90 against the bankable P90 export (P50<->P90 symmetry) via
    :func:`reconcile_frozen_p90_with_bankable_summary`, which runs unconditionally (it does
    not depend on capacity_mw / capacity_factor).
    """
    # P90 first: it is independent of capacity/CF, so it must not be skipped by the
    # capacity/CF early-return below (round-2 audit).
    reconcile_frozen_p90_with_bankable_summary(config, config_path)

    capacity_mw, capacity_factor = resolve_billed_capacity_and_factor(config)
    if capacity_mw is None or capacity_factor is None:
        return

    references = collect_bankable_net_aep_gwh(config)
    if not references:
        return

    implied_gwh = capacity_mw * capacity_factor * _GWH_PER_MW_AT_CF1
    tolerance_pct = resolve_tolerance_pct(config)
    if tolerance_pct != default_tolerance_pct():
        logger.warning(
            "AEP reconciliation tolerance widened to %.3f%% (audited override) for %s",
            tolerance_pct,
            config_path or "<config>",
        )
    tolerance = tolerance_pct / 100.0

    where = f" in '{config_path}'" if config_path else ""
    problems: list[str] = []
    for label, reference_gwh in references.items():
        if reference_gwh <= 0:
            raise AepReconciliationError(
                f"Bankable AEP {label}={reference_gwh} GWh is non-positive{where} — a "
                "zero/negative net AEP is nonsensical; fix the export or expected_results."
            )
        relative = abs(implied_gwh - reference_gwh) / reference_gwh
        if relative > tolerance:
            problems.append(
                f"{label}={reference_gwh:.2f} GWh vs "
                f"capacity_mw*capacity_factor*8.760={implied_gwh:.2f} GWh "
                f"({relative * 100:.1f}% > {tolerance * 100:.1f}% tolerance)"
            )

    if problems:
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
    "resolve_billed_capacity_and_factor",
    "collect_bankable_net_aep_gwh",
    "collect_bankable_net_aep_p90_gwh",
    "reconcile_frozen_p90_with_bankable_summary",
    "reconcile_capacity_factor_with_bankable_aep",
]
