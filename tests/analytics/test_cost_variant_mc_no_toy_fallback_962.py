"""The two lender-case cost variants run their Monte Carlo with the toy fallback off (#962).

Owner ruling on #962 item 1, extended on 2026-11-16 to the EIA-prudent and the
contractor-lean CAPEX variants of the lender case: a trial whose full v14 evaluation
raises stops the run instead of reporting fabricated KPIs. #1721 did the same for the
lender case, the 5 US-cent variant and Kalpitiya. A healthy run is unchanged, because
no trial falls back. Offline: committed scenarios only. No figure is asserted.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, cast

import pytest
import yaml

import analytics.mc.engine as mc_engine
from analytics.mc.engine import run_monte_carlo_analysis

_SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
_VARIANTS = (
    "dutchbay_capex_eia_prudent_2025Q4.yaml",
    "dutchbay_capex_sinohydro_lean_2025Q4.yaml",
)


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _load(name: str) -> Dict[str, Any]:
    cfg = yaml.safe_load((_SCENARIOS / name).read_text(encoding="utf-8"))
    assert isinstance(cfg, dict)
    return cast(Dict[str, Any], copy.deepcopy(cfg))


@pytest.mark.parametrize("name", _VARIANTS)
def test_cost_variant_declares_the_fallback_off(name: str) -> None:
    assert _load(name)["monte_carlo"]["allow_toy_fallback"] is False


@pytest.mark.parametrize("name", _VARIANTS)
def test_healthy_cost_variant_run_reports_the_fallback_off_and_unused(
    name: str,
) -> None:
    result = run_monte_carlo_analysis(base_config=_load(name), n_trials=4, seed=42)
    assert result.metadata["allow_toy_fallback"] is False
    assert result.metadata["toy_fallback_count"] == 0
    assert result.failed_iterations == 0


@pytest.mark.parametrize("name", _VARIANTS)
def test_a_failed_cost_variant_trial_stops_the_run(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: with the fallback on, this run substitutes a toy trial."""

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated trial failure")

    monkeypatch.setattr(mc_engine, "evaluate_with_overrides", _boom)
    with pytest.raises(RuntimeError, match="toy-metric fallback is disabled"):
        run_monte_carlo_analysis(base_config=_load(name), n_trials=2, seed=42)
