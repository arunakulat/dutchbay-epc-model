"""Tests for the async ANALYSIS-job request model (#993 PR-B1/PR-B2).

The request boundary is fail-loud (CESSPIT): it rejects a non-deterministic resource
basis and a scenario variant whose resolved config has no list-form MC drivers, so a bad
MC submission returns 422 on POST rather than failing opaquely mid-job. Tornado builds
its own canonical driver set and does not inherit the MC-only parameter constraint.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
from pydantic import ValidationError

from app.jobs.models import AnalysisJobRequest, WindJobRequest
from app.models.inputs import ScenarioVariant, WindFarmInputs


def _inputs(variant: ScenarioVariant = "lendercase") -> WindFarmInputs:
    return WindFarmInputs(
        scenario_variant=variant,
        site_name="Dutch Bay",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )


def _wind(
    *,
    variant: ScenarioVariant = "lendercase",
    resource_mode: str = "weibull",
    weibull_a: Optional[float] = 8.199,
    weibull_k: Optional[float] = 2.665,
) -> WindJobRequest:
    return WindJobRequest(
        inputs=_inputs(variant),
        site_lat=8.33,
        site_lon=79.76,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        hub_height_m=119.0,
        resource_mode=resource_mode,  # type: ignore[arg-type]
        weibull_a=weibull_a,
        weibull_k=weibull_k,
    )


def _mc_request(**overrides: Any) -> AnalysisJobRequest:
    kwargs: dict[str, Any] = {"analysis_type": "mc", "wind": _wind()}
    kwargs.update(overrides)
    return AnalysisJobRequest(**kwargs)


def test_valid_mc_request_constructs() -> None:
    req = _mc_request(n_trials=500, seed=7, metric="equity_irr")
    assert req.analysis_type == "mc"
    assert req.metric == "equity_irr"
    assert req.n_trials == 500 and req.seed == 7
    assert req.wind.resource_mode == "weibull"
    assert req.wind.inputs.scenario_variant == "lendercase"


def test_metric_defaults_to_project_irr() -> None:
    assert _mc_request().metric == "project_irr"


def test_rejects_era5_resource_mode() -> None:
    """A live-ERA5 basis is minutes-long and unbounded — rejected at the boundary."""
    with pytest.raises(ValidationError) as exc:
        _mc_request(wind=_wind(resource_mode="era5", weibull_a=None, weibull_k=None))
    assert "weibull" in str(exc.value)


def test_rejects_basecase_no_list_form_mc_parameters() -> None:
    """basecase pins a legacy DICT-form monte_carlo.parameters the MC engine rejects."""
    with pytest.raises(ValidationError) as exc:
        _mc_request(wind=_wind(variant="basecase"))
    msg = str(exc.value)
    assert "monte_carlo.parameters" in msg and "lendercase" in msg


def test_rejects_equitycase_no_list_form_mc_parameters() -> None:
    with pytest.raises(ValidationError):
        _mc_request(wind=_wind(variant="equitycase"))


def test_n_trials_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        _mc_request(n_trials=100)  # below the 200 floor
    with pytest.raises(ValidationError):
        _mc_request(n_trials=50_000)  # above the 20000 ceiling
    assert _mc_request(n_trials=200).n_trials == 200
    assert _mc_request(n_trials=20_000).n_trials == 20_000


def test_analysis_type_is_required_and_rejects_unsupported_family() -> None:
    with pytest.raises(ValidationError):
        AnalysisJobRequest(wind=_wind())  # type: ignore[call-arg]
    assert (
        AnalysisJobRequest(analysis_type="tornado", wind=_wind()).analysis_type
        == "tornado"
    )
    with pytest.raises(ValidationError):
        AnalysisJobRequest(analysis_type="morris", wind=_wind())  # type: ignore[arg-type]


def test_invalid_metric_rejected() -> None:
    with pytest.raises(ValidationError):
        _mc_request(metric="min_dscr")  # not in the B1 metric set


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        _mc_request(correlation=True)  # extra="forbid"


def test_embedded_wind_validators_are_reused() -> None:
    """Embedding WindJobRequest reuses its strict validators: a weibull request missing
    A/k fails inside the nested model (built from a dict)."""
    with pytest.raises(ValidationError):
        AnalysisJobRequest(
            analysis_type="mc",
            wind={
                "inputs": _inputs(),
                "site_lat": 8.33,
                "site_lon": 79.76,
                "turbine_model": "iea_reference_10mw",
                "num_turbines": 15,
                "hub_height_m": 119.0,
                "resource_mode": "weibull",
                # weibull_a / weibull_k omitted -> nested WindJobRequest rejects
            },
        )


# --------------------------------------------------------------------------- #
# _require_runnable_mc_parameters branch coverage — the resolved scenario is
# monkeypatched so each malformation is exercised independently of the committed
# variants (which cannot produce empty-list / absent / alt-key shapes).
# --------------------------------------------------------------------------- #
def test_rejects_empty_list_mc_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty parameters list is rejected up-front (would otherwise trip the engine's
    'no parameters' MonteCarloConfigError mid-job)."""
    monkeypatch.setattr(
        WindJobRequest,
        "to_finance_scenario",
        lambda self: {"monte_carlo": {"parameters": []}},
    )
    with pytest.raises(ValidationError) as exc:
        _mc_request()
    assert "monte_carlo.parameters" in str(exc.value)


def test_rejects_absent_monte_carlo_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scenario with no monte_carlo block at all is rejected up-front."""
    monkeypatch.setattr(
        WindJobRequest, "to_finance_scenario", lambda self: {"project": {}}
    )
    with pytest.raises(ValidationError):
        _mc_request()


def test_accepts_list_form_params_alt_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine reads `monte_carlo.parameters` OR the legacy `params` key; a list-form
    `params` block is a valid driver set and must be ACCEPTED (not rejected)."""
    monkeypatch.setattr(
        WindJobRequest,
        "to_finance_scenario",
        lambda self: {
            "monte_carlo": {
                "params": [{"name": "capex.usd_total", "low": 1.0, "high": 2.0}]
            }
        },
    )
    req = _mc_request()  # must not raise
    assert req.analysis_type == "mc"


def test_tornado_does_not_require_monte_carlo_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR-B2 builds canonical one-way drivers, so an absent MC block is irrelevant."""
    monkeypatch.setattr(
        WindJobRequest, "to_finance_scenario", lambda self: {"project": {}}
    )
    req = AnalysisJobRequest(analysis_type="tornado", wind=_wind())
    assert req.analysis_type == "tornado"
