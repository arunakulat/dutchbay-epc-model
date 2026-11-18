"""``POST /run-pipeline`` takes the USD opex FX drift step (#1578 next-20 item 4).

The route applies its own dotted overrides and calls the engine directly, so before
this change it never called ``with_usd_opex_fx_reference``. An FX drift override then
moved the model curve but left a USD opex share on its own authored path: the route
returned the pre-#1730 IRR (9.60% for ``fx.annual_depr: 0.03`` on the wind scenario,
against 9.50% through ``evaluate_with_overrides``).

The oracle is the Python override gateway, which already carries the step and its own
tests. The endpoint function is called directly, as in ``test_run_pipeline_endpoint``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml
from fastapi import HTTPException

from analytics.evaluation_v14 import evaluate_with_overrides
from api.pipeline_api import RunPipelineRequest, run_pipeline
from finance.cashflow_v14_params import USD_FX_DRIFT_OVERRIDE, USD_FX_REFERENCE

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"


def _api(overrides: Dict[str, Any]) -> Dict[str, Any]:
    resp = run_pipeline(RunPipelineRequest(config_path=str(WIND), overrides=overrides))
    return resp.kpis.model_dump()


@pytest.mark.parametrize(
    "overrides",
    [
        {"fx.annual_depr": 0.03},
        {"fx.annual_depr": 0.0},  # the authored drift is a stress too (2026-11-16)
        {"fx.start_lkr_per_usd": 360.0},  # spot only: the own path stays
        {"fx.start_lkr_per_usd": 360.0, "fx.annual_depr": 0.05},
        # a drift that starts in year 12: replaced from there only (2026-11-16 14:28Z)
        {"fx.curve": [333.79] * 11 + [333.79 * 1.05**k for k in range(1, 40)]},
    ],
    ids=["drift", "authored_drift", "spot_only", "spot_and_drift", "late_curve"],
)
def test_route_matches_the_override_gateway(overrides: Dict[str, Any]) -> None:
    gateway = evaluate_with_overrides(WIND, overrides)
    api = _api(overrides)
    for key in ("project_irr", "equity_irr"):
        assert api[key] == pytest.approx(gateway[key], abs=1e-12), key


def test_drift_override_moves_the_route_result() -> None:
    """Responsiveness: a 3%/yr drift lowers project IRR below the base over the route."""
    assert _api({"fx.annual_depr": 0.03})["project_irr"] < _api({})["project_irr"]


def test_route_refuses_a_drift_stress_the_curve_does_not_read() -> None:
    with pytest.raises(HTTPException) as err:
        _api({"fx.annual_depr_pct": 3.0})
    assert err.value.status_code == 422
    assert "fx.annual_depr_pct" in str(err.value.detail)


@pytest.mark.parametrize(
    "key, value",
    [(USD_FX_REFERENCE, {"start_lkr_per_usd": 300.0}), (USD_FX_DRIFT_OVERRIDE, True)],
)
def test_route_refuses_an_authored_gateway_key(key: str, value: Any) -> None:
    """Neither an inline config nor a dotted override may set the gateway's keys."""
    cfg = yaml.safe_load(WIND.read_text())
    cfg["opex"]["currency_split"][key] = value
    with pytest.raises(HTTPException) as err:
        run_pipeline(RunPipelineRequest(config=cfg))
    assert err.value.status_code == 422
    assert f"opex.currency_split.{key}" in str(err.value.detail)

    with pytest.raises(HTTPException) as err:
        _api({f"opex.currency_split.{key}": value})
    assert err.value.status_code == 422
    assert f"opex.currency_split.{key}" in str(err.value.detail)
