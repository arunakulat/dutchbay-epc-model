"""Job-domain models for the asynchronous live-ERA5 finance path.

The slow path (download ERA5 → Weibull → AEP → finance) runs minutes, so the
wizard submits a job and polls for progress rather than blocking a request. These
models describe a job's request, lifecycle state, and progress. No finance logic
(Dolphin) — the request just carries inputs and reuses ``WindFarmInputs`` for the
finance side; the orchestration lives in :mod:`app.jobs.runner`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models.inputs import WindFarmInputs


def utc_now_iso() -> str:
    """Return the current UTC time as a second-precision ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobState(str, Enum):
    """Lifecycle state of an async job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


#: States from which a job will not transition further.
TERMINAL_STATES = frozenset({JobState.SUCCEEDED, JobState.FAILED})


class JobProgress(BaseModel):
    """A coarse progress marker for a running job.

    ``extra="ignore"`` (not ``forbid``) so the model round-trips through JSON: the
    computed ``pct`` field is emitted by ``model_dump_json`` and must be tolerated
    (ignored) on re-parse by the Redis store. This is an internal state model, not
    a user-input surface.
    """

    model_config = ConfigDict(extra="ignore")

    step: int = Field(..., ge=0, description="Completed step index (0 = not started).")
    total_steps: int = Field(..., gt=0, description="Total steps in the job.")
    message: str = Field(..., description="Human-readable current activity.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pct(self) -> float:
        """Completion percentage (0–100), one decimal."""
        return round(100.0 * self.step / self.total_steps, 1)


class JobRecord(BaseModel):
    """The full, serialisable state of one async job.

    Frozen (#608, the analytics/core frozen-contract pattern): every lifecycle
    transition goes through a store's ``update()`` — which constructs anew via
    ``model_copy(update=...)`` and stamps ``updated_at`` — so in-place attribute
    assignment on a fetched record is a bug (it would silently skip the stamp
    and, on the Redis store, never persist) and now raises.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    owner: str = Field(
        ...,
        description="Authenticated subject that owns this job (per-client isolation).",
    )
    state: JobState
    progress: JobProgress
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="On success, the job's result dict — a CaseResult for a wind "
        "finance job, or an AnalysisResult envelope for an analysis job (#993 PR-B).",
    )
    error: Optional[str] = Field(default=None, description="Error string on failure.")
    created_at: str
    updated_at: str


class WindJobRequest(BaseModel):
    """An async live-ERA5 job submission.

    Reuses :class:`~app.models.inputs.WindFarmInputs` for the finance side
    (Dolphin) and adds the ERA5/site fields the wind pipeline needs to recompute
    AEP from scratch. Date defaults match the canonical ERA5 window and are
    overridable (CCCDIR — documented defaults, not buried constants).
    """

    model_config = ConfigDict(extra="forbid")

    inputs: WindFarmInputs
    site_lat: float = Field(..., ge=-90.0, le=90.0)
    site_lon: float = Field(..., ge=-180.0, le=180.0)
    turbine_model: str = Field(..., min_length=1, description="power_curves.yaml name.")
    num_turbines: int = Field(..., gt=0)
    hub_height_m: float = Field(..., gt=0.0)
    start_date: str = Field(default="2014-12-01", description="ERA5 window start.")
    end_date: str = Field(default="2025-12-31", description="ERA5 window end.")
    p_level: Literal["P50", "P75", "P90"] = "P75"

    #: Wind-resource basis. ``era5`` fetches a live single-cell ERA5 timeseries;
    #: ``weibull`` builds a DETERMINISTIC screening assessment from a supplied
    #: hub-height Weibull A/k with NO network fetch (#993). Documented default (CCCDIR).
    resource_mode: Literal["era5", "weibull"] = Field(
        default="era5",
        description="'era5' (live single-cell ERA5) or 'weibull' (deterministic "
        "screening from a supplied hub-height Weibull A/k, no fetch).",
    )
    weibull_a: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Weibull scale A (m/s) AT HUB HEIGHT; required when "
        "resource_mode='weibull'.",
    )
    weibull_k: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Weibull shape k; required when resource_mode='weibull'.",
    )
    shear_exponent: Optional[float] = Field(
        default=None,
        ge=0.05,
        le=0.40,
        description="Power-law shear exponent alpha for the ERA5 100m->hub "
        "extrapolation (era5 mode only). None uses the ERA5-derived per-hour alpha; "
        "a value overrides it for every hour. Bounded to the engine's "
        "[alpha_min, alpha_max]=[0.05, 0.40] so an in-range value is used verbatim.",
    )

    @field_validator("turbine_model")
    @classmethod
    def _validate_turbine_model(cls, v: str) -> str:
        """CESSPIT strict: reject an unknown turbine at request time (#965).

        Validates against the live ``power_curves.yaml`` keys (single source of truth
        via ``wind_resource.energy_calculator.available_turbine_models``) so a bad name
        fails on POST /jobs with an actionable 422 listing the valid models — not
        mid-job with a deep ``KeyError`` inside the energy calculator. The import is
        lazy so importing this module stays light (the energy calculator pulls scipy
        at import) and the API surface never drags the optional ``[wind]`` toolchain.
        """
        from wind_resource.energy_calculator import available_turbine_models

        valid = available_turbine_models()
        if v not in valid:
            raise ValueError(f"Unknown turbine_model {v!r}; valid: {sorted(valid)}")
        return v

    @model_validator(mode="after")
    def _require_weibull_params(self) -> "WindJobRequest":
        """CESSPIT strict: a Weibull screening job must carry BOTH A and k.

        Fails at request time with an actionable 422 (not mid-job with an opaque
        ``None`` flowing into the series builder) when ``resource_mode='weibull'``
        omits either scale or shape.
        """
        if self.resource_mode == "weibull":
            missing = [
                name
                for name, val in (
                    ("weibull_a", self.weibull_a),
                    ("weibull_k", self.weibull_k),
                )
                if val is None
            ]
            if missing:
                raise ValueError(
                    f"resource_mode='weibull' requires {', '.join(missing)}; "
                    "provide weibull_a (m/s, at hub height) and weibull_k."
                )
        return self

    def site_location(self) -> Dict[str, Any]:
        """Build the ``{name, lat, lon}`` dict the wind pipeline requires."""
        return {
            "name": self.inputs.site_name,
            "lat": self.site_lat,
            "lon": self.site_lon,
        }

    def to_finance_scenario(self) -> Dict[str, Any]:
        """Map the embedded finance inputs to a full v14 scenario dict."""
        return self.inputs.to_scenario_config()


#: Analysis types whose engine consumes ``monte_carlo.parameters`` (a list of
#: ``{name, low, high}`` driver mappings). For these, the resolved scenario must
#: carry a non-empty LIST-form block or the engine raises mid-job — so we reject at
#: the request boundary instead (CESSPIT). ``tornado`` (PR-B2) builds its own driver
#: set and is intentionally absent; ``morris`` (PR-B3) will be added here.
_ANALYSIS_TYPES_REQUIRING_MC_PARAMS: frozenset[str] = frozenset({"mc"})


class AnalysisJobRequest(BaseModel):
    """An async ANALYSIS-job submission: run a bounded MC / sensitivity / global-SA
    engine over the freshly-assessed screening case (#993 PR-B).

    Embeds a :class:`WindJobRequest` (Dolphin — reuses its strict validators and the
    ERA5/Weibull assessment seam) and adds the analysis knobs. The analysis runs on
    the ACTIVE assessed case (the live capacity factor, not the stale form input —
    #993); to keep that recompute deterministic, network-free, and bounded, the
    embedded wind request must use ``resource_mode='weibull'`` (a live ERA5 fetch is
    minutes-long and unbounded — not an "analysis" workload). Unknown fields are
    rejected (CESSPIT).
    """

    model_config = ConfigDict(extra="forbid")

    analysis_type: Literal["mc"] = Field(
        ...,
        description="The analysis to run. PR-B1 supports 'mc' (bounded Monte Carlo); "
        "'tornado' and 'morris' follow in PR-B2/PR-B3.",
    )
    metric: Literal["project_irr", "equity_irr", "project_npv"] = Field(
        default="project_irr",
        description="Focal metric the analysis targets. For MC this labels the result "
        "(the engine computes all metrics); for the sensitivity families it selects the "
        "swept metric.",
    )
    wind: WindJobRequest = Field(
        ...,
        description="The embedded wind job carrying the finance inputs, site, turbine, "
        "and (weibull) resource basis used to recompute the assessed case.",
    )
    n_trials: int = Field(
        default=2000,
        ge=200,
        le=20000,
        description="Monte Carlo trial count (mc only). Bounded so the job cannot run "
        "unboundedly long; the lender-grade floor (1000) is a report-layer policy, not "
        "an engine limit.",
    )
    seed: int = Field(
        default=123,
        ge=0,
        description="Deterministic RNG seed for reproducible MC draws (MRM-01).",
    )

    @model_validator(mode="after")
    def _require_bounded_deterministic_resource(self) -> "AnalysisJobRequest":
        """CESSPIT strict: an analysis job must use the deterministic Weibull basis.

        A live ERA5 fetch is minutes-long and network-bound — fine for a one-shot
        assessment, but pairing it with a fan-out sweep is an unbounded workload. Fail
        loud at the boundary with an actionable 422 rather than silently flipping the
        client's chosen mode (no silent defaults).
        """
        if self.wind.resource_mode != "weibull":
            raise ValueError(
                "analysis jobs require wind.resource_mode='weibull' (a deterministic, "
                "network-free screening basis so the assessed-case recompute is bounded); "
                f"got {self.wind.resource_mode!r}. Supply wind.weibull_a and "
                "wind.weibull_k. Live-ERA5 analysis is not supported on this route."
            )
        return self

    @model_validator(mode="after")
    def _require_runnable_mc_parameters(self) -> "AnalysisJobRequest":
        """CESSPIT strict: reject a variant whose resolved scenario has no MC drivers.

        The MC engine consumes ``monte_carlo.parameters`` as an explicit LIST of
        ``{name, low, high}`` mappings and raises ``MonteCarloConfigError`` on a
        dict-form or empty block. Of the committed variants only ``lendercase`` pins
        the list form; ``basecase``/``equitycase`` carry a legacy dict of per-parameter
        scalars. Validate the RESOLVED scenario here (mirroring the request-time,
        file-backed turbine-model check) so a bad variant fails on POST with an
        actionable 422, not mid-job with an opaque engine error behind the generic
        failure boundary.
        """
        if self.analysis_type in _ANALYSIS_TYPES_REQUIRING_MC_PARAMS:
            scenario = self.wind.to_finance_scenario()
            mc = scenario.get("monte_carlo") if isinstance(scenario, Mapping) else None
            mc_block: Mapping[str, Any] = mc if isinstance(mc, Mapping) else {}
            params = mc_block.get("parameters")
            if params is None:
                params = mc_block.get("params")
            if not isinstance(params, list) or not params:
                variant = self.wind.inputs.scenario_variant
                raise ValueError(
                    f"analysis_type={self.analysis_type!r} requires the resolved "
                    f"scenario (variant={variant!r}) to define a non-empty LIST-form "
                    "monte_carlo.parameters (a list of {name, low, high} driver "
                    f"mappings). The {variant!r} base does not provide one in that "
                    "form; use scenario_variant='lendercase'."
                )
        return self
