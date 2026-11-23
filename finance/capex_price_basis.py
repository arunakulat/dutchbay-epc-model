"""Escalate capex from its declared price date to the construction draws (#1569).

A scenario's ``capex.usd_total`` is priced in some year. Before #1569 the engine treated
it as the amount spent during construction, whatever year it was priced in. Blue Whale's
capex is priced in 2026 and, on a one-year build to a 2028 COD, is spent in 2027, so the
undeclared convention left out a year of escalation.

A scenario opts in with a ``capex.price_basis`` block::

    capex:
      usd_total: 10899980          # priced at price_basis.price_year
      cost_basis_year: 2026        # must equal price_year when both are declared
      price_basis:
        price_year: 2026
        escalation_pct: 5.0        # per year, from the price year to each draw
        source: "..."

The capex is spent in the construction periods, which run from financial close,
``project.cod_year - construction_periods``, one per year. Each period's share of the
capex (``Financing_Terms.construction_schedule``, or the placeholder sized to the period
count) escalates from the price year to the year the period starts::

    usd_total' = usd_total * sum_i w_i * (1 + e) ** (close_year + i - price_year)

with ``w_i`` the phasing shares normalised to one. A zero-period build spends at COD.

The block is resolved once, on the configuration the pipeline evaluates, and is then
replaced by ``capex.price_basis_applied``, which records the stated amount, the factor and
the years, so that a configuration that passes through the pipeline twice is not
escalated twice. A scenario without the block is returned unchanged.

The engine also reads capex amounts stated under other keys, some of them in place of
``capex.usd_total`` (``finance.capex_usd``, a ``capex.breakdown`` with
``derive_from_breakdown``, a tax base such as ``tax.depreciable_capex_lkr``). Before
#1591 D-1/A-1 those amounts bypassed the price date silently. By the owner's ruling of
2026-11-14 the factor now applies to every such amount automatically, and the change is
disclosed: each key and its stated amount is listed under
``capex.price_basis_applied.automatically_escalated``, and a warning is logged. The ``project``
section's capex totals, which the equity distribution reads, are among those keys.

By the ruling of 2026-11-15 each per-technology
``generation.technologies.<name>.capex_usd`` takes the same factor as the total. It is a
component of the total, priced at the same price year, never read in place of it: the
financed engine treats it as reporting-only, and the batch LCOS view, the per-technology
WBS and the portfolio aggregator read it. Its stated amounts are recorded under
``capex.price_basis_applied.technology_capex_at_price_year``, as ``usd_total``'s is under
``usd_total_at_price_year``, with no warning, because the declared block itself
escalates them.
"""

from __future__ import annotations

import copy
import logging
import math
from typing import Any, Dict, List, Mapping, MutableMapping, Tuple

from finance.debt_v14 import (
    _resolve_construction_periods,
    _section_case_insensitive,
    placeholder_construction_schedule,
)

logger = logging.getLogger(__name__)

PRICE_BASIS_KEY = "price_basis"
APPLIED_KEY = "price_basis_applied"
AUTO_KEY = "automatically_escalated"
TECH_KEY = "technology_capex_at_price_year"
_ALLOWED_KEYS = frozenset({"price_year", "escalation_pct", "source"})

# Capex amounts the engine reads besides capex.usd_total (#1591 D-1/A-1): the debt and
# NPV capex resolvers (finance/debt/capex.py, analytics/core/metrics.py), the EPC helper
# alias and the tax-base ladder (finance/cashflow_v14.py). Matched case-insensitively,
# as those readers match them. Per-kW figures and percentages are not amounts.
_SECTION_AMOUNT_KEYS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "capex",
        (
            "usd_total",
            "epc_usd",
            "capex_total_usd",
            "total_capex_usd",
            "total_capex",
            "lkr_total",
        ),
    ),
    ("finance", ("capex_total_usd", "capex_usd")),
    ("costs", ("capex_total_usd", "capex_usd", "total_capex_usd", "total_capex")),
    ("tax", ("depreciable_capex_lkr", "dep_base_lkr")),
    # The equity distribution's flat capex lookup (finance/equity_distribution_v14_hydra.py)
    # also reads the project section's totals (#1704 review).
    ("project", ("capex_usd", "capex_total_usd", "total_capex_usd")),
)
_TOP_LEVEL_AMOUNT_KEYS = ("capex_usd_total", "capex_total_usd", "total_capex_usd")


def _whole_year(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} must be a whole calendar year, got {value!r}")
    return int(value)


def _phasing_weights(config: Mapping[str, Any], periods: int) -> List[float]:
    """Return the capex share spent in each construction period, summing to one."""
    terms = _section_case_insensitive(config, "Financing_Terms") or {}
    schedule = terms.get("construction_schedule")
    if schedule is None:
        schedule = placeholder_construction_schedule(periods)
    values = [float(v) for v in schedule]
    if len(values) != periods:
        raise ValueError(
            f"capex.price_basis needs one capex phasing entry per construction period: "
            f"Financing_Terms.construction_schedule has {len(values)}, the build has "
            f"{periods}"
        )
    total = sum(values)
    if any(v < 0.0 for v in values) or total <= 0.0:
        raise ValueError(
            "Financing_Terms.construction_schedule must be non-negative with a positive "
            f"sum to phase capex escalation, got {values}"
        )
    return [v / total for v in values]


def capex_escalation_factor(config: Mapping[str, Any]) -> Dict[str, Any] | None:
    """Return the escalation the ``capex.price_basis`` block implies, or ``None``.

    Args:
        config: The scenario mapping.

    Returns:
        ``None`` when no block is declared. Otherwise a mapping with ``factor``,
        ``price_year``, ``close_year``, ``cod_year``, ``construction_periods``,
        ``escalation_pct`` and the phasing ``weights``.

    Raises:
        ValueError: If the block is malformed, names an unknown key, contradicts
            ``capex.cost_basis_year``, misses ``project.cod_year``, or prices the capex
            after financial close.
    """
    capex = config.get("capex")
    if not isinstance(capex, Mapping):
        return None
    block = capex.get(PRICE_BASIS_KEY)
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise ValueError("capex.price_basis must be a mapping")
    unknown = sorted(set(block) - _ALLOWED_KEYS)
    if unknown:
        raise ValueError(
            f"capex.price_basis has keys {unknown}; allowed: {sorted(_ALLOWED_KEYS)}"
        )
    price_year = _whole_year(block.get("price_year"), "capex.price_basis.price_year")
    basis_year = capex.get("cost_basis_year")
    if basis_year is not None and basis_year != price_year:
        raise ValueError(
            f"capex.price_basis.price_year={price_year} and "
            f"capex.cost_basis_year={basis_year!r} disagree; the capex has one price date"
        )
    rate_raw = block.get("escalation_pct")
    if isinstance(rate_raw, bool) or not isinstance(rate_raw, (int, float)):
        raise ValueError(
            "capex.price_basis.escalation_pct must be a number (percent per year), "
            f"got {rate_raw!r}"
        )
    rate = float(rate_raw) / 100.0
    if not -1.0 < rate < 1.0:
        raise ValueError(
            f"capex.price_basis.escalation_pct={rate_raw} is out of range (percent)"
        )
    project = config.get("project")
    cod_raw = project.get("cod_year") if isinstance(project, Mapping) else None
    if cod_raw is None:
        raise ValueError(
            "capex.price_basis needs project.cod_year to date the construction draws"
        )
    cod_year = _whole_year(cod_raw, "project.cod_year")
    periods = _resolve_construction_periods(config)
    close_year = cod_year - periods
    if price_year > close_year:
        raise ValueError(
            f"capex.price_basis.price_year={price_year} is after financial close "
            f"({close_year} = project.cod_year {cod_year} - {periods} construction "
            "period(s)); the engine does not de-escalate capex"
        )
    if periods == 0:
        weights: List[float] = []
        factor = (1.0 + rate) ** (cod_year - price_year)
    else:
        weights = _phasing_weights(config, periods)
        factor = sum(
            w * (1.0 + rate) ** (close_year + i - price_year)
            for i, w in enumerate(weights)
        )
    return {
        "factor": factor,
        "price_year": price_year,
        "close_year": close_year,
        "cod_year": cod_year,
        "construction_periods": periods,
        "escalation_pct": float(rate_raw),
        "weights": weights,
    }


def _amount(value: Any) -> float | None:
    """Return ``value`` as a finite number when the capex readers would use it."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _escalate_in(
    block: MutableMapping[str, Any],
    keys: Tuple[str, ...],
    prefix: str,
    factor: float,
    found: Dict[str, float],
    skip: str | None = None,
) -> None:
    """Escalate each amount in ``block`` whose key matches ``keys`` (any case)."""
    for name in list(block):
        if not isinstance(name, str) or name == skip or name.lower() not in keys:
            continue
        stated = _amount(block[name])
        if stated is not None:
            found[f"{prefix}{name}"] = stated
            block[name] = stated * factor


def _escalate_breakdown(
    block: MutableMapping[str, Any], prefix: str, factor: float, found: Dict[str, float]
) -> None:
    """Escalate the numeric ``capex.breakdown`` line items, which the readers sum."""
    for name in list(block):
        if not isinstance(name, str) or name.lower() != "breakdown":
            continue
        items = block[name]
        if not isinstance(items, Mapping):
            continue
        items = dict(items)
        for item, value in items.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found[f"{prefix}{name}.{item}"] = float(value)
                items[item] = float(value) * factor
        block[name] = items


def _escalate_technologies(
    out: Dict[str, Any], factor: float, found: Dict[str, float]
) -> None:
    """Escalate each ``generation.technologies.<name>.capex_usd`` (ruling 2026-11-15).

    The per-technology capex is a component of the financed total, priced at the same
    price year. The financed engine treats it as reporting-only, but the batch LCOS
    view, the per-technology WBS and the portfolio aggregator read it, so it takes the
    factor the total takes. A BESS ``revenue.augmentation_schedule`` is spent in its own
    operating year and is not a construction draw, so it is not escalated.
    """
    for gen_name in list(out):
        if not isinstance(gen_name, str) or gen_name.lower() != "generation":
            continue
        generation = out[gen_name]
        if not isinstance(generation, Mapping):
            continue
        generation = copy.deepcopy(dict(generation))
        techs = generation.get("technologies")
        if not isinstance(techs, Mapping):
            continue
        techs = dict(techs)
        for tech, block in techs.items():
            if not isinstance(block, Mapping):
                continue
            block = dict(block)
            _escalate_in(
                block,
                ("capex_usd",),
                f"{gen_name}.technologies.{tech}.",
                factor,
                found,
            )
            techs[tech] = block
        generation["technologies"] = techs
        out[gen_name] = generation


def _escalate_other_amounts(out: Dict[str, Any], factor: float) -> Dict[str, float]:
    """Escalate every capex amount except ``capex.usd_total``; return what moved.

    ``out`` is modified in place: each section that is touched is replaced by a copy,
    so the caller's configuration is never changed.
    """
    found: Dict[str, float] = {}
    for section, keys in _SECTION_AMOUNT_KEYS:
        for name in list(out):
            if not isinstance(name, str) or name.lower() != section:
                continue
            if not isinstance(out[name], Mapping):
                continue
            block = copy.deepcopy(dict(out[name]))
            out[name] = block
            if section == "capex":
                _escalate_breakdown(block, f"{name}.", factor, found)
            # The canonical capex.usd_total is the stated amount, escalated by the
            # caller; any other spelling of it is read like it and escalated here.
            skip = "usd_total" if name == "capex" else None
            _escalate_in(block, keys, f"{name}.", factor, found, skip)
    _escalate_in(out, _TOP_LEVEL_AMOUNT_KEYS, "", factor, found)
    return found


def apply_capex_price_basis(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``config`` with its capex amounts escalated to the draws.

    A configuration without ``capex.price_basis`` is returned as a plain copy with no
    key changed. With the block, ``capex.usd_total`` (the amount at the price year) is
    multiplied by :func:`capex_escalation_factor`, and the block is replaced by
    ``capex.price_basis_applied``.

    Each ``generation.technologies.<name>.capex_usd`` is multiplied by the same
    factor and its stated amount recorded under
    ``capex.price_basis_applied.technology_capex_at_price_year`` (ruling 2026-11-15).

    Every other capex amount the engine reads (see ``_SECTION_AMOUNT_KEYS``, the
    numeric ``capex.breakdown`` line items and the top-level aliases) is multiplied by
    the same factor automatically (#1591 D-1/A-1). Those keys and their stated amounts
    are recorded under ``capex.price_basis_applied.automatically_escalated`` and a
    warning is logged, so the automatic step is never silent. Without such keys the
    result is byte-identical to the usd_total-only escalation.

    Raises:
        ValueError: As :func:`capex_escalation_factor`; if ``capex.usd_total`` is
            declared but is not a number; or if the block finds no capex amount at
            all to escalate.
    """
    resolved = capex_escalation_factor(config)
    out = dict(config)
    if resolved is None:
        return out
    factor = resolved["factor"]
    stated_raw = config["capex"].get("usd_total")
    if stated_raw is not None and (
        isinstance(stated_raw, bool) or not isinstance(stated_raw, (int, float))
    ):
        raise ValueError(
            "capex.price_basis escalates capex.usd_total, which must be a number; "
            f"got {stated_raw!r}"
        )
    auto = _escalate_other_amounts(out, factor)
    technologies: Dict[str, float] = {}
    _escalate_technologies(out, factor, technologies)
    if stated_raw is None and not auto:
        raise ValueError(
            "capex.price_basis found no capex amount to escalate: state "
            "capex.usd_total at the price year"
        )
    capex = out["capex"]
    block = capex.pop(PRICE_BASIS_KEY)
    applied: Dict[str, Any] = dict(block)
    if stated_raw is not None:
        capex["usd_total"] = float(stated_raw) * factor
        applied["usd_total_at_price_year"] = float(stated_raw)
    applied.update(
        {
            "factor": factor,
            "close_year": resolved["close_year"],
            "cod_year": resolved["cod_year"],
            "construction_periods": resolved["construction_periods"],
        }
    )
    if technologies:
        applied[TECH_KEY] = technologies
    if auto:
        applied[AUTO_KEY] = auto
        logger.warning(
            "%s",
            automatic_escalation_message(resolved["price_year"], factor, sorted(auto)),
        )
    capex[APPLIED_KEY] = applied
    return out


class UnappliedCapexPriceBasisError(ValueError):
    """A capex amount was read before the declared ``capex.price_basis`` was applied."""


def refuse_unapplied_price_basis(config: Mapping[str, Any], reader: str) -> None:
    """Refuse a capex amount read before a declared price date was applied (#1899).

    ``capex.price_basis`` is resolved once, by :func:`apply_capex_price_basis`, which
    replaces it with ``capex.price_basis_applied``. A reader that still sees the declared
    block holds the stated, price-year capex, not the capex the engine finances. Before
    #1899 such a reader used the stated figure silently. The fix is to read the scenario
    through :func:`analytics.evaluation_v14.evaluated_scenario_config` (or the pipeline).
    A configuration without the block, or with it already applied, passes.
    """
    capex = _section_case_insensitive(dict(config), "capex") if config else None
    if not isinstance(capex, Mapping):
        return
    if any(isinstance(key, str) and key.lower() == PRICE_BASIS_KEY for key in capex):
        raise UnappliedCapexPriceBasisError(
            f"{reader} read capex from a configuration whose capex.price_basis has not "
            "been applied, so it would use the stated price-year amount instead of the "
            "capex escalated to the construction draws (#1569, #1899). Pass the "
            "scenario through analytics.evaluation_v14.evaluated_scenario_config() "
            "or the pipeline first."
        )


def automatic_escalation_message(
    price_year: int, factor: float, keys: List[str]
) -> str:
    """The disclosure for capex amounts escalated automatically (#1591 D-1/A-1)."""
    return (
        f"capex.price_basis: the price-year factor {factor:.6f} (from {price_year}) was "
        f"applied AUTOMATICALLY to {', '.join(keys)}: capex amounts stated beside or "
        "instead of capex.usd_total (a capex.breakdown is escalated to stay "
        "consistent with it). Each is taken as stated "
        "at the price year; LKR amounts keep the FX they were stated at; the stated "
        f"amounts are kept in capex.price_basis_applied.{AUTO_KEY}."
    )


def automatic_escalation(config: Mapping[str, Any]) -> Dict[str, Any] | None:
    """Return the automatic-escalation disclosure of a resolved config, or ``None``.

    For the pipeline result: present only when :func:`apply_capex_price_basis`
    escalated a capex amount other than ``capex.usd_total``.
    """
    capex = config.get("capex")
    applied = capex.get(APPLIED_KEY) if isinstance(capex, Mapping) else None
    if not isinstance(applied, Mapping) or not applied.get(AUTO_KEY):
        return None
    auto = dict(applied[AUTO_KEY])
    price_year = int(applied["price_year"])
    factor = float(applied["factor"])
    return {
        "automatically_applied": True,
        "factor": factor,
        "price_year": price_year,
        "keys_at_price_year": auto,
        "warning": automatic_escalation_message(price_year, factor, sorted(auto)),
    }


__all__ = [
    "AUTO_KEY",
    "TECH_KEY",
    "apply_capex_price_basis",
    "automatic_escalation",
    "automatic_escalation_message",
    "refuse_unapplied_price_basis",
    "UnappliedCapexPriceBasisError",
    "capex_escalation_factor",
]
