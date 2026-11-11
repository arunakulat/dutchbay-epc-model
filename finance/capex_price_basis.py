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
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping

from finance.debt_v14 import (
    _resolve_construction_periods,
    _section_case_insensitive,
    placeholder_construction_schedule,
)

PRICE_BASIS_KEY = "price_basis"
APPLIED_KEY = "price_basis_applied"
_ALLOWED_KEYS = frozenset({"price_year", "escalation_pct", "source"})


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


def apply_capex_price_basis(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``config`` with ``capex.usd_total`` escalated to the draws.

    A configuration without ``capex.price_basis`` is returned as a plain copy with no
    key changed. With the block, ``capex.usd_total`` (the amount at the price year) is
    multiplied by :func:`capex_escalation_factor`, and the block is replaced by
    ``capex.price_basis_applied``.

    Raises:
        ValueError: As :func:`capex_escalation_factor`, or if the block is declared
            without ``capex.usd_total`` (the one capex key it escalates).
    """
    resolved = capex_escalation_factor(config)
    out = dict(config)
    if resolved is None:
        return out
    capex = copy.deepcopy(dict(config["capex"]))
    stated = capex.get("usd_total")
    if isinstance(stated, bool) or not isinstance(stated, (int, float)):
        raise ValueError(
            "capex.price_basis escalates capex.usd_total, which must be a number; "
            f"got {stated!r}"
        )
    block = capex.pop(PRICE_BASIS_KEY)
    capex["usd_total"] = float(stated) * resolved["factor"]
    capex[APPLIED_KEY] = {
        **dict(block),
        "usd_total_at_price_year": float(stated),
        "factor": resolved["factor"],
        "close_year": resolved["close_year"],
        "cod_year": resolved["cod_year"],
        "construction_periods": resolved["construction_periods"],
    }
    out["capex"] = capex
    return out


__all__ = ["apply_capex_price_basis", "capex_escalation_factor"]
