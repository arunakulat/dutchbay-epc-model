"""Blue Whale equipment-cost parity benchmark and unpriced cost-buildup evaluation.

Implements the exact ``Decimal`` / ``Fraction`` arithmetic from the 2026-11-14
Blue Whale review package (``BW-COST-AEP-REVIEW-2026-11-14``, v1.1) and enforces
``None``-safe validation for itemized road vs. marine cost-buildup packages.

This module computes conditional equipment-cost parity thresholds and
uncalibrated sensitivities; it does **not** predict OEM commercial quotes or
modify scenario CAPEX inputs.
"""

from __future__ import annotations

import json
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import yaml

_DECIMAL_PREC = 45
VALID_DELIVERY_ROUTES = frozenset({"road", "marine"})
CAPEX_SITE_INPUT_COPIES = (
    "rated_capacity_mw",
    "road_allowance_usd_per_kw",
    "epc_wrap_pct",
)


def _to_decimal(value: Any) -> Decimal:
    """Convert a numeric or string config value to ``Decimal`` via ``str``."""
    return Decimal(str(value))


def _fraction_to_decimal(frac: Fraction) -> Decimal:
    """Convert an exact ``Fraction`` to ``Decimal`` under the active context."""
    return Decimal(frac.numerator) / Decimal(frac.denominator)


def _resolve_repo_path(raw_path: str, repo_root: Path) -> Path:
    """Resolve ``raw_path`` against ``repo_root`` when relative."""
    p = Path(raw_path)
    return p if p.is_absolute() else repo_root / p


def _load_blue_whale_aep_and_hold(
    summary_path: Path,
    loss_retention_factors: Sequence[Any],
) -> Tuple[Decimal, str]:
    """Load and cross-check Blue Whale net P50 AEP (MWh/yr) and its HOLD status."""
    if not loss_retention_factors:
        raise ValueError("blue_whale.loss_retention_factors must be non-empty")
    loss_retention = Decimal("1")
    for raw_factor in loss_retention_factors:
        factor = _to_decimal(raw_factor)
        if not (Decimal("0") < factor <= Decimal("1")):
            raise ValueError(
                f"loss_retention_factors entries must be in (0, 1], got {factor}"
            )
        loss_retention *= factor

    raw = json.loads(summary_path.read_text(encoding="utf-8"), parse_float=Decimal)
    net_aep_gwh = _to_decimal(raw["yield"]["net_aep_gwh"])
    p50_net_gwh = _to_decimal(raw["uncertainty"]["p50_net_gwh"])
    if net_aep_gwh != p50_net_gwh:
        raise ValueError(
            f"net_aep_gwh ({net_aep_gwh}) does not match p50_net_gwh ({p50_net_gwh})"
        )
    gross_aep_gwh = _to_decimal(raw["yield"]["gross_aep_gwh"])
    if abs(gross_aep_gwh * loss_retention - net_aep_gwh) >= Decimal("1e-12"):
        raise ValueError("gross_aep_gwh * loss_retention diverges from net_aep_gwh")
    hold_note = str(raw.get("hold") or "").strip()
    if not hold_note:
        raise ValueError(
            f"Met-mast summary {summary_path} is missing its 'hold' status field"
        )
    return net_aep_gwh * Decimal("1000"), hold_note


def _load_blue_whale_capex_site_inputs(
    bw: Mapping[str, Any],
    repo_root: Path,
) -> Tuple[Decimal, Decimal, Decimal]:
    """Read rated capacity, road allowance, and EPC wrap from the capex config.

    Refuses duplicate copies on ``blue_whale`` (``#1686`` L-16 pattern).
    """
    copies = [k for k in CAPEX_SITE_INPUT_COPIES if k in bw]
    if copies:
        raise ValueError(
            f"blue_whale must not repeat capex site inputs ({', '.join(copies)}); "
            "they are read from capex_solar_resource_config"
        )
    rel = bw.get("capex_solar_resource_config")
    if not rel:
        raise ValueError("blue_whale.capex_solar_resource_config is required")
    capex_path = _resolve_repo_path(str(rel), repo_root)
    capex_cfg = yaml.safe_load(capex_path.read_text(encoding="utf-8"))
    if not isinstance(capex_cfg, Mapping) or "wind" not in capex_cfg:
        raise ValueError(
            f"capex_solar_resource_config {capex_path} must define a 'wind' mapping"
        )
    wind = capex_cfg["wind"]
    cap_mw = _to_decimal(wind["rated_kw"]) / Decimal("1000")
    road_allow_per_kw = _to_decimal(wind["inland_transport_usd_per_kw"]["mode"])
    epc_wrap_frac = _to_decimal(wind["epc_margin_pct"]["mode"])
    return cap_mw, road_allow_per_kw, epc_wrap_frac


def compute_equipment_parity(
    cfg: Mapping[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """Compute Mannar benchmark, Blue Whale parity threshold, and sensitivities.

    Args:
        cfg: Parsed ``blue_whale_equipment_parity_v1`` configuration mapping.
        repo_root: Repository root used to resolve relative summary paths.

    Returns:
        JSON-serializable dictionary of exact decimal-string results,
        sensitivity cases, Ashuri (2016) counterexample rows, and check flags.
    """
    getcontext().prec = _DECIMAL_PREC
    bw = cfg["blue_whale"]
    mn = cfg["mannar_benchmark"]

    summary_path = _resolve_repo_path(str(bw["summary_json_path"]), repo_root)
    aep_b, aep_hold_note = _load_blue_whale_aep_and_hold(
        summary_path, bw["loss_retention_factors"]
    )

    cap_b, road_allow_per_kw, epc_wrap_frac = _load_blue_whale_capex_site_inputs(
        bw, repo_root
    )
    life_b = _to_decimal(bw["operating_life_years"])
    hours_yr = _to_decimal(bw["hours_per_year"])

    count_m = _to_decimal(mn["turbine_count"])
    cap_m = _to_decimal(mn["rated_capacity_mw"])
    cap_m_hist = _to_decimal(mn["historical_unreconciled_capacity_mw"])
    cost_m_total = _to_decimal(mn["turbine_supply_usd"])
    aep_m_total = _to_decimal(mn["annual_aep_mwh"])
    life_m = _to_decimal(mn["operating_life_years"])

    cost_m_unit = cost_m_total / count_m
    aep_m_unit = aep_m_total / count_m
    cap_m_unit = cap_m / count_m

    unit_m_mw = cost_m_total / cap_m
    energy_m_total = aep_m_total * life_m
    rate_m = cost_m_total / energy_m_total
    cf_m_pct = (aep_m_total / (cap_m * hours_yr)) * Decimal("100")

    energy_b = aep_b * life_b
    cf_b_pct = (aep_b / (cap_b * hours_yr)) * Decimal("100")
    yield_ratio = (aep_b / cap_b) / (aep_m_unit / cap_m_unit)
    cost_capacity = unit_m_mw * cap_b
    rate_capacity = cost_capacity / energy_b
    parity_cost = rate_m * energy_b
    break_even_premium = yield_ratio - Decimal("1")

    # Independent exact Fraction cross-checks for parity and yield ratio.
    fr_yield_ratio = (Fraction(str(aep_b)) / Fraction(str(cap_b))) / (
        Fraction(str(aep_m_unit)) / Fraction(str(cap_m_unit))
    )
    fr_parity_cost = (
        Fraction(str(cost_m_total))
        * Fraction(str(aep_b))
        * Fraction(str(life_b))
        / (Fraction(str(aep_m_total)) * Fraction(str(life_m)))
    )
    if abs(_fraction_to_decimal(fr_yield_ratio) - yield_ratio) >= Decimal("1e-40"):
        raise ValueError("yield_ratio failed Fraction cross-check")
    if abs(_fraction_to_decimal(fr_parity_cost) - parity_cost) >= Decimal("1e-35"):
        raise ValueError("parity_cost failed Fraction cross-check")

    raw_premiums = [
        _to_decimal(p) / Decimal("100") for p in cfg["sensitivity_premium_pct"]
    ]
    premiums = sorted({*raw_premiums, break_even_premium})
    sensitivity_cases: List[Dict[str, str]] = []
    for p in premiums:
        cost = cost_capacity * (Decimal("1") + p)
        rate = cost / energy_b
        sensitivity_cases.append(
            {
                "assumed_equipment_price_per_mw_change_pct": str(p * Decimal("100")),
                "equipment_cost_usd": str(cost),
                "equipment_cost_per_lifetime_mwh_usd": str(rate),
                "change_vs_mannar_pct": str(
                    (rate / rate_m - Decimal("1")) * Decimal("100")
                ),
                "classification": "uncalibrated sensitivity, not quote or forecast",
            }
        )

    ashuri_rows: List[Dict[str, str]] = []
    for row in cfg["ashuri_2016_counterexample"]:
        c = _to_decimal(row["modelled_tcc_usd_2010_basis"])
        e = _to_decimal(row["modelled_annual_mwh"])
        ashuri_rows.append(
            {
                "rating_mw": str(row["rating_mw"]),
                "modelled_tcc_usd_2010_basis": str(c),
                "modelled_annual_mwh": str(e),
                "authors_common_20y_equipment_usd_per_mwh": str(c / (e * life_b)),
            }
        )
    ashuri_rise_pct = (
        Decimal(ashuri_rows[1]["authors_common_20y_equipment_usd_per_mwh"])
        / Decimal(ashuri_rows[0]["authors_common_20y_equipment_usd_per_mwh"])
        - Decimal("1")
    ) * Decimal("100")

    road_allowance_usd = road_allow_per_kw * cap_b * Decimal("1000")
    road_allowance_wrap_usd = road_allowance_usd * (Decimal("1") + epc_wrap_frac)

    return {
        "purpose": (
            "Reproducible conditional equipment-cost parity benchmark (not a quote/forecast; "
            "met-mast P50 AEP divisor remains under HOLD)"
        ),
        "mannar_cost_status": str(mn["status"]),
        "blue_whale_aep_hold_status": aep_hold_note,
        "calculation_basis": (
            f"Equipment only; constant AEP; {int(life_b)} years; "
            "no discounting, FX, escalation or degradation"
        ),
        "results": {
            "mannar_equipment_usd_per_unit": str(cost_m_unit),
            "mannar_equipment_usd_per_mw": str(unit_m_mw),
            "mannar_equipment_usd_per_kw_50mw": str(
                cost_m_total / (cap_m * Decimal("1000"))
            ),
            "mannar_equipment_usd_per_kw_56mw_historical_unreconciled": str(
                cost_m_total / (cap_m_hist * Decimal("1000"))
            ),
            "mannar_lifetime_mwh": str(energy_m_total),
            "mannar_capacity_factor_pct": str(cf_m_pct),
            "mannar_equipment_usd_per_lifetime_mwh": str(rate_m),
            "blue_whale_annual_mwh": str(aep_b),
            "blue_whale_lifetime_mwh": str(energy_b),
            "blue_whale_capacity_factor_pct": str(cf_b_pct),
            "blue_whale_to_mannar_yield_per_mw_ratio": str(yield_ratio),
            "break_even_equipment_price_per_mw_premium_pct": str(
                break_even_premium * Decimal("100")
            ),
            "constant_price_per_mw_equipment_cost_usd": str(cost_capacity),
            "constant_price_per_mw_equipment_usd_per_lifetime_mwh": str(rate_capacity),
            "constant_price_per_mw_change_in_usd_per_lifetime_mwh_pct": str(
                (rate_capacity / rate_m - Decimal("1")) * Decimal("100")
            ),
            "same_usd_per_mwh_parity_equipment_cost_usd": str(parity_cost),
            "road_allowance_usd": str(road_allowance_usd),
            "road_allowance_plus_epc_wrap_usd": str(road_allowance_wrap_usd),
            "ashuri_5_to_10mw_common_life_equipment_usd_per_mwh_change_pct": str(
                ashuri_rise_pct
            ),
        },
        "sensitivity_cases": sensitivity_cases,
        "ashuri_2016_counterexample": ashuri_rows,
        "checks": {
            "net_aep_and_p50_match": True,
            "gross_to_net_loss_stack_matches_source": True,
            "fraction_cross_checks_passed": True,
        },
    }


def evaluate_cost_buildup(
    packages: Sequence[Mapping[str, Any]],
    delivery_route: str,
) -> Dict[str, Any]:
    """Validate and summarize an itemized road or marine cost-buildup table.

    Unpriced packages (``quoted_amount_usd is None``) are never treated as zero;
    if any required package for ``delivery_route`` is unpriced, ``total_usd``
    remains ``None`` and ``status`` is ``"UNPRICED_EVIDENCE_GAPS"``.
    """
    if delivery_route not in VALID_DELIVERY_ROUTES:
        raise ValueError(
            f"delivery_route must be one of {sorted(VALID_DELIVERY_ROUTES)}, got {delivery_route!r}"
        )

    allowed_routes = {
        "common",
        "route_specific",
        delivery_route,
        f"{delivery_route}_conditional",
    }
    applicable: List[Mapping[str, Any]] = [
        pkg for pkg in packages if str(pkg.get("route")) in allowed_routes
    ]

    missing_ids: List[str] = []
    priced_sum = Decimal("0")
    for pkg in applicable:
        pkg_id = str(pkg["id"])
        amount = pkg.get("quoted_amount_usd")
        if amount is None:
            if str(pkg.get("route")) != f"{delivery_route}_conditional":
                missing_ids.append(pkg_id)
            continue
        dec_amount = _to_decimal(amount)
        if dec_amount < Decimal("0"):
            raise ValueError(
                f"Package {pkg_id} has negative quoted_amount_usd: {dec_amount}"
            )
        priced_sum += dec_amount

    is_complete = len(missing_ids) == 0 and len(applicable) > 0
    return {
        "schema": "blue_whale.cost_buildup_evaluation.v1",
        "delivery_route": delivery_route,
        "applicable_package_count": len(applicable),
        "unpriced_required_package_ids": missing_ids,
        "status": "COMPLETE" if is_complete else "UNPRICED_EVIDENCE_GAPS",
        "total_usd": str(priced_sum) if is_complete else None,
    }
