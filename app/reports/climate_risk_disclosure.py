"""Bounded climate-risk disclosure contract and renderer (#1335, D5).

Provides a report-only climate disclosure contract mapping physical and transition
risks to explicit financial drivers (production, direct cost, outage, useful life,
liquidity, and financing terms).

Strict Boundaries:
1. Pure presentation and disclosure: moves NO canonical KPI (IRR, DSCR, NPV, CFADS).
2. Explicit provenance: jurisdiction, reporting perimeter, time horizons, scenario sources.
3. No universal hardcoded 1.5°C/4°C pair: scenario selection is evidence- and perimeter-specific.
4. No generic WACC markup that double-counts modelled physical or cost impacts.
5. Missing analysis is explicitly disclosed as missing, never masked as zero or immaterial.
6. Explicit disclaimer rejecting IFRS S1/S2 compliance or third-party assurance claims.
7. Standalone Jinja2 template partial decoupled from report.html.j2 pending #1636 landing.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "climate_risk_disclosure.html.j2"

#: Un-suppressible mandatory disclaimer. Never allow removal or compliance softening.
MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER = (
    "This disclosure provides structured climate-risk scenario commentary for informational "
    "and risk-screening purposes only. It does not constitute formal compliance with IFRS S1 "
    "(General Requirements for Disclosure of Sustainability-related Financial Information), "
    "IFRS S2 (Climate-related Disclosures), or TCFD, and has not undergone third-party audit "
    "or assurance. Figures do not alter committed project cash flows or canonical financial KPIs."
)

RiskType = Literal[
    "physical_acute",
    "physical_chronic",
    "transition_policy_legal",
    "transition_market",
    "transition_technology",
]

AnalysisStatus = Literal[
    "analyzed_present",
    "analyzed_absent",
    "missing_not_evaluated",
]

TransmissionChannel = Literal[
    "production_yield",
    "capital_cost",
    "operating_cost",
    "outage_curtailment",
    "useful_life",
    "liquidity_working_capital",
    "financing_terms",
]

TimeHorizonKind = Literal["short_term", "medium_term", "long_term"]
ResidualSeverity = Literal["low", "medium", "high", "undetermined"]

_PROHIBITED_COMPLIANCE_PATTERNS = (
    re.compile(r"\bifrs\s*s1\s*compliant\b", re.IGNORECASE),
    re.compile(r"\bifrs\s*s2\s*compliant\b", re.IGNORECASE),
    re.compile(r"\bthird-party\s*assured\b", re.IGNORECASE),
    re.compile(r"\baudited\s*climate\s*disclosure\b", re.IGNORECASE),
    re.compile(r"\bverified\s*by\s*auditor\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class TimeHorizon:
    """Explicit project time horizon with operational context."""

    kind: TimeHorizonKind
    label: str
    start_year: int
    end_year: int
    operational_context: str

    def __post_init__(self) -> None:
        if self.start_year > self.end_year:
            raise ValueError(
                f"Invalid time horizon: start_year {self.start_year} exceeds end_year {self.end_year}."
            )
        if not self.label.strip():
            raise ValueError("Time horizon label must not be empty.")


@dataclass(frozen=True)
class ClimateScenario:
    """Governed climate scenario definition with mandatory selection rationale."""

    scenario_id: str
    name: str
    pathway_family: str
    selection_rationale: str
    source_citation: str
    temperature_trajectory: Optional[str] = None
    source_digest: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must not be empty.")
        if not self.name.strip():
            raise ValueError("scenario name must not be empty.")
        if len(self.selection_rationale.strip()) < 12:
            raise ValueError(
                "selection_rationale must provide a substantive perimeter-specific justification (>=12 chars)."
            )
        if not self.source_citation.strip():
            raise ValueError("source_citation must not be empty.")
        if self.source_digest is not None:
            if not re.match(r"^[0-9a-f]{64}$", self.source_digest):
                raise ValueError(
                    "source_digest must be a 64-character lowercase hex string."
                )


@dataclass(frozen=True)
class FinancialTransmissionItem:
    """Explicit mapping from a climate hazard to a financial statement transmission channel."""

    channel: TransmissionChannel
    description: str
    modelled_impact: Optional[str] = None
    already_modelled_in_cashflows: bool = False
    wacc_adjustment_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("Transmission item description must not be empty.")
        # Double-counting guard: If already modelled in cash flows, a parallel WACC adjustment is strictly forbidden.
        if self.already_modelled_in_cashflows and self.wacc_adjustment_allowed:
            raise ValueError(
                "Double-counting prohibited: an impact already modelled in cash flows cannot take a parallel WACC adjustment."
            )


@dataclass(frozen=True)
class ClimateRiskDriver:
    """Structured physical or transition climate risk item."""

    risk_id: str
    risk_type: RiskType
    title: str
    time_horizon: TimeHorizonKind
    analysis_status: AnalysisStatus
    hazard_description: str
    evidence_basis: str
    mitigation_summary: str
    residual_severity: ResidualSeverity
    transmission_channels: tuple[FinancialTransmissionItem, ...] = ()

    def __post_init__(self) -> None:
        if not self.risk_id.strip():
            raise ValueError("risk_id must not be empty.")
        if not self.title.strip():
            raise ValueError("risk title must not be empty.")
        if not self.hazard_description.strip():
            raise ValueError("hazard_description must not be empty.")

        # Guard: Missing analysis must not claim immateriality or low severity
        if self.analysis_status == "missing_not_evaluated":
            if self.residual_severity != "undetermined":
                raise ValueError(
                    f"Risk {self.risk_id}: missing analysis cannot claim resolved severity '{self.residual_severity}'; "
                    "must be 'undetermined'."
                )
            if self.transmission_channels:
                raise ValueError(
                    f"Risk {self.risk_id}: missing analysis cannot declare quantitative transmission channels."
                )

        # Guard: Ensure no un-substantiated IFRS assurance claim in text
        for text in (
            self.hazard_description,
            self.evidence_basis,
            self.mitigation_summary,
        ):
            for pattern in _PROHIBITED_COMPLIANCE_PATTERNS:
                if pattern.search(text):
                    raise ValueError(
                        f"Risk {self.risk_id}: prohibited compliance or assurance assertion detected in description."
                    )


@dataclass(frozen=True)
class ClimateDisclosurePerimeter:
    """Project-specific reporting boundary and jurisdictional perimeter."""

    project_name: str
    jurisdiction: str
    jurisdiction_iso: str
    reporting_boundary: str
    asset_lifespan_years: int

    def __post_init__(self) -> None:
        if not self.project_name.strip():
            raise ValueError("project_name must not be empty.")
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must not be empty.")
        if not re.match(r"^[A-Z]{2}$", self.jurisdiction_iso):
            raise ValueError(
                f"jurisdiction_iso must be a 2-letter uppercase ISO code, got {self.jurisdiction_iso!r}."
            )
        if self.asset_lifespan_years <= 0:
            raise ValueError("asset_lifespan_years must be positive.")


@dataclass(frozen=True)
class ClimateRiskDisclosureContext:
    """Complete presentation-layer context for rendering the D5 disclosure section."""

    perimeter: ClimateDisclosurePerimeter
    scenarios: tuple[ClimateScenario, ...]
    time_horizons: tuple[TimeHorizon, ...]
    drivers: tuple[ClimateRiskDriver, ...]
    disclaimer: str = MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValueError("At least one climate scenario must be declared.")
        if not self.time_horizons:
            raise ValueError("At least one time horizon must be declared.")
        if not self.drivers:
            raise ValueError("At least one climate risk driver must be registered.")
        if self.disclaimer != MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER:
            raise ValueError(
                "MANDATORY_CLIMATE_DISCLOSURE_DISCLAIMER must not be altered."
            )

        # Guard: Universal un-rationalized 1.5C/4.0C pair prohibition
        scenario_names_lower = {s.name.lower() for s in self.scenarios}
        if scenario_names_lower == {"1.5°c", "4.0°c"} or scenario_names_lower == {
            "1.5c",
            "4c",
        }:
            for s in self.scenarios:
                if (
                    "generic pair" in s.selection_rationale.lower()
                    or len(s.selection_rationale) < 30
                ):
                    raise ValueError(
                        "Universal hardcoded 1.5°C/4°C scenario pairs without robust site-specific rationale are prohibited."
                    )

    @property
    def missing_analyses_count(self) -> int:
        """Count of registered risks with status missing_not_evaluated."""
        return sum(
            1 for d in self.drivers if d.analysis_status == "missing_not_evaluated"
        )

    @property
    def missing_analyses_drivers(self) -> tuple[ClimateRiskDriver, ...]:
        """Tuple of drivers requiring further analytical assessment."""
        return tuple(
            d for d in self.drivers if d.analysis_status == "missing_not_evaluated"
        )

    def model_dump(self) -> dict[str, Any]:
        """Serialize context to inert dictionary."""
        return asdict(self)


def get_template_environment() -> Environment:
    """Create Jinja2 environment configured for report templates."""
    loader = FileSystemLoader(str(_TEMPLATE_DIR))
    return Environment(
        loader=loader,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_climate_risk_disclosure_partial(
    context: ClimateRiskDisclosureContext,
) -> str:
    """Render the D5 climate-risk disclosure section as an HTML partial.

    This function produces standalone HTML markup ready for direct preview or embedding
    into report.html.j2 once the active pull request queue lands.
    """
    env = get_template_environment()
    template = env.get_template(_TEMPLATE_NAME)
    return template.render(ctx=context, standalone=False)


def render_climate_risk_disclosure_html(context: ClimateRiskDisclosureContext) -> str:
    """Render the D5 climate-risk disclosure section as a complete standalone HTML document."""
    env = get_template_environment()
    template = env.get_template(_TEMPLATE_NAME)
    return template.render(ctx=context, standalone=True)
