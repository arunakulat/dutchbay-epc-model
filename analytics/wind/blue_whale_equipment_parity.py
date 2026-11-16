"""Single-site adapter for :mod:`analytics.wind.equipment_parity` (#1755).

The equipment-cost parity analysis now runs for any scenario that declares an
``equipment_cost_parity`` block (owner ruling of 2026-11-16; contract #1754). This module
keeps the original single-site interface working: it maps a
``blue_whale_equipment_parity_v1`` configuration (``blue_whale``, ``mannar_benchmark``,
``sensitivity_premium_pct``, ``ashuri_2016_counterexample``) onto the universal module and
renames the result keys back, so ``scripts/run_blue_whale_equipment_parity_v14.py`` prints
the same bytes as before. It holds no arithmetic of its own.

It goes once the site's inputs live in its scenario block and the universal runner
(``scripts/run_equipment_parity_v14.py``) replaces the single-site script.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from analytics.wind.equipment_parity import VALID_DELIVERY_ROUTES  # noqa: F401
from analytics.wind.equipment_parity import (
    compute_equipment_parity_from_block,
)
from analytics.wind.equipment_parity import (
    evaluate_cost_buildup as _evaluate_cost_buildup,
)

CAPEX_SITE_INPUT_COPIES = (
    "rated_capacity_mw",
    "road_allowance_usd_per_kw",
    "epc_wrap_pct",
)

#: Universal result key -> the single-site key this module has always returned.
RESULT_KEY_MAP: Dict[str, str] = {
    "benchmark_equipment_usd_per_unit": "mannar_equipment_usd_per_unit",
    "benchmark_equipment_usd_per_mw": "mannar_equipment_usd_per_mw",
    "benchmark_equipment_usd_per_kw": "mannar_equipment_usd_per_kw_50mw",
    "benchmark_equipment_usd_per_kw_historical_unreconciled": (
        "mannar_equipment_usd_per_kw_56mw_historical_unreconciled"
    ),
    "benchmark_lifetime_mwh": "mannar_lifetime_mwh",
    "benchmark_capacity_factor_pct": "mannar_capacity_factor_pct",
    "benchmark_equipment_usd_per_lifetime_mwh": "mannar_equipment_usd_per_lifetime_mwh",
    "site_annual_mwh": "blue_whale_annual_mwh",
    "site_lifetime_mwh": "blue_whale_lifetime_mwh",
    "site_capacity_factor_pct": "blue_whale_capacity_factor_pct",
    "site_to_benchmark_yield_per_mw_ratio": "blue_whale_to_mannar_yield_per_mw_ratio",
    "reference_scaling_first_to_second_rating_usd_per_mwh_change_pct": (
        "ashuri_5_to_10mw_common_life_equipment_usd_per_mwh_change_pct"
    ),
}

#: Universal top-level and sensitivity-case keys -> single-site keys.
TOP_KEY_MAP: Dict[str, str] = {
    "benchmark_cost_status": "mannar_cost_status",
    "site_aep_hold_status": "blue_whale_aep_hold_status",
    "reference_scaling_counterexample": "ashuri_2016_counterexample",
}
CASE_KEY_MAP: Dict[str, str] = {"change_vs_benchmark_pct": "change_vs_mannar_pct"}

_LEGACY_COST_BUILDUP_SCHEMA = "blue_whale.cost_buildup_evaluation.v1"


def _rename(mapping: Mapping[str, Any], key_map: Mapping[str, str]) -> Dict[str, Any]:
    return {key_map.get(k, k): v for k, v in mapping.items()}


def compute_equipment_parity(
    cfg: Mapping[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """Compute the single-site parity result from a ``blue_whale_equipment_parity_v1`` config.

    Args:
        cfg: Parsed ``blue_whale_equipment_parity_v1`` configuration mapping.
        repo_root: Repository root used to resolve relative summary paths.

    Returns:
        The universal result with the original single-site key names.
    """
    bw = cfg["blue_whale"]
    copies = [k for k in CAPEX_SITE_INPUT_COPIES if k in bw]
    if copies:
        raise ValueError(
            f"blue_whale must not repeat capex site inputs ({', '.join(copies)}); "
            "they are read from capex_solar_resource_config"
        )
    if not bw.get("loss_retention_factors"):
        raise ValueError("blue_whale.loss_retention_factors must be non-empty")
    if not bw.get("capex_solar_resource_config"):
        raise ValueError("blue_whale.capex_solar_resource_config is required")
    block = {
        "energy_summary": bw["summary_json_path"],
        "capex_config": bw["capex_solar_resource_config"],
        "operating_life_years": bw["operating_life_years"],
        "loss_retention_factors": bw["loss_retention_factors"],
        "benchmark": cfg["mannar_benchmark"],
        "sensitivity_premium_pct": cfg["sensitivity_premium_pct"],
    }
    method = {
        "hours_per_year": bw["hours_per_year"],
        "reference_scaling_counterexample": cfg["ashuri_2016_counterexample"],
    }
    out = compute_equipment_parity_from_block(block, method, repo_root)
    legacy = _rename(out, TOP_KEY_MAP)
    legacy["results"] = _rename(out["results"], RESULT_KEY_MAP)
    legacy["sensitivity_cases"] = [
        _rename(case, CASE_KEY_MAP) for case in out["sensitivity_cases"]
    ]
    return legacy


def evaluate_cost_buildup(
    packages: Sequence[Mapping[str, Any]],
    delivery_route: str,
) -> Dict[str, Any]:
    """Single-site wrapper of :func:`analytics.wind.equipment_parity.evaluate_cost_buildup`."""
    out = _evaluate_cost_buildup(packages, delivery_route)
    out["schema"] = _LEGACY_COST_BUILDUP_SCHEMA
    return out
