"""Typed response models for the web boundary."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, Field


class CaseResult(BaseModel):
    """Client-facing summary of a finance-case run.

    A focused projection of the canonical pipeline result for the ``POST /cases``
    wizard surface — the lender KPIs plus the audit manifest. (The full
    annual-cashflow / debt-schedule detail is available via the lower-level
    ``/run-pipeline`` route.)
    """

    status: str = Field(..., description="'success' or an error status.")
    scenario_variant: str = Field(..., description="Base variant the run started from.")
    kpis: Dict[str, float] = Field(
        default_factory=dict,
        description="Flat lender KPIs (project_irr, equity_irr, min_dscr, ...).",
    )
    run_manifest: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Audit manifest (config hash, engine version, commit).",
    )

    @classmethod
    def from_pipeline_result(
        cls, result: Mapping[str, Any], *, scenario_variant: str
    ) -> "CaseResult":
        """Project a canonical pipeline result dict into a ``CaseResult``."""
        raw_kpis = result.get("kpis") or {}
        kpis = {
            str(k): float(v)
            for k, v in raw_kpis.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        manifest = result.get("run_manifest")
        return cls(
            status=str(result.get("status", "unknown")),
            scenario_variant=scenario_variant,
            kpis=kpis,
            run_manifest=dict(manifest) if isinstance(manifest, Mapping) else None,
        )
