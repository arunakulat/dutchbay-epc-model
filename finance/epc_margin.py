"""EPC construction-margin economics, for any scenario that declares an ``epc`` block.

Some procurements are **EPC supply contracts**, not build-own-operate projects: the
contractor engineers, procures and constructs an asset (a battery system, for example) and
hands it over to the client, which then owns and operates it. The contractor's economics
are therefore a **construction margin** (the EPC contract price less the supply and build
cost, realised over the construction period), **not** a 15- or 20-year operating cashflow.
That is a different financial structure from the operating cashflow engine
(``finance.cashflow_v14``), so the margin is computed here and reported beside it, never
folded into it.

HOW A SCENARIO REACHES IT (#1780)
    * Any scenario that declares an ``epc`` block gets ``result["epc_margin"]`` from the
      canonical pipeline (``analytics.pipeline_v14_enhanced``). It moves no scenario KPI.
    * An EPC-only scenario (an ``epc`` block and no operating project; see
      :func:`is_epc_only_scenario`) runs through the main CLI ``run_full_pipeline_v14.py``,
      which prints :func:`epc_only_result`.
    * Pre-flight (``analytics.schema_guard``) checks a declared block with
      :func:`validate_epc_block`, the same contract the computation reads.

What it computes from the ``epc`` block: total cost, gross margin (and margin %),
return-on-cost, the month-by-month net cashflow (milestone receipts minus cost outflows),
the **peak working capital** the contractor must fund, and an annualised construction IRR
(via :func:`finance.irr.irr`, ARCH-02). All values are in the contract currency (USD by
convention here). Every figure comes from the scenario; the module holds no business value.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from finance.irr import irr

#: Tolerance for the payment-schedule percentages summing to 1.0.
_PCT_SUM_TOL = 1e-6
_MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class EpcMarginResult:
    """Construction-margin economics of an EPC supply contract.

    Attributes:
        contract_value: The EPC contract price the client pays.
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
            raise ValueError(
                f"epc.cost.{category}={value} must be non-negative finite."
            )
        total += value
    if not math.isfinite(total):
        raise ValueError("epc.cost categories sum to a total that is not finite.")
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
        if (
            not isinstance(month, int)
            or isinstance(month, bool)
            or not 0 <= month <= months
        ):
            raise ValueError(
                f"epc.{field} month={month!r} must be an integer in [0, {months}]."
            )
        if (
            isinstance(pct, bool)
            or not isinstance(pct, (int, float))
            or not 0 <= pct <= 1
        ):
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

    contract_value = _require_positive(
        epc.get("contract_value_usd"), "contract_value_usd"
    )
    total_cost = _resolve_total_cost(epc)

    months_raw = epc.get("construction_months")
    if (
        not isinstance(months_raw, int)
        or isinstance(months_raw, bool)
        or months_raw <= 0
    ):
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


# ---------------------------------------------------------------------------
# Scenario contract, pre-flight and the pipeline's result entry (#1780)
# ---------------------------------------------------------------------------

#: The keys an ``epc`` block may carry. Anything else is refused (CESSPIT fail-loud).
_EPC_KEYS = frozenset(
    {
        "description",
        "contract_value_usd",
        "cost",
        "construction_months",
        "payment_schedule",
        "cost_schedule",
    }
)

#: Top-level keys an EPC-only scenario may carry besides ``epc``.
_EPC_ONLY_COMPANION_KEYS = frozenset({"metadata"})

STATUS_RUN = "run"
STATUS_FAILED = "failed"

_BASIS = (
    "EPC supply contract: a construction margin over the construction period, separate "
    "from any operating cashflow; no scenario KPI uses it"
)


def validate_epc_block(config: Mapping[str, Any], errors: List[str]) -> None:
    """Append the problems with a declared ``epc`` block to ``errors`` (present-only).

    A scenario without the block gets no error. A declared block must be a mapping with
    only the known keys, and must compute: the same checks :func:`compute_epc_margin`
    applies, so pre-flight and the computation cannot drift.

    Args:
        config: The scenario mapping.
        errors: The pre-flight error list, appended to in place.
    """
    if not isinstance(config, Mapping) or "epc" not in config:
        return
    epc = config["epc"]
    if not isinstance(epc, Mapping):
        errors.append(f"epc must be a mapping; got {type(epc).__name__}.")
        return
    unknown = sorted(str(k) for k in epc if k not in _EPC_KEYS)
    if unknown:
        errors.append(
            f"epc has unknown key(s) {unknown}; allowed: {sorted(_EPC_KEYS)}."
        )
        return
    try:
        compute_epc_margin(config)
    except ValueError as exc:
        errors.append(str(exc))


def is_epc_only_scenario(config: Any) -> bool:
    """Whether ``config`` is an EPC-only scenario: an ``epc`` block and no operating project.

    True when the scenario carries an ``epc`` key and nothing else at the top level except
    ``metadata``. Any other top-level block means an operating project, which runs through
    the full pipeline (and gets the margin beside its own figures).
    """
    if not isinstance(config, Mapping) or "epc" not in config:
        return False
    return all(k == "epc" or k in _EPC_ONLY_COMPANION_KEYS for k in config)


def epc_margin_failure(reason: str) -> Dict[str, Any]:
    """The result entry for a declared ``epc`` block that could not be computed.

    Args:
        reason: Why it could not run.

    Returns:
        ``{"status": "failed", "reason": ..., "basis": ...}``.
    """
    return {"status": STATUS_FAILED, "reason": str(reason), "basis": _BASIS}


#: Why ``annualized_irr`` can be null: when the receipts run ahead of the costs, the
#: monthly flows have a positive NPV at every rate, so no rate sets it to zero.
IRR_NOTE = (
    "no IRR: the monthly net cashflow has no rate at which its NPV is zero, which happens "
    "when receipts run ahead of costs; read the margin and peak working capital instead"
)


def epc_margin_result(config: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The pipeline's ``epc_margin`` entry for any scenario (#1780).

    Args:
        config: The scenario mapping.

    Returns:
        ``None`` when the scenario declares no ``epc`` block. Otherwise
        ``{"status": "run", "basis": ..., **EpcMarginResult fields}``.

    Raises:
        ValueError: The declared block is malformed (see :func:`validate_epc_block`).
    """
    if not isinstance(config, Mapping) or "epc" not in config:
        return None
    errors: List[str] = []
    validate_epc_block(config, errors)
    if errors:
        raise ValueError("; ".join(errors))
    entry: Dict[str, Any] = {
        "status": STATUS_RUN,
        "basis": _BASIS,
        **asdict(compute_epc_margin(config)),
    }
    if entry["annualized_irr"] is None:
        entry["irr_note"] = IRR_NOTE
    return entry


def epc_only_result(config: Mapping[str, Any], config_path: str) -> Dict[str, Any]:
    """The main CLI's result for an EPC-only scenario (#1780).

    Args:
        config: An EPC-only scenario (:func:`is_epc_only_scenario`).
        config_path: The scenario path, echoed back.

    Returns:
        ``{"status": "success", "scenario_kind": "epc_only", "config_path": ...,
        "epc_margin": {...}}``, or ``status: "error"`` with the reason and the failed
        ``epc_margin`` entry when the block does not compute.
    """
    base: Dict[str, Any] = {
        "scenario_kind": "epc_only",
        "config_path": str(config_path),
    }
    try:
        entry = epc_margin_result(config)
    except ValueError as exc:
        return {
            "status": "error",
            "error": str(exc),
            **base,
            "epc_margin": epc_margin_failure(str(exc)),
        }
    return {"status": "success", **base, "epc_margin": entry}


__all__ = [
    "EpcMarginResult",
    "STATUS_FAILED",
    "STATUS_RUN",
    "compute_epc_margin",
    "epc_margin_failure",
    "epc_margin_result",
    "epc_only_result",
    "is_epc_only_scenario",
    "validate_epc_block",
]
