"""Tests for Blue Whale equipment-cost parity benchmark and cost-buildup guards."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.wind.blue_whale_equipment_parity import (
    compute_equipment_parity,
    evaluate_cost_buildup,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF_PATH = REPO_ROOT / "conf" / "blue_whale_equipment_parity.yaml"


def _load_cfg() -> dict[str, Any]:
    loaded = yaml.safe_load(CONF_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return {str(k): v for k, v in loaded.items()}


def test_equipment_parity_matches_2026_11_14_review_brief() -> None:
    """Reproduces exact Decimal outputs from the owner's private review brief of 2026-11-14."""
    cfg = _load_cfg()
    out = compute_equipment_parity(cfg, REPO_ROOT)
    res = out["results"]

    assert res["mannar_equipment_usd_per_mw"] == "389800"
    assert res["mannar_equipment_usd_per_lifetime_mwh"].startswith(
        "4.7077294685990338164"
    )
    assert res["blue_whale_annual_mwh"] == "40574.749451543354000"
    assert res["blue_whale_lifetime_mwh"] == "811494.989030867080000"
    assert res["constant_price_per_mw_equipment_cost_usd"] == "3703100.0"
    assert res["constant_price_per_mw_equipment_usd_per_lifetime_mwh"].startswith(
        "4.5633060586393147362"
    )
    assert res["constant_price_per_mw_change_in_usd_per_lifetime_mwh_pct"].startswith(
        "-3.0677933157169676352"
    )
    assert res["same_usd_per_mwh_parity_equipment_cost_usd"].startswith(
        "3820298.8734810626543"
    )
    assert res["break_even_equipment_price_per_mw_premium_pct"].startswith(
        "3.1648854603187236206"
    )
    assert res["road_allowance_usd"] == "380000.00"
    assert res["road_allowance_plus_epc_wrap_usd"] == "399000.0000"
    assert res[
        "ashuri_5_to_10mw_common_life_equipment_usd_per_mwh_change_pct"
    ].startswith("28.718969119847209104")
    assert "HOLD" in out["blue_whale_aep_hold_status"]
    assert "P50/P90 and lender use stands" in out["blue_whale_aep_hold_status"]
    assert all(out["checks"].values())


def test_equipment_parity_algebraic_and_monotonicity_invariants() -> None:
    """TEST-01: independent algebraic identities and sensitivity monotonicity."""
    cfg = _load_cfg()
    out = compute_equipment_parity(cfg, REPO_ROOT)
    res = out["results"]

    rate_m = Decimal(res["mannar_equipment_usd_per_lifetime_mwh"])
    rate_cap = Decimal(res["constant_price_per_mw_equipment_usd_per_lifetime_mwh"])
    yield_ratio = Decimal(res["blue_whale_to_mannar_yield_per_mw_ratio"])
    parity_cost = Decimal(res["same_usd_per_mwh_parity_equipment_cost_usd"])
    cap_cost = Decimal(res["constant_price_per_mw_equipment_cost_usd"])
    premium = Decimal(res["break_even_equipment_price_per_mw_premium_pct"]) / Decimal(
        "100"
    )

    assert abs(rate_cap / rate_m - Decimal("1") / yield_ratio) < Decimal("1e-40")
    assert abs(parity_cost - cap_cost * (Decimal("1") + premium)) < Decimal("1e-35")

    cases = out["sensitivity_cases"]
    changes = [Decimal(c["change_vs_mannar_pct"]) for c in cases]
    assert changes == sorted(changes)
    assert changes[0] < Decimal("0") < changes[-1]

    break_even_case = min(cases, key=lambda c: abs(Decimal(c["change_vs_mannar_pct"])))
    assert abs(Decimal(break_even_case["change_vs_mannar_pct"])) < Decimal("1e-35")


def test_cost_buildup_refuses_unpriced_totals_and_negative_amounts() -> None:
    """Unpriced (None) packages must never be treated as zero or summed."""
    cfg = _load_cfg()
    packages = cfg["cost_buildup_packages"]

    road = evaluate_cost_buildup(packages, "road")
    assert road["status"] == "UNPRICED_EVIDENCE_GAPS"
    assert road["total_usd"] is None
    assert "E01" in road["unpriced_required_package_ids"]
    assert "R01" in road["unpriced_required_package_ids"]
    assert "M01" not in road["unpriced_required_package_ids"]

    marine = evaluate_cost_buildup(packages, "marine")
    assert marine["status"] == "UNPRICED_EVIDENCE_GAPS"
    assert marine["total_usd"] is None
    assert "M01" in marine["unpriced_required_package_ids"]
    assert "R01" not in marine["unpriced_required_package_ids"]

    # Pricing all required marine packages (leaving marine_conditional M06 as None) succeeds.
    priced_marine = [
        (
            {**pkg, "quoted_amount_usd": 100.0}
            if pkg["route"] != "marine_conditional"
            else dict(pkg)
        )
        for pkg in packages
    ]
    complete_marine = evaluate_cost_buildup(priced_marine, "marine")
    assert complete_marine["status"] == "COMPLETE"
    assert complete_marine["total_usd"] == "1300.0"

    with pytest.raises(ValueError, match="negative"):
        evaluate_cost_buildup(
            [{"id": "E01", "route": "common", "quoted_amount_usd": -1.0}],
            "road",
        )

    with pytest.raises(ValueError, match="delivery_route"):
        evaluate_cost_buildup(packages, "air")


def test_hydra_cli_emits_valid_json() -> None:
    """Hydra CLI prints one valid JSON object with parity and buildup keys."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_blue_whale_equipment_parity_v14.py"),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert "equipment_parity" in payload
    assert "cost_buildup" in payload
    assert payload["cost_buildup"]["road"]["status"] == "UNPRICED_EVIDENCE_GAPS"
    assert payload["cost_buildup"]["marine"]["status"] == "UNPRICED_EVIDENCE_GAPS"


def test_capex_site_inputs_are_read_from_capex_config_without_duplicates() -> None:
    """#1686 L-16 pattern: site capex inputs live in capex_solar_resource_config only."""
    cfg = _load_cfg()
    bw = cfg["blue_whale"]
    assert not {
        "rated_capacity_mw",
        "road_allowance_usd_per_kw",
        "epc_wrap_pct",
    } & set(bw)
    assert (
        bw["capex_solar_resource_config"] == "conf/blue_whale_capex_solar_resource.yaml"
    )


def test_capex_site_inputs_follow_capex_config_changes(tmp_path: Path) -> None:
    """TEST-01 responsiveness: parity outputs track changes in the capex YAML."""
    capex_src = REPO_ROOT / "conf" / "blue_whale_capex_solar_resource.yaml"
    capex_data = yaml.safe_load(capex_src.read_text(encoding="utf-8"))
    capex_data["wind"]["rated_kw"] = 10000.0
    capex_data["wind"]["inland_transport_usd_per_kw"]["mode"] = 50.0
    capex_data["wind"]["epc_margin_pct"]["mode"] = 0.10
    moved = tmp_path / "capex.yaml"
    moved.write_text(yaml.safe_dump(capex_data), encoding="utf-8")

    cfg = _load_cfg()
    cfg["blue_whale"] = {
        **cfg["blue_whale"],
        "capex_solar_resource_config": str(moved),
    }
    res = compute_equipment_parity(cfg, REPO_ROOT)["results"]
    assert Decimal(res["constant_price_per_mw_equipment_cost_usd"]) == Decimal(
        "3898000"
    )
    assert Decimal(res["road_allowance_usd"]) == Decimal("500000")
    assert Decimal(res["road_allowance_plus_epc_wrap_usd"]) == Decimal("550000")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"rated_capacity_mw": 9.5}, "must not repeat capex site inputs"),
        ({"road_allowance_usd_per_kw": 40}, "must not repeat capex site inputs"),
        ({"epc_wrap_pct": 5}, "must not repeat capex site inputs"),
        (
            {"capex_solar_resource_config": None},
            "capex_solar_resource_config is required",
        ),
    ],
)
def test_duplicate_capex_site_inputs_or_missing_config_refused(
    changes: dict[str, Any], message: str
) -> None:
    """Refuse duplicate capex site inputs or missing capex_solar_resource_config."""
    cfg = _load_cfg()
    cfg["blue_whale"] = {**cfg["blue_whale"], **changes}
    with pytest.raises(ValueError, match=message):
        compute_equipment_parity(cfg, REPO_ROOT)


def test_loss_retention_factors_come_from_yaml_and_validate() -> None:
    """FRAMEWORK-02: loss_retention_factors come from YAML and fail loudly if invalid."""
    cfg = _load_cfg()
    assert cfg["blue_whale"]["loss_retention_factors"] == [0.97, 0.98, 0.98, 0.99]

    empty_cfg = {
        **cfg,
        "blue_whale": {**cfg["blue_whale"], "loss_retention_factors": []},
    }
    with pytest.raises(ValueError, match="non-empty"):
        compute_equipment_parity(empty_cfg, REPO_ROOT)

    bad_cfg = {
        **cfg,
        "blue_whale": {**cfg["blue_whale"], "loss_retention_factors": [1.05]},
    }
    with pytest.raises(ValueError, match="must be in"):
        compute_equipment_parity(bad_cfg, REPO_ROOT)
