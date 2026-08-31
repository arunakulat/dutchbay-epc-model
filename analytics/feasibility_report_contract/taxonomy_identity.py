"""Import-safe identity projection of the feasibility-section taxonomy.

``config/feasibility_sections.yaml`` remains the single authored source.  This
module is a generated contract identity surface for pure consumers that must not
perform filesystem I/O at import or call time.  The source digest and ordered IDs
are checked against the YAML by contract tests, so a taxonomy edit cannot drift
silently from this projection.
"""

from __future__ import annotations

from typing import Final

FEASIBILITY_TAXONOMY_SOURCE_PATH: Final = "config/feasibility_sections.yaml"
FEASIBILITY_TAXONOMY_SOURCE_SHA256: Final = (
    "ee2987df5ef97ee16cc970d53d483c60026b6f80cd9866cc1f94a066c9a5174e"
)
FEASIBILITY_SECTION_IDS: Final[tuple[str, ...]] = (
    "executive_investment_thesis",
    "project_description_and_structure",
    "site_land_permits_legal_status",
    "resource_and_energy_yield",
    "technology_selection_design_basis",
    "grid_interconnection_curtailment",
    "construction_logistics_plan",
    "environmental_social_summary",
    "climate_resilience_assessment",
    "capex_opex_contingency_procurement",
    "revenue_ppa_tariff_assumptions",
    "financing_plan_debt_sizing",
    "tax_fx_inflation_accounting",
    "base_case_financial_outputs",
    "sensitivity_downside_cases",
    "monte_carlo_risk_distribution",
    "optimization_alternatives_analysis",
    "risk_register_and_mitigations",
    "decision_checklist_conditions_precedent",
    "appendices_provenance_audit_trail",
)

__all__ = (
    "FEASIBILITY_SECTION_IDS",
    "FEASIBILITY_TAXONOMY_SOURCE_PATH",
    "FEASIBILITY_TAXONOMY_SOURCE_SHA256",
)
