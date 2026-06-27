"""Per-technology tornado sensitivity for hybrid (multi-tech) scenarios — Epic 6.1.

Answers the lender question *"which technology drives the IRR / covenant
volatility?"* for a combined-plant scenario (e.g. the 209.6 MW wind+solar hybrid).
For every technology declared in ``generation.technologies`` it sweeps the three
finance levers that actually flow through the M3 per-tech cashflow
(:mod:`finance.cashflow_v14_production`) and reports the swing each one induces on
a set of KPIs, tagged by technology and sorted by absolute impact.

Technology independence
-----------------------
Nothing here is wind-specific: a *generation* technology is any block carrying a
``capacity_factor`` (wind, solar, tidal, run-of-river, …), discovered and swept on
the same footing, so the tool works for wind-only, solar-only, or any hybrid. A
*storage* technology (``type: bess`` — a ``power_mw`` rating, no capacity factor) is
**also swept**, on its own driver: the bid Capacity Charge Rate
(``revenue.capacity_charge_lkr_per_mw_month``), which is now a live finance driver
(the BESS capacity charge ``R × power_mw × 12`` flows through the cashflow —
:mod:`finance.bess_revenue`). So a wind+solar+BESS hybrid, or a standalone BESS,
ranks the BESS alongside the generation techs. Any block that is neither a generation
tech nor a sweepable storage tech (e.g. storage without a revenue lever) is surfaced
via a ``WARNING`` so a tornado is never mistaken for a complete one.

Why *coupled* overrides (and not a plain one-way path sweep)
------------------------------------------------------------
A naive one-way sweep of a single ``generation.technologies.<tech>.<field>`` path
does **not** produce an honest per-tech finance tornado — empirically (2026-06-24):

* ``capex_usd`` is a **reporting-only** field (it feeds the per-tech lender split in
  :mod:`analytics.portfolio.generation_aggregator`); the financed CAPEX is
  ``capex.usd_total``. Sweeping it alone yields a zero-impact *phantom bar*.
* ``capacity_factor`` is a **live** finance driver, but the M3 cashflow reconciles
  the per-tech year-1 capacity against the project headline
  ``project.capacity_mw × project.capacity_factor`` (±1%, see
  :func:`finance.cashflow_v14_production.resolve_tech_generation_specs`). Shocking a
  single tech's CF in isolation breaks that reconciliation and **raises**.

So each lever is swept as a *coupled* override that keeps the scenario internally
consistent and routes the shock to the field the engine actually reads:

==================  ===========================================================
Driver              Coupled override applied per shock
==================  ===========================================================
``capex_usd``       per-tech ``capex_usd`` **and** ``capex.usd_total`` move by the
                    same absolute delta (a tech CAPEX over/under-run on the
                    financed total).
``capacity_factor`` per-tech ``capacity_factor`` **and** the blended
                    ``project.capacity_factor`` move together, so the combined
                    generation re-prices *and* the ±1% reconciliation holds exactly.
``degradation_pct`` per-tech ``degradation_pct`` alone — degradation is not part of
                    the year-1 capacity reconciliation, so no coupling is needed.
==================  ===========================================================

All evaluation goes through the canonical gateway
:func:`analytics.evaluation_v14.evaluate_with_overrides` (ARCH-04); this module does
no finance recomputation of its own. The perturbations pass in-memory dicts, so the
authored-config ``aep_reconciliation`` guard (wired at the file-load boundary) does
not fire — only the in-cashflow per-tech reconciliation does, which the CF coupling
satisfies by construction.

A note on covenant metrics: under dual-DSCR debt sizing ``min_dscr`` is sculpted to
its target (1.30) on every case, so a ``min_dscr`` tornado is structurally flat. The
covenant-stress signal surfaces instead in the **balloon** (``balloon_pct``): a
squeezed CFADS amortises less, leaving a larger balloon. :func:`flat_metrics` flags
any all-flat metric so a pinned ``min_dscr`` is self-documenting rather than silently
misleading.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from analytics.evaluation_v14 import evaluate_with_overrides
from finance.tech_types import is_generation_type, is_storage_type

logger = logging.getLogger(__name__)

#: Config keys that mark a technology block as **storage** (e.g. BESS): a power
#: and/or energy rating rather than a capacity factor. Storage carries no
#: ``capacity_factor`` and contributes no generation/CFADS in the current finance
#: engine (``finance.cashflow_v14_production.resolve_tech_generation_specs`` skips
#: it), so it is detected and reported but **not swept** — sweeping it would be a
#: phantom axis until storage economics are modelled.
_STORAGE_KEYS: Tuple[str, ...] = ("power_mw", "energy_mwh")

#: Per-tech finance levers swept, in display order. Each maps to a coupled override
#: (see module docstring). ``capex_usd`` / ``capacity_factor`` / ``degradation_pct``
#: are the per-tech config fields under ``generation.technologies.<tech>``.
DEFAULT_DRIVERS: Tuple[str, ...] = ("capex_usd", "capacity_factor", "degradation_pct")

#: Per-storage (``type: bess``) finance levers swept — both BESS revenue models:
#:   * ``capacity_charge_lkr_per_mw_month`` — the bid Capacity Charge Rate ``R`` (capacity
#:     charge ``R × power_mw × 12``), the distributed 10MW capacity-tolling tender;
#:   * ``tariff_lkr_per_kwh`` — the night-peak Solar+BESS energy tariff (energy revenue
#:     ``energy_mwh × 1000 × cycles × RTE × availability × tariff``).
#: Both are LIVE drivers that flow through the cashflow (finance.bess_revenue), so the
#: applicable one is swept per scenario. Each is a per-tech field under
#: ``generation.technologies.<tech>.revenue`` and shocks directly (no coupling needed — BESS
#: revenue is additive and not part of the generation reconciliation). ``applicable_storage_drivers``
#: only sweeps the lever actually present, so a capacity-charge BESS is not given a phantom
#: tariff bar and vice-versa.
DEFAULT_STORAGE_DRIVERS: Tuple[str, ...] = (
    "capacity_charge_lkr_per_mw_month",
    "tariff_lkr_per_kwh",
)

#: KPIs reported per bar, in display order. ``min_dscr`` is retained (the canonical
#: lender covenant) even though dual-DSCR sizing pins it; ``balloon_pct`` carries the
#: covenant-stress signal it cannot. See :func:`flat_metrics`.
DEFAULT_METRICS: Tuple[str, ...] = (
    "project_irr",
    "equity_irr",
    "min_dscr",
    "balloon_pct",
)

#: Default symmetric shock applied to every driver (±10%). A uniform band makes the
#: absolute impacts directly comparable across techs and drivers — exactly what the
#: "which tech drives volatility" ranking needs.
DEFAULT_SHOCK_PCT: float = 0.10

#: Impacts at or below this are treated as zero (FP noise / covenant-pinned).
_FLAT_TOL: float = 1e-9


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


@dataclass(frozen=True)
class MultiTechTornadoBar:
    """One tornado bar: a single (technology, driver) shock on a single metric.

    Attributes:
        technology: The technology shocked (e.g. ``"wind"``).
        driver: The finance lever shocked (a key of :data:`DEFAULT_DRIVERS`).
        metric: The KPI name (e.g. ``"project_irr"``).
        base_case: The KPI value with no shock (identical across a metric's bars).
        low_case: The KPI value under the low (``1 - shock_pct``) coupled override.
        high_case: The KPI value under the high (``1 + shock_pct``) coupled override.
        shock_pct: The symmetric shock fraction applied (e.g. ``0.10`` for ±10%).
    """

    technology: str
    driver: str
    metric: str
    base_case: float
    low_case: float
    high_case: float
    shock_pct: float

    @property
    def impact_abs(self) -> float:
        """Tornado-bar magnitude: ``|high_case - low_case|``."""
        return abs(self.high_case - self.low_case)

    @property
    def label(self) -> str:
        """Human label ``"<technology>.<driver>"`` for display."""
        return f"{self.technology}.{self.driver}"


def _technology_blocks(config: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """Every ``(name, block)`` under ``generation.technologies``, in declared order."""
    techs = _nested_get(config, "generation", "technologies")
    if not isinstance(techs, Mapping):
        return []
    return [
        (str(name), block)
        for name, block in techs.items()
        if isinstance(block, Mapping)
    ]


def _is_generation(block: Mapping[str, Any]) -> bool:
    """A *generation* technology earns capacity_factor x tariff revenue.

    Class-agnostic (wind, solar, tidal, run-of-river … all qualify on the same footing
    — no wind-specific special-casing). An explicit ``type`` is AUTHORITATIVE: a
    recognised generation type (finance.tech_types.GENERATION_TYPES) is generation, a
    storage type (``type: bess``) never is — even if it mis-carries a ``capacity_factor``.
    An absent or unrecognised ``type`` falls back to the key-sniff (a ``capacity_factor``
    marks generation) so legacy scenarios authored before the enum still work.
    """
    tech_type = block.get("type")
    if tech_type is not None:
        if is_storage_type(tech_type):
            return False
        if is_generation_type(tech_type):
            return True
        # unrecognised explicit type -> fall through to the key-sniff (never silently drop)
    return block.get("capacity_factor") is not None


def _is_storage(block: Mapping[str, Any]) -> bool:
    """A *storage* technology (e.g. BESS): a recognised storage ``type`` (authoritative),
    or — absent/unrecognised type — a power/energy rating without a capacity factor."""
    tech_type = block.get("type")
    if tech_type is not None:
        if is_storage_type(tech_type):
            return True
        if is_generation_type(tech_type):
            return False
    return not _is_generation(block) and any(
        block.get(key) is not None for key in _STORAGE_KEYS
    )


def discover_generation_technologies(config: Mapping[str, Any]) -> List[str]:
    """List the **generation** technologies under ``generation.technologies``.

    A generation technology is any block carrying a ``capacity_factor`` — the lever
    the cashflow prices revenue on. The check is class-agnostic (wind == solar ==
    tidal == …): nothing here is specific to wind. Non-generating blocks (storage /
    BESS, or anything else without a capacity factor) are excluded — see
    :func:`discover_storage_technologies` / :func:`discover_non_generation_technologies`.

    Args:
        config: A loaded scenario config mapping.

    Returns:
        Generation-technology names, in declaration order.
    """
    return [name for name, block in _technology_blocks(config) if _is_generation(block)]


def discover_storage_technologies(config: Mapping[str, Any]) -> List[str]:
    """List the **storage** technologies (e.g. BESS) under ``generation.technologies``.

    Storage blocks carry a power/energy rating (:data:`_STORAGE_KEYS`) and no
    capacity factor. They contribute no generation/CFADS in the current finance
    engine, so the tornado reports them but does not sweep them (see the module
    docstring).

    Args:
        config: A loaded scenario config mapping.

    Returns:
        Storage-technology names, in declaration order.
    """
    return [name for name, block in _technology_blocks(config) if _is_storage(block)]


def discover_non_generation_technologies(config: Mapping[str, Any]) -> List[str]:
    """Every technology block that is **not** a generation technology.

    The robust superset of :func:`discover_storage_technologies`: it also catches
    blocks that are neither generation nor recognised storage, so a future or
    mis-keyed technology is surfaced rather than silently dropped from the tornado.

    Args:
        config: A loaded scenario config mapping.

    Returns:
        Non-generation technology names, in declaration order.
    """
    return [
        name for name, block in _technology_blocks(config) if not _is_generation(block)
    ]


def applicable_drivers(
    config: Mapping[str, Any],
    tech: str,
    drivers: Sequence[str] = DEFAULT_DRIVERS,
) -> List[str]:
    """Return the requested drivers whose per-tech config field is present.

    A driver is only swept when its underlying field exists for the technology, so
    a tech that omits (say) ``degradation_pct`` simply yields no degradation bar
    rather than a phantom one.

    Args:
        config: A loaded scenario config mapping.
        tech: The technology name.
        drivers: Drivers to consider (defaults to :data:`DEFAULT_DRIVERS`).

    Returns:
        The subset of ``drivers`` applicable to ``tech``, preserving order.
    """
    present: List[str] = []
    for driver in drivers:
        if _as_float(_nested_get(config, "generation", "technologies", tech, driver)) is not None:
            present.append(driver)
    return present


def _blended_capacity_factor(
    config: Mapping[str, Any], *, shocked_tech: str, shocked_cf: float
) -> float:
    """Capacity-weighted blended CF with one tech's CF overridden.

    Uses ``project.capacity_mw`` as the denominator (the value the in-cashflow
    reconciliation divides by), so setting ``project.capacity_factor`` to this result
    makes the per-tech year-1 capacity reconcile **exactly**.

    Raises:
        ValueError: ``project.capacity_mw`` is missing or non-positive.
    """
    total_mw = _as_float(_nested_get(config, "project", "capacity_mw"))
    if total_mw is None or total_mw <= 0:
        raise ValueError(
            "project.capacity_mw must be a positive number to blend capacity factors."
        )
    techs = _nested_get(config, "generation", "technologies")
    weighted = 0.0
    for name in discover_generation_technologies(config):
        block = techs[name]
        mw = _as_float(block.get("capacity_mw"))
        cf = shocked_cf if name == shocked_tech else _as_float(block.get("capacity_factor"))
        if mw is None or cf is None:
            raise ValueError(
                f"generation.technologies['{name}'] needs numeric capacity_mw and "
                "capacity_factor to blend capacity factors."
            )
        weighted += mw * cf
    return weighted / total_mw


def build_coupled_override(
    config: Mapping[str, Any], tech: str, driver: str, multiplier: float
) -> Dict[str, float]:
    """Build the coupled override dict for one (tech, driver) shock.

    See the module docstring for the coupling rationale. The returned dict uses
    flat dotted keys, ready for :func:`analytics.evaluation_v14.evaluate_with_overrides`.

    Args:
        config: A loaded scenario config mapping.
        tech: The technology to shock.
        driver: One of :data:`DEFAULT_DRIVERS`.
        multiplier: The shock factor (e.g. ``0.9`` for −10%, ``1.1`` for +10%).

    Returns:
        A mapping of dotted config path → new value.

    Raises:
        ValueError: The driver is unknown, or the per-tech field is absent/invalid.
    """
    if driver not in DEFAULT_DRIVERS:
        raise ValueError(
            f"unknown driver {driver!r}; expected one of {DEFAULT_DRIVERS}."
        )
    base = _as_float(_nested_get(config, "generation", "technologies", tech, driver))
    if base is None:
        raise ValueError(
            f"generation.technologies['{tech}'].{driver} is absent or non-numeric; "
            "cannot build a coupled override for it."
        )

    if driver == "capex_usd":
        usd_total = _as_float(_nested_get(config, "capex", "usd_total"))
        if usd_total is None:
            raise ValueError(
                "capex.usd_total is required to couple a per-tech capex shock to the "
                "financed total."
            )
        delta = base * (multiplier - 1.0)
        return {
            f"generation.technologies.{tech}.capex_usd": base + delta,
            "capex.usd_total": usd_total + delta,
        }

    if driver == "capacity_factor":
        new_cf = base * multiplier
        return {
            f"generation.technologies.{tech}.capacity_factor": new_cf,
            "project.capacity_factor": _blended_capacity_factor(
                config, shocked_tech=tech, shocked_cf=new_cf
            ),
        }

    if driver == "degradation_pct":
        # Degradation is not part of the year-1 capacity reconciliation, so the
        # per-tech field is shocked directly (no coupling).
        return {f"generation.technologies.{tech}.degradation_pct": base * multiplier}

    # Unreachable: the top-of-function guard rejects any driver not handled above.
    # Retained for static exhaustiveness (mypy) only.
    raise AssertionError(f"unhandled driver {driver!r}")  # pragma: no cover


def applicable_storage_drivers(
    config: Mapping[str, Any],
    tech: str,
    drivers: Sequence[str] = DEFAULT_STORAGE_DRIVERS,
) -> List[str]:
    """Return the storage drivers whose per-tech ``revenue`` field is present.

    A storage driver is only swept when its field exists under
    ``generation.technologies.<tech>.revenue`` (e.g. a BESS without a capacity-charge
    rate yields no bar rather than a phantom one).
    """
    present: List[str] = []
    for driver in drivers:
        value = _nested_get(config, "generation", "technologies", tech, "revenue", driver)
        if _as_float(value) is not None:
            present.append(driver)
    return present


def build_storage_override(
    config: Mapping[str, Any], tech: str, driver: str, multiplier: float
) -> Dict[str, float]:
    """Build the (direct, single-key) override for one storage (tech, driver) shock.

    Unlike a generation driver, a storage revenue lever needs no coupling: the BESS
    capacity charge is additive and not part of the year-1 generation reconciliation,
    so the per-tech ``revenue`` field is shocked directly.

    Raises:
        ValueError: The driver is unknown, or the per-tech field is absent/invalid.
    """
    if driver not in DEFAULT_STORAGE_DRIVERS:
        raise ValueError(
            f"unknown storage driver {driver!r}; expected one of {DEFAULT_STORAGE_DRIVERS}."
        )
    base = _as_float(
        _nested_get(config, "generation", "technologies", tech, "revenue", driver)
    )
    if base is None:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{driver} is absent or "
            "non-numeric; cannot build a storage override for it."
        )
    return {f"generation.technologies.{tech}.revenue.{driver}": base * multiplier}


def _metric_value(kpis: Mapping[str, Any], metric: str) -> float:
    """Extract a numeric KPI, failing loud if it is absent or non-numeric."""
    if metric not in kpis:
        available = ", ".join(sorted(str(k) for k in kpis))
        raise ValueError(
            f"metric '{metric}' is not in the evaluation KPIs. Available: {available}."
        )
    value = kpis[metric]
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"KPI '{metric}' is not numeric: {value!r}.") from exc


def _evaluate(config: Mapping[str, Any], overrides: Mapping[str, float]) -> Mapping[str, Any]:
    """Evaluate the scenario through the canonical gateway and return its KPIs."""
    result = evaluate_with_overrides(raw_config=config, overrides=overrides)
    if not isinstance(result, Mapping):  # pragma: no cover - defensive
        raise TypeError(f"evaluate_with_overrides returned {type(result).__name__}, not a mapping.")
    return result


def run_multi_tech_tornado(
    config: Mapping[str, Any],
    *,
    metrics: Sequence[str] = DEFAULT_METRICS,
    drivers: Sequence[str] = DEFAULT_DRIVERS,
    storage_drivers: Sequence[str] = DEFAULT_STORAGE_DRIVERS,
    shock_pct: float = DEFAULT_SHOCK_PCT,
) -> List[MultiTechTornadoBar]:
    """Run the per-technology tornado for a multi-tech scenario.

    For every (technology, applicable-driver) pair it evaluates a low and a high
    coupled-override case and emits one :class:`MultiTechTornadoBar` per requested
    metric. Bars are returned grouped by metric (in ``metrics`` order) and, within a
    metric, sorted by descending absolute impact (tornado convention).

    Args:
        config: A loaded scenario config mapping (e.g. from
            :func:`analytics.scenario_loader.load_scenario_config`).
        metrics: KPI names to report (defaults to :data:`DEFAULT_METRICS`).
        drivers: Per-tech drivers to sweep (defaults to :data:`DEFAULT_DRIVERS`).
        shock_pct: Symmetric shock fraction (defaults to :data:`DEFAULT_SHOCK_PCT`).

    Returns:
        The tornado bars. Empty if the scenario declares no generation technologies.

    Raises:
        ValueError: ``shock_pct`` is not in ``(0, 1)``, or a requested metric is
            absent from the evaluation KPIs.
    """
    if not 0.0 < shock_pct < 1.0:
        raise ValueError(f"shock_pct must be in (0, 1); got {shock_pct}.")

    gen_techs = discover_generation_technologies(config)
    # Storage (BESS) is now swept too — its capacity charge is a live finance driver.
    # Only storage blocks carrying a sweepable revenue lever are included.
    storage_techs = [
        t
        for t in discover_storage_technologies(config)
        if applicable_storage_drivers(config, t, storage_drivers)
    ]

    # Never silently drop a tech block. Anything non-generation that we cannot sweep
    # (storage without a sweepable revenue lever, or some other kind) is warned about so
    # a tornado is never mistaken for complete.
    swept_storage = set(storage_techs)
    unswept = [t for t in discover_non_generation_technologies(config) if t not in swept_storage]
    if unswept:
        logger.warning(
            "multi-tech tornado: not sweeping %d technology block(s) %s — they are "
            "non-generation and carry no sweepable driver (e.g. storage without a "
            "revenue lever).",
            len(unswept),
            unswept,
        )

    if not gen_techs and not storage_techs:
        return []

    base_kpis = _evaluate(config, {})
    base_by_metric = {m: _metric_value(base_kpis, m) for m in metrics}

    low_mult, high_mult = 1.0 - shock_pct, 1.0 + shock_pct
    bars: List[MultiTechTornadoBar] = []

    def _emit(
        tech: str, driver: str, low_kpis: Mapping[str, Any], high_kpis: Mapping[str, Any]
    ) -> None:
        for metric in metrics:
            bars.append(
                MultiTechTornadoBar(
                    technology=tech,
                    driver=driver,
                    metric=metric,
                    base_case=base_by_metric[metric],
                    low_case=_metric_value(low_kpis, metric),
                    high_case=_metric_value(high_kpis, metric),
                    shock_pct=shock_pct,
                )
            )

    for tech in gen_techs:
        for driver in applicable_drivers(config, tech, drivers):
            _emit(
                tech,
                driver,
                _evaluate(config, build_coupled_override(config, tech, driver, low_mult)),
                _evaluate(config, build_coupled_override(config, tech, driver, high_mult)),
            )
    for tech in storage_techs:
        for driver in applicable_storage_drivers(config, tech, storage_drivers):
            _emit(
                tech,
                driver,
                _evaluate(config, build_storage_override(config, tech, driver, low_mult)),
                _evaluate(config, build_storage_override(config, tech, driver, high_mult)),
            )

    # Group by metric (preserve requested order), sort each group by |impact| desc.
    metric_order = {m: i for i, m in enumerate(metrics)}
    bars.sort(key=lambda b: (metric_order.get(b.metric, len(metrics)), -b.impact_abs))
    return bars


def impact_by_technology(
    bars: Sequence[MultiTechTornadoBar], metric: str
) -> Dict[str, float]:
    """Total absolute impact per technology for one metric, ranked descending.

    This is the lender headline — *which technology drives this metric's volatility*
    — obtained by summing every driver's ``|impact|`` for each technology.

    Args:
        bars: Tornado bars (e.g. from :func:`run_multi_tech_tornado`).
        metric: The metric to rank by.

    Returns:
        ``{technology: summed_abs_impact}`` ordered by descending impact.
    """
    totals: Dict[str, float] = {}
    for bar in bars:
        if bar.metric == metric:
            totals[bar.technology] = totals.get(bar.technology, 0.0) + bar.impact_abs
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))


def flat_metrics(bars: Sequence[MultiTechTornadoBar]) -> List[str]:
    """Metrics whose every bar is flat (no axis moves them) — e.g. a pinned DSCR.

    A flat metric is not a phantom *axis* (the swept levers genuinely move other
    metrics); it means the KPI is structurally insensitive here — most often
    ``min_dscr``, sculpted to its target by dual-DSCR debt sizing. Surfacing it keeps
    an all-zero tornado honest instead of silently misleading.

    Args:
        bars: Tornado bars to inspect.

    Returns:
        Metric names (in first-seen order) with no bar exceeding the flat tolerance.
    """
    seen: List[str] = []
    moved: set[str] = set()
    for bar in bars:
        if bar.metric not in seen:
            seen.append(bar.metric)
        if bar.impact_abs > _FLAT_TOL:
            moved.add(bar.metric)
    return [m for m in seen if m not in moved]
