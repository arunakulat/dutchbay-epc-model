"""A bare ``capex`` Monte Carlo parameter is refused on a full scenario (#1793).

On a scenario with a capex section, the name overrides the whole section with one number,
which every trial refuses (#1767). It is refused before sampling, in any case or padding.
The minimal smoke config, which has no capex section, keeps the name for its toy metric.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine

ROOT = Path(__file__).resolve().parents[2]
USD_SCENARIO = ROOT / "scenarios/dutchbay_lendercase_2025Q4.yaml"


def _usd_with(param: dict[str, Any]) -> dict[str, Any]:
    cfg = yaml.safe_load(USD_SCENARIO.read_text(encoding="utf-8"))
    cfg["monte_carlo"]["parameters"] = [param]
    cfg["monte_carlo"].pop("correlation", None)
    return cfg


@pytest.mark.parametrize("name", ["capex", "CAPEX", " capex ", "Capex"])
def test_bare_capex_is_refused_before_any_trial(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import analytics.mc.engine as engine_module

    def _no_trial(*_a: Any, **_k: Any) -> None:
        raise AssertionError("a trial ran")

    monkeypatch.setattr(engine_module, "evaluate_with_overrides", _no_trial)
    with pytest.raises(
        MonteCarloConfigError, match=r"refused before sampling \(#1793\)"
    ) as err:
        MonteCarloEngine(_usd_with({"name": name, "low": 1.0, "high": 2.0}))
    assert repr(name) in str(err.value)
    assert "capex.usd_total" in str(err.value)


def test_a_capex_section_in_another_spelling_counts_as_full() -> None:
    cfg = _usd_with({"name": "capex", "low": 1.0, "high": 2.0})
    cfg["CAPEX"] = cfg.pop("capex")
    with pytest.raises(MonteCarloConfigError, match="#1793"):
        MonteCarloEngine._refuse_bare_capex_on_full_scenario(cfg, ["capex"])


def test_capex_usd_total_is_still_accepted() -> None:
    cfg = yaml.safe_load(USD_SCENARIO.read_text(encoding="utf-8"))
    base = float(cfg["capex"]["usd_total"])
    MonteCarloEngine(
        _usd_with({"name": "capex.usd_total", "low": base * 0.9, "high": base * 1.1})
    )


def test_the_smoke_config_keeps_its_capex_name() -> None:
    from analytics.mc.engine import run_monte_carlo_analysis

    smoke = {
        "scenario_name": "smoke",
        "monte_carlo": {
            "allow_toy_fallback": True,
            "parameters": [
                {"name": "capex", "low": 100.0, "high": 120.0},
                {"name": "tariff", "low": 0.08, "high": 0.12},
            ],
        },
    }
    result = run_monte_carlo_analysis(base_config=smoke, n_trials=8, seed=1)
    assert result.metadata["n_trials"] == 8


def test_the_emitter_plan_lists_the_refusal() -> None:
    from analytics.emit_selection import _needs_monte_carlo_parameters

    reason = _needs_monte_carlo_parameters(
        _usd_with({"name": "capex", "low": 1.0, "high": 2.0}), cfg=None
    )
    assert reason is not None and "#1793" in reason
