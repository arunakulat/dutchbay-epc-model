"""Battery-storage (BESS) revenue for the v14 cashflow — capacity-charge tolling.

A BESS is **not** a generation source: it has no capacity factor and no AEP, so the
cashflow's ``capacity_mw × capacity_factor × tariff`` revenue basis does not apply to
it. In the Sri Lanka / Ceylon Electricity Board (CEB) standalone-BESS tender — the
distributed 16 × 10 MW / 40 MWh programme, ``TR/REP&PM/ICB/2025/003/C`` — the asset
instead earns an **availability-based Capacity Charge** in LKR/MW/month, flat over the
contract term, with no per-kWh energy revenue (CEB dispatches the asset; the only
energy-linked cashflow is a one-way liquidated damage to CEB).

This module resolves ``type: bess`` technologies declared under
``generation.technologies`` and computes that capacity-charge revenue per operating
year. The cashflow adds the result to (generation) revenue. Absent any ``type: bess``
block it returns ``None`` / ``0.0``, so a wind/solar-only run is **byte-identical**.

Revenue, per BESS, per year within the contract term::

    annual_lkr = R_lkr_per_mw_month * power_mw * 12 * availability_factor * dispatchable_ratio

where ``R`` is the bid Capacity Charge Rate. ``availability_factor`` (default ``1.0``)
derates the charge when monthly availability falls below the 97% guarantee — at or
above 97% the tender applies no availability derate, hence the ``1.0`` default.
``dispatchable_ratio`` (default ``1.0``) is the ADSC/MDSC degradation factor (capped at
1.0): the BESS is assumed augmented/sized to hold its Minimum Dispatchable Storage
Capacity schedule, so the charge is undiminished. The charge is **flat — no
escalation** — per the tender, paid for ``contract_years`` (then zero).

NB: the round-trip-efficiency and functional-performance liquidated damages, and a
sub-97% availability month, are *downside* levers; they are exposed here as optional
multipliers (``availability_factor`` / ``dispatchable_ratio``) rather than modelled
from a dispatch simulation, which the engine does not run.

This module covers ``model: capacity_charge`` only. Two other CEB BESS structures are
out of scope: (1) a BESS charged by an existing solar PV plant paid an energy tariff for
night-peak export — a different ``revenue.model`` (energy / time-shift); and (2) the
Kolonnawa 100 MW single-site project, a CEB-owned night-peak supply procured via an EPC
contract — a construction-margin deal, not an operational tolling/tariff stream, so it
does not belong on this operational cashflow path at all.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

#: The explicit per-technology type discriminator value marking a storage block.
BESS_TYPE = "bess"

#: Revenue models this module understands.
SUPPORTED_BESS_REVENUE_MODELS = ("capacity_charge",)

_MONTHS_PER_YEAR = 12.0


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    """Walk a nested mapping by ``path``; return ``None`` on any miss."""
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _as_float(value: Any) -> Optional[float]:
    """Coerce a config scalar to ``float``; ``None`` for absent/non-numeric/bool."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _unit_factor(value: Any, *, tech: str, field: str) -> float:
    """Validate a downside multiplier in ``[0, 1]``; default ``1.0`` when absent.

    Both BESS downside levers (``availability_factor``, ``dispatchable_ratio``) are
    derate factors bounded by ``[0, 1]``. A value outside that range (e.g. ``97``
    instead of ``0.97``, or a stray sign) is a config error and **raises** rather than
    silently inflating or negating the capacity charge (CESSPIT fail-loud), symmetric
    with the module's other guards.
    """
    coerced = _as_float(value)
    if coerced is None:
        if value is None:
            return 1.0
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={value!r} is not "
            "numeric; it is a derate factor in [0, 1] (e.g. 0.97)."
        )
    if not 0.0 <= coerced <= 1.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={coerced} is out of "
            "range; it is a derate factor and must be in [0, 1] (e.g. 0.97, not 97)."
        )
    return coerced


def resolve_bess_specs(
    config: Mapping[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    """Resolve capacity-charge specs for every ``type: bess`` technology.

    Scans ``generation.technologies`` for blocks whose ``type`` is ``"bess"`` and
    builds a normalised spec per block. Returns ``None`` when no such block exists, so
    the cashflow keeps its byte-identical wind/solar behaviour.

    Each BESS block must declare ``power_mw`` and a ``revenue`` sub-block with
    ``model: capacity_charge`` and ``capacity_charge_lkr_per_mw_month``; a missing or
    non-numeric value raises (CESSPIT fail-loud — a mis-keyed BESS must not silently
    earn zero). Optional: ``revenue.contract_years`` (default ``None`` → paid for the
    full project life), ``revenue.availability_factor`` and
    ``revenue.dispatchable_ratio`` (default ``1.0``; ``dispatchable_ratio`` is clamped
    to ``[0, 1]``).

    Args:
        config: A loaded scenario config mapping.

    Returns:
        A list of ``{technology, power_mw, r_lkr_per_mw_month, contract_years,
        availability_factor, dispatchable_ratio}`` dicts, or ``None`` if no BESS block
        is present.

    Raises:
        ValueError: A ``type: bess`` block is malformed (missing/invalid ``power_mw``,
            ``revenue``, ``model``, or ``capacity_charge_lkr_per_mw_month``).
    """
    techs = _nested_get(config, "generation", "technologies")
    if not isinstance(techs, Mapping):
        return None

    specs: List[Dict[str, Any]] = []
    for name, block in techs.items():
        if not isinstance(block, Mapping):
            continue
        if block.get("type") != BESS_TYPE:
            # A block that declares a BESS revenue model but is NOT typed as a BESS is a
            # mis-key that would silently earn zero — fail loud (CESSPIT). A plain
            # storage block (power/energy, no BESS revenue model) is just skipped.
            rev_block = block.get("revenue")
            if (
                isinstance(rev_block, Mapping)
                and rev_block.get("model") in SUPPORTED_BESS_REVENUE_MODELS
            ):
                raise ValueError(
                    f"generation.technologies['{name}'] declares a BESS revenue model "
                    f"({rev_block.get('model')!r}) but is not type: {BESS_TYPE!r}. Add "
                    f"`type: {BESS_TYPE}`, or remove the revenue block."
                )
            continue

        power_mw = _as_float(block.get("power_mw"))
        if power_mw is None or power_mw <= 0:
            raise ValueError(
                f"generation.technologies['{name}'] is type: bess but has no positive "
                "power_mw — a capacity charge needs the contracted power rating (MW)."
            )

        # Cross-assert the (informational) energy rating against power x duration so a
        # typo cannot masquerade as a valid spec — the capacity charge itself is
        # POWER-based (LKR/MW/month), so energy_mwh / duration_h only document the
        # 4-hour / 0.25C nature. Other reporting-only fields: capex_usd (the financed
        # capex is capex.usd_total, as for wind/solar) and availability_pct (the live
        # derate is revenue.availability_factor).
        energy_mwh = _as_float(block.get("energy_mwh"))
        duration_h = _as_float(block.get("duration_h"))
        if energy_mwh is not None and duration_h is not None:
            implied_mwh = power_mw * duration_h
            if implied_mwh <= 0 or abs(energy_mwh - implied_mwh) / implied_mwh > 0.01:
                raise ValueError(
                    f"generation.technologies['{name}']: energy_mwh={energy_mwh} does "
                    f"not reconcile with power_mw*duration_h={implied_mwh:.4f} (within "
                    "1%). Align the BESS rating."
                )

        revenue = block.get("revenue")
        if not isinstance(revenue, Mapping):
            raise ValueError(
                f"generation.technologies['{name}'] (type: bess) needs a 'revenue' "
                "block declaring the model and its parameters."
            )
        model = revenue.get("model")
        if model not in SUPPORTED_BESS_REVENUE_MODELS:
            raise ValueError(
                f"generation.technologies['{name}'].revenue.model={model!r} is not "
                f"supported; expected one of {SUPPORTED_BESS_REVENUE_MODELS}."
            )

        r_lkr = _as_float(revenue.get("capacity_charge_lkr_per_mw_month"))
        if r_lkr is None or r_lkr < 0:
            raise ValueError(
                f"generation.technologies['{name}'].revenue."
                "capacity_charge_lkr_per_mw_month must be a non-negative number "
                "(LKR/MW/month, the bid Capacity Charge Rate)."
            )

        contract_years_raw = revenue.get("contract_years")
        contract_years: Optional[int] = None
        if contract_years_raw is not None:
            cy_float = _as_float(contract_years_raw)
            if cy_float is None or cy_float != int(cy_float) or cy_float <= 0:
                raise ValueError(
                    f"generation.technologies['{name}'].revenue.contract_years="
                    f"{contract_years_raw!r} is invalid; expected a positive whole "
                    "number of years."
                )
            contract_years = int(cy_float)

        availability = _unit_factor(
            revenue.get("availability_factor"), tech=str(name), field="availability_factor"
        )
        dispatchable = _unit_factor(
            revenue.get("dispatchable_ratio"), tech=str(name), field="dispatchable_ratio"
        )

        specs.append(
            {
                "technology": str(name),
                "power_mw": power_mw,
                "r_lkr_per_mw_month": r_lkr,
                "contract_years": contract_years,
                "availability_factor": availability,
                "dispatchable_ratio": dispatchable,
            }
        )

    return specs or None


def bess_capacity_charge_lkr_for_year(
    specs: Optional[List[Dict[str, Any]]], year_index: int
) -> float:
    """Total BESS capacity-charge revenue (LKR) for one operating year.

    Sums the flat annual capacity charge over every BESS spec, paying each only while
    the operating year is within its ``contract_years`` window (a spec with
    ``contract_years is None`` is paid every year). ``year_index`` is 0-based
    (operating year 1 → 0).

    Args:
        specs: Resolved BESS specs from :func:`resolve_bess_specs`, or ``None``.
        year_index: Zero-based operating-year index.

    Returns:
        The combined capacity-charge revenue in LKR (``0.0`` when ``specs`` is empty
        or every BESS contract has expired for this year).
    """
    if not specs:
        return 0.0
    total = 0.0
    for spec in specs:
        contract_years = spec["contract_years"]
        if contract_years is not None and year_index >= contract_years:
            continue
        total += (
            spec["r_lkr_per_mw_month"]
            * spec["power_mw"]
            * _MONTHS_PER_YEAR
            * spec["availability_factor"]
            * spec["dispatchable_ratio"]
        )
    return total


__all__ = [
    "BESS_TYPE",
    "SUPPORTED_BESS_REVENUE_MODELS",
    "resolve_bess_specs",
    "bess_capacity_charge_lkr_for_year",
]
