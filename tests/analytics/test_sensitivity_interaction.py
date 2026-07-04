"""Two-factor interaction grid (#739) — engine tests.

Two layers:
- Pure-math layer: the evaluation gateway is monkeypatched with a deterministic
  closed-form metric so the interaction arithmetic is pinned EXACTLY (an
  additive metric must produce an all-zero interaction surface; a multiplicative
  one must produce the analytically derived corner term).
- Integration layer: one real lendercase grid (3x3 + base = 10 evaluations)
  proving the wiring end-to-end against the committed scenario.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

import pytest

import analytics.sensitivity.interaction as interaction_mod
from analytics.contracts_v14 import ParameterRangeConfig, TwoFactorInteractionGrid
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity.engine import SensitivityRunConfig
from analytics.sensitivity.interaction import build_two_factor_interaction_grid

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Synthetic config: two independent scalar drivers the fake gateway reads.
_BASE_CFG: Dict[str, Any] = {"drivers": {"x": 10.0, "y": 5.0}}


def _param(name: str, base: float) -> ParameterRangeConfig:
    return ParameterRangeConfig(
        variable_name=name, base_value=base, low_pct=-10.0, high_pct=10.0, label=name
    )


def _fake_gateway(
    metric_fn: Callable[[float, float], float],
) -> Callable[..., Dict[str, Any]]:
    """Build an evaluate_with_overrides stand-in computing metric_fn(x, y)."""

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


def test_additive_metric_zero_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """m = 2x + 3y is exactly additive -> interaction surface all-zero."""
    monkeypatch.setattr(
        interaction_mod,
        "evaluate_with_overrides",
        _fake_gateway(lambda x, y: 2.0 * x + 3.0 * y),
    )
    grid = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.x", 10.0),
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
    )
    assert isinstance(grid, TwoFactorInteractionGrid)
    assert grid.base_metric == pytest.approx(2.0 * 10.0 + 3.0 * 5.0)
    for row in grid.interaction:
        for term in row:
            assert term == pytest.approx(0.0, abs=1e-12)
    assert grid.max_abs_interaction == pytest.approx(0.0, abs=1e-12)
    assert grid.metadata["n_failed_cells"] == 0
    assert grid.metadata["base_mismatch"] is False


def test_multiplicative_metric_exact_corner_interaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """m = x*y: interaction(a,b) = (xa-x0)*(yb-y0), derived analytically.

    For the +/-10% sweep on x0=10, y0=5: dx = +/-1, dy = +/-0.5, so every
    non-marginal corner must equal dx*dy = +/-0.5 exactly.
    """
    monkeypatch.setattr(
        interaction_mod, "evaluate_with_overrides", _fake_gateway(lambda x, y: x * y)
    )
    grid = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.x", 10.0),
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
    )
    # Labels order is (base, low, high) — derive index positions from labels.
    a_low = grid.a_labels.index("drivers.x=low")
    a_high = grid.a_labels.index("drivers.x=high")
    b_low = grid.b_labels.index("drivers.y=low")
    b_high = grid.b_labels.index("drivers.y=high")
    assert grid.interaction[a_low][b_low] == pytest.approx((-1.0) * (-0.5))
    assert grid.interaction[a_low][b_high] == pytest.approx((-1.0) * (+0.5))
    assert grid.interaction[a_high][b_low] == pytest.approx((+1.0) * (-0.5))
    assert grid.interaction[a_high][b_high] == pytest.approx((+1.0) * (+0.5))
    # Marginal row/column (base axis) interaction is identically zero.
    for ib in range(len(grid.b_labels)):
        assert grid.interaction[0][ib] == pytest.approx(0.0, abs=1e-12)
    for ia in range(len(grid.a_labels)):
        assert grid.interaction[ia][0] == pytest.approx(0.0, abs=1e-12)
    assert grid.max_abs_interaction == pytest.approx(0.5)


def test_same_driver_rejected() -> None:
    with pytest.raises(ValueError, match="two DISTINCT drivers"):
        build_two_factor_interaction_grid(
            base_config=_BASE_CFG,
            param_a=_param("drivers.x", 10.0),
            param_b=_param("drivers.x", 10.0),
            metric_key="metric",
        )


def test_unresolvable_driver_raises_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        interaction_mod, "evaluate_with_overrides", _fake_gateway(lambda x, y: x + y)
    )
    with pytest.raises(ValueError, match="does not resolve"):
        build_two_factor_interaction_grid(
            base_config=_BASE_CFG,
            param_a=_param("drivers.nope", 1.0),
            param_b=_param("drivers.y", 5.0),
            metric_key="metric",
        )


def test_interior_cell_failure_is_nan_and_disclosed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing interior joint cell -> NaN + n_failed_cells, marginals loud."""

    def metric(x: float, y: float) -> float:
        return x + y

    real = _fake_gateway(metric)

    def _eval(**kwargs: Any) -> Dict[str, Any]:
        ov = dict(kwargs.get("overrides") or {})
        # Fail ONLY the joint low/low corner (both keys overridden off-base).
        if ov.get("drivers.x") == pytest.approx(9.0) and ov.get(
            "drivers.y"
        ) == pytest.approx(4.5):
            return {"kpis": {}}  # metric missing -> KeyError inside extraction
        return real(**kwargs)

    monkeypatch.setattr(interaction_mod, "evaluate_with_overrides", _eval)
    grid = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.x", 10.0),
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
    )
    a_low = grid.a_labels.index("drivers.x=low")
    b_low = grid.b_labels.index("drivers.y=low")
    assert math.isnan(grid.values[a_low][b_low])
    assert math.isnan(grid.interaction[a_low][b_low])
    assert grid.metadata["n_failed_cells"] == 1
    # NaN cells must not poison the headline.
    assert not math.isnan(grid.max_abs_interaction)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_valued_base_fails_loud(
    monkeypatch: pytest.MonkeyPatch, bad: float
) -> None:
    """A metric that EVALUATES to NaN/inf on the base case raises (review finding 1).

    Without the guard, an all-NaN base yields n_failed_cells=0 and
    max_abs_interaction=0.0 — reading as "no interaction, nothing failed";
    an all-inf base reproduces the same quiet shape via inf-inf = NaN.
    """
    monkeypatch.setattr(
        interaction_mod,
        "evaluate_with_overrides",
        _fake_gateway(lambda x, y: bad),
    )
    with pytest.raises(ValueError, match="non-finite .* on the base case"):
        build_two_factor_interaction_grid(
            base_config=_BASE_CFG,
            param_a=_param("drivers.x", 10.0),
            param_b=_param("drivers.y", 5.0),
            metric_key="metric",
        )


def test_nan_valued_marginal_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    """A NaN-VALUED metric on a marginal (edge) cell raises like a missing one."""

    def metric(x: float, y: float) -> float:
        # NaN only on the a=low marginal (x shocked, y at base).
        if x == pytest.approx(9.0) and y == pytest.approx(5.0):
            return float("nan")
        return x + y

    monkeypatch.setattr(
        interaction_mod, "evaluate_with_overrides", _fake_gateway(metric)
    )
    with pytest.raises(ValueError, match="marginal cell"):
        build_two_factor_interaction_grid(
            base_config=_BASE_CFG,
            param_a=_param("drivers.x", 10.0),
            param_b=_param("drivers.y", 5.0),
            metric_key="metric",
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_valued_interior_cell_counted(
    monkeypatch: pytest.MonkeyPatch, bad: float
) -> None:
    """A NaN/inf-VALUED interior cell is disclosed exactly like a missing one.

    inf is normalised to NaN in the stored surface (uniform failure
    representation) so the headline can never be poisoned to inf.
    """

    def metric(x: float, y: float) -> float:
        # Non-finite only on the joint low/low corner (both drivers off-base).
        if x == pytest.approx(9.0) and y == pytest.approx(4.5):
            return bad
        return x + y

    monkeypatch.setattr(
        interaction_mod, "evaluate_with_overrides", _fake_gateway(metric)
    )
    grid = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.x", 10.0),
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
    )
    a_low = grid.a_labels.index("drivers.x=low")
    b_low = grid.b_labels.index("drivers.y=low")
    assert math.isnan(grid.values[a_low][b_low])
    assert grid.metadata["n_failed_cells"] == 1
    assert math.isfinite(grid.max_abs_interaction)


def test_nonstrict_unresolved_driver_disclosed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-strict + unresolvable driver: the flat axis is DISCLOSED in metadata."""
    monkeypatch.setattr(
        interaction_mod, "evaluate_with_overrides", _fake_gateway(lambda x, y: x + y)
    )
    grid = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.nope", 1.0),
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
        run_cfg=SensitivityRunConfig(strict=False),
    )
    assert grid.metadata["unresolved_drivers"] == ["drivers.nope"]
    # Strict runs carry the empty list (disclosure key always present).
    grid_ok = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.x", 10.0),
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
    )
    assert grid_ok.metadata["unresolved_drivers"] == []


def test_declared_base_drift_disclosed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A declared base_value that drifted from the config is disclosed."""
    monkeypatch.setattr(
        interaction_mod, "evaluate_with_overrides", _fake_gateway(lambda x, y: x + y)
    )
    grid = build_two_factor_interaction_grid(
        base_config=_BASE_CFG,
        param_a=_param("drivers.x", 12.0),  # config says 10.0
        param_b=_param("drivers.y", 5.0),
        metric_key="metric",
    )
    assert grid.metadata["base_mismatch"] is True


def test_lendercase_integration_grid() -> None:
    """End-to-end: a real 3x3 grid on the committed lender case.

    Declared bases match the committed scenario exactly (project.capacity_factor
    0.332, capex.usd_total 159.6e6), so the declared-base cell must agree with
    the evaluated true base (no base_mismatch) and the whole surface be finite.
    """
    cfg = load_scenario_config(LENDER)
    grid = build_two_factor_interaction_grid(
        base_config=cfg,
        base_config_path=LENDER,
        param_a=_param("project.capacity_factor", 0.332),
        param_b=_param("capex.usd_total", 159_600_000.0),
        metric_key="project_irr",
        run_cfg=SensitivityRunConfig(strict=True),
    )
    assert len(grid.values) == 3 and len(grid.values[0]) == 3
    assert grid.metadata["n_evaluations"] == 10
    assert grid.metadata["n_failed_cells"] == 0
    assert grid.metadata["base_mismatch"] is False
    for row in grid.values:
        for v in row:
            assert math.isfinite(v)
    # Sanity on direction: higher CF at base capex must not LOWER the IRR.
    a_low = grid.a_labels.index("project.capacity_factor=low")
    a_high = grid.a_labels.index("project.capacity_factor=high")
    assert grid.values[a_high][0] >= grid.values[a_low][0]
