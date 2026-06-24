"""EPC construction-margin economics (e.g. the Kolonnawa BESS EPC tender).

Some CEB BESS procurements are **EPC supply contracts**, not Build-Own-Operate tolling:
the developer engineers, procures and constructs the BESS (batteries + ancillaries) and
hands it over to CEB, which then owns and operates it (e.g. for night-peak supply). The
developer's economics are therefore a **construction margin** — the EPC contract price
less the supply/build cost, realised over the construction period — **not** a 15/20-year
operational CFADS stream. This is a fundamentally different financial structure from the
v14 operational cashflow engine (``finance.cashflow_v14``), so it lives in its own
self-contained module rather than being shoehorned onto the operational path (which would
be decorative — modelling a one-off construction deal as if it had an operating phase).

What it computes from an ``epc`` config block: total cost, gross margin (and margin %),
return-on-cost, the month-by-month net cashflow (milestone receipts minus cost outflows),
the **peak working capital** the contractor must fund, and an annualised construction IRR
(via :func:`finance.irr.irr` — ARCH-02). All values are in the contract currency (USD by
convention here).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from finance.irr import irr

#: Tolerance for the payment-schedule percentages summing to 1.0.
_PCT_SUM_TOL = 1e-6
_MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class EpcMarginResult:
    """Construction-margin economics of an EPC supply contract.

    Attributes:
        contract_value: The EPC contract price the client (CEB) pays.
        total_cost: The contractor's total supply + build cost.
        gross_margin: ``contract_value - total_cost``.
        gross_margin_pct: ``gross_margin / contract_value`` (fraction).
        return_on_cost_pct: ``gross_margin / total_cost`` (fraction).
        construction_months: Length of the construction period.
        peak_working_capital: Maximum cumulative cash the contractor must fund (the
            most-negative point of the cumulative net cashflow; ``0.0`` if never
            negative).
        monthly_net_cashflow: Net cash (milestone receipts − cost outflows) per month,
            length ``construction_months + 1`` (month 0 … month N).
        annualized_irr: Construction-period IRR annualised from the monthly net
            cashflow, or ``None`` if undefined (e.g. no sign change).
    """

    contract_value: float
    total_cost: float
    gross_margin: float
    gross_margin_pct: float
    return_on_cost_pct: float
    construction_months: int
    peak_working_capital: float
    monthly_net_cashflow: List[float]
    annualized_irr: Optional[float]


def _require_positive(value: Any, name: str) -> float:
    """Coerce ``value`` to a positive finite float or raise (CESSPIT fail-loud)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"epc.{name} must be a positive number; got {value!r}.")
    coerced = float(value)
    if not math.isfinite(coerced) or coerced <= 0:
        raise ValueError(f"epc.{name} must be a positive finite number; got {coerced}.")
    return coerced


def _resolve_total_cost(epc: Mapping[str, Any]) -> float:
    """Sum the ``epc.cost`` breakdown (every numeric category)."""
    cost = epc.get("cost")
    if not isinstance(cost, Mapping) or not cost:
        raise ValueError(
            "epc.cost must be a non-empty mapping of cost categories to USD amounts "
            "(e.g. batteries_usd, ancillaries_usd)."
        )
    total = 0.0
    for category, amount in cost.items():
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError(f"epc.cost.{category}={amount!r} is not numeric.")
        value = float(amount)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"epc.cost.{category}={value} must be non-negative finite.")
        total += value
    if total <= 0:
        raise ValueError("epc.cost categories sum to a non-positive total.")
    return total


def _schedule_to_monthly(
    schedule: Any, total: float, months: int, *, field: str
) -> List[float]:
    """Turn a ``[{month, pct}, …]`` schedule into a per-month amount array.

    Percentages must sum to 1.0 (within tolerance) and every ``month`` must lie in
    ``[0, months]``. ``None`` yields an even spread of ``total`` across months 1…N.
    """
    amounts = [0.0] * (months + 1)
    if schedule is None:
        # Even spread across the operating months 1..N (month 0 is contract signing).
        per_month = total / months if months > 0 else 0.0
        for m in range(1, months + 1):
            amounts[m] = per_month
        return amounts
    if not isinstance(schedule, Sequence) or isinstance(schedule, (str, bytes)):
        raise ValueError(f"epc.{field} must be a list of {{month, pct}} entries.")
    pct_sum = 0.0
    for entry in schedule:
        if not isinstance(entry, Mapping) or "month" not in entry or "pct" not in entry:
            raise ValueError(
                f"epc.{field} entries must be mappings with 'month' and 'pct' keys."
            )
        month = entry["month"]
        pct = entry["pct"]
        if not isinstance(month, int) or isinstance(month, bool) or not 0 <= month <= months:
            raise ValueError(
                f"epc.{field} month={month!r} must be an integer in [0, {months}]."
            )
        if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not 0 <= pct <= 1:
            raise ValueError(f"epc.{field} pct={pct!r} must be a number in [0, 1].")
        amounts[month] += float(pct) * total
        pct_sum += float(pct)
    if abs(pct_sum - 1.0) > _PCT_SUM_TOL:
        raise ValueError(
            f"epc.{field} percentages sum to {pct_sum:.6f}, not 1.0. Align the schedule."
        )
    return amounts


def compute_epc_margin(config: Mapping[str, Any]) -> EpcMarginResult:
    """Compute the construction-margin economics of an ``epc`` config block.

    Args:
        config: A scenario config carrying an ``epc`` block with ``contract_value_usd``,
            a ``cost`` breakdown, ``construction_months``, and optional
            ``payment_schedule`` / ``cost_schedule`` lists of ``{month, pct}``.

    Returns:
        The :class:`EpcMarginResult`.

    Raises:
        ValueError: The ``epc`` block is missing or malformed.
    """
    epc = config.get("epc")
    if not isinstance(epc, Mapping):
        raise ValueError("config has no 'epc' block to compute an EPC margin from.")

    contract_value = _require_positive(epc.get("contract_value_usd"), "contract_value_usd")
    total_cost = _resolve_total_cost(epc)

    months_raw = epc.get("construction_months")
    if not isinstance(months_raw, int) or isinstance(months_raw, bool) or months_raw <= 0:
        raise ValueError(
            f"epc.construction_months must be a positive integer; got {months_raw!r}."
        )
    months = months_raw

    receipts = _schedule_to_monthly(
        epc.get("payment_schedule"), contract_value, months, field="payment_schedule"
    )
    costs = _schedule_to_monthly(
        epc.get("cost_schedule"), total_cost, months, field="cost_schedule"
    )

    net = [receipts[m] - costs[m] for m in range(months + 1)]

    cumulative = 0.0
    peak_working_capital = 0.0
    for value in net:
        cumulative += value
        peak_working_capital = max(peak_working_capital, -cumulative)

    gross_margin = contract_value - total_cost
    monthly_irr = irr(net)
    annualized_irr: Optional[float] = None
    if monthly_irr is not None and math.isfinite(monthly_irr) and monthly_irr > -1.0:
        annualized_irr = (1.0 + monthly_irr) ** _MONTHS_PER_YEAR - 1.0

    return EpcMarginResult(
        contract_value=contract_value,
        total_cost=total_cost,
        gross_margin=gross_margin,
        gross_margin_pct=gross_margin / contract_value,
        return_on_cost_pct=gross_margin / total_cost,
        construction_months=months,
        peak_working_capital=peak_working_capital,
        monthly_net_cashflow=net,
        annualized_irr=annualized_irr,
    )


__all__ = ["EpcMarginResult", "compute_epc_margin"]
