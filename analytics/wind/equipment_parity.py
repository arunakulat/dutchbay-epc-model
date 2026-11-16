"""Equipment-cost parity benchmark and unpriced cost-buildup evaluation, for any site (#1755).

For a site's single-turbine project, this compares the equipment cost per lifetime MWh with
a benchmark project's, and computes the equipment price at which the two are equal. It also
checks whether an itemised road or marine cost buildup is fully priced. The arithmetic is
exact (``Decimal`` with ``Fraction`` cross-checks).

Every site input comes from the scenario's ``equipment_cost_parity`` block (contract:
:mod:`analytics.site_analysis_blocks`, #1754), so any scenario that declares the block can
run the analysis and a scenario without it gets "not applicable". The method inputs (hours
per year and the published reference-scaling counterexample) come from the runner's method
config. Nothing here names a site, a path or a figure.

Every energy summary the block names must carry a non-empty ``hold`` field. The result
reports it as ``site_aep_hold_status``, so the status of the AEP divisor is the site's own,
never a sentence fixed in code.

The results are conditional parity thresholds and uncalibrated sensitivities. They do not
predict an OEM quote and change no scenario capex.

It generalises the original single-site module under the owner's 2026-11-16 ruling that
every scenario includes the site analyses; that module now only adapts its old
configuration to this one.
"""

from __future__ import annotations

import json
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import yaml

from analytics.site_analysis_blocks import resolve_site_analysis_block

BLOCK_NAME = "equipment_cost_parity"
RESULT_SCHEMA = "equipment_cost_parity_result_v1"
COST_BUILDUP_SCHEMA = "cost_buildup_evaluation.v1"

_DECIMAL_PREC = 45
VALID_DELIVERY_ROUTES = frozenset({"road", "marine"})


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


def load_site_aep_and_hold(
    summary_path: Path,
    loss_retention_factors: Sequence[Any],
) -> Tuple[Decimal, str]:
    """Load and cross-check the site's net P50 AEP (MWh/yr) and its HOLD status."""
    if not loss_retention_factors:
        raise ValueError(f"{BLOCK_NAME}.loss_retention_factors must be non-empty")
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
            f"Energy summary {summary_path} is missing its 'hold' status field"
        )
    return net_aep_gwh * Decimal("1000"), hold_note


def load_site_capex_inputs(
    capex_config: str,
    repo_root: Path,
) -> Tuple[Decimal, Decimal, Decimal]:
    """Read rated capacity, road allowance and EPC wrap from the site's capex config."""
    capex_path = _resolve_repo_path(str(capex_config), repo_root)
    capex_cfg = yaml.safe_load(capex_path.read_text(encoding="utf-8"))
    if not isinstance(capex_cfg, Mapping) or "wind" not in capex_cfg:
        raise ValueError(f"capex config {capex_path} must define a 'wind' mapping")
    wind = capex_cfg["wind"]
    cap_mw = _to_decimal(wind["rated_kw"]) / Decimal("1000")
    road_allow_per_kw = _to_decimal(wind["inland_transport_usd_per_kw"]["mode"])
    epc_wrap_frac = _to_decimal(wind["epc_margin_pct"]["mode"])
    return cap_mw, road_allow_per_kw, epc_wrap_frac


def compute_equipment_parity_from_block(
    block: Mapping[str, Any],
    method: Mapping[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """Compute the benchmark, the site's parity threshold and the sensitivities.

    Args:
        block: An ``equipment_cost_parity`` block (already validated by the caller, or
            built by the single-site adapter).
        method: ``hours_per_year``, ``reference_scaling_counterexample`` (a list of at
            least two rows of ``rating_mw``, ``modelled_tcc_usd_2010_basis`` and
            ``modelled_annual_mwh``) and ``reference_scaling_common_life_years``, the
            common life the reference authors' per-MWh figures use.
        repo_root: Repository root used to resolve the block's file references.

    Returns:
        JSON-serialisable exact decimal-string results, sensitivity cases, the
        reference-scaling rows and the check flags.
    """
    getcontext().prec = _DECIMAL_PREC
    bm = block["benchmark"]

    summary_path = _resolve_repo_path(str(block["energy_summary"]), repo_root)
    aep_b, aep_hold_note = load_site_aep_and_hold(
        summary_path, block["loss_retention_factors"]
    )

    cap_b, road_allow_per_kw, epc_wrap_frac = load_site_capex_inputs(
        str(block["capex_config"]), repo_root
    )
    life_b = _to_decimal(block["operating_life_years"])
    hours_yr = _to_decimal(method["hours_per_year"])

    count_m = _to_decimal(bm["turbine_count"])
    cap_m = _to_decimal(bm["rated_capacity_mw"])
    has_hist = bm.get("historical_unreconciled_capacity_mw") is not None
    cap_m_hist = (
        _to_decimal(bm["historical_unreconciled_capacity_mw"]) if has_hist else None
    )
    cost_m_total = _to_decimal(bm["turbine_supply_usd"])
    aep_m_total = _to_decimal(bm["annual_aep_mwh"])
    life_m = _to_decimal(bm["operating_life_years"])

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
    # The premium per MW at which the site's equipment cost per lifetime MWh equals the
    # benchmark's. Lives may differ, so the yield ratio is scaled by the life ratio; with
    # equal lives the ratio is exactly 1 and this is the yield ratio less one.
    break_even_premium = yield_ratio * (life_b / life_m) - Decimal("1")

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
        _to_decimal(p) / Decimal("100") for p in block["sensitivity_premium_pct"]
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
                "change_vs_benchmark_pct": str(
                    (rate / rate_m - Decimal("1")) * Decimal("100")
                ),
                "classification": "uncalibrated sensitivity, not quote or forecast",
            }
        )

    common_life = _to_decimal(method["reference_scaling_common_life_years"])
    if common_life <= 0:
        raise ValueError("reference_scaling_common_life_years must be positive")
    scaling_rows: List[Dict[str, str]] = []
    for row in method["reference_scaling_counterexample"]:
        c = _to_decimal(row["modelled_tcc_usd_2010_basis"])
        e = _to_decimal(row["modelled_annual_mwh"])
        scaling_rows.append(
            {
                "rating_mw": str(row["rating_mw"]),
                "modelled_tcc_usd_2010_basis": str(c),
                "modelled_annual_mwh": str(e),
                "authors_common_life_equipment_usd_per_mwh": str(c / (e * common_life)),
            }
        )
    scaling_rise_pct = (
        Decimal(scaling_rows[1]["authors_common_life_equipment_usd_per_mwh"])
        / Decimal(scaling_rows[0]["authors_common_life_equipment_usd_per_mwh"])
        - Decimal("1")
    ) * Decimal("100")

    road_allowance_usd = road_allow_per_kw * cap_b * Decimal("1000")
    road_allowance_wrap_usd = road_allowance_usd * (Decimal("1") + epc_wrap_frac)

    results: Dict[str, str] = {
        "benchmark_equipment_usd_per_unit": str(cost_m_unit),
        "benchmark_equipment_usd_per_mw": str(unit_m_mw),
        "benchmark_equipment_usd_per_kw": str(cost_m_total / (cap_m * Decimal("1000"))),
    }
    if cap_m_hist is not None:
        results["benchmark_equipment_usd_per_kw_historical_unreconciled"] = str(
            cost_m_total / (cap_m_hist * Decimal("1000"))
        )
    results.update(
        {
            "benchmark_lifetime_mwh": str(energy_m_total),
            "benchmark_capacity_factor_pct": str(cf_m_pct),
            "benchmark_equipment_usd_per_lifetime_mwh": str(rate_m),
            "site_annual_mwh": str(aep_b),
            "site_lifetime_mwh": str(energy_b),
            "site_capacity_factor_pct": str(cf_b_pct),
            "site_to_benchmark_yield_per_mw_ratio": str(yield_ratio),
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
            "reference_scaling_first_to_second_rating_usd_per_mwh_change_pct": str(
                scaling_rise_pct
            ),
        }
    )

    return {
        "purpose": (
            "Reproducible conditional equipment-cost parity benchmark (not a quote/forecast; "
            "the AEP divisor's status is site_aep_hold_status)"
        ),
        "benchmark_cost_status": str(bm["status"]),
        "site_aep_hold_status": aep_hold_note,
        "calculation_basis": (
            f"Equipment only; constant AEP; {int(life_b)} years; "
            "no discounting, FX, escalation or degradation"
        ),
        "results": results,
        "sensitivity_cases": sensitivity_cases,
        "reference_scaling_counterexample": scaling_rows,
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
    """Validate and summarise an itemised road or marine cost-buildup table.

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
        "schema": COST_BUILDUP_SCHEMA,
        "delivery_route": delivery_route,
        "applicable_package_count": len(applicable),
        "unpriced_required_package_ids": missing_ids,
        "status": "COMPLETE" if is_complete else "UNPRICED_EVIDENCE_GAPS",
        "total_usd": str(priced_sum) if is_complete else None,
    }


def run_equipment_parity_for_scenario(
    scenario: Mapping[str, Any],
    method: Mapping[str, Any],
    repo_root: Path,
    *,
    scenario_label: str = "the scenario",
) -> Dict[str, Any]:
    """Run the analysis for a scenario, or report it not applicable.

    A scenario without an ``equipment_cost_parity`` block gets
    ``{"status": "not_applicable", ...}``. A malformed block raises ``ValueError``
    (from :func:`analytics.site_analysis_blocks.resolve_site_analysis_block`).
    """
    block = resolve_site_analysis_block(scenario, BLOCK_NAME)
    if block is None:
        return {
            "schema": RESULT_SCHEMA,
            "status": "not_applicable",
            "reason": f"no {BLOCK_NAME} block in {scenario_label}",
        }
    parity = compute_equipment_parity_from_block(block, method, repo_root)
    packages = block["cost_buildup_packages"]
    return {
        "schema": RESULT_SCHEMA,
        "status": "completed",
        "site": {"name": block["site"]["name"], "location": block["site"]["location"]},
        "benchmark_name": block["benchmark"]["name"],
        "equipment_parity": parity,
        "cost_buildup": {
            route: evaluate_cost_buildup(packages, route)
            for route in sorted(VALID_DELIVERY_ROUTES)
        },
    }


__all__ = [
    "BLOCK_NAME",
    "COST_BUILDUP_SCHEMA",
    "RESULT_SCHEMA",
    "VALID_DELIVERY_ROUTES",
    "compute_equipment_parity_from_block",
    "evaluate_cost_buildup",
    "load_site_aep_and_hold",
    "load_site_capex_inputs",
    "run_equipment_parity_for_scenario",
]
