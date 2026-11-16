"""Standalone battery economics run from any scenario's YAML (#1774).

The owner ruled on 2026-11-16 that all code must be available to any scenario. These tests
pin the three parts of that for ``finance.bess_project_economics``:

- the canonical pipeline returns ``bess_project_economics`` for any scenario that declares
  ``bess_economics.enabled: true``, and adds nothing for one that does not;
- a declared block is checked strictly in pre-flight, naming the path;
- the cycling basis is a required scenario input, and the module names no supplier or tender.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Dict, List

import numpy_financial as npf
import pytest
import yaml

from finance.bess_project_economics import (
    STATUS_NOT_APPLICABLE,
    STATUS_RUN,
    bess_economics_result,
    capacity_charge_effective_cost_curve,
    compute_bess_project_economics,
    resolve_charging_cost_spec,
    validate_bess_economics_block,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "finance" / "bess_project_economics.py"
#: A committed capacity-charge battery scenario: the pipeline runs it as it stands.
CAPACITY_CHARGE_SCENARIO = (
    REPO_ROOT / "scenarios" / "ceb_bess_10mw_capacity_charge.yaml"
)


def _block(**overrides: Any) -> Dict[str, Any]:
    """An enabled block with only the inputs that have no code default."""
    block: Dict[str, Any] = {
        "enabled": True,
        "capex": {"equipment_usd": 5_000_000.0},
        "discharge_cycles_per_year": 300.0,
    }
    block.update(overrides)
    return block


def _capacity_cfg(block: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "generation": {
            "technologies": {
                "store": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "duration_h": 4.0,
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 2_000_000.0,
                    },
                }
            }
        },
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr_pct": 0.0},
    }
    if block is not None:
        cfg["bess_economics"] = block
    return cfg


def _errors(cfg: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    validate_bess_economics_block(cfg, errors)
    return errors


# --------------------------------------------------------------------------- no hidden inputs


def test_economics_refuses_a_missing_cycling_basis() -> None:
    block = _block()
    del block["discharge_cycles_per_year"]
    with pytest.raises(ValueError, match="discharge_cycles_per_year"):
        compute_bess_project_economics(
            _capacity_cfg(block), discount_rate=0.10, project_years=5
        )


def test_effective_cost_refuses_a_missing_cycling_basis() -> None:
    block = _block()
    del block["discharge_cycles_per_year"]
    with pytest.raises(ValueError, match="no code default"):
        capacity_charge_effective_cost_curve(_capacity_cfg(block), years=3)


def test_effective_cost_needs_no_cycling_basis_without_a_capacity_charge_battery() -> (
    None
):
    cfg = _capacity_cfg({"enabled": True})
    cfg["generation"]["technologies"]["store"]["revenue"] = {
        "model": "energy_tariff",
        "tariff_lkr_per_kwh": 40.0,
    }
    assert capacity_charge_effective_cost_curve(cfg, years=3) is None


def test_declared_cycles_drive_the_discharge_basis() -> None:
    """Responsiveness: the discharge basis is energy x the DECLARED cycles, not a constant."""
    for cycles in (250.0, 365.0):
        curve = capacity_charge_effective_cost_curve(
            _capacity_cfg(_block(discharge_cycles_per_year=cycles)), years=1
        )
        assert curve is not None
        assert curve[0]["discharge_mwh"] == pytest.approx(40.0 * cycles)


def test_charging_cycles_default_to_the_declared_discharge_cycles() -> None:
    cfg = _capacity_cfg(_block(charging={"tariff_lkr_per_kwh": 20.0}))
    spec = resolve_charging_cost_spec(cfg)
    assert spec is not None
    assert spec.cycles_per_year == 300.0


def test_module_names_no_supplier_tender_or_utility() -> None:
    text = MODULE.read_text(encoding="utf-8")
    for pattern in (
        r"huawei",
        r"luna\s*2000",
        r"\bCEB\b",
        r"TR/REP",
        r"price offer",
        r"\bSL\b",
    ):
        assert not re.search(pattern, text, re.IGNORECASE), pattern


# --------------------------------------------------------------------------- pre-flight


def test_absent_block_adds_no_error() -> None:
    assert _errors(_capacity_cfg(None)) == []


def test_minimal_enabled_block_is_valid() -> None:
    assert _errors(_capacity_cfg(_block())) == []


def test_full_block_is_valid() -> None:
    block = _block(
        capex={
            "equipment_usd": 5_000_000.0,
            "freight_usd": 100_000.0,
            "optional_warranty_usd": 900_000.0,
            "warranty_is_dutiable": False,
            "customs_duty_pct": 0.15,
        },
        charging={"tariff_lkr_per_kwh": 20.0, "round_trip_efficiency": 0.88},
        opex_lkr_per_year=10_000_000.0,
        opex_escalation_pct=3.0,
        warranty_schedule=[{"year": 10, "lkr": 50_000_000.0}],
        sources=["an illustrative quote"],
        notes="test block",
    )
    assert _errors(_capacity_cfg(block)) == []


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        ("yes", "bess_economics: must be a mapping"),
        (_block(cycles=400), "bess_economics.cycles: unknown key"),
        (_block(enabled="true"), "bess_economics.enabled: must be true or false"),
        (_block(capex={}), "bess_economics.capex.equipment_usd: required"),
        (_block(capex=None), "bess_economics.capex: required"),
        (
            _block(capex={"equipment_usd": 1.0, "duty_pct": 0.1}),
            "bess_economics.capex.duty_pct: unknown key",
        ),
        (
            _block(capex={"equipment_usd": 1.0, "customs_duty_pct": 15}),
            "bess_economics.capex.customs_duty_pct: must be <= 1.0",
        ),
        (
            _block(capex={"equipment_usd": -1.0}),
            "bess_economics.capex.equipment_usd: must be >= 0",
        ),
        (_block(discharge_cycles_per_year=0), "discharge_cycles_per_year: must be > 0"),
        (_block(discharge_cycles_per_year=None), "discharge_cycles_per_year: required"),
        (
            _block(charging={"round_trip_efficiency": 0.9}),
            "tariff_lkr_per_kwh: required",
        ),
        (
            _block(charging={"tariff_lkr_per_kwh": 20.0, "round_trip_efficiency": 0}),
            "round_trip_efficiency: must be > 0",
        ),
        (_block(warranty_schedule={"year": 1}), "warranty_schedule: must be a list"),
        (
            _block(warranty_schedule=[{"year": 0.5, "lkr": 1.0}]),
            "warranty_schedule[0].year: must be a positive whole operating year",
        ),
        (_block(sources="a quote"), "bess_economics.sources: must be a list"),
        (_block(opex_escalation_pct=150), "opex_escalation_pct: must be <= 100.0"),
    ],
)
def test_declared_block_is_strict(block: Any, expected: str) -> None:
    errors = _errors(_capacity_cfg(None) | {"bess_economics": block})
    assert any(expected in error for error in errors), errors


def test_disabled_block_does_not_require_the_run_inputs() -> None:
    assert _errors(_capacity_cfg({"enabled": False})) == []


def test_schema_guard_runs_the_block_check() -> None:
    from analytics.schema_guard import _validate_bess_economics_block

    errors: List[str] = []
    _validate_bess_economics_block({"bess_economics": _block(typo=1)}, errors)
    assert any("bess_economics.typo: unknown key" in e for e in errors)
    clean: List[str] = []
    _validate_bess_economics_block({"project": {}}, clean)
    assert clean == []


# --------------------------------------------------------------------------- result entry


def test_result_entry_is_none_without_the_opt_in() -> None:
    assert (
        bess_economics_result(_capacity_cfg(None), discount_rate=0.1, project_years=5)
        is None
    )
    assert (
        bess_economics_result(
            _capacity_cfg({"enabled": False}), discount_rate=0.1, project_years=5
        )
        is None
    )


def test_result_entry_lists_an_opted_in_scenario_without_a_capacity_charge_battery() -> (
    None
):
    cfg = _capacity_cfg(_block())
    cfg["generation"]["technologies"] = {}
    entry = bess_economics_result(cfg, discount_rate=0.1, project_years=5)
    assert entry is not None
    assert entry["status"] == STATUS_NOT_APPLICABLE
    assert "capacity_charge" in entry["reason"]
    assert entry["projects"] == []


def test_result_entry_carries_every_capacity_charge_battery() -> None:
    entry = bess_economics_result(
        _capacity_cfg(_block()), discount_rate=0.1, project_years=5
    )
    assert entry is not None
    assert entry["status"] == STATUS_RUN
    assert entry["discount_rate"] == 0.1
    assert entry["project_years"] == 5
    assert [p["technology"] for p in entry["projects"]] == ["store"]


# --------------------------------------------------------------------------- pipeline


def _scenario_with_block(tmp_path: Path, block: Dict[str, Any] | None) -> Path:
    raw = yaml.safe_load(CAPACITY_CHARGE_SCENARIO.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    if block is not None:
        raw["bess_economics"] = block
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_pipeline_adds_nothing_without_the_block(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    result = run_v14_pipeline_enhanced(str(_scenario_with_block(tmp_path, None)))
    assert result["status"] == "success"
    assert "bess_project_economics" not in result


def test_pipeline_runs_the_analysis_for_a_scenario_that_opts_in(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    base = run_v14_pipeline_enhanced(str(_scenario_with_block(tmp_path, None)))
    result = run_v14_pipeline_enhanced(str(_scenario_with_block(tmp_path, _block())))
    assert result["status"] == "success"

    entry = result["bess_project_economics"]
    assert entry["status"] == STATUS_RUN
    # The scenario's own discount rate and life, not a constant.
    assert entry["discount_rate"] == pytest.approx(result["kpis"]["discount_rate_used"])
    assert entry["project_years"] == 15
    project = entry["projects"][0]
    cashflow = project["cashflow_lkr"]
    # Independent oracle: numpy-financial's IRR on the emitted cashflow.
    assert project["irr"] == pytest.approx(npf.irr(cashflow), rel=1e-9)

    # KPI-neutral: the scenario's own figures do not move.
    for key in ("kpis", "annual_rows", "debt_result", "equity_distribution"):
        assert result[key] == base[key], key


def test_pipeline_preflight_refuses_a_bad_block(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    path = _scenario_with_block(tmp_path, _block(cycles_per_yr=400))
    with pytest.raises(Exception, match="bess_economics.cycles_per_yr: unknown key"):
        run_v14_pipeline_enhanced(str(path))


def test_pipeline_with_validation_off_lists_a_bad_block_and_keeps_the_figures(
    tmp_path: Path,
) -> None:
    """Write the figures, list the failure (owner ruling 2026-11-16)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    block = _block()
    del block["discharge_cycles_per_year"]
    base = run_v14_pipeline_enhanced(
        str(_scenario_with_block(tmp_path, None)), validation_mode="off"
    )
    result = run_v14_pipeline_enhanced(
        str(_scenario_with_block(tmp_path, block)), validation_mode="off"
    )
    assert result["status"] == "success"
    entry = result["bess_project_economics"]
    assert entry["status"] == "failed"
    assert "discharge_cycles_per_year" in entry["reason"]
    assert entry["projects"] == []
    assert result["kpis"] == base["kpis"]
