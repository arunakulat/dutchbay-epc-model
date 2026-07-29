"""Tests for the async job-domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.jobs.models import (
    TERMINAL_STATES,
    JobProgress,
    JobRecord,
    JobState,
    WindJobRequest,
    utc_now_iso,
)
from app.models.inputs import WindFarmInputs


def _inputs(**overrides: object) -> WindFarmInputs:
    base = dict(
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
    base.update(overrides)
    return WindFarmInputs(**base)


def _request(**overrides: object) -> WindJobRequest:
    base = dict(
        inputs=_inputs(),
        site_lat=8.33,
        site_lon=79.76,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        hub_height_m=119.0,
    )
    base.update(overrides)
    return WindJobRequest(**base)


def test_utc_now_iso_is_isoformat() -> None:
    stamp = utc_now_iso()
    assert "T" in stamp and stamp.endswith("+00:00")


def test_progress_pct_computed() -> None:
    p = JobProgress(step=1, total_steps=4, message="x")
    assert p.pct == 25.0
    assert "pct" in p.model_dump()  # computed field is serialised


def test_progress_zero_step() -> None:
    assert JobProgress(step=0, total_steps=4, message="queued").pct == 0.0


def _job_record() -> JobRecord:
    return JobRecord(
        job_id="j1",
        owner="u1",
        state=JobState.QUEUED,
        progress=JobProgress(step=0, total_steps=4, message="Queued"),
        created_at="t0",
        updated_at="t0",
    )


# --------------------------------------------------------------------------- #
# Frozen-contract semantics (#608): transitions construct anew via the stores
# --------------------------------------------------------------------------- #
def test_job_record_is_frozen() -> None:
    record = _job_record()
    with pytest.raises(ValidationError):
        record.state = JobState.RUNNING
    with pytest.raises(ValidationError):
        record.updated_at = "t1"


def test_job_record_model_copy_update_is_the_transition_path() -> None:
    # The store update path (model_copy(update=...)) must stay frozen-compatible.
    record = _job_record()
    updated = record.model_copy(update={"state": JobState.RUNNING, "updated_at": "t1"})
    assert updated.state is JobState.RUNNING and updated.updated_at == "t1"
    assert record.state is JobState.QUEUED  # the original is untouched


def test_job_record_json_round_trip_survives_frozen() -> None:
    # The Redis store round-trips records through JSON (incl. the computed
    # progress.pct field, tolerated by JobProgress's extra="ignore").
    record = _job_record()
    parsed = JobRecord.model_validate_json(record.model_dump_json())
    assert parsed == record


def test_terminal_states() -> None:
    assert JobState.SUCCEEDED in TERMINAL_STATES
    assert JobState.FAILED in TERMINAL_STATES
    assert JobState.RUNNING not in TERMINAL_STATES
    assert JobState.QUEUED not in TERMINAL_STATES


def test_request_site_location() -> None:
    loc = _request().site_location()
    assert loc == {"name": "Dutch Bay", "lat": 8.33, "lon": 79.76}


def test_request_to_finance_scenario_runs_mapping() -> None:
    scenario = _request().to_finance_scenario()
    assert isinstance(scenario, dict)
    assert scenario  # non-empty merged scenario


def test_request_defaults_and_validation() -> None:
    req = _request()
    assert req.p_level == "P75"
    assert req.start_date == "2014-12-01"
    with pytest.raises(ValueError):  # latitude out of range
        _request(site_lat=120.0)
    with pytest.raises(ValueError):  # unknown field rejected (extra=forbid)
        WindJobRequest(
            inputs=_inputs(),
            site_lat=8.0,
            site_lon=79.0,
            turbine_model="iea_reference_10mw",
            num_turbines=1,
            hub_height_m=100.0,
            bogus=1,
        )


def test_turbine_model_unknown_rejected_at_request_time() -> None:
    # CESSPIT strict (#965): an unknown turbine fails validation with an actionable
    # message listing the valid keys — a 422 on POST /jobs, not a mid-job KeyError.
    with pytest.raises(ValidationError) as excinfo:
        _request(turbine_model="IEA-10MW")
    msg = str(excinfo.value)
    assert "Unknown turbine_model" in msg
    assert "iea_reference_10mw" in msg  # valid keys are surfaced to the caller


def test_turbine_model_valid_accepted() -> None:
    # Each key defined in power_curves.yaml is accepted (single source of truth).
    from wind_resource.energy_calculator import available_turbine_models

    for model in available_turbine_models():
        assert _request(turbine_model=model).turbine_model == model


# --------------------------------------------------------------------------- #
# #993: resource_mode + Weibull screening params; #994: shear exponent
# --------------------------------------------------------------------------- #
def test_resource_mode_defaults_to_era5() -> None:
    req = _request()
    assert req.resource_mode == "era5"
    assert req.weibull_a is None and req.weibull_k is None
    assert req.shear_exponent is None


def test_weibull_mode_requires_a_and_k() -> None:
    # CESSPIT strict: a Weibull screening job must carry BOTH A and k, or fail with an
    # actionable 422 at request time — not a mid-job None flowing into the series builder.
    with pytest.raises(ValidationError) as ex_none:
        _request(resource_mode="weibull")
    assert "weibull_a" in str(ex_none.value) and "weibull_k" in str(ex_none.value)

    with pytest.raises(ValidationError) as ex_partial:  # k missing
        _request(resource_mode="weibull", weibull_a=8.2)
    assert "weibull_k" in str(ex_partial.value)

    req = _request(resource_mode="weibull", weibull_a=8.2, weibull_k=2.665)
    assert req.resource_mode == "weibull"
    assert req.weibull_a == 8.2 and req.weibull_k == 2.665


def test_weibull_params_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _request(resource_mode="weibull", weibull_a=0.0, weibull_k=2.0)
    with pytest.raises(ValidationError):
        _request(resource_mode="weibull", weibull_a=8.0, weibull_k=-1.0)


def test_shear_exponent_bounds() -> None:
    # #994: bounded to the engine's [alpha_min, alpha_max] = [0.05, 0.40] so an in-range
    # value is used verbatim (no silent clip).
    assert _request(shear_exponent=0.20).shear_exponent == 0.20
    assert _request(shear_exponent=0.05).shear_exponent == 0.05  # lower bound inclusive
    assert _request(shear_exponent=0.40).shear_exponent == 0.40  # upper bound inclusive
    with pytest.raises(ValidationError):
        _request(shear_exponent=0.04)  # below alpha_min
    with pytest.raises(ValidationError):
        _request(shear_exponent=0.45)  # above alpha_max
