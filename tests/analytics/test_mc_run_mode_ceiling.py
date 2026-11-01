"""MC trials must obey the pre-existing run-mode permission ceiling (#962)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.mc.engine import run_monte_carlo_analysis


def _broken_config(mode_key: str, mode: str | None) -> dict[str, Any]:
    """Use a valid sampled driver with a deliberately incomplete finance config."""
    config: dict[str, Any] = {
        "capex": {"usd_total": 100.0},
        "monte_carlo": {
            "parameters": [{"name": "capex.usd_total", "low": 80.0, "high": 120.0}]
        },
    }
    if mode_key == "run":
        config[mode_key] = {"mode": mode}
    elif mode_key:
        config[mode_key] = mode
    return config


@pytest.mark.parametrize("mode_key", ["run", "run_mode"])
@pytest.mark.parametrize("mode", ["lender", "ic"])
@pytest.mark.parametrize("fallback", [None, False, True])
def test_decision_modes_never_substitute_toy_kpis(
    mode_key: str, mode: str, fallback: bool | None
) -> None:
    config = _broken_config(mode_key, mode)
    if fallback is not None:
        config["monte_carlo"]["allow_toy_fallback"] = fallback
    original = deepcopy(config)
    with pytest.raises(RuntimeError, match="toy-metric fallback is disabled"):
        run_monte_carlo_analysis(base_config=config, n_trials=2, seed=1)
    assert config == original


@pytest.mark.parametrize("mode", ["screening", "developer", None])
@pytest.mark.parametrize("fallback", [None, False, True])
def test_permissive_modes_preserve_the_explicit_engine_setting(
    mode: str | None, fallback: bool | None
) -> None:
    config = _broken_config("run" if mode else "", mode)
    if fallback is not None:
        config["monte_carlo"]["allow_toy_fallback"] = fallback
    if fallback is False:
        with pytest.raises(RuntimeError, match="toy-metric fallback is disabled"):
            run_monte_carlo_analysis(base_config=config, n_trials=2, seed=1)
    else:
        result = run_monte_carlo_analysis(base_config=config, n_trials=2, seed=1)
        assert result.metadata["toy_fallback_count"] == 2
        assert result.metadata["allow_toy_fallback"] is True


@pytest.mark.parametrize(
    "declaration",
    [
        {"run": {"mdoe": "lender"}},
        {"run": {"mode": "bankable"}},
        {"run": {"mode": "lender"}, "run_mode": "developer"},
    ],
)
def test_bad_declaration_is_not_swallowed_by_the_toy_fallback(
    declaration: dict[str, Any],
) -> None:
    config = {**_broken_config("", None), **declaration}
    with pytest.raises(ValueError):
        run_monte_carlo_analysis(base_config=config, n_trials=2, seed=1)


def test_healthy_seeded_metrics_do_not_change_when_lender_mode_is_declared() -> None:
    scenario = (
        Path(__file__).resolve().parents[2]
        / "scenarios/dutchbay_lendercase_2025Q4.yaml"
    )
    config = yaml.safe_load(scenario.read_text(encoding="utf-8"))
    base = run_monte_carlo_analysis(base_config=config, n_trials=4, seed=42)
    lender = run_monte_carlo_analysis(
        base_config={**config, "run": {"mode": "lender"}}, n_trials=4, seed=42
    )
    assert lender.summary == base.summary
    assert lender.failed_iterations == base.failed_iterations == 0
    assert (
        lender.metadata["toy_fallback_count"]
        == base.metadata["toy_fallback_count"]
        == 0
    )
    assert lender.metadata["allow_toy_fallback"] is False
