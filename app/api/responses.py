"""Typed response models for the web boundary.

The public HTTP contract (#788 P1 / #841). :data:`API_CONTRACT_VERSION` versions the
client-facing response shape (the wizard, and later an iOS client, code against it):
bump the MINOR on an additive change (a new optional field) and the MAJOR on a breaking
one (a removed/renamed/retyped field). ``tests/app/test_api_contract.py`` pins the public
field set, so a breaking change to a response model fails loudly rather than silently
shipping to clients.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, Field

#: Public API contract version (SemVer). Surfaced on ``GET /health`` and on every
#: :class:`CaseResult`. Bump on any change to the client-facing response shape.
API_CONTRACT_VERSION = "1.0"


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
    contract_version: str = Field(
        default=API_CONTRACT_VERSION,
        description="Public API contract version this response conforms to (#841).",
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
