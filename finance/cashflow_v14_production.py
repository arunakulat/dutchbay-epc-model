"""Production and Revenue Calculations for V14 Cashflow Model.

This module calculates annual energy production with industry-standard
performance degradation, revenue from tariffs, and statutory deductions.

Key Features:
- Wind turbine performance degradation (IEC 61400-12-1:2022)
- Grid loss calculations
- Multi-year revenue projections
- Statutory deductions (success fee, environmental surcharge, social levy)

Industry Standards:
- IEC 61400-12-1:2022 Annex C: Performance monitoring
- Staffell & Green (2014): Wind farm degradation analysis
- NREL (2019): Long-term performance trends

Author: Dutch Bay EPC Model Team
Date: December 2025
Version: 2.0.0 (Added degradation)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .tech_types import (
    is_generation_type,
    is_modelled_generation_type,
    is_storage_type,
)


def validate_storage_capex_declared(config: Dict[str, Any]) -> None:
    """CESSPIT / BESS-3: a revenue-producing ``type: bess`` block must declare a positive
    ``capex_usd`` — a storage asset is not free revenue.

    This blocks the specific footgun the audit found: a battery folded onto a hybrid as a
    pure revenue override (no capex) that lifts project IRR for nothing. The modeller must
    still include the BESS capex in the financed ``capex.usd_total`` to finance it —
    per-tech ``capex_usd`` remains reporting-only by design (the ``capex.usd_total`` is the
    single authoritative financed total, deliberately decoupled so Monte-Carlo/sensitivity
    can perturb it). Coupling per-tech capex/opex into the financed total is tracked
    separately as ARCH-3.
    """
    generation = config.get("generation")
    techs = generation.get("technologies") if isinstance(generation, dict) else None
    if not isinstance(techs, dict):
        return
    for name, block in techs.items():
        if not isinstance(block, dict):
            continue
        if is_storage_type(block.get("type")) and isinstance(
            block.get("revenue"), dict
        ):
            try:
                capex_usd: Optional[float] = float(block.get("capex_usd"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                capex_usd = None
            if capex_usd is None or capex_usd <= 0.0:
                raise ValueError(
                    f"generation.technologies['{name}'] is a revenue-producing type:bess "
                    "block but declares no positive capex_usd. A storage asset is not free "
                    "revenue — declare its capex_usd and include it in capex.usd_total "
                    "(BESS-3)."
                )


def _calculate_net_production(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    grid_loss_pct: float,
    year: int,
    curtailment_pct: float = 0.0,
    grid_outage_pct: float = 0.0,
) -> tuple[float, float]:
    """Calculate gross and net kWh for a given year from capacity + capacity factor.

    This is the LIVE production primitive: the cashflow (via
    ``calculate_net_production_for_year``) computes each year's gross/net energy
    here, including grid losses and the financed curtailment lever. ``M3`` reuses
    it per technology to sum a multi-tech plant. Year-over-year degradation is
    applied by the caller via the scenario ``degradation_pct`` (see
    ``cashflow_v14_params``); this primitive models grid loss/curtailment only.

    Parameters
    ----------
    capacity_mw :
        Installed capacity (MW).
    capacity_factor :
        Net capacity factor (decimal).
    degradation :
        Annual degradation rate (decimal).
    grid_loss_pct :
        Grid losses (decimal share of gross).
    year :
        Zero-based year index (0 = first operating year).
    curtailment_pct :
        INCREMENTAL financed grid-curtailment haircut (decimal), applied after grid
        losses. Default 0.0 → byte-identical (the physical/embedded curtailment is
        already in capacity_factor); a first-class stress/risk lever above that base.
    grid_outage_pct :
        INCREMENTAL grid-UNAVAILABILITY / outage haircut (decimal), applied after
        curtailment (#744). Default 0.0 → byte-identical (embedded availability is
        already in capacity_factor); models ADDITIONAL documented grid downtime.
    """
    hours_per_year = 8760.0
    effective_cf = capacity_factor * ((1.0 - degradation) ** year)
    gross_kwh = capacity_mw * 1e3 * hours_per_year * effective_cf
    grid_loss = gross_kwh * grid_loss_pct
    net_kwh = (
        (gross_kwh - grid_loss) * (1.0 - curtailment_pct) * (1.0 - grid_outage_pct)
    )
    return gross_kwh, net_kwh


def resolve_tech_generation_specs(
    config: Dict[str, Any],
    params: Dict[str, Any],
    *,
    tolerance: float = 0.01,
) -> Optional[List[Dict[str, Any]]]:
    """Resolve per-technology generation specs from ``generation.technologies``.

    Returns a list of ``{technology, capacity_mw, capacity_factor, degradation}``
    when the multi-tech block is present (so the cashflow sums per-tech generation,
    each with its **own** degradation), or ``None`` for the legacy single-tech path
    (which then runs byte-identically). Per-tech ``degradation_pct`` falls back to
    the project degradation; it is a free per-tech input (there is no project-level
    per-tech-degradation counterpart, so only year-1 *capacity* is reconciled).

    CESSPIT/CCCDIR fail-loud contract:

    * A technology that declares ANY generation intent (``aep_gwh`` — the reporting
      key — or ``capacity_mw``/``capacity_factor`` — the finance keys) MUST declare
      both finance keys, or this raises. This prevents a tech that is mis-keyed for
      one of the two consumers (the cashflow here vs. the reporting aggregator) from
      being silently dropped from generation.
    * A technology with no generation keys at all (e.g. storage: ``power_mw`` /
      ``energy_mwh``) contributes no generation and is skipped silently.
    * The per-tech year-1 generation must reconcile with the project headline
      (``capacity_mw × capacity_factor``) within ``tolerance``; a non-positive
      headline, or a mismatch, raises (so ``project.capacity_factor`` is a
      cross-checked input, never decorative).
    """
    generation = config.get("generation")
    techs = generation.get("technologies") if isinstance(generation, dict) else None
    if not isinstance(techs, dict) or not techs:
        return None

    project_degradation = float(params.get("degradation", 0.0))
    specs: List[Dict[str, Any]] = []
    for name, block in techs.items():
        if not isinstance(block, dict):
            continue
        # `type` is authoritative: any storage block (type: bess, or a future storage type
        # in finance.tech_types.STORAGE_TYPES) is NOT a generation technology even if it
        # (mis-)carries a capacity_factor, so it never earns tariff revenue here — only its
        # BESS capacity charge (finance.bess_revenue). This closes the double-count:
        # generation tariff AND capacity charge.
        if is_storage_type(block.get("type")):
            continue
        cap = block.get("capacity_mw")
        cap_factor = block.get("capacity_factor")
        if cap is None or cap_factor is None:
            # aep_gwh (the reporting key) or capacity_factor signals a *generation*
            # tech; capacity_mw alone does not (storage carries a power rating).
            declares_generation = (
                block.get("aep_gwh") is not None
                or block.get("capacity_factor") is not None
            )
            if declares_generation:
                raise ValueError(
                    f"generation.technologies['{name}'] declares generation "
                    "(aep_gwh / capacity_factor) but is missing capacity_mw and/or "
                    "capacity_factor — the cashflow needs both to model its output. "
                    "Declare both, or remove the generation keys if this is a "
                    "non-generating technology (e.g. storage)."
                )
            continue  # not a generation tech (e.g. storage) -> intentionally skipped
        # ARCH-1 (#474): an explicitly-typed ENUM-ONLY generation tech (tidal / hydro /
        # geothermal / run_of_river) has NO validated resource model, so billing it here
        # would silently use an UNVALIDATED flat capacity_factor x tariff. Fail loud unless
        # the scenario deliberately opts into the experimental proxy, so a user can never
        # silently get a fake result. Untyped generation blocks are the conventional CF
        # path (not gated); wind/solar are modelled (finance.tech_types).
        declared_type = block.get("type")
        if (
            is_generation_type(declared_type)
            and not is_modelled_generation_type(declared_type)
            and not bool(block.get("allow_unvalidated_flat_cf", False))
        ):
            raise ValueError(
                f"generation.technologies['{name}'] declares type={declared_type!r}, a "
                "recognised but UNMODELLED generation technology — it has no resource model "
                "and would bill an unvalidated flat capacity_factor x tariff. Supported "
                "modelled generation: wind, solar (storage: bess). To deliberately use the "
                "experimental flat-CF proxy, set this block's "
                "allow_unvalidated_flat_cf: true."
            )
        # Unit convention MUST match the single-tech path: _build_cashflow_params
        # reads project.degradation(_pct) as a PERCENT and divides by 100. So a
        # per-tech degradation_pct here is also a percent (e.g. 0.6 -> 0.6%/yr).
        # The project fallback comes from params["degradation"], which is ALREADY
        # the divided decimal, so it is used as-is (no second /100).
        deg_raw = block.get("degradation_pct", block.get("degradation"))
        if deg_raw is not None:
            deg_value = float(deg_raw)
            if deg_value < 0:
                raise ValueError(
                    f"generation.technologies['{name}'].degradation_pct={deg_value} "
                    "is invalid (must be >= 0, percent)."
                )
            degradation = deg_value / 100.0
        else:
            degradation = project_degradation  # already a decimal (post /100)
        specs.append(
            {
                "technology": str(name),
                "capacity_mw": float(cap),
                "capacity_factor": float(cap_factor),
                "degradation": degradation,
            }
        )
    if not specs:
        return None

    expected = float(params["capacity_mw"]) * float(params["capacity_factor"])
    if expected <= 0:
        raise ValueError(
            "Cannot reconcile generation.technologies: the project headline "
            f"capacity_mw*capacity_factor={expected:.4f} is non-positive."
        )
    actual = sum(s["capacity_mw"] * s["capacity_factor"] for s in specs)
    if abs(actual - expected) / expected > tolerance:
        raise ValueError(
            "generation.technologies year-1 capacity (sum capacity_mw*capacity_factor"
            f"={actual:.4f}) does not reconcile with project capacity_mw*capacity_factor"
            f"={expected:.4f} within {tolerance:.0%}. Align the hybrid scenario."
        )
    return specs


def calculate_net_production_for_year(
    params: Dict[str, Any], year_index: int
) -> tuple[float, float]:
    """Gross/net kWh for a year — multi-tech sum if specs are present, else single.

    With ``params["tech_generation_specs"]`` set (by ``_prepare_cashflow_context``)
    the result is the sum over technologies of :func:`_calculate_net_production`,
    each with its own capacity / capacity factor / degradation. Absent that key, it
    is exactly the legacy single-tech call (byte-identical wind-only behaviour).
    """
    grid_loss = float(params["grid_loss_pct"])
    curtailment = float(params.get("curtailment_pct", 0.0))
    grid_outage = float(params.get("grid_outage_pct", 0.0))
    specs = params.get("tech_generation_specs")
    if specs:
        gross_total = 0.0
        net_total = 0.0
        for spec in specs:
            gross, net = _calculate_net_production(
                spec["capacity_mw"],
                spec["capacity_factor"],
                spec["degradation"],
                grid_loss,
                year_index,
                curtailment_pct=curtailment,
                grid_outage_pct=grid_outage,
            )
            gross_total += gross
            net_total += net
        return gross_total, net_total
    return _calculate_net_production(
        float(params["capacity_mw"]),
        float(params["capacity_factor"]),
        float(params["degradation"]),
        grid_loss,
        year_index,
        curtailment_pct=curtailment,
        grid_outage_pct=grid_outage,
    )


def _calculate_revenue_lkr(net_kwh: float, tariff_lkr_per_kwh: float) -> float:
    """Compute revenue in LKR = net energy * tariff."""
    return net_kwh * tariff_lkr_per_kwh


def _calculate_statutory_deductions(
    revenue_lkr: float,
    success_fee_pct: float,
    env_surcharge_pct: float,
    social_levy_pct: float,
) -> Dict[str, float]:
    """Calculate statutory charges as percentages of revenue.

    All percentage arguments are decimals (e.g. 0.01 = 1%).
    """
    success_fee = revenue_lkr * success_fee_pct
    env_surcharge = revenue_lkr * env_surcharge_pct
    social_levy = revenue_lkr * social_levy_pct
    total = success_fee + env_surcharge + social_levy
    return {
        "success_fee": success_fee,
        "environmental_surcharge": env_surcharge,
        "social_services_levy": social_levy,
        "total_statutory_deductions": total,
    }


def _calculate_opex_lkr(
    opex_usd_per_year: float, fx_rate: float, vat_pct: float = 0.0
) -> float:
    """Convert annual OPEX from USD to LKR at a given FX rate.

    ``vat_pct`` (#738) is the unrecoverable input-VAT decimal on O&M (0.0 when the
    ``taxes_indirect`` block is absent or relieved — the ``* (1.0 + 0.0)`` is an
    exact IEEE identity, so the levy-free path stays byte-identical). This is the
    ONE shared helper both row builders call, so the two cannot drift; escalation
    compounds in the caller first and VAT multiplies the escalated figure —
    ad-valorem, order-independent. The row's ``opex_usd`` stays the PRE-VAT
    escalated USD figure; ``opex_lkr`` is VAT-inclusive.
    """
    return opex_usd_per_year * (1.0 + vat_pct) * fx_rate


def _apply_risk_haircut(cfads_lkr: float, risk_haircut_pct: float) -> float:
    """Apply a conservative risk haircut to CFADS.

    The haircut always moves CFADS in the adverse direction: a positive CFADS is
    reduced toward zero (``cfads * (1 - h)``) and a negative CFADS (a loss year) is
    made *more* negative (``cfads * (1 + h)``). Expressed sign-safely as
    ``cfads - h * |cfads|``.

    The prior multiplicative form ``cfads * (1 - h)`` inverted on losses — it
    *shrank* a negative CFADS toward zero (``-1000 -> -900``), softening the very
    downside the haircut exists to stress (audit D6, #572). The non-negative branch
    keeps the exact ``cfads * (1 - h)`` expression, so the committed all-positive
    lender case is byte-identical (no floating-point reassociation).
    """
    if cfads_lkr >= 0.0:
        return cfads_lkr * (1.0 - risk_haircut_pct)
    return cfads_lkr * (1.0 + risk_haircut_pct)


__all__ = [
    "_calculate_net_production",
    "_calculate_revenue_lkr",
    "_calculate_statutory_deductions",
    "_calculate_opex_lkr",
    "_apply_risk_haircut",
]
