"""Typed response models for the web boundary.

The public HTTP contract (#788 P1 / #841) has two version axes that complement each
other: the URL surface is pinned under ``/v1`` (see ``app.api.main.API_V1_PREFIX`` — a
future breaking change lands as ``/v2``), and :data:`API_CONTRACT_VERSION` versions the
client-facing response *shape* (the wizard, and later an iOS client, code against it):
bump the MINOR on an additive change (a new optional field) and the MAJOR on a breaking
one (a removed/renamed/retyped field). ``tests/app/test_api_contract.py`` pins the public
field set + types + the OpenAPI schema, so a breaking change to a response model fails
loudly rather than silently shipping to clients.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, Field

#: Public API contract version (SemVer). Surfaced on ``GET /health`` and on every
#: :class:`CaseResult`. Bump on any change to the client-facing response shape.
#: 1.1 (#993): added the optional ``CaseResult.wind_assessment`` block (additive).
API_CONTRACT_VERSION = "1.1"


class WindAssessment(BaseModel):
    """Screening-grade wind-resource assessment surfaced alongside the finance KPIs.

    All three exceedance levels + capacity factors, resource provenance/grade, site
    metadata, the assessed data period, and the fitted wind statistics — so a wizard or
    iOS client can show the full P50/P75/P90 picture and its provenance (#993), not only
    the single P-level the finance case was billed off. Dict-typed sub-blocks (rather
    than deeply nested models) keep the contract additive and tolerant of extra
    provenance keys the producer may add over time.
    """

    p_levels_gwh: Dict[str, float] = Field(
        default_factory=dict,
        description="Net AEP by exceedance level (P50/P75/P90), in GWh.",
    )
    net_capacity_factor: Dict[str, float] = Field(
        default_factory=dict,
        description="Net capacity factor (decimal) by exceedance level.",
    )
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Engine version, grade (screening/bankable), exceedance method, "
        "and uncertainty sigma.",
    )
    site: Dict[str, Any] = Field(
        default_factory=dict, description="Site metadata (name, lat, lon)."
    )
    data_period: Dict[str, Any] = Field(
        default_factory=dict,
        description="Assessed window (start, end, data points).",
    )
    wind_stats: Dict[str, float] = Field(
        default_factory=dict,
        description="Fitted wind statistics (mean wind speed, Weibull A and k).",
    )


class CaseResult(BaseModel):
    """Client-facing summary of a finance-case run.

    A focused projection of the canonical pipeline result for the ``POST /v1/cases``
    wizard surface — the lender KPIs plus the audit manifest. (The full
    annual-cashflow / debt-schedule detail is available via the lower-level
    ``/v1/run-pipeline`` route.)
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
    wind_assessment: Optional[WindAssessment] = Field(
        default=None,
        description="Full screening-grade wind assessment (all P50/P75/P90 + provenance "
        "+ site + data period + wind stats) — present on async wind-job results, absent "
        "on plain finance cases (#993).",
    )

    @classmethod
    def from_pipeline_result(
        cls,
        result: Mapping[str, Any],
        *,
        scenario_variant: str,
        wind_assessment: Optional[WindAssessment] = None,
    ) -> "CaseResult":
        """Project a canonical pipeline result dict into a ``CaseResult``.

        ``wind_assessment`` is threaded through unchanged when the caller (the async
        wind-job runner) has one; it defaults to ``None`` for plain finance cases.
        """
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
            wind_assessment=wind_assessment,
        )
