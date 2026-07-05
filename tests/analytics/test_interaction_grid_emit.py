"""Two-factor interaction-grid report emitter (#739 slice-2) — tests.

The emitter (``app.reports.interaction_grid_emit``) is the opt-in, batch-path caller that runs the
heavy N×M grid and renders the lender report section. These tests pin:
  - config-driven build success (drivers + metric resolved from the ``interaction_grid`` block),
    with the heavy per-cell pipeline STUBBED so the test is fast (a deterministic closed-form
    metric, exactly as the slice-1 engine tests do);
  - fail-loud (CESSPIT) when the block is absent, or omits the metric / a driver, or a driver spec
    is malformed / does not resolve to a config path;
  - the latency guard: ``app/api/main.py`` (the synchronous HTTP route) is NOT modified by this
    slice — the grid must never be reachable from the sync route (#645).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Mapping

import pytest
import yaml

import analytics.sensitivity.interaction as interaction_mod
from app.reports.interaction_grid_emit import (
    build_interaction_grid_for_scenario,
    emit_interaction_grid_report_from_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# A minimal, self-contained scenario the fake gateway can read: two independent scalar drivers plus
# the interaction_grid block that selects them. Kept tiny so no real finance runs in these tests.
_BASE_SCENARIO: Dict[str, Any] = {
    "drivers": {"x": 10.0, "y": 5.0},
    "interaction_grid": {
        "metric": "metric",
        "param_a": {
            "variable_name": "drivers.x",
            "base_value": 10.0,
            "low_pct": -10.0,
            "high_pct": 10.0,
            "label": "Driver X",
        },
        "param_b": {
            "variable_name": "drivers.y",
            "base_value": 5.0,
            "low_pct": -10.0,
            "high_pct": 10.0,
            "label": "Driver Y",
        },
    },
}


def _write_scenario(tmp_path: Path, cfg: Mapping[str, Any]) -> Path:
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(dict(cfg)), encoding="utf-8")
    return path


def _fake_gateway(
    metric_fn: Callable[[float, float], float],
) -> Callable[..., Dict[str, Any]]:
    """An evaluate_with_overrides stand-in computing metric_fn(x, y) from overrides."""

    def _eval(
        *,
        config_path: Any = None,
        raw_config: Mapping[str, Any] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        assert raw_config is not None
        ov = dict(overrides or {})
        x = float(ov.get("drivers.x", raw_config["drivers"]["x"]))
        y = float(ov.get("drivers.y", raw_config["drivers"]["y"]))
        return {"kpis": {"metric": metric_fn(x, y)}}

    return _eval


def test_build_grid_from_config_multiplicative_interaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A multiplicative metric m = x*y surfaces a non-zero interaction corner (drivers coupled)."""
    monkeypatch.setattr(
        interaction_mod,
        "evaluate_with_overrides",
        _fake_gateway(lambda x, y: x * y),
    )
    scenario = _write_scenario(tmp_path, _BASE_SCENARIO)
    grid = build_interaction_grid_for_scenario(scenario)
    assert grid.metric_name == "metric"
    assert grid.param_a_name == "drivers.x"
    assert grid.param_b_name == "drivers.y"
    assert grid.metadata["param_a_label"] == "Driver X"
    # A multiplicative metric is NOT additive → a non-zero interaction surface.
    assert grid.max_abs_interaction > 0.0
    assert grid.metadata["n_failed_cells"] == 0


def test_emit_writes_report_with_interaction_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full emitter renders a lender HTML report carrying the interaction-grid section."""
    monkeypatch.setattr(
        interaction_mod,
        "evaluate_with_overrides",
        _fake_gateway(lambda x, y: x * y),
    )
    scenario = _write_scenario(tmp_path, _BASE_SCENARIO)
    result = {"kpis": {"project_irr": 0.05}}
    out_html = tmp_path / "interaction_grid_report.html"
    written = emit_interaction_grid_report_from_pipeline(
        result, scenario, out_html, generated_at="2026-07-05T00:00:00+00:00"
    )
    assert written == out_html and out_html.exists()
    html = out_html.read_text(encoding="utf-8")
    assert "Interaction Grid" in html
    assert "Driver X" in html and "Driver Y" in html


def test_missing_block_fails_loud(tmp_path: Path) -> None:
    cfg = {"drivers": {"x": 10.0, "y": 5.0}}  # no interaction_grid block
    scenario = _write_scenario(tmp_path, cfg)
    with pytest.raises(ValueError, match="interaction_grid"):
        build_interaction_grid_for_scenario(scenario)


def test_missing_metric_fails_loud(tmp_path: Path) -> None:
    cfg = {k: v for k, v in _BASE_SCENARIO.items()}
    cfg["interaction_grid"] = {
        k: v for k, v in _BASE_SCENARIO["interaction_grid"].items() if k != "metric"
    }
    scenario = _write_scenario(tmp_path, cfg)
    with pytest.raises(ValueError, match="metric"):
        build_interaction_grid_for_scenario(scenario)


def test_missing_driver_fails_loud(tmp_path: Path) -> None:
    cfg = {k: v for k, v in _BASE_SCENARIO.items()}
    cfg["interaction_grid"] = {
        k: v for k, v in _BASE_SCENARIO["interaction_grid"].items() if k != "param_b"
    }
    scenario = _write_scenario(tmp_path, cfg)
    with pytest.raises(ValueError, match="param_b"):
        build_interaction_grid_for_scenario(scenario)


def test_driver_without_range_fails_loud(tmp_path: Path) -> None:
    cfg = {k: v for k, v in _BASE_SCENARIO.items()}
    cfg["interaction_grid"] = dict(_BASE_SCENARIO["interaction_grid"])
    cfg["interaction_grid"]["param_a"] = {
        "variable_name": "drivers.x",
        "base_value": 10.0,
    }  # no low/high → flat axis
    scenario = _write_scenario(tmp_path, cfg)
    with pytest.raises(ValueError, match="sweep range"):
        build_interaction_grid_for_scenario(scenario)


def test_driver_unknown_key_fails_loud(tmp_path: Path) -> None:
    cfg = {k: v for k, v in _BASE_SCENARIO.items()}
    cfg["interaction_grid"] = dict(_BASE_SCENARIO["interaction_grid"])
    cfg["interaction_grid"]["param_a"] = {
        "variable_name": "drivers.x",
        "base_value": 10.0,
        "low_percent": -10.0,  # typo of low_pct → must be rejected, not silently dropped
        "high_pct": 10.0,
    }
    scenario = _write_scenario(tmp_path, cfg)
    with pytest.raises(ValueError, match="unknown key"):
        build_interaction_grid_for_scenario(scenario)


def test_unresolvable_driver_fails_loud(tmp_path: Path) -> None:
    """A driver path absent from the config fails loud in strict mode (audit-R1, via the primitive)."""
    cfg = {k: v for k, v in _BASE_SCENARIO.items()}
    cfg["interaction_grid"] = dict(_BASE_SCENARIO["interaction_grid"])
    cfg["interaction_grid"]["param_a"] = {
        "variable_name": "drivers.does_not_exist",
        "base_value": 10.0,
        "low_pct": -10.0,
        "high_pct": 10.0,
    }
    scenario = _write_scenario(tmp_path, cfg)
    with pytest.raises(ValueError, match="does not resolve"):
        build_interaction_grid_for_scenario(scenario)


def test_sync_api_route_is_not_modified_by_this_slice() -> None:
    """Latency guard (#645): the interaction grid must never be reachable from the sync HTTP route.

    The N×M grid is a full-pipeline evaluation per cell; wiring it into ``app/api/main.py`` would
    reintroduce the latency the #645 ledger forbids. The Optional-default-None field on
    ReportContext is what keeps the sync route fast, so main.py must carry no reference to the grid.
    """
    main_src = (REPO_ROOT / "app" / "api" / "main.py").read_text(encoding="utf-8")
    assert "interaction_grid" not in main_src
    assert "interaction_grid_emit" not in main_src
