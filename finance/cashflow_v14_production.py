from __future__ import annotations

from typing import Dict


def _calculate_net_production(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    grid_loss_pct: float,
    year: int,
) -> tuple[float, float]:
    """
    Calculate gross and net kWh for a given year.

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
    """
    hours_per_year = 8760.0
    effective_cf = capacity_factor * ((1.0 - degradation) ** year)
    gross_kwh = capacity_mw * 1e3 * hours_per_year * effective_cf
    grid_loss = gross_kwh * grid_loss_pct
    net_kwh = gross_kwh - grid_loss
    return gross_kwh, net_kwh


def _calculate_revenue_lkr(net_kwh: float, tariff_lkr_per_kwh: float) -> float:
    """Compute revenue in LKR = net energy * tariff."""
    return net_kwh * tariff_lkr_per_kwh


def _calculate_statutory_deductions(
    revenue_lkr: float,
    success_fee_pct: float,
    env_surcharge_pct: float,
    social_levy_pct: float,
) -> Dict[str, float]:
    """
    Calculate statutory charges as percentages of revenue.

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


def _calculate_opex_lkr(opex_usd_per_year: float, fx_rate: float) -> float:
    """Convert annual OPEX from USD to LKR at a given FX rate."""
    return opex_usd_per_year * fx_rate


def _apply_risk_haircut(cfads_lkr: float, risk_haircut_pct: float) -> float:
    """Apply risk haircut: CFADS * (1 - haircut)."""
    return cfads_lkr * (1.0 - risk_haircut_pct)


__all__ = [
    "_calculate_net_production",
    "_calculate_revenue_lkr",
    "_calculate_statutory_deductions",
    "_calculate_opex_lkr",
    "_apply_risk_haircut",
]
