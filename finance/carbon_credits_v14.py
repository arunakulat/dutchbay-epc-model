"""Default-off carbon-credit eligibility, issuance and cashflow contract (#1428).

All parameters and outputs are strictly config-first and default-off. Without
accepted registry/legal evidence, revenue stays zero, stays out of covenants and
canonical KPIs, and synthetic placeholder values are explicitly labelled as
placeholder data until user/registry evidence is received.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class CarbonCreditConfigError(ValueError):
    """Raised when carbon-credit configuration violates strict contract rules."""


@dataclass(frozen=True)
class CarbonCreditContract:
    """Validated default-off carbon-credit contract parameters (#1428)."""

    enabled: bool = False
    is_placeholder: bool = True
    data_status: str = "synthetic_placeholder"
    claim_authority: str = "none_placeholder_only"
    registry_name: str = ""
    methodology_id: str = ""
    methodology_version: str = ""
    project_life_years: int = 0
    gross_eligible_tco2e_per_year: float = 0.0
    deduction_pct: float = 0.0
    rejection_rate_pct: float = 0.0
    issuance_delay_years: int = 0
    price_usd_per_tco2e: float = 0.0
    issuance_cost_usd_per_tco2e: float = 0.0
    tax_rate_pct: float = 0.0
    revenue_share_pct: float = 0.0
    covenant_eligible: bool = False
    included_in_canonical_kpis: bool = False


@dataclass(frozen=True)
class CarbonCreditYearRow:
    """One project year's estimated, issued and sold carbon-credit ledger row."""

    year: int
    estimated_tco2e: float
    issued_tco2e: float
    sold_tco2e: float
    gross_revenue_usd: float
    issuance_cost_usd: float
    tax_usd: float
    revenue_share_usd: float
    net_revenue_usd: float


@dataclass(frozen=True)
class CarbonCreditSchedule:
    """Full multi-year carbon-credit schedule with provenance and authority bounds."""

    enabled: bool
    is_placeholder: bool
    data_status: str
    claim_authority: str
    covenant_eligible: bool
    included_in_canonical_kpis: bool
    rows: tuple[CarbonCreditYearRow, ...]
    total_estimated_tco2e: float
    total_issued_tco2e: float
    total_sold_tco2e: float
    total_gross_revenue_usd: float
    total_issuance_cost_usd: float
    total_tax_usd: float
    total_revenue_share_usd: float
    total_net_revenue_usd: float


def _finite_non_negative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CarbonCreditConfigError(f"{name} must be a finite number; got {value!r}")
    out = float(value)
    if not math.isfinite(out) or out < 0.0:
        raise CarbonCreditConfigError(f"{name} must be >= 0 and finite; got {value!r}")
    return out


def _pct(value: Any, name: str) -> float:
    out = _finite_non_negative(value, name)
    if out > 100.0:
        raise CarbonCreditConfigError(f"{name} must be in [0, 100]; got {value!r}")
    return out


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CarbonCreditConfigError(f"{name} must be an integer >= 0; got {value!r}")
    return int(value)


def _non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CarbonCreditConfigError(f"{name} must be a non-empty string")
    return value.strip()


def resolve_carbon_credit_contract(
    raw: Mapping[str, Any] | None,
) -> CarbonCreditContract:
    """Validate and resolve a ``carbon_credits`` config mapping (default-off).

    Args:
        raw: Optional configuration mapping (e.g. ``cfg.get("carbon_credits")``).

    Returns:
        A validated :class:`CarbonCreditContract`. When ``raw`` is ``None`` or
        ``enabled`` is ``False``, returns a zero-revenue default-off contract.
    """
    if raw is None:
        return CarbonCreditContract()
    if not isinstance(raw, Mapping):
        raise CarbonCreditConfigError("carbon_credits must be a mapping when provided")

    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise CarbonCreditConfigError(
            f"carbon_credits.enabled must be a boolean; got {enabled!r}"
        )

    if raw.get("covenant_eligible", False) is not False:
        raise CarbonCreditConfigError(
            "carbon_credits.covenant_eligible must be false (#1428: stays out of covenants)"
        )
    if raw.get("included_in_canonical_kpis", False) is not False:
        raise CarbonCreditConfigError(
            "carbon_credits.included_in_canonical_kpis must be false (#1428: stays out of canonical KPIs)"
        )

    if not enabled:
        return CarbonCreditContract(enabled=False)

    is_placeholder = raw.get("placeholder_data", True)
    if not isinstance(is_placeholder, bool):
        raise CarbonCreditConfigError(
            "carbon_credits.placeholder_data must be a boolean"
        )
    accepted_evidence_ref = raw.get("accepted_evidence_ref")
    if not is_placeholder and (
        not isinstance(accepted_evidence_ref, str) or not accepted_evidence_ref.strip()
    ):
        raise CarbonCreditConfigError(
            "carbon_credits.accepted_evidence_ref is required when placeholder_data is false"
        )

    data_status = "synthetic_placeholder" if is_placeholder else "accepted_evidence"
    claim_authority = (
        "none_placeholder_only" if is_placeholder else "evidence_bound_non_covenant"
    )

    return CarbonCreditContract(
        enabled=True,
        is_placeholder=is_placeholder,
        data_status=data_status,
        claim_authority=claim_authority,
        registry_name=_non_empty_str(raw.get("registry_name"), "registry_name"),
        methodology_id=_non_empty_str(raw.get("methodology_id"), "methodology_id"),
        methodology_version=_non_empty_str(
            raw.get("methodology_version"), "methodology_version"
        ),
        project_life_years=_non_negative_int(
            raw.get("project_life_years"), "project_life_years"
        ),
        gross_eligible_tco2e_per_year=_finite_non_negative(
            raw.get("gross_eligible_tco2e_per_year"), "gross_eligible_tco2e_per_year"
        ),
        deduction_pct=_pct(raw.get("deduction_pct", 0.0), "deduction_pct"),
        rejection_rate_pct=_pct(
            raw.get("rejection_rate_pct", 0.0), "rejection_rate_pct"
        ),
        issuance_delay_years=_non_negative_int(
            raw.get("issuance_delay_years", 0), "issuance_delay_years"
        ),
        price_usd_per_tco2e=_finite_non_negative(
            raw.get("price_usd_per_tco2e"), "price_usd_per_tco2e"
        ),
        issuance_cost_usd_per_tco2e=_finite_non_negative(
            raw.get("issuance_cost_usd_per_tco2e", 0.0),
            "issuance_cost_usd_per_tco2e",
        ),
        tax_rate_pct=_pct(raw.get("tax_rate_pct", 0.0), "tax_rate_pct"),
        revenue_share_pct=_pct(raw.get("revenue_share_pct", 0.0), "revenue_share_pct"),
        covenant_eligible=False,
        included_in_canonical_kpis=False,
    )


def evaluate_carbon_credit_schedule(
    contract: CarbonCreditContract,
) -> CarbonCreditSchedule:
    """Evaluate multi-year carbon-credit estimated, issued, sold units and net revenue.

    Revenue stays strictly zero when ``contract.enabled`` is ``False`` or when
    ``contract.is_placeholder`` is ``True`` unless explicitly evaluated for
    advisory placeholder inspection via ``allow_placeholder_cashflow=False``
    semantics: placeholder runs compute advisory units/revenue while flagging
    ``is_placeholder=True`` and keeping canonical KPIs / covenants untouched.
    """
    if not contract.enabled or contract.project_life_years == 0:
        return CarbonCreditSchedule(
            enabled=contract.enabled,
            is_placeholder=contract.is_placeholder,
            data_status=contract.data_status,
            claim_authority=contract.claim_authority,
            covenant_eligible=False,
            included_in_canonical_kpis=False,
            rows=(),
            total_estimated_tco2e=0.0,
            total_issued_tco2e=0.0,
            total_sold_tco2e=0.0,
            total_gross_revenue_usd=0.0,
            total_issuance_cost_usd=0.0,
            total_tax_usd=0.0,
            total_revenue_share_usd=0.0,
            total_net_revenue_usd=0.0,
        )

    net_factor = (1.0 - contract.deduction_pct / 100.0) * (
        1.0 - contract.rejection_rate_pct / 100.0
    )
    rows: list[CarbonCreditYearRow] = []
    # Queue of issued tonnes delayed by issuance_delay_years; issued in year t + delay
    # when t + delay <= project_life_years.
    delayed_issuance: dict[int, float] = {}
    for year in range(1, contract.project_life_years + 1):
        estimated = contract.gross_eligible_tco2e_per_year
        target_year = year + contract.issuance_delay_years
        if target_year <= contract.project_life_years:
            delayed_issuance[target_year] = (
                delayed_issuance.get(target_year, 0.0) + estimated * net_factor
            )

        issued = delayed_issuance.get(year, 0.0)
        sold = issued
        gross_rev = sold * contract.price_usd_per_tco2e
        issuance_cost = issued * contract.issuance_cost_usd_per_tco2e
        pre_tax = max(0.0, gross_rev - issuance_cost)
        tax = pre_tax * (contract.tax_rate_pct / 100.0)
        after_tax = max(0.0, pre_tax - tax)
        rev_share = after_tax * (contract.revenue_share_pct / 100.0)
        net_rev = gross_rev - issuance_cost - tax - rev_share

        rows.append(
            CarbonCreditYearRow(
                year=year,
                estimated_tco2e=estimated,
                issued_tco2e=issued,
                sold_tco2e=sold,
                gross_revenue_usd=gross_rev,
                issuance_cost_usd=issuance_cost,
                tax_usd=tax,
                revenue_share_usd=rev_share,
                net_revenue_usd=net_rev,
            )
        )

    return CarbonCreditSchedule(
        enabled=True,
        is_placeholder=contract.is_placeholder,
        data_status=contract.data_status,
        claim_authority=contract.claim_authority,
        covenant_eligible=False,
        included_in_canonical_kpis=False,
        rows=tuple(rows),
        total_estimated_tco2e=sum(r.estimated_tco2e for r in rows),
        total_issued_tco2e=sum(r.issued_tco2e for r in rows),
        total_sold_tco2e=sum(r.sold_tco2e for r in rows),
        total_gross_revenue_usd=sum(r.gross_revenue_usd for r in rows),
        total_issuance_cost_usd=sum(r.issuance_cost_usd for r in rows),
        total_tax_usd=sum(r.tax_usd for r in rows),
        total_revenue_share_usd=sum(r.revenue_share_usd for r in rows),
        total_net_revenue_usd=sum(r.net_revenue_usd for r in rows),
    )


def evaluate_carbon_credit_scenarios(
    base_raw: Mapping[str, Any],
    scenarios: Sequence[tuple[str, Mapping[str, Any]]],
) -> dict[str, CarbonCreditSchedule]:
    """Evaluate named price/volume/delay/rejection stress scenarios (#1428)."""
    results: dict[str, CarbonCreditSchedule] = {}
    for label, overrides in scenarios:
        merged = {**base_raw, **overrides}
        contract = resolve_carbon_credit_contract(merged)
        results[label] = evaluate_carbon_credit_schedule(contract)
    return results
