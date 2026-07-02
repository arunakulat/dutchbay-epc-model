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
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

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
        default=None, description="The CaseResult dict on success."
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
