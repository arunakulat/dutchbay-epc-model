"""#1817: the tornado and global SA read a declared CAPEX breakdown reconciliation.

A scenario whose ``monte_carlo.parameters`` declare ``reconcile_breakdown: pro_rata`` on
``capex.usd_total`` (#1762) got no tornado: a CAPEX shock left ``capex.breakdown`` summing
to the old total, the trial path refused the mismatch, and that one refusal removed every
bar. Now:

- the tornado and global SA scale the breakdown pro rata through ``coherent_overrides``,
  the same scaling the Monte Carlo engine applies;
- without the declaration the shock is still refused, but only that driver's bar is
  reported "not computed" with the reason, and the other bars render;
- one helper decides which technologies a ``project.capacity_factor`` shock couples, for
  the tornado, the global SA and the Monte Carlo engine alike, and it counts what the
  pipeline's year-1 reconciliation counts.
"""

from __future__ import annotations

import copy
import logging
import math
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.core.sensitivity_runner import run_sensitivity_analysis_from_path
from analytics.sensitivity.engine import (
    coherent_overrides,
    coupled_technology_capacity_factors,
    declared_breakdown_reconciliation,
    pro_rata_breakdown,
)

REPO = Path(__file__).resolve().parents[2]
#: The one committed scenario that declares the reconciliation (#1762, #1771).
DECLARING = REPO / "scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml"
CAPEX = "capex.usd_total"
CF = "project.capacity_factor"


def _breakdown_cfg(*, declared: bool = True) -> Dict[str, Any]:
    param: Dict[str, Any] = {"name": CAPEX, "low": 90.0, "high": 120.0}
    if declared:
        param["reconcile_breakdown"] = "pro_rata"
    return {
        "capex": {
            "usd_total": 100.0,
            "derive_from_breakdown": True,
            "breakdown": {"turbines": 60.0, "civils": 40.0, "note": "not a line"},
        },
        "monte_carlo": {"parameters": [param]},
    }


def _strip_declaration(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    for p in out["monte_carlo"]["parameters"]:
        p.pop("reconcile_breakdown", None)
    return out


# ------------------------------------------------------------------ coherent_overrides


def test_a_declared_capex_shock_scales_every_breakdown_line_pro_rata() -> None:
    out = coherent_overrides(_breakdown_cfg(), {CAPEX: 110.0})
    assert out == {
        CAPEX: 110.0,
        "capex.breakdown.turbines": pytest.approx(66.0),
        "capex.breakdown.civils": pytest.approx(44.0),
    }
    # The scaled lines reconcile with the shocked total exactly.
    lines = [v for k, v in out.items() if k.startswith("capex.breakdown.")]
    assert sum(lines) == pytest.approx(110.0, rel=1e-12)


def test_the_scaling_is_the_monte_carlo_engines_own() -> None:
    cfg = _breakdown_cfg()
    out = coherent_overrides(cfg, {CAPEX: 110.0})
    shared = pro_rata_breakdown(cfg, 110.0)
    assert {f"capex.breakdown.{k}": v for k, v in shared.items()} == {
        k: v for k, v in out.items() if k != CAPEX
    }


def test_without_the_declaration_a_capex_shock_passes_unchanged() -> None:
    assert coherent_overrides(_breakdown_cfg(declared=False), {CAPEX: 110.0}) == {
        CAPEX: 110.0
    }


def test_a_declaration_does_not_touch_other_drivers() -> None:
    assert coherent_overrides(_breakdown_cfg(), {"opex.usd_per_year": 5.0}) == {
        "opex.usd_per_year": 5.0
    }


def test_a_line_overridden_directly_and_through_the_total_is_refused() -> None:
    with pytest.raises(ValueError, match="overridden directly and through"):
        coherent_overrides(
            _breakdown_cfg(), {CAPEX: 110.0, "capex.breakdown.civils": 1.0}
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda c: c["monte_carlo"]["parameters"][0].update(
                reconcile_breakdown="scaled"
            ),
            "must be 'pro_rata'",
        ),
        (lambda c: c["capex"].pop("derive_from_breakdown"), "derive_from_breakdown"),
        (lambda c: c["capex"].update(breakdown={"a": 0.0}), "positive total"),
    ],
)
def test_an_invalid_declaration_is_refused_on_the_tornado_path(
    mutate: Any, message: str
) -> None:
    cfg = _breakdown_cfg()
    mutate(cfg)
    with pytest.raises(ValueError, match=message):
        coherent_overrides(cfg, {CAPEX: 110.0})


def test_the_monte_carlo_engine_reads_the_same_declaration() -> None:
    from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine

    cfg = _breakdown_cfg()
    assert MonteCarloEngine._extract_breakdown_reconciliation(cfg) == (
        declared_breakdown_reconciliation(cfg)
    )
    cfg["monte_carlo"]["parameters"][0]["reconcile_breakdown"] = "scaled"
    with pytest.raises(MonteCarloConfigError, match="must be 'pro_rata'"):
        MonteCarloEngine._extract_breakdown_reconciliation(cfg)


# ------------------------------------------------------------------ the shared CF helper


def _mixed_technologies() -> Dict[str, Any]:
    return {
        "project": {"capacity_mw": 20.0, "capacity_factor": 0.3},
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 10.0, "capacity_factor": "0.4"},
                "solar": {"capacity_mw": "10", "capacity_factor": 0.2},
                "bess_1": {"type": "bess", "power_mw": 5.0, "capacity_factor": 0.9},
                "storage": {"type": "BESS", "capacity_mw": 5.0, "capacity_factor": 0.9},
            }
        },
    }


def test_the_helper_counts_what_the_year_1_reconciliation_counts() -> None:
    from finance.cashflow_v14_production import resolve_tech_generation_specs

    cfg = _mixed_technologies()
    specs = resolve_tech_generation_specs(cfg, {"degradation": 0.0, **cfg["project"]})
    assert specs is not None
    counted = coupled_technology_capacity_factors(cfg)
    # Storage is skipped whatever its spelling; a numeric string counts, as there.
    assert counted == {"wind": 0.4, "solar": 0.2}
    assert {s["technology"]: s["capacity_factor"] for s in specs} == counted


def test_the_tornado_and_the_monte_carlo_engine_couple_the_same_technologies() -> None:
    from analytics.mc.engine import MonteCarloEngine

    cfg = _mixed_technologies()
    cfg["monte_carlo"] = {
        "allow_toy_fallback": True,
        "parameters": [{"name": CF, "low": 0.27, "high": 0.33}],
    }
    engine = MonteCarloEngine.__new__(MonteCarloEngine)
    engine._param_names = [CF]
    engine._base_config = cfg
    engine._cf_coupling = None
    engine._init_cf_coupling()
    assert engine._cf_coupling == (0.3, {"wind": 0.4, "solar": 0.2})
    tornado = coherent_overrides(cfg, {CF: 0.33})
    assert sorted(k for k in tornado if k != CF) == [
        "generation.technologies.solar.capacity_factor",
        "generation.technologies.wind.capacity_factor",
    ]


# ------------------------------------------------------------------ the real tornado


def _two_drivers(cfg: Dict[str, Any]) -> list[ParameterRangeConfig]:
    return [
        ParameterRangeConfig(
            variable_name=CAPEX,
            base_value=float(cfg["capex"]["usd_total"]),
            low_pct=-10.0,
            high_pct=10.0,
            label="CAPEX",
        ),
        ParameterRangeConfig(
            variable_name="opex.usd_per_year",
            base_value=float(cfg["opex"]["usd_per_year"]),
            low_pct=-15.0,
            high_pct=15.0,
            label="OPEX",
        ),
    ]


def test_the_declaring_scenario_gets_a_computed_capex_bar(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.CRITICAL)
    cfg = yaml.safe_load(DECLARING.read_text(encoding="utf-8"))
    suite = run_sensitivity_analysis_from_path(DECLARING, parameters=_two_drivers(cfg))
    assert suite.metadata["not_computed_drivers"] == {}
    for tornado in suite.tornado_results:
        assert "not_computed" not in tornado.metadata
    capex = suite.tornado_results[0]
    assert math.isfinite(capex.impact_abs)
    # A CAPEX overrun lowers the project IRR.
    assert capex.shock_results[0].high_case < capex.base_metric


def test_without_the_declaration_only_the_capex_bar_is_not_computed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.CRITICAL)
    cfg = _strip_declaration(yaml.safe_load(DECLARING.read_text(encoding="utf-8")))
    path = tmp_path / "undeclared.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    suite = run_sensitivity_analysis_from_path(path, parameters=_two_drivers(cfg))

    capex, opex = suite.tornado_results
    # Still refused, and the refused driver is named with the trial path's reason.
    assert list(suite.metadata["not_computed_drivers"]) == [CAPEX]
    reason = capex.metadata["not_computed"]
    assert reason.startswith("PipelineValidationError: ")
    assert "capex.breakdown" in reason
    assert math.isnan(capex.impact_abs)
    # Not computed is not "undefined": no rate failed to solve.
    assert CAPEX not in suite.metadata.get("undefined_drivers", [])
    # The rest of the tornado renders. (This scenario's project IRR is undefined at the
    # high OPEX point, so the low point is the one with a figure.)
    assert "not_computed" not in opex.metadata
    assert math.isfinite(opex.shock_results[0].low_case)


def test_a_fault_that_is_not_a_refusal_still_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analytics.sensitivity.engine as engine_module

    real = engine_module.evaluate_with_overrides

    def _faulty(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("overrides"):
            raise TypeError("a coding fault")
        return real(*args, **kwargs)

    monkeypatch.setattr(engine_module, "evaluate_with_overrides", _faulty)
    cfg = yaml.safe_load(DECLARING.read_text(encoding="utf-8"))
    with pytest.raises(TypeError, match="a coding fault"):
        run_sensitivity_analysis_from_path(DECLARING, parameters=_two_drivers(cfg)[1:])


# ------------------------------------------------------------------ the global SA


def test_the_global_sa_evaluator_applies_the_same_coupling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analytics.sensitivity.global_sa as global_sa

    seen: list[Dict[str, Any]] = []

    def _capture(_path: Any, *, overrides: Dict[str, Any]) -> Dict[str, Any]:
        seen.append(dict(overrides))
        return {}

    monkeypatch.setattr(global_sa, "evaluate_with_overrides", _capture)
    cfg = yaml.safe_load(DECLARING.read_text(encoding="utf-8"))
    total = float(cfg["capex"]["usd_total"]) * 1.1
    global_sa._engine_evaluate_fn(str(DECLARING))({CAPEX: total})
    (overrides,) = seen
    lines = {k: v for k, v in overrides.items() if k.startswith("capex.breakdown.")}
    assert lines, "the breakdown was not scaled"
    assert sum(lines.values()) == pytest.approx(total, rel=1e-9)
