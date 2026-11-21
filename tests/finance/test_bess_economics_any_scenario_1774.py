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
import hashlib
import re
import subprocess
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
        # Required since #1429: no code default for the build time (was 2 periods).
        "timeline": {"construction_years": 2},
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


def test_a_separate_charging_cycles_input_is_refused() -> None:
    """#1776 domain D-2: charging energy follows the discharge cycles; no second input."""
    errors = _errors(
        _capacity_cfg(
            _block(charging={"tariff_lkr_per_kwh": 20.0, "cycles_per_year": 365.0})
        )
    )
    assert any("charging.cycles_per_year: unknown key" in e for e in errors)


def test_declared_cycles_drive_the_charging_cost() -> None:
    """#1776 domain D-5: the economics' charging cost scales with the declared cycles."""
    costs = []
    for cycles in (250.0, 365.0):
        cfg = _capacity_cfg(
            _block(
                discharge_cycles_per_year=cycles,
                charging={"tariff_lkr_per_kwh": 10.0, "round_trip_efficiency": 0.8},
            )
        )
        projects = compute_bess_project_economics(
            cfg, discount_rate=0.10, project_years=3
        )
        assert projects is not None
        costs.append(projects[0].charging_cost_lkr[0])
    # year 1 at full health: 40 MWh x cycles / 0.8 x 1000 kWh/MWh x 10 LKR/kWh
    assert costs[0] == pytest.approx(40.0 * 250.0 / 0.8 * 1000.0 * 10.0)
    assert costs[1] == pytest.approx(40.0 * 365.0 / 0.8 * 1000.0 * 10.0)


def _two_battery_cfg() -> Dict[str, Any]:
    cfg = _capacity_cfg(_block())
    techs = cfg["generation"]["technologies"]
    techs["store_b"] = copy.deepcopy(techs["store"])
    return cfg


def test_more_than_one_capacity_charge_battery_is_refused() -> None:
    """#1776 domain D-3: one block is one battery project; two would double the capex."""
    errors = _errors(_two_battery_cfg())
    assert any("declares 2 capacity-charge batteries" in e for e in errors)
    with pytest.raises(ValueError, match="2 capacity-charge batteries"):
        compute_bess_project_economics(
            _two_battery_cfg(), discount_rate=0.10, project_years=3
        )


def test_flows_translate_at_the_operating_fx_curve_with_its_offset() -> None:
    """#1776 domain D-1/D-4: USD on the scenario's operating FX curve, offset as the cashflow."""
    cfg = _capacity_cfg(_block())
    cfg["fx"] = {"start_lkr_per_usd": 300.0, "annual_depr_pct": 5.0}
    cfg["timeline"] = {"construction_years": 1}
    project = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=3)[
        0
    ]
    assert project.fx_lkr_per_usd[0] == pytest.approx(300.0 * 1.05)
    assert project.cashflow_usd[0] == pytest.approx(-5_000_000.0)
    for t, rate in enumerate(project.fx_lkr_per_usd, start=1):
        assert project.cashflow_usd[t] == pytest.approx(project.cashflow_lkr[t] / rate)
    assert project.npv_usd == pytest.approx(npf.npv(0.10, project.cashflow_usd))


#: sha256 of the lower-cased word tokens (and adjacent token pairs) the module must not
#: contain: the battery supplier's name, its product names and a tender reference prefix.
#: Held as digests so this public file does not write the names it guards against (#1776
#: assurance M-1). A digest is checked against every token and every adjacent pair.
_GUARDED_TOKEN_DIGESTS = frozenset(
    {
        "8ebc1ca3dc4b3cf19a0b02bbd10a47f6339af8aa6d24dd7b89d785176ca67d27",
        "970ec274ca867815174ebe4eff19282000f9495a6c7254e94991d1fb4dc3df30",
        "b81c8201acfc7639be3bd3d7f875ba5ca76e422fa2163cec9dace50662b637a7",
        "e2cc900a1480fdd6ffa89ce9778ebef4f44ca724949e7035db6a099e76361ecf",
    }
)


def _token_digests(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    pairs = [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]
    return {hashlib.sha256(t.encode()).hexdigest() for t in [*tokens, *pairs]}


def test_module_names_no_supplier_tender_or_utility() -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert not _token_digests(text) & _GUARDED_TOKEN_DIGESTS
    for pattern in (r"\bCEB\b", r"price offer", r"\bSL\b"):
        assert not re.search(pattern, text, re.IGNORECASE), pattern


def test_the_name_guard_detects_a_guarded_token() -> None:
    """The guard is live: the module as it stood on main before #1774 trips it."""
    base = subprocess.run(
        ["git", "show", "46a6d700:finance/bess_project_economics.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if base.returncode != 0:
        pytest.skip("base commit not available in this clone")
    assert _token_digests(base.stdout) & _GUARDED_TOKEN_DIGESTS


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
        (_block(notes=["a list"]), "bess_economics.notes: must be text"),
        (
            _block(capex={"equipment_usd": 1.0, "warranty_is_dutiable": "yes"}),
            "bess_economics.capex.warranty_is_dutiable: must be true or false",
        ),
        (
            _block(warranty_schedule=[{"year": 1, "lkr": 1.0, "usd": 2.0}]),
            "warranty_schedule[0].usd: unknown key",
        ),
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


def _scenario_with_block(
    tmp_path: Path, block: Dict[str, Any] | None, *, life_years: int | None = None
) -> Path:
    raw = yaml.safe_load(CAPACITY_CHARGE_SCENARIO.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    if block is not None:
        raw["bess_economics"] = block
    if life_years is not None:
        raw["project"]["life_years"] = life_years
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
    assert project["irr_lkr"] == pytest.approx(npf.irr(cashflow), rel=1e-9)
    usd = project["cashflow_usd"]
    assert project["irr_usd"] == pytest.approx(npf.irr(usd), rel=1e-9)
    assert project["npv_usd"] == pytest.approx(npf.npv(entry["discount_rate"], usd))
    assert entry["currency_basis"].startswith("USD, nominal, pre-tax, unlevered")

    # KPI-neutral: the scenario's own figures do not move.
    for key in ("kpis", "annual_rows", "debt_result", "equity_distribution"):
        assert result[key] == base[key], key


def test_pipeline_adds_nothing_when_the_block_is_disabled(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    path = _scenario_with_block(tmp_path, {"enabled": False})
    result = run_v14_pipeline_enhanced(str(path))
    assert result["status"] == "success"
    assert "bess_project_economics" not in result


def test_pipeline_passes_the_scenario_life_not_a_constant(tmp_path: Path) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline_enhanced

    path = _scenario_with_block(tmp_path, _block(), life_years=20)
    result = run_v14_pipeline_enhanced(str(path))
    assert result["bess_project_economics"]["project_years"] == 20


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
