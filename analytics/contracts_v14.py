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
    # DEPRECATED naming (#648): the live engine selector is the ``monte_carlo.sampler`` config
    # key (see analytics.mc.engine.MonteCarloEngine._resolve_sampler), NOT ``sampling_method``.
    # This field name predates that switch; ``monte_carlo.sampling_method`` in a scenario YAML
    # is now accepted as a deprecated alias for ``sampler`` (mapped on with a DeprecationWarning)
    # rather than silently ignored. Prefer ``sampler`` in new scenarios.
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
    # Re-instated Sprint 19 (#60 unpark): these were dropped from the contract in
    # the Palette refactor (979520b) while ``casper_payload`` kept building/reading
    # them. The generation sub-contracts (GenerationProfile / MultiTechGenerationResult
    # / TechnologyBreakdown) were already re-instated below for the same reason.
    generation: MultiTechGenerationResult | None = None
    multi_tech_generation_breakdown: list[TechnologyBreakdown] | None = None
    # Per-technology cost/return work-breakdown (ARCH-3, #475): additive read-only
    # CAPEX/OPEX/WACC attribution reconciled to the financed totals; None when the
    # scenario carries no generation.technologies block.
    multi_tech_wbs: MultiTechWBS | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Class-level frozen attribute (NOT __init__ arg). Resolved Sprint 18D
    # (D.X+6): previously defined as ``def contract_version(self) -> str``,
    # which silently became a bound method when callers used attribute
    # access (``result.contract_version`` rather than ``result.contract_version()``).
    # That produced misleading values in serialization paths and was
    # inconsistent with the plain string-attribute ``contract_version`` shape
    # used by sibling contracts at the time (the CHANGELOG Sprint 18D entry
    # cites ``RefinancingResult``, a contract removed before the repository
    # import; it no longer exists in tracked code).
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
# ``_technology_breakdown_to_list``). A same-named ``TechnologyBreakdown``
# model with a different field surface (capacity_mw / capex_usd /
# opex_annual_usd) historically lived in ``finance/contracts.py``; that module
# was removed as a dead duplicate in #299, leaving the dataclass below as the
# only ``TechnologyBreakdown`` in the codebase.
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

    NOTE: this is the only ``TechnologyBreakdown`` in the codebase. A
    same-named model carrying capex/opex/capacity fields historically lived
    in ``finance/contracts.py``, but that module was removed as a dead
    duplicate in #299. The CASPER payload pipeline consumes this contract via
    ``_technology_breakdown_to_list``.
    """

    technology: str
    share_of_capex_pct: float | None = None
    share_of_cfads_pct: float | None = None
    share_of_aep_pct: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class TechnologyCostReturn(ContractMixin):
    """Per-technology cost/return line of the multi-tech work-breakdown (ARCH-3).

    Attributes the *reporting* per-tech CAPEX/OPEX/cost-of-capital of a hybrid to a
    single technology. CAPEX/OPEX are read from the ``generation.technologies.<tech>``
    block; the financed totals remain ``capex.usd_total`` / project ``opex`` (the
    deliberate phantom-capex decoupling — finance reads the total, this surface
    reports the split). ``cost_of_equity`` is a per-tech disclosure only: it is
    populated when the tech block declares its own ``wacc.cost_of_equity``, else
    ``None`` and ``wacc_basis == "blended"`` (the project WACC applies). It does NOT
    feed back into the financed economics — per-tech-WACC financing is a separate,
    KPI-moving step.
    """

    technology: str
    capex_usd: float | None = None
    opex_usd_per_year: float | None = None
    cost_of_equity: float | None = None
    wacc_basis: str = "blended"
    share_of_capex_pct: float | None = None
    share_of_opex_pct: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class MultiTechWBS(ContractMixin):
    """Per-technology cost/return work-breakdown with total reconciliation (ARCH-3).

    The keystone the audit deferred in #448: a per-tech CAPEX/OPEX/WACC breakdown
    reconciled against the authoritative financed totals. ``capex_residual_usd`` is the
    shared / balance-of-plant / unallocated bucket (e.g. grid connection, development
    cost) — a positive residual (financed > allocated) is expected and legitimate.
    Allocations that *exceed* the financed total beyond ``reconcile_tolerance_pct`` are
    a real error and fail loud at build time (CESSPIT). This surface is additive and
    read-only: it performs no finance recomputation, so committed scenarios are
    KPI-neutral.
    """

    technologies: dict[str, TechnologyCostReturn] = field(default_factory=dict)
    financed_capex_usd: float | None = None
    allocated_capex_usd: float = 0.0
    capex_residual_usd: float | None = None
    capex_reconciled: bool = False
    financed_opex_usd_per_year: float | None = None
    allocated_opex_usd_per_year: float = 0.0
    opex_residual_usd_per_year: float | None = None
    opex_reconciled: bool = False
    project_wacc_nominal: float | None = None
    reconcile_tolerance_pct: float = 1.0
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe payload (parity with ``MultiTechGenerationResult.to_dict``)."""
        return self.model_dump()


@dataclass(frozen=True)
class SharedPoiCurtailmentResult(ContractMixin):
    """Shared point-of-interconnection curtailment for a hybrid plant (ARCH-5, #476).

    When several technologies inject through one shared POI, their *combined* instantaneous
    output can exceed the POI export limit; the excess is physically curtailed (lost, not
    deemed/paid — distinct from grid-instructed curtailment). Computed from per-technology
    hourly injection profiles against ``poi_limit_mw``; ``curtailment_pct`` is the curtailed
    share of combined gross generation. Opt-in: absent a POI limit or hourly profiles, the
    interaction is not modelled (no committed scenario is affected — KPI-neutral).
    """

    poi_limit_mw: float
    gross_energy_mwh: float
    curtailed_energy_mwh: float
    curtailment_pct: float
    hours_curtailed: int
    hours_total: int


@dataclass(frozen=True)
class IrrBridgeComponent(ContractMixin):
    """One leg of the project→equity IRR bridge (an additive IRR contribution, decimal).

    ``contribution`` is the change in IRR (decimal, e.g. 0.012 = +1.2 pp) attributed to this
    effect as the cashflow is transformed step-by-step from the project basis toward the equity
    basis. ``irr_after`` is the intermediate IRR of the *cumulative* transformation up to and
    including this leg (so successive ``irr_after`` values walk from the project IRR to the
    equity IRR), or ``None`` if that intermediate IRR is undefined. Every leg is a labelled,
    signed step — no leg silently re-derives a published headline KPI.
    """

    name: str
    contribution: float
    irr_after: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ProjectEquityIrrBridge(ContractMixin):
    """Reconciliation of the published project IRR to the published equity IRR (IC disclosure).

    A **disclosure-only** decomposition of the leverage uplift ``equity_irr − project_irr`` into
    labelled legs (leverage, cost of debt, tax shield, cashflow timing) plus an explicit
    ``residual`` that captures everything not attributed to a named leg (covenant lockup, DSRA,
    WHT, terminal value, and the intrinsic non-additivity of IRR). By construction
    ``sum(component.contribution for component in components) + residual == equity_irr −
    project_irr`` to within ``reconcile_tolerance`` — asserted at build time (CESSPIT). It never
    recomputes or moves a headline KPI: ``project_irr`` and ``equity_irr`` are the engine-published
    values, and the legs only *explain* the gap between them. ``None``-valued IRRs (undefined
    project or equity IRR) are represented honestly rather than coerced to a number.
    """

    project_irr: float | None
    equity_irr: float | None
    total_uplift: float | None
    components: list[IrrBridgeComponent] = field(default_factory=list)
    residual: float = 0.0
    reconciled: bool = False
    reconcile_tolerance: float = 1e-9
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)


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
    "TechnologyCostReturn",
    "MultiTechWBS",
    "SharedPoiCurtailmentResult",
    "IrrBridgeComponent",
    "ProjectEquityIrrBridge",
]
