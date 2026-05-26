"""DutchBay v14 analytics contracts.

This module is the backward-compatible source of truth for v14 analytics
contracts. It deliberately uses dataclasses for the current compatibility
repair because the canonical pipeline serializes ScenarioResult with
``dataclasses.asdict``. A later migration can move these contracts into the
``analytics.contracts`` package as Pydantic models once the pipeline serializer
supports both dataclasses and Pydantic objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, cast

from analytics.fx.fx_contracts import FXCurveOutput, FXRiskProfile, FXStructuredBlock

# Canonical CASPER contract version string. Unified Sprint 18D (D.X+5) to
# match the value already shipping in the JSON payload
# (``analytics.casper.casper_payload.CASPER_CONTRACT_VERSION``), which is the
# customer/API-visible surface. The two constants were divergent on main
# ("v1.0" here vs "casper_result_v1" in casper_payload) — disclosed as
# Defect #3 in CHANGELOG v14.14.1.
CASPER_CONTRACT_VERSION = "casper_result_v1"


def _dump(value: Any) -> Any:
    """Serialize dataclasses recursively; leave plain values unchanged."""
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _dump(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dump(v) for v in value]
    return value


class ContractMixin:
    """Small compatibility mixin for dataclass contracts."""

    def model_dump(self) -> dict[str, Any]:
        return cast(dict[str, Any], _dump(self))

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


def check_covenant_breach_with_tolerance(
    actual: float,
    threshold: float,
    tolerance_bps: int = 1,
    covenant_type: str = "floor",
) -> bool:
    """Return True when a covenant is breached beyond tolerance."""
    if tolerance_bps < 0:
        raise ValueError(f"tolerance_bps must be non-negative, got {tolerance_bps}")
    if covenant_type not in {"floor", "ceiling"}:
        raise ValueError("covenant_type must be 'floor' or 'ceiling'")

    tolerance_abs = abs(threshold) * (tolerance_bps / 10_000.0)
    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)
    return actual > (threshold + tolerance_abs)


@dataclass(frozen=True)
class WaccComponents(ContractMixin):
    mode: str
    wacc_nominal: float
    wacc_real: float | None = None
    wacc_prudential: float = 0.0
    risk_free_rate: float = 0.0
    market_risk_premium: float = 0.0
    asset_beta: float = 0.0
    target_debt_to_equity: float = 0.0
    target_debt_to_value: float = 0.0
    target_equity_to_value: float = 1.0
    cost_of_debt_pretax: float = 0.0
    cost_of_debt_aftertax: float = 0.0
    equity_beta_levered: float = 0.0
    cost_of_equity: float = 0.0
    tax_rate: float = 0.0
    inflation_rate: float | None = None
    prudential_spread_bps: int = 0


@dataclass(frozen=True)
class WaccResult(ContractMixin):
    base: WaccComponents
    prudential_rate: float
    prudential_npv: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrancheDebtProfile(ContractMixin):
    construction_years: int
    tenor_years: int
    timeline_periods: int
    total_debt: float
    total_idc: float
    lkr_principal: float = 0.0
    usd_principal: float = 0.0
    dfi_principal: float = 0.0
    lkr_idc: float = 0.0
    usd_idc: float = 0.0
    dfi_idc: float = 0.0
    lkr_rate: float | None = None
    usd_rate: float | None = None
    dfi_rate: float | None = None
    interest_only_years: int = 0
    amortization_style: str = "sculpted"
    dscr_target: float | None = None


@dataclass(frozen=True)
class DebtCovenantSnapshot(ContractMixin):
    dscr_min: float
    dscr_threshold: float
    years_below_threshold: int
    first_breach_year: int | None
    last_breach_year: int | None
    balloon_remaining: float
    balloon_flag: bool
    audit_status: str
    notes: str = ""
    llcr: float | None = None
    plcr: float | None = None
    llcr_threshold: float | None = None
    plcr_threshold: float | None = None
    fx_min: float | None = None
    fx_max: float | None = None
    fx_avg: float | None = None


@dataclass(frozen=True)
class ScenarioResult(ContractMixin):
    scenario_name: str
    config_path: str
    project_npv: float
    project_irr: float
    dscr_series: list[float]
    min_dscr: float
    max_debt_usd: float
    wacc: WaccResult | None = None
    discount_rate_used: float | None = None
    wacc_label: str | None = None
    validation_mode: str = "strict"
    config: dict[str, Any] = field(default_factory=dict)
    annual_rows: list[dict[str, Any]] = field(default_factory=list)
    debt_result: dict[str, Any] = field(default_factory=dict)
    kpis: dict[str, Any] = field(default_factory=dict)
    debt_profile: TrancheDebtProfile | None = None
    debt_covenants: DebtCovenantSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    wacc_is_real: bool | None = None
    fx_block: FXStructuredBlock | None = None
    fx_curve: FXCurveOutput | None = None
    fx_risk_profile: FXRiskProfile | None = None
    cashflow: CashflowResult | None = None
    equity_performance: EquityPerformance | None = None


@dataclass(frozen=True)
class ParameterRangeConfig(ContractMixin):
    variable_name: str
    base_value: float
    low_pct: float | None = None
    high_pct: float | None = None
    low_value: float | None = None
    high_value: float | None = None
    label: str | None = None
    points: int = 2


@dataclass(frozen=True)
class ShockSpec(ContractMixin):
    variable_name: str
    shock_value: float
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShockResult(ContractMixin):
    variable_name: str | None = None
    label: str | None = None
    low_case: float | None = None
    high_case: float | None = None
    base_case: float | None = None
    impact: float | None = None
    impact_abs: float | None = None
    metric_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TornadoResult(ContractMixin):
    metric_name: str
    base_metric: float
    shock_results: list[ShockResult] = field(default_factory=list)
    label: str | None = None
    impact_abs: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MultiMetricTornadoResult(ContractMixin):
    variable_name: str
    results_by_metric: dict[str, TornadoResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SensitivitySuite(ContractMixin):
    base_config_path: str | None = None
    metric: str = "project_irr"
    tornado_results: list[TornadoResult] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Sprint 18C — ARCH-04 unification (issue #52)
    base_kpis: dict[str, float] = field(default_factory=dict)
    scenario_name: str | None = None
    analysis_timestamp: str | None = None


@dataclass(frozen=True)
class MultiMetricSensitivitySuite(ContractMixin):
    base_config_path: str | None = None
    metrics: list[str] = field(default_factory=list)
    results: list[MultiMetricTornadoResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SensitivityRequest(ContractMixin):
    base_config_path: str
    parameters: list[ParameterRangeConfig]
    metric: str = "project_irr"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BreakevenResult(ContractMixin):
    variable: str
    target_metric: str
    target_value: float
    breakeven_value: float | None = None
    status: str = "unknown"
    bracket: tuple[float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StandardShockLibrary(ContractMixin):
    shocks: dict[str, ShockSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class Distribution(ContractMixin):
    dist_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DerivedParameter(ContractMixin):
    name: str
    expression: str
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MonteCarloScenario(ContractMixin):
    scenario_name: str
    n_iterations: int = 1000
    sampling_method: str = "lhs"
    seed: int | None = None
    distributions: dict[str, Distribution] = field(default_factory=dict)
    derived_parameters: list[DerivedParameter] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MonteCarloResult(ContractMixin):
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    trials: dict[str, list[float]] = field(default_factory=dict)
    percentiles: dict[int, dict[str, float]] = field(default_factory=dict)
    scenario_name: str | None = None
    iterations: int = 0
    failed_iterations: int = 0
    raw_results: list[dict[str, Any]] | None = None
    project_irr_mean: float | None = None
    project_irr_std: float | None = None
    project_irr_p10: float | None = None
    project_irr_p50: float | None = None
    project_irr_p90: float | None = None
    project_npv_mean: float | None = None
    project_npv_p10: float | None = None
    project_npv_p50: float | None = None
    project_npv_p90: float | None = None
    dscr_min_p10: float | None = None
    dscr_min_p50: float | None = None
    n_iterations: int | None = None
    mean: float | None = None
    std: float | None = None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    metric_name: str | None = None
    sampling_method: str | None = None

    def __post_init__(self) -> None:
        if not self.trials:
            return
        lengths = {metric: len(values) for metric, values in self.trials.items()}
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            raise ValueError(
                "MonteCarloResult trial arrays must all have the same length; "
                f"got lengths {lengths}"
            )

    def success_rate(self) -> float:
        """Return the Monte Carlo success rate as a percentage (0-100).

        Computed from ``iterations`` and ``failed_iterations``:
            success_rate = (iterations - failed_iterations) / iterations * 100

        Returns ``0.0`` when ``iterations == 0`` (no trials run) to avoid
        division-by-zero; callers should inspect ``iterations`` if they need
        to distinguish "no run" from "all failed".

        Consumed by ``analytics.casper.casper_payload._monte_carlo_to_dict``
        to populate the ``"success_rate_pct"`` field of the CASPER JSON payload.
        """
        if self.iterations <= 0:
            return 0.0
        successful = self.iterations - self.failed_iterations
        return 100.0 * successful / self.iterations


@dataclass(frozen=True)
class CasperResult(ContractMixin):
    scenario: ScenarioResult | str
    baseline_kpis: dict[str, float] = field(default_factory=dict)
    sensitivities: SensitivitySuite | None = None
    monte_carlo: MonteCarloResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Class-level frozen attribute (NOT __init__ arg). Resolved Sprint 18D
    # (D.X+6): previously defined as ``def contract_version(self) -> str``,
    # which silently became a bound method when callers used attribute
    # access (``result.contract_version`` rather than ``result.contract_version()``).
    # That produced misleading values in serialization paths and contradicted
    # the sibling ``RefinancingResult.contract_version`` attribute shape.
    # ``init=False`` keeps the value pinned to the module-level constant
    # while still supporting ``ContractMixin.model_dump()`` / dataclasses.asdict.
    contract_version: str = field(default=CASPER_CONTRACT_VERSION, init=False)


@dataclass(frozen=True)
class CashflowResult(ContractMixin):
    annual_rows: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EquityPerformance(ContractMixin):
    equity_irr: float | None = None
    equity_npv: float | None = None
    equity_multiple: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DownsideMetrics(ContractMixin):
    dscr_min: float | None = None
    project_irr_p10: float | None = None
    project_npv_p10: float | None = None
    breach_probability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Multi-technology generation contracts (re-instated Sprint 18D)
#
# These three dataclasses were originally introduced in Sprint 9 (commit
# 260fc3b) and consumed by ``analytics.casper.casper_payload``. They were
# inadvertently deleted from ``contracts_v14.py`` during the Palette refactor
# (commit 979520b, Feb 24 2026) while their import sites in
# ``analytics/casper/casper_payload.py`` were left untouched. The deletion
# survived undetected because no test imported ``analytics.casper.casper_payload``
# at module level until Sprint 18D's contract-freeze test was revived.
#
# Surfaces here match the consumer expectations in
# ``analytics/casper/casper_payload.py`` (``_generation_to_dict``,
# ``_technology_breakdown_to_list``) and are *intentionally distinct* from
# the ``TechnologyBreakdown`` model in ``finance.contracts`` which carries a
# different field surface (capacity_mw / capex_usd / opex_annual_usd).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationProfile(ContractMixin):
    """Per-technology generation profile (annual AEP/CFADS view)."""

    technology: str
    annual_aep_kwh: float
    annual_cfads_usd: float
    availability_pct: float | None = None
    losses_breakdown: dict[str, float] | None = None


@dataclass(frozen=True)
class MultiTechGenerationResult(ContractMixin):
    """Aggregated generation view across multiple technologies.

    Consumed by ``analytics.casper.casper_payload._generation_to_dict`` which
    invokes ``to_dict()`` to serialize the structure into a JSON-safe payload.
    """

    total_aep_kwh: float
    total_cfads_usd: float
    technologies: dict[str, GenerationProfile] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_aep_kwh": self.total_aep_kwh,
            "total_cfads_usd": self.total_cfads_usd,
            "technologies": {
                tech: {
                    "technology": profile.technology,
                    "annual_aep_kwh": profile.annual_aep_kwh,
                    "annual_cfads_usd": profile.annual_cfads_usd,
                    "availability_pct": profile.availability_pct,
                    "losses_breakdown": (
                        dict(profile.losses_breakdown)
                        if profile.losses_breakdown is not None
                        else None
                    ),
                }
                for tech, profile in self.technologies.items()
            },
        }


@dataclass(frozen=True)
class TechnologyBreakdown(ContractMixin):
    """Per-technology KPI share for lender / investor visibility.

    NOTE: This contract is *distinct* from ``finance.contracts.TechnologyBreakdown``
    (which carries capex/opex/capacity fields). The two share a name for
    historical reasons but serve different consumers. The CASPER payload
    pipeline consumes this analytics-side variant via
    ``_technology_breakdown_to_list``.
    """

    technology: str
    share_of_capex_pct: float | None = None
    share_of_cfads_pct: float | None = None
    share_of_aep_pct: float | None = None
    notes: str | None = None


__all__ = [
    "CASPER_CONTRACT_VERSION",
    "check_covenant_breach_with_tolerance",
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    "ShockSpec",
    "StandardShockLibrary",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "MultiMetricSensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    "ShockResult",
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    "CasperResult",
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    "CashflowResult",
    "EquityPerformance",
    "DownsideMetrics",
    "GenerationProfile",
    "MultiTechGenerationResult",
    "TechnologyBreakdown",
]
