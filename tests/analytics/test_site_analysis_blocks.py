"""Contract tests for the optional site-analysis scenario blocks (#1754).

Values below are synthetic. The referenced files are existing public repository files,
used only because a block's file references must resolve.
"""

from __future__ import annotations

import copy
import datetime as dt
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from analytics.site_analysis_blocks import (
    SITE_ANALYSIS_BLOCKS,
    SITE_ANALYSIS_NAMES,
    STATUS_NOT_APPLICABLE,
    STATUS_RUN,
    allowed_keys,
    declared_site_analysis_blocks,
    plan_site_analyses,
    resolve_site_analysis_block,
    validate_site_analysis_blocks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "analytics" / "site_analysis_blocks.py"
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

_ENVELOPE: Dict[str, Any] = {
    "site": {
        "name": "Example site",
        "location": "Example district",
        "latitude_deg": 8.0,
        "longitude_deg": 79.8,
    },
    "retrieved": "2026-11-16",
    "sources": ["Example tariff decision", "Example supplier range"],
}

VALID_BLOCKS: Dict[str, Dict[str, Any]] = {
    "storage_options": {
        **_ENVELOPE,
        "technology": {
            "wind_turbine": {
                "rated_mw": 5.0,
                "hub_height_m": 120.0,
                "rotor_diameter_m": 150.0,
                "cut_in_ms": 3.0,
                "cut_out_ms": 25.0,
            },
            "battery": {"round_trip_efficiency": 0.85, "dc_per_nominal": 1.1},
        },
        "sizes": {
            "options": [
                {"id": "small", "power_mw": 2.0, "energy_mwh": 8.0},
                {"id": "large", "power_mw": 4.0, "energy_mwh": 16.0},
            ]
        },
        "tariff": {
            "currency": "LKR",
            "wind_components": [20.0, 5.0],
            "storage_priority_components": [40.0, 3.0],
            "storage_other_components": [15.0, 2.0],
            "round_trip_efficiency_basis": 0.9,
            "contract_years": 15,
            "priority_window_utc_hours": [12, 13, 14, 15],
        },
        "grid_limits": {"export_limit_mw": 10.0},
    },
    "solar_storage_sizing": {
        **_ENVELOPE,
        "unit_config": "conf/blue_whale_solar_bess.yaml",
        "pricing_config": "conf/blue_whale_pv_bess_pricing.yaml",
        "regulatory_config": "conf/blue_whale_pucsl_fit_2026.yaml",
        "unit_overrides": {"dispatch.export_limit_mw": 10.0},
        "grid": {
            "pv_tables": [100, "land_max"],
            "pv_ac_mw": [3.0, 4.0],
            "min_dc_ac_ratio": 1.0,
            "max_dc_ac_ratio": 1.5,
            "bess_power_mw": [0.5, 1.0],
            "bess_duration_h": 4.0,
        },
        "readings": {
            "sum": {
                "max_pv_ac_plus_bess_mw": 10.0,
                "max_export_mw": None,
                "max_pv_ac_mw": 10.0,
                "max_bess_power_mw": 10.0,
            },
            "committed": "sum",
        },
        "uncertainty": {
            "yield_sigma_pct": 4.0,
            "yield_clip_sigma": 3.0,
            "rte_low": 0.8,
            "rte_high": 0.9,
            "residual_fade_pct_per_year": {"low": 0.0, "mode": 0.0, "high": 0.5},
        },
        "battery_health": {
            "fade_pct_per_year": 1.5,
            "fade_basis": "Example: a linear rate",
            "augment_below_soh": 0.8,
            "restore_to_soh": 1.0,
            "augmentation_usd_per_kwh": 100.0,
            "augmentation_basis": "Example: an assumption",
            "replaces_price_reserve": True,
        },
        "plant": {
            "grid_civils_development_usd": 1000000.0,
            "fixed_opex_usd_per_year": 100000.0,
            "bess_dc_per_nominal": 1.1,
        },
        "curtailment_scenario": {
            "enabled": True,
            "daytime_export_curtailment_fraction": 0.1,
            "basis": "Example: a scenario only",
        },
        "sensitivities": {
            "round_trip_efficiency": 0.9,
            "one_at_a_time": [{"name": "rte_low", "round_trip_efficiency": 0.8}],
            "break_even": [],
        },
        "recommendation": {
            "committed": {
                "reading": "sum",
                "pv_tables": 100,
                "pv_ac_mw": 3.0,
                "bess_power_mw": 0.5,
            }
        },
        "limitations": ["Example: placeholder inputs"],
    },
    "financing_screening": {
        **_ENVELOPE,
        "label": "screening",
        "debt": {
            "dfi_share": 0.3,
            "dfi_rate_decimal": 0.08,
            "local_rate_decimal": 0.12,
            "dfi_tenor_years": 15,
            "local_tenor_years": 10,
        },
        "opex": {
            "usd_share": 0.7,
            "usd_escalation_decimal": 0.025,
            "local_escalation_decimal": 0.05,
        },
        "min_downside_dscr": 1.1,
        "allowance_years": 20,
        "fx_shock": {"shock_decimal": 0.1, "operating_year": 5},
    },
    "equipment_cost_parity": {
        **_ENVELOPE,
        "energy_summary": "docs/blue_whale/met_mast_transfer_summary.json",
        "capex_config": "conf/blue_whale_capex_solar_resource.yaml",
        "operating_life_years": 20,
        "loss_retention_factors": [0.97, 0.98],
        "benchmark": {
            "name": "Example benchmark project",
            "source": "Example public statement",
            "status": "Approximate secondary benchmark",
            "turbine_count": 10,
            "rated_capacity_mw": 50.0,
            "turbine_supply_usd": 20000000.0,
            "annual_aep_mwh": 200000.0,
            "operating_life_years": 20,
        },
        "sensitivity_premium_pct": [-10.0, 0.0, 10.0],
        "cost_buildup_packages": [
            {
                "id": "E01",
                "package": "Machine",
                "route": "common",
                "quoted_amount_usd": None,
            },
            {
                "id": "M01",
                "package": "Barge",
                "route": "marine",
                "quoted_amount_usd": 0.0,
            },
        ],
    },
}


def _errors(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    validate_site_analysis_blocks(config, errors)
    return errors


def _with(block: str, mutate: Any) -> Dict[str, Any]:
    body = copy.deepcopy(VALID_BLOCKS[block])
    mutate(body)
    return {block: body}


def test_block_list_is_the_four_analyses() -> None:
    assert SITE_ANALYSIS_BLOCKS == (
        "storage_options",
        "solar_storage_sizing",
        "financing_screening",
        "equipment_cost_parity",
    )
    assert set(VALID_BLOCKS) == set(SITE_ANALYSIS_BLOCKS)


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_valid_block_passes_and_resolves(block: str) -> None:
    config = {block: copy.deepcopy(VALID_BLOCKS[block])}
    assert _errors(config) == []
    assert resolve_site_analysis_block(config, block) == VALID_BLOCKS[block]
    assert declared_site_analysis_blocks(config) == [block]


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_absent_block_is_not_applicable(block: str) -> None:
    assert resolve_site_analysis_block({}, block) is None
    assert _errors({"project": {"name": "x"}}) == []


def test_every_analysis_is_planned_for_a_scenario_without_blocks() -> None:
    """On by default: all four are listed, each with the reason it does not apply."""
    plan = plan_site_analyses(_lender_config())
    assert list(plan) == list(SITE_ANALYSIS_BLOCKS)
    for block, entry in plan.items():
        assert entry == {
            "analysis": SITE_ANALYSIS_NAMES[block],
            "status": STATUS_NOT_APPLICABLE,
            "reason": f"the scenario declares no {block} block",
        }


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_a_declared_block_plans_its_analysis_to_run(block: str) -> None:
    plan = plan_site_analyses({block: copy.deepcopy(VALID_BLOCKS[block])})
    assert plan[block] == {"analysis": SITE_ANALYSIS_NAMES[block], "status": STATUS_RUN}
    others = {name for name, entry in plan.items() if entry["status"] == STATUS_RUN}
    assert others == {block}


def test_plan_refuses_a_malformed_block() -> None:
    with pytest.raises(ValueError, match="is malformed"):
        body = copy.deepcopy(VALID_BLOCKS["equipment_cost_parity"])
        body.pop("site")
        plan_site_analyses({"equipment_cost_parity": body})


def test_unknown_block_name_is_refused() -> None:
    with pytest.raises(KeyError, match="unknown site-analysis block"):
        resolve_site_analysis_block({}, "storage_option")


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_unknown_top_level_key_fails(block: str) -> None:
    errors = _errors(_with(block, lambda b: b.update({"extra_knob": 1})))
    assert any(e.startswith(f"{block}.extra_knob: unknown key") for e in errors)


def test_unknown_nested_key_fails() -> None:
    errors = _errors(
        _with("storage_options", lambda b: b["tariff"].update({"windcomponents": [1]}))
    )
    assert any(
        "storage_options.tariff.windcomponents: unknown key" in e for e in errors
    )


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_missing_envelope_key_fails(block: str) -> None:
    errors = _errors(_with(block, lambda b: b.pop("sources")))
    assert f"{block}.sources: required key is missing" in errors


@pytest.mark.parametrize(
    "block, mutate, fragment",
    [
        (
            "storage_options",
            lambda b: b["technology"]["battery"].update({"round_trip_efficiency": 1.2}),
            "storage_options.technology.battery.round_trip_efficiency: must be <= 1.0",
        ),
        (
            "storage_options",
            lambda b: b["tariff"].update({"priority_window_utc_hours": [12, 24]}),
            "storage_options.tariff.priority_window_utc_hours[1]: must be an integer hour",
        ),
        (
            "storage_options",
            lambda b: b["tariff"].update({"priority_window_utc_hours": [12, 12]}),
            "storage_options.tariff.priority_window_utc_hours: entries must be unique",
        ),
        (
            "storage_options",
            lambda b: b["tariff"].update({"currency": "rupees"}),
            "storage_options.tariff.currency: must be a three-letter ISO currency code",
        ),
        (
            "storage_options",
            lambda b: b["technology"]["wind_turbine"].update({"cut_out_ms": 2.0}),
            "storage_options.technology.wind_turbine: cut_out_ms must be above cut_in_ms",
        ),
        (
            "storage_options",
            lambda b: b["sizes"].update({"options": []}),
            "storage_options.sizes.options: must be a non-empty list",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["grid"].update({"bess_power_mw": [True]}),
            "solar_storage_sizing.grid.bess_power_mw[0]: must be a finite number",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["grid"].update({"pv_tables": [0, "most"]}),
            "solar_storage_sizing.grid.pv_tables[0]: must be a positive integer",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["grid"].update({"max_dc_ac_ratio": 0.9}),
            "solar_storage_sizing.grid: max_dc_ac_ratio must not be below "
            "min_dc_ac_ratio",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["readings"].update({"committed": "export"}),
            "solar_storage_sizing.readings.committed: must name one of the readings",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["readings"].update({"by_reading": b["readings"]["sum"]}),
            "solar_storage_sizing.readings.by_reading: 'by_reading' is a reserved name",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["readings"]["sum"].update({"max_export_mw": 0.0}),
            "solar_storage_sizing.readings.sum.max_export_mw: must be > 0.0",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["uncertainty"].update({"rte_high": 0.7}),
            "solar_storage_sizing.uncertainty: rte_high must not be below rte_low",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["battery_health"].update({"replaces_price_reserve": "yes"}),
            "solar_storage_sizing.battery_health.replaces_price_reserve: must be true "
            "or false",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["plant"].update({"bess_dc_per_nominal": 0.9}),
            "solar_storage_sizing.plant.bess_dc_per_nominal: must be >= 1.0",
        ),
        (
            "solar_storage_sizing",
            lambda b: b["sensitivities"].update({"break_even": "none"}),
            "solar_storage_sizing.sensitivities.break_even: must be a list",
        ),
        (
            "solar_storage_sizing",
            lambda b: b.update(
                {"recommendation": {"other": b["recommendation"]["committed"]}}
            ),
            "solar_storage_sizing.recommendation.committed: required key is missing",
        ),
        (
            "solar_storage_sizing",
            lambda b: b.update({"limitations": []}),
            "solar_storage_sizing.limitations: must be a non-empty list",
        ),
        (
            "financing_screening",
            lambda b: b.update({"label": "lender"}),
            "financing_screening.label: must be 'screening'",
        ),
        (
            "financing_screening",
            lambda b: b["debt"].update({"dfi_tenor_years": 0}),
            "financing_screening.debt.dfi_tenor_years: must be a positive integer",
        ),
        (
            "financing_screening",
            lambda b: b["debt"].update({"dfi_share": float("nan")}),
            "financing_screening.debt.dfi_share: must be a finite number",
        ),
        (
            "equipment_cost_parity",
            lambda b: b["cost_buildup_packages"][0].update({"route": "air"}),
            "equipment_cost_parity.cost_buildup_packages[0].route: must be one of",
        ),
        (
            "equipment_cost_parity",
            lambda b: b["cost_buildup_packages"][1].update({"id": "E01"}),
            "equipment_cost_parity.cost_buildup_packages: package ids must be unique",
        ),
        (
            "equipment_cost_parity",
            lambda b: b["cost_buildup_packages"][0].update({"quoted_amount_usd": -1}),
            "equipment_cost_parity.cost_buildup_packages[0].quoted_amount_usd: must be >= 0.0",
        ),
        (
            "equipment_cost_parity",
            lambda b: b.update({"private_anchors": "/private/anchors.yaml"}),
            "equipment_cost_parity.private_anchors: unknown key",
        ),
        (
            "equipment_cost_parity",
            lambda b: b.pop("capex_config"),
            "equipment_cost_parity.capex_config: required key is missing",
        ),
        (
            "equipment_cost_parity",
            lambda b: b["benchmark"].update({"turbine_count": 10.5}),
            "equipment_cost_parity.benchmark.turbine_count: must be a positive integer",
        ),
    ],
)
def test_bad_value_fails_with_its_path(block: str, mutate: Any, fragment: str) -> None:
    errors = _errors(_with(block, mutate))
    assert any(e.startswith(fragment) for e in errors), errors


@pytest.mark.parametrize(
    "value, ok",
    [
        ("2026-11-16", True),
        (dt.date(2026, 11, 16), True),
        ("2026-13-01", False),
        ("16 Nov 2026", False),
        (dt.datetime(2026, 11, 16, 1, 0), False),
    ],
)
def test_retrieved_must_be_an_iso_date(value: Any, ok: bool) -> None:
    errors = _errors(_with("storage_options", lambda b: b.update({"retrieved": value})))
    assert (errors == []) is ok, errors


@pytest.mark.parametrize(
    "value, fragment",
    [
        ("conf/does_not_exist.yaml", "file not found in the repository"),
        ("/etc/hosts", "must be relative to the repository root"),
        ("conf/../conf/blue_whale_pv_bess_pricing.yaml", "without '..'"),
        ("", "must be a repository-relative file path"),
    ],
)
def test_file_references_must_resolve_inside_the_repository(
    value: str, fragment: str
) -> None:
    errors = _errors(
        _with("solar_storage_sizing", lambda b: b.update({"pricing_config": value}))
    )
    assert any(
        e.startswith("solar_storage_sizing.pricing_config:") and fragment in e
        for e in errors
    ), errors


def test_coordinates_come_in_pairs() -> None:
    errors = _errors(
        _with("financing_screening", lambda b: b["site"].pop("longitude_deg"))
    )
    assert (
        "financing_screening.site: latitude_deg and longitude_deg must be given together"
        in errors
    )


def test_block_must_be_a_mapping() -> None:
    assert _errors({"storage_options": ["not", "a", "mapping"]}) == [
        "storage_options: must be a mapping (got list)"
    ]


def test_resolve_raises_with_every_problem() -> None:
    config = _with(
        "storage_options",
        lambda b: (b.pop("retrieved"), b["tariff"].update({"contract_years": -1})),
    )
    with pytest.raises(ValueError) as excinfo:
        resolve_site_analysis_block(config, "storage_options")
    message = str(excinfo.value)
    assert "storage_options.retrieved: required key is missing" in message
    assert (
        "storage_options.tariff.contract_years: must be a positive integer" in message
    )


def test_allowed_keys_include_the_envelope() -> None:
    for block in SITE_ANALYSIS_BLOCKS:
        keys = allowed_keys(block)
        assert {"site", "retrieved", "sources", "method_config", "notes"} <= set(keys)


def test_module_holds_no_site_name_or_path() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    for literal in (
        "blue_whale",
        "blue whale",
        "dutchbay",
        "dutch bay",
        "kalpitiya",
        "mannar",
        "mullikulam",
        "lot 5b",
        "conf/",
        "scenarios/",
        "docs/",
    ):
        assert literal not in source, literal


def _committed_scenarios() -> List[Path]:
    return sorted((REPO_ROOT / "scenarios").rglob("*.yaml"))


DECLARED_BLOCKS = {
    # #1578 U3: the PV + BESS sizing's inputs.
    "scenarios/blue_whale_solar_bess_lot5b_2026.yaml": ["solar_storage_sizing"],
}


def test_committed_scenarios_declare_exactly_the_listed_blocks() -> None:
    declared = {}
    for path in _committed_scenarios():
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except yaml.YAMLError:
            continue
        for doc in docs:
            if isinstance(doc, dict) and declared_site_analysis_blocks(doc):
                declared[str(path.relative_to(REPO_ROOT))] = (
                    declared_site_analysis_blocks(doc)
                )
    assert declared == DECLARED_BLOCKS


@pytest.mark.parametrize("path", sorted(DECLARED_BLOCKS))
def test_committed_blocks_are_valid(path: str) -> None:
    config = yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert _errors(config) == []


def _lender_config() -> Dict[str, Any]:
    return yaml.safe_load(LENDER_SCENARIO.read_text(encoding="utf-8"))


def test_schema_guard_skips_the_module_when_no_block_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "analytics.site_analysis_blocks", raising=False)
    validate_config_for_v14(_lender_config(), "lender", ["cashflow", "debt"])
    assert "analytics.site_analysis_blocks" not in sys.modules


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_schema_guard_accepts_a_valid_block(block: str) -> None:
    config = _lender_config()
    config[block] = copy.deepcopy(VALID_BLOCKS[block])
    validate_config_for_v14(config, "lender", ["cashflow", "debt"])


@pytest.mark.parametrize("block", SITE_ANALYSIS_BLOCKS)
def test_schema_guard_refuses_a_malformed_block(block: str) -> None:
    config = _lender_config()
    config[block] = {"site": {}}
    with pytest.raises(ConfigValidationError, match=rf"{block}\.retrieved"):
        validate_config_for_v14(config, "lender", ["cashflow", "debt"])
