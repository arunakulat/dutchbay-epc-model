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
from analytics.resource_contracts import ResourceAssessment

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
class TwoFactorInteractionGrid(ContractMixin):
    """Two-driver sensitivity interaction surface (#739).

    ``values[i][j]`` is the RAW metric at row driver A's case ``a_labels[i]``
    and column driver B's case ``b_labels[j]`` (labels ordered base/low/high as
    emitted by the sweep adapter; raw metric values, NOT exceedance levels).
    ``interaction[i][j]`` is the deviation of the joint cell from the additive
    combination of the two one-way effects measured in the metric's own units —
    identically zero everywhere when the drivers do not interact. Cells that
    failed to evaluate carry NaN and are counted in
    ``metadata['n_failed_cells']`` (never silently substituted).
    """

    metric_name: str
    param_a_name: str
    param_b_name: str
    a_labels: list[str] = field(default_factory=list)
    b_labels: list[str] = field(default_factory=list)
    values: list[list[float]] = field(default_factory=list)
    interaction: list[list[float]] = field(default_factory=list)
    base_metric: float = 0.0
    max_abs_interaction: float = 0.0
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


# ---------------------------------------------------------------------------
# Grid interconnection strength (advisory; issue #872)
# ---------------------------------------------------------------------------
# SCR-band thresholds for the grid-following (GFL) vs grid-forming (GFM) screen.
# Common design practice / IEEE Std 2800 territory: SCR < ~2 is weak (GFM likely
# required), SCR > ~5 is strong (GFL comfortable), the band between is marginal
# (GFM may be prudent; confirm with a dynamic study). These are SCREENING defaults,
# overridable per-site via the `grid` config block — the config values win when
# provided (CESSPIT: no silent magic constant downstream).
GRID_SCR_WEAK_BELOW = 2.0
GRID_SCR_STRONG_ABOVE = 5.0
# Below this SCR an EMT (PSCAD/EMTP) confirmation is mandated before the screen can
# feed any interconnection decision — RMS/positive-sequence screening is not trusted
# for weak-grid IBR stability. Centralized here so nothing downstream re-derives it.
GRID_EMT_CONFIRMATION_SCR = 3.0


def grid_scr_band(
    scr: float,
    *,
    weak_below: float = GRID_SCR_WEAK_BELOW,
    strong_above: float = GRID_SCR_STRONG_ABOVE,
) -> str:
    """Band an SCR value into ``"weak" | "marginal" | "strong"``.

    The single source of truth for SCR banding — the short-circuit module and any
    report surface call this, so the GFL/GFM screen never drifts between callers.
    """
    if scr < weak_below:
        return "weak"
    if scr > strong_above:
        return "strong"
    return "marginal"


def grid_gfl_gfm_recommendation(band: str) -> str:
    """Map an SCR band to the GFL-vs-GFM screening recommendation string."""
    return {
        "weak": "GFL at risk at this SCR — grid-forming (GFM) likely required; confirm the CEB/NSCC grid-forming clause.",
        "marginal": "GFL marginal at this SCR — GFM may be prudent; confirm with a dynamic study.",
        "strong": "GFL viable at this SCR.",
    }.get(band, "SCR band undetermined — recompute the screen.")


@dataclass(frozen=True)
class GridStrengthResult(ContractMixin):
    """Advisory grid-strength / interconnection screen for the POC (issue #872).

    Emitted by :mod:`analytics.grid.short_circuit` from a design-stage short-circuit
    screen (pandapower IEC 60909, or a closed-form Thevenin fallback). It is a
    SCREENING advisory ONLY — it never feeds the finance engine, so committed
    scenarios are byte-identical (KPI-neutral).

    This contract is the CONTRACT-LEVEL bankability caveat: it centralizes the two
    lender-facing rules so nothing downstream re-implements them.

    1. IEC 60909 MIN-case governs the screen. Short-circuit fault level MUST be the
       IEC 60909 *minimum* fault level at the POC (weakest credible grid). The MAX
       case (largest fault level → most optimistic SCR) is reported for context only;
       ``scr`` and ``scr_band`` are taken from the min case. A screen built on the max
       case is NOT bankable and MUST set ``bankable=False``.
    2. Provenance → caveat strength. Any in-house Python screen is design-stage: it is
       never the utility-accepted bankable connection study (CEB/NSCC require PSS/E or
       PowerFactory against their confidential grid base case). ``bankable`` therefore
       defaults to ``False``; ``emt_confirmation_required`` is set whenever the SCR is
       low enough (``< GRID_EMT_CONFIRMATION_SCR``) that RMS/positive-sequence
       screening cannot be trusted and an EMT (PSCAD/EMTP) study is mandated.

    Use :meth:`from_screen` to construct one — it applies the min-case rule, the
    banding, the GFL/GFM recommendation and the EMT caveat consistently.
    """

    scr: float
    scr_band: str
    gfl_gfm_recommendation: str
    fault_level_poc_mva: float
    fault_level_case: str = "iec60909_min"
    plant_rating_mva: float | None = None
    fault_level_poc_max_mva: float | None = None
    method: str = "closed_form"  # "pandapower_iec60909" | "closed_form"
    bankable: bool = False
    emt_confirmation_required: bool = False
    provenance: str = ""
    notes: str = ""

    @classmethod
    def from_screen(
        cls,
        *,
        scr_min: float,
        fault_level_poc_min_mva: float,
        plant_rating_mva: float,
        fault_level_poc_max_mva: float | None = None,
        method: str = "closed_form",
        provenance: str = "",
        weak_below: float = GRID_SCR_WEAK_BELOW,
        strong_above: float = GRID_SCR_STRONG_ABOVE,
        emt_confirmation_scr: float = GRID_EMT_CONFIRMATION_SCR,
        notes: str = "",
    ) -> "GridStrengthResult":
        """Build the advisory result from a MIN-case short-circuit screen.

        The SCR/band are taken from the IEC 60909 min case (rule 1). ``bankable`` is
        always ``False`` for an in-house Python screen (rule 2); ``emt_confirmation_required``
        is set when ``scr_min < emt_confirmation_scr``.
        """
        band = grid_scr_band(scr_min, weak_below=weak_below, strong_above=strong_above)
        return cls(
            scr=scr_min,
            scr_band=band,
            gfl_gfm_recommendation=grid_gfl_gfm_recommendation(band),
            fault_level_poc_mva=fault_level_poc_min_mva,
            fault_level_case="iec60909_min",
            plant_rating_mva=plant_rating_mva,
            fault_level_poc_max_mva=fault_level_poc_max_mva,
            method=method,
            bankable=False,
            emt_confirmation_required=scr_min < emt_confirmation_scr,
            provenance=provenance,
            notes=notes,
        )


# ─────────────────────────────────────────────────────────────────────────────
# D3 (#874) — steady-state reactive / voltage screen contracts.
#
# The D1 GridStrengthResult answers "is the grid stiff enough (SCR@POC)?"; D3 adds
# the reactive-capability question "can the plant hold the POC power factor / voltage
# inside the grid-code PQ box across the P × grid-voltage operating envelope, and if
# not how many Mvar short is it?". Like GridStrengthResult these are ADVISORY, design-
# stage screens — ``bankable=False`` always: the utility-accepted study is a PSS/E /
# PowerFactory run against the CEB/NSCC confidential grid base case. They therefore
# NEVER feed the finance engine (committed scenarios stay byte-identical / KPI-neutral).
# ─────────────────────────────────────────────────────────────────────────────

_REACTIVE_SCREEN_PROVENANCE = (
    "In-house Python design-stage reactive/voltage screen (pandapower AC load-flow; "
    "POC transformer + collector equivalent; per-resource Q-limits from the reactive-"
    "capability curve). NOT the utility-accepted bankable grid-connection study — "
    "CEB/NSCC require PSS/E or PowerFactory against their confidential grid base case."
)


@dataclass(frozen=True)
class ReactiveCapabilityResult(ContractMixin):
    """Advisory reactive-capability / PQ-box screen at the POC (issue #874).

    Reports whether the aggregate plant can meet the grid-code reactive requirement at
    the point of connection — expressed as the required ``pf_range`` (equivalently a
    ±Q(P) capability box) — over the worst operating point of the P × grid-voltage
    sweep. It is an ADVISORY only (``bankable=False``); it never feeds the finance
    engine.

    Fields
        pf_required_min / pf_required_max: the grid-code power-factor limits (signed;
            e.g. -0.95 lagging / +0.95 leading) the plant must be able to hold at the POC.
        mvar_required: the Mvar the grid code demands at the governing operating point
            (the ± capability the PQ box requires at that P, given the pf limit).
        mvar_available: the Mvar the plant can actually deliver at that operating point
            (sum of per-resource reactive headroom after the collector/transformer path).
        mvar_shortfall: ``max(0, mvar_required - mvar_available)`` — the Mvar gap the
            plant must close (0.0 when the plant meets the requirement). This is the
            sizing figure for any additional reactive plant (STATCOM / MSC).
        pf_at_poc: the achievable power factor at the POC at the governing operating
            point (signed; the sign follows the reactive-flow direction convention).
        inside_pq_box: True iff the plant stays inside the required PQ box at EVERY
            swept operating point (``mvar_shortfall == 0`` across the whole sweep) AND
            the governing corner's load-flow converged — a non-converged governing corner
            is a binding failure and forces this False.
        governing_p_mw / governing_grid_v_pu: the P (MW) and grid voltage (pu) of the
            worst-case operating point that set ``mvar_shortfall`` (the binding corner).
        governing_converged: whether the load-flow converged at the governing corner.
            False = the screen could not place the operating point (binding failure).
    """

    pf_required_min: float
    pf_required_max: float
    mvar_required: float
    mvar_available: float
    mvar_shortfall: float
    pf_at_poc: float
    inside_pq_box: bool
    governing_p_mw: float | None = None
    governing_grid_v_pu: float | None = None
    governing_converged: bool = True
    method: str = "pandapower_runpp"  # "pandapower_runpp" | "closed_form"
    bankable: bool = False
    provenance: str = _REACTIVE_SCREEN_PROVENANCE
    notes: str = ""

    @classmethod
    def from_screen(
        cls,
        *,
        pf_required_min: float,
        pf_required_max: float,
        mvar_required: float,
        mvar_available: float,
        pf_at_poc: float,
        governing_p_mw: float | None = None,
        governing_grid_v_pu: float | None = None,
        governing_converged: bool = True,
        method: str = "pandapower_runpp",
        provenance: str = _REACTIVE_SCREEN_PROVENANCE,
        notes: str = "",
    ) -> "ReactiveCapabilityResult":
        """Build the advisory reactive result, deriving the shortfall + PQ-box verdict.

        ``mvar_shortfall`` is ``max(0, mvar_required - mvar_available)``. A non-converged
        governing corner (``governing_converged=False``) is a BINDING failure: the shortfall
        is escalated to at least the full reactive demand and ``inside_pq_box`` is forced
        False (the screen could not place the operating point, so the plant is NOT provably
        compliant). ``inside_pq_box`` is otherwise True iff the shortfall is zero.
        ``bankable`` is always ``False`` for an in-house Python screen.
        """
        shortfall = max(0.0, float(mvar_required) - float(mvar_available))
        if not governing_converged:
            # Binding failure: the load-flow could not place the governing operating point,
            # so the reactive gap is at least the full demand there and the plant cannot be
            # certified inside the PQ box by this screen.
            shortfall = max(shortfall, float(mvar_required))
        return cls(
            pf_required_min=pf_required_min,
            pf_required_max=pf_required_max,
            mvar_required=mvar_required,
            mvar_available=mvar_available,
            mvar_shortfall=shortfall,
            pf_at_poc=pf_at_poc,
            inside_pq_box=bool(governing_converged) and shortfall <= 0.0,
            governing_p_mw=governing_p_mw,
            governing_grid_v_pu=governing_grid_v_pu,
            governing_converged=governing_converged,
            method=method,
            bankable=False,
            provenance=provenance,
            notes=notes,
        )


@dataclass(frozen=True)
class PowerFlowResult(ContractMixin):
    """Advisory steady-state AC load-flow snapshot at the governing operating point (#874).

    Captures the pandapower ``runpp`` outcome for the worst-case operating point of the
    reactive screen's P × grid-voltage sweep: the bus voltages (pu), the achieved POC
    power factor, and whether the solve converged. ADVISORY only (``bankable=False``);
    a non-converged solve (``converged=False``) means the screen could not place the
    operating point and its reactive verdict for that corner is unreliable.

    Fields
        converged: True iff the pandapower load-flow solved at the governing point.
        bus_voltages_pu: bus-name → voltage-magnitude (pu) at the governing point.
        poc_voltage_pu: the POC busbar voltage magnitude (pu) at the governing point.
        poc_pf: the achieved power factor at the POC (signed) at the governing point.
        governing_p_mw / governing_grid_v_pu: the operating point this snapshot is for.
    """

    converged: bool
    bus_voltages_pu: dict[str, float]
    poc_voltage_pu: float
    poc_pf: float
    governing_p_mw: float | None = None
    governing_grid_v_pu: float | None = None
    method: str = "pandapower_runpp"
    bankable: bool = False
    provenance: str = _REACTIVE_SCREEN_PROVENANCE
    notes: str = ""


@dataclass(frozen=True)
class GridStudyResult(ContractMixin):
    """Bundled advisory grid interconnection study for the POC (issue #874).

    The single composite the D3 gateway (:func:`analytics.grid.evaluate_grid.evaluate_grid`)
    returns: the D1 SCR/grid-strength screen plus the D3 reactive-capability + power-flow
    screens, tied to one POC. Every sub-screen is design-stage advisory
    (``bankable=False``) and none of them feeds the finance engine, so committed
    scenarios remain byte-identical (KPI-neutral).

    Fields
        strength: the D1 :class:`GridStrengthResult` (SCR@POC → GFL/GFM/EMT screen).
        reactive: the D3 :class:`ReactiveCapabilityResult` (PQ-box / Mvar-shortfall
            screen); ``None`` when the reactive screen was not run (e.g. missing config).
        power_flow: the D3 :class:`PowerFlowResult` snapshot at the governing operating
            point; ``None`` when the reactive screen did not run.
        study_enabled: echoes ``grid.study_enabled`` — the master default-off gate.
        poc_bus_name: the POC busbar identifier the study is tied to.
    """

    strength: "GridStrengthResult"
    reactive: "ReactiveCapabilityResult | None" = None
    power_flow: "PowerFlowResult | None" = None
    study_enabled: bool = False
    poc_bus_name: str | None = None
    bankable: bool = False
    provenance: str = ""
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# D5b (#880) — static hybrid POC aggregation contract.
#
# The D1/D3/D4 screens above characterise ONE resource (or one flat aggregate) at the
# POC. A hybrid plant puts MULTIPLE converter-interfaced resources (wind + solar + BESS)
# behind ONE point of connection, and two POC-level metrics only exist for the *combined*
# fleet — they are NOT a single-tech box:
#
#   * a COMPOSITE / weighted SCR (WSCR): every IBR MW added behind the POC shares the same
#     upstream fault level, so stacking solar/BESS behind a wind POC LOWERS the effective
#     SCR each inverter sees (fault level ÷ TOTAL IBR MVA). A BESS PCS additionally
#     STIFFENS the grid (adds to the fault level), so it enters both the numerator (as a
#     fault-current source) and the denominator (as IBR MVA); and
#   * an AGGREGATE Q(P,V) capability envelope: the plant's reactive headroom at the POC is
#     the VECTOR SUM of each resource's ±Q (from its D4b/c/d plug-in) MINUS the reactive
#     absorbed by the collector network + POC transformer between the resources and the
#     POC — never a single resource's box.
#
# Like every grid screen this is design-stage ADVISORY (``bankable=False``): it never
# feeds the finance engine, so committed scenarios stay byte-identical (KPI-neutral).
# ─────────────────────────────────────────────────────────────────────────────

_POC_AGGREGATION_PROVENANCE = (
    "In-house Python design-stage STATIC hybrid-POC aggregation (weighted/composite SCR "
    "over the combined IBR fleet behind one POC; aggregate ±Q(P) reactive envelope = "
    "vector sum of the per-tech D4b/c/d plug-in headroom MINUS the collector + POC-"
    "transformer reactive path). Pure static screening — NO ANDES / EMT. NOT the "
    "utility-accepted bankable grid-connection study — CEB/NSCC require PSS/E or "
    "PowerFactory against their confidential grid base case."
)


@dataclass(frozen=True)
class ResourceReactiveContribution(ContractMixin):
    """One resource's reactive + rating contribution to the hybrid POC envelope (#880).

    Pure data — the per-resource line item aggregated (vector-summed) into the plant-level
    :class:`PocCapabilityEnvelope`. Each field is the GROSS contribution at the resource
    terminals (before the collector/transformer reactive path is netted at the POC).

    Fields
        name: the resource identifier (the tech block name / label).
        tech: the resource technology class (``"wind"`` | ``"solar"`` | ``"bess"`` | …).
        rated_mva: the resource's apparent-power rating (MVA) — its IBR-MVA weight in the
            composite-SCR denominator.
        q_available_mvar: the ± reactive headroom (Mvar, symmetric magnitude) this resource
            can present at the POC active-power reference, from its D4b/c/d plug-in
            (a Type-3 DFIG's is the partial-load-narrowed value; a BESS's is SoH-degraded).
        fault_mva_contribution: the resource's contribution to the POC fault level (MVA).
            A BESS PCS adds a real (current-limited) contribution; grid-following wind/solar
            add ≈0 (they ride their current limit and do not stiffen the grid like a
            machine), so they are credited ~nothing here — exactly the D4c anti-optimism rule.
        is_synchronous: whether the resource presents a machine-like (voltage-source) fault
            contribution. Always ``False`` for the modelled IBR fleet (wind/solar/BESS are
            converter-interfaced) — a downstream aggregation must never credit them as a
            synchronous machine, which would OVERSTATE grid strength.
    """

    name: str
    tech: str
    rated_mva: float
    q_available_mvar: float
    fault_mva_contribution: float
    is_synchronous: bool = False


@dataclass(frozen=True)
class PocCapabilityEnvelope(ContractMixin):
    """Advisory STATIC hybrid-POC aggregation for a combined IBR fleet (issue #880).

    Emitted by :func:`analytics.grid.hybrid.poc_aggregation.aggregate_poc_capability` for a
    hybrid plant that puts MULTIPLE converter-interfaced resources (wind + solar + BESS)
    behind ONE point of connection. It reports the two plant-level metrics that only exist
    for the combined fleet:

    1. the COMPOSITE / weighted SCR (``composite_scr``): the upstream fault level at the POC
       (source + every resource's own fault contribution) divided by the TOTAL IBR MVA
       behind the POC. Adding IBR MW behind the POC LOWERS this vs a single-tech SCR — the
       load-bearing hybrid rule. Banded (weak/moderate/strong) exactly like the D1
       :class:`GridStrengthResult`.
    2. the AGGREGATE reactive capability (``aggregate_q_available_mvar``): the VECTOR SUM of
       each resource's ±Q headroom MINUS the reactive absorbed by the collector network +
       POC transformer (``collector_transformer_q_loss_mvar``) — the ±Q the fleet can
       actually present AT THE POC — screened against the grid-code demand there
       (``aggregate_q_required_mvar``) into a Mvar ``aggregate_q_shortfall_mvar`` + PQ-box
       verdict (``inside_pq_box``).

    ADVISORY only (``bankable=False``): a pure STATIC screen (no ANDES / EMT); it never
    feeds the finance engine, so committed scenarios stay byte-identical (KPI-neutral).

    Fields
        contributions: the per-resource :class:`ResourceReactiveContribution` line items
            aggregated into the plant-level metrics (the audit trail of the vector sum).
        total_ibr_mva: the TOTAL IBR apparent-power behind the POC (Σ resource rated_mva) —
            the composite-SCR denominator.
        source_fault_level_mva: the upstream (grid source) fault level at the POC (MVA).
        aggregate_fault_level_mva: the total POC fault level = source + Σ resource fault
            contributions (a BESS PCS stiffens it; grid-following wind/solar add ≈0).
        composite_scr: the weighted/composite SCR = ``aggregate_fault_level_mva`` /
            ``total_ibr_mva`` (LOWER than a single-tech SCR because the whole fleet shares
            one fault level).
        scr_band / gfl_gfm_recommendation: the composite-SCR band + GFL/GFM recommendation
            (same thresholds/logic as the D1 grid-strength screen).
        gross_q_available_mvar: the Σ of the resources' ±Q headroom BEFORE the collector/
            transformer reactive path is netted.
        collector_transformer_q_loss_mvar: the reactive (Mvar) absorbed by the collector
            network + POC transformer between the resources and the POC (subtracted from
            the gross reactive to give the AT-POC headroom).
        aggregate_q_available_mvar: the ± reactive the fleet can present AT THE POC =
            ``max(0, gross_q_available_mvar - collector_transformer_q_loss_mvar)``.
        aggregate_q_required_mvar: the Mvar the grid code demands at the POC reference P.
        aggregate_q_shortfall_mvar: ``max(0, required - available)`` — the STATCOM/MSC
            sizing figure for the WHOLE hybrid plant at the POC.
        inside_pq_box: True iff the aggregate available reactive meets the demand
            (``aggregate_q_shortfall_mvar == 0``).
        reference_p_mw: the POC active-power reference the reactive demand is evaluated at.
        pf_required_min / pf_required_max: the grid-code pf limits (signed) the plant holds.
        n_resources: the number of resources aggregated behind the POC.
    """

    contributions: tuple["ResourceReactiveContribution", ...]
    total_ibr_mva: float
    source_fault_level_mva: float
    aggregate_fault_level_mva: float
    composite_scr: float
    scr_band: str
    gfl_gfm_recommendation: str
    gross_q_available_mvar: float
    collector_transformer_q_loss_mvar: float
    aggregate_q_available_mvar: float
    aggregate_q_required_mvar: float
    aggregate_q_shortfall_mvar: float
    inside_pq_box: bool
    reference_p_mw: float
    pf_required_min: float
    pf_required_max: float
    n_resources: int = 0
    method: str = "static_poc_aggregation"
    bankable: bool = False
    provenance: str = _POC_AGGREGATION_PROVENANCE
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# D4a (#875) — RMS ride-through (fault-ride-through) dynamics contract.
#
# The reactive/SCR screens above are STEADY-STATE; D4a adds the DYNAMIC question:
# "does the plant ride through a voltage dip (LVRT) / swell (HVRT) / frequency
# excursion, per the grid-code envelope?". The dynamics core
# (:mod:`analytics.grid.ride_through`) runs one generic WECC IBR RMS case per kind
# through ANDES and reports whether the time-domain solve rode it through. Like the
# other grid screens this is design-stage ADVISORY (``bankable=False``): the generic
# WECC model is NOT the OEM-certified ``.dyr``/``.dll``, and a true FRT compliance
# study is an EMT (PSCAD/EMTP) run against the utility base case. It NEVER feeds the
# finance engine (committed scenarios stay byte-identical / KPI-neutral).
# ─────────────────────────────────────────────────────────────────────────────

_RIDE_THROUGH_PROVENANCE = (
    "In-house Python design-stage RMS ride-through screen (ANDES positive-sequence "
    "time-domain; GENERIC WECC IBR model — REGCA1/REECA1/REPCA1 — NOT the OEM-certified "
    ".dyr/.dll). Screening-grade: a true fault-ride-through compliance study is an EMT "
    "(PSCAD/EMTP) run against the utility's confidential base case with the OEM binaries. "
    "NOT the utility-accepted bankable connection study."
)

_RIDE_THROUGH_DISCLAIMER = (
    "GENERIC WECC model, NOT the OEM-certified .dyr/.dll — advisory screening only; "
    "confirm with an EMT FRT study against the utility base case."
)


@dataclass(frozen=True)
class RideThroughResult(ContractMixin):
    """Advisory RMS ride-through (fault-ride-through) screen for one case (issue #875).

    Emitted by :mod:`analytics.grid.ride_through` for one of the three grid-code
    ride-through cases — ``"lvrt"`` (voltage dip), ``"hvrt"`` (voltage swell), or
    ``"frequency"`` (a frequency excursion). It reports whether the ANDES RMS
    time-domain solve rode the disturbance through, using the GENERIC WECC IBR model.
    ADVISORY only (``bankable=False``): the generic model is not the OEM-certified
    ``.dyr``/``.dll`` and a true FRT study is an EMT run — the ``disclaimer`` field
    carries that caveat. It never feeds the finance engine (KPI-neutral).

    Fields
        case: the ride-through case kind (``"lvrt"`` | ``"hvrt"`` | ``"frequency"``).
        ran: True iff the ANDES RMS solve was actually EXECUTED for this case (the
            dynamic-study gate was on AND a candidate ANDES case loaded and the TDS ran).
            It stays True for an early-terminated / diverged solve — the solver DID run, it
            just did not exit cleanly. It is False whenever the gate was off (envelope
            parsed / case set up but ANDES not run) or every candidate case failed to
            LOAD/SET UP (a genuine setup failure — no network could be built to attempt the
            solve). ``ran`` says only "did the solver run" — it is NOT a compliance verdict;
            read ``rode_through`` for that.
        converged: raw RMS-solve SMOKE TEST — whether the ANDES time-domain solve exited
            cleanly (``exit_code == 0``). Convergence is necessary but NOT sufficient for
            ride-through: a solve can converge to a state where the IBR has tripped or the
            bus voltage has collapsed/failed to recover. NEVER read convergence as
            compliance. False when the solve did not run, diverged, or terminated early on
            a stability-criteria violation.
        rode_through: the COMPLIANCE VERDICT. True = the disturbance was ridden through.
            False = a real breach — this covers BOTH a cleanly converged solve that did not
            recover / tripped the IBR (graded on the PHYSICAL ENVELOPE: post-fault recovered
            bus voltage vs the entry threshold + IBR-trip detection), AND an
            UNSTABLE / early-terminated / diverged LVRT solve under an APPLIED fault (the
            solve blew up because the bus collapsed — the plant did not ride through). It is
            NEVER read from the raw ``converged`` flag. ``None`` = NOT-RUN / UNSUPPORTED: the
            disturbance was not modeled (unmodeled HVRT / frequency), the dynamic-study gate
            was off, or a genuine case-setup failure meant no solve could be attempted at
            all. An honest ``None`` is preferred over a spurious ``True``, but a diverged
            solve under an applied fault is evidence of FAILURE (False), not absence of
            evidence (None).
        target_pu: the voltage ride-through threshold (pu) the case probes — the LVRT /
            HVRT entry pu (``None`` for the frequency case).
        target_hz: the frequency (Hz) the frequency case probes (``None`` for voltage
            cases).
        k_factor: the fault-current (reactive) injection gain the grid code demands for
            this case (0.0 for the frequency case).
        min_voltage_pu / max_voltage_pu: the deepest / highest bus voltage (pu) over the
            simulation — the depth of the dip / height of the swell the IBRs rode
            (``None`` when the solve did not run).
        freq_extreme_hz: the measured frequency EXTREME (Hz) — the nadir/zenith furthest
            from nominal — for the ``"frequency"`` case (``None`` for the voltage cases and
            when the frequency solve did not run). This is the physically-measured dynamic
            nadir the D5c combined-frequency study surfaces instead of a NOT-RUN.
        n_devices: the number of WECC IBR / synchronous devices on the dynamics case.
        disclaimer: the fixed "generic WECC model, NOT the OEM-certified .dyr/.dll"
            caveat (a distinct field so downstream reports cannot drop it).
    """

    case: str
    ran: bool
    converged: bool
    rode_through: bool | None = None
    target_pu: float | None = None
    target_hz: float | None = None
    k_factor: float = 0.0
    min_voltage_pu: float | None = None
    max_voltage_pu: float | None = None
    freq_extreme_hz: float | None = None
    n_devices: int = 0
    method: str = "andes_rms"
    bankable: bool = False
    disclaimer: str = _RIDE_THROUGH_DISCLAIMER
    provenance: str = _RIDE_THROUGH_PROVENANCE
    detail: str = ""

    @classmethod
    def from_case(
        cls,
        *,
        case: str,
        ran: bool,
        converged: bool,
        rode_through: bool | None = None,
        target_pu: float | None = None,
        target_hz: float | None = None,
        k_factor: float = 0.0,
        min_voltage_pu: float | None = None,
        max_voltage_pu: float | None = None,
        freq_extreme_hz: float | None = None,
        n_devices: int = 0,
        method: str = "andes_rms",
        provenance: str = _RIDE_THROUGH_PROVENANCE,
        detail: str = "",
    ) -> "RideThroughResult":
        """Build the advisory ride-through result for one case.

        ``bankable`` is always ``False`` (in-house generic-WECC screen) and the fixed
        OEM-model ``disclaimer`` is always stamped, so no downstream emitter can present
        the screen as a certified FRT compliance result. ``rode_through`` is the
        envelope-derived compliance verdict (``None`` = NOT-RUN / UNSUPPORTED); it is NOT
        defaulted from ``converged`` — the caller must pass the physically-derived value.
        """
        return cls(
            case=case,
            ran=bool(ran),
            converged=bool(converged),
            rode_through=rode_through,
            target_pu=target_pu,
            target_hz=target_hz,
            k_factor=k_factor,
            min_voltage_pu=min_voltage_pu,
            max_voltage_pu=max_voltage_pu,
            freq_extreme_hz=freq_extreme_hz,
            n_devices=n_devices,
            method=method,
            bankable=False,
            disclaimer=_RIDE_THROUGH_DISCLAIMER,
            provenance=provenance,
            detail=detail,
        )


# ─────────────────────────────────────────────────────────────────────────────
# D5a (#879) — shared BESS state-of-charge model + reserve-split accounting.
#
# The grid-capability plug-ins above answer converter/PQ questions at a POINT in
# time; D5a adds the ENERGY-ACCOUNTING question that every downstream multi-service
# BESS study (firming, frequency response, curtailment absorption — D5c/D6) must
# share: given the battery's usable energy at a state-of-charge, how much MWh can be
# committed to each reserve, and can the SAME MWh be claimed by more than one service?
#
# The FOUNDATIONAL invariant this contract centralizes: the sum of the reserves
# allocated in a given flow direction MUST NOT exceed the usable headroom in that
# direction at the given SoC — a request that exceeds it is REJECTED with an explicit
# shortfall, NEVER silently over-allocated (NO SPURIOUS PASS). Discharge services
# (firming + frequency-response down-regulation / droop discharge) draw from the
# energy ABOVE the min-SoC floor; curtailment-absorption charges into the room BELOW
# the max-SoC ceiling. The two directions are physically distinct energy pools, so a
# split is feasible only when BOTH directions clear.
#
# Like the other grid contracts these are design-stage ADVISORY (``bankable=False``)
# and NEVER feed the finance engine, so committed scenarios stay byte-identical
# (KPI-neutral). A later dolphin (D5c/D6) wires this SoC model into the multi-service
# dispatch; here it is a standalone, config-level accounting contract.
# ─────────────────────────────────────────────────────────────────────────────

_BESS_SOC_PROVENANCE = (
    "In-house Python design-stage BESS state-of-charge + reserve-split accounting: "
    "usable energy = nameplate * SoH, bounded by the [min_soc, max_soc] operating "
    "window; multi-service reserves (firming / frequency-response / curtailment "
    "absorption) allocated against the direction-specific headroom with a strict "
    "no-double-count energy invariant. Advisory / config-level ONLY — NOT a dispatch "
    "optimisation and NOT the utility-accepted bankable study."
)


# ─────────────────────────────────────────────────────────────────────────────
# D7 (#883) — harmonics / flicker + frequency-headroom SCR-coupled screen contract.
#
# The SCR / reactive / ride-through screens above answer stiffness, steady-state
# reactive and dynamic ride-through. D7 adds the POWER-QUALITY question, and it is
# EXPLICITLY SCR-COUPLED: harmonic voltage distortion and flicker Pst at the POC
# both WORSEN as the SCR (grid stiffness) drops, because the injected harmonic
# current and flicker current see a weaker (higher-impedance) grid. The screen also
# indexes the IEEE 519:2022 voltage/current-distortion limits by the D1 Isc/IL (SCR)
# ratio — the limit table is itself a function of grid stiffness — and sizes the
# frequency-response de-load / droop headroom (energy foregone) from the grid-code
# frequency ride-through band. Like every other grid screen this is design-stage
# ADVISORY (``bankable=False``); it is a SCREENING APPROXIMATION that DEGRADES as SCR
# falls, NOT a standalone pass/fail — a true harmonic/flicker study is a frequency-
# domain PSS/E or PowerFactory scan against the utility's confidential harmonic base
# case with the OEM current-emission spectra. It NEVER feeds the finance engine
# (committed scenarios stay byte-identical / KPI-neutral).
# ─────────────────────────────────────────────────────────────────────────────

_HARMONIC_SCREEN_PROVENANCE = (
    "In-house Python design-stage harmonics/flicker + frequency-headroom screen "
    "(SCR-coupled Zbus(h) harmonic-voltage estimate vs IEEE 519:2022 limits indexed by "
    "Isc/IL; IEC 61400-21 flicker Pst from POC Ssc; frequency-response de-load/droop "
    "headroom from the grid-code ride-through band). SCREENING APPROXIMATION that "
    "DEGRADES as SCR falls — NOT a standalone pass/fail and NOT the utility-accepted "
    "bankable study (CEB/NSCC require a frequency-domain PSS/E or PowerFactory harmonic "
    "scan against their confidential base case with the OEM current-emission spectra)."
)

_HARMONIC_SCREEN_DISCLAIMER = (
    "SCR-COUPLED SCREENING APPROXIMATION — harmonic voltage + flicker WORSEN as SCR "
    "drops; degrades as the grid weakens. NOT a standalone pass/fail; confirm with a "
    "frequency-domain harmonic study against the utility base case."
)

_CURTAILMENT_SHARE_PROVENANCE = (
    "In-house Python design-stage OpenDSSDirect QSTS (quasi-static time-series) "
    "curtailment split: per-tech generation profiles injected against a REAL feeder "
    "model (load-flow feasibility solved), curtailed energy integrated over the year and "
    "split into DEEMED-PAID (grid-instructed — an EXPLICIT committed operator/feeder-limit "
    "schedule, NOT a monitor heuristic — paid as deemed energy under the CEB SPPA, so "
    "KPI-neutral) vs SELF-CURTAILED (physical export-cap shed of the injected generation — "
    "a real energy loss), with export-cap surplus optionally recovered into the shared BESS "
    "SoC (energy-conserved). ADVISORY / config-level ONLY — a synthetic/demo feeder is a "
    "smoke test that NEVER overwrites the real loss placeholder, and this result NEVER "
    "feeds the finance engine here (D6b wires the self-curtailment loss). NOT the "
    "utility-accepted bankable hosting-capacity study (that is a QSTS against the TSO base "
    "feeder with the OEM inverter models)."
)


@dataclass(frozen=True)
class BessSocState(ContractMixin):
    """The usable-energy picture of a BESS at one state-of-charge (issue #879).

    A pure energy-accounting snapshot shared by every multi-service BESS study so the
    SAME usable-capacity / headroom numbers are computed ONCE, not re-derived (and
    subtly diverged) per service. ADVISORY / config-level (``bankable=False``); it
    never feeds the finance engine.

    All energies are MWh at the AC terminals (round-trip efficiency is a dispatch-layer
    concern, out of scope for this static accounting snapshot).

    Fields
        nameplate_energy_mwh: the BESS nameplate (beginning-of-life) energy rating.
        soh_fraction: the state-of-health fraction in (0, 1] applied to the nameplate
            to get the usable energy at this point in life.
        usable_energy_mwh: ``nameplate_energy_mwh * soh_fraction`` — the SoH-degraded
            usable energy that the operating SoC window is taken against.
        soc_fraction: the state-of-charge fraction in [0, 1] (fraction of usable energy
            currently stored).
        min_soc_fraction / max_soc_fraction: the operating SoC window [floor, ceiling]
            (fractions in [0, 1], floor < ceiling) the battery is held within.
        stored_energy_mwh: ``usable_energy_mwh * soc_fraction`` — energy currently stored.
        dischargeable_mwh: energy available to DISCHARGE before hitting the min-SoC floor
            (``max(0, (soc - min_soc)) * usable_energy_mwh``) — the pool firming and
            frequency-response down/droop-discharge reserves compete for.
        chargeable_mwh: room available to CHARGE before hitting the max-SoC ceiling
            (``max(0, (max_soc - soc)) * usable_energy_mwh``) — the pool
            curtailment-absorption competes for.
    """

    nameplate_energy_mwh: float
    soh_fraction: float
    usable_energy_mwh: float
    soc_fraction: float
    min_soc_fraction: float
    max_soc_fraction: float
    stored_energy_mwh: float
    dischargeable_mwh: float
    chargeable_mwh: float
    method: str = "closed_form"
    bankable: bool = False
    provenance: str = _BESS_SOC_PROVENANCE
    notes: str = ""


@dataclass(frozen=True)
class ReserveSplitResult(ContractMixin):
    """Advisory allocation of a BESS's usable energy across competing reserves (#879).

    Enforces the FOUNDATIONAL no-double-count energy invariant: the SAME MWh cannot be
    claimed by firming AND frequency-response AND curtailment-absorption at once. Each
    service is allocated against the headroom in its flow direction (discharge services
    against ``dischargeable_mwh``; curtailment-absorption against ``chargeable_mwh``),
    and a request whose direction-total EXCEEDS that headroom is REJECTED — ``feasible``
    is False and the per-direction shortfall is reported (NO SPURIOUS PASS: the split is
    never silently over-allocated). ADVISORY / config-level (``bankable=False``); it
    never feeds the finance engine.

    Fields
        soc: the :class:`BessSocState` the split is evaluated against.
        firming_request_mwh / frequency_request_mwh: the requested DISCHARGE-direction
            reserves (MWh) for firming and frequency response.
        curtailment_request_mwh: the requested CHARGE-direction reserve (MWh) for
            curtailment absorption.
        firming_allocated_mwh / frequency_allocated_mwh / curtailment_allocated_mwh:
            the MWh actually allocatable to each service WITHOUT breaching its direction's
            headroom. On a feasible split each equals its request; on an infeasible split
            the granted MWh are clamped to the available headroom (never over-allocated).
        discharge_requested_mwh / discharge_available_mwh / discharge_shortfall_mwh: the
            total requested vs available vs missing MWh in the DISCHARGE direction
            (firming + frequency vs ``dischargeable_mwh``).
        charge_requested_mwh / charge_available_mwh / charge_shortfall_mwh: the same for
            the CHARGE direction (curtailment vs ``chargeable_mwh``).
        feasible: True iff BOTH directions clear (every reserve is fully covered by its
            direction's headroom — zero shortfall in each direction). A single MWh is
            NEVER counted toward more than one service, so the invariant
            (Σ discharge reserves ≤ dischargeable) AND (Σ charge reserves ≤ chargeable)
            holds by construction whenever ``feasible`` is True.
    """

    soc: "BessSocState"
    firming_request_mwh: float
    frequency_request_mwh: float
    curtailment_request_mwh: float
    firming_allocated_mwh: float
    frequency_allocated_mwh: float
    curtailment_allocated_mwh: float
    discharge_requested_mwh: float
    discharge_available_mwh: float
    discharge_shortfall_mwh: float
    charge_requested_mwh: float
    charge_available_mwh: float
    charge_shortfall_mwh: float
    feasible: bool
    method: str = "closed_form"
    bankable: bool = False
    provenance: str = _BESS_SOC_PROVENANCE
    notes: str = ""


@dataclass(frozen=True)
class HarmonicComplianceResult(ContractMixin):
    """Advisory SCR-coupled harmonics / flicker + frequency-headroom screen (issue #883).

    Emitted by :mod:`analytics.grid.harmonics` (with the frequency-headroom sizing from
    :mod:`analytics.grid.frequency_response`). Reports, at the POC:

      1. the worst per-order harmonic voltage distortion (``V_h = |Zbus(h)| · I_h`` from an
         OEM/config current-emission spectrum) and the total harmonic voltage distortion
         (THD_v), each compared to the IEEE 519:2022 voltage-distortion limits that are
         INDEXED by the D1 Isc/IL (SCR) ratio;
      2. the IEC 61400-21 short-term flicker ``Pst`` at the POC from the plant's flicker
         coefficient and the POC short-circuit apparent power ``Ssc``; and
      3. the frequency-response de-load / droop headroom (MW held in reserve + the annual
         ENERGY FOREGONE, MWh/yr) implied by the grid-code frequency ride-through band.

    EXPLICITLY SCR-COUPLED: both the harmonic voltage and the flicker Pst scale INVERSELY
    with grid stiffness — as the SCR (equivalently ``Ssc``) drops, the same injected
    harmonic / flicker current produces a LARGER POC voltage disturbance, so the screen
    verdict DEGRADES. It is a SCREENING APPROXIMATION, NOT a standalone pass/fail, and is
    ADVISORY only (``bankable=False``); it never feeds the finance engine (KPI-neutral).

    Fields
        scr: the short-circuit ratio the screen is coupled to (from the D1 SCR screen);
            lower SCR ⇒ higher harmonic voltage + flicker.
        isc_il_ratio: the IEEE 519 Isc/IL ratio (short-circuit current ÷ plant load
            current at the POC) that INDEXES the distortion-limit table.
        worst_harmonic_order: the harmonic order (h) with the largest voltage distortion.
        worst_harmonic_voltage_pct: the worst per-order harmonic voltage V_h (% of nominal).
        harmonic_voltage_limit_pct: the IEEE 519:2022 individual-harmonic voltage limit
            (%) at the plant's voltage level (the per-order compliance yardstick).
        thd_voltage_pct: total harmonic voltage distortion at the POC (% of nominal).
        thd_voltage_limit_pct: the IEEE 519:2022 THD_v limit (%) at the plant's voltage.
        current_tdd_pct: total demand distortion of the injected harmonic current (% of IL).
        current_tdd_limit_pct: the IEEE 519:2022 current-TDD limit (%) INDEXED by
            ``isc_il_ratio`` (a weaker grid ⇒ a lower allowed TDD).
        flicker_pst: the IEC 61400-21 short-term flicker severity at the POC.
        flicker_pst_limit: the flicker Pst planning limit (typically 0.35 at HV).
        poc_ssc_mva: the POC short-circuit apparent power (MVA) the flicker / harmonic
            voltage are referred to (the SCR coupling term).
        harmonic_within_limits / flicker_within_limits: per-domain SCREENING verdicts —
            True iff the estimate sits within the (SCR-indexed) limit. ``None`` when the
            screen could not evaluate that domain (missing spectrum / flicker coefficient)
            — an honest NOT-RUN, never a spurious pass.
        freq_response_headroom_mw: the MW of active-power reserve the grid-code droop /
            de-load requirement holds back (the frequency-response headroom).
        energy_foregone_mwh_yr: the annual energy (MWh/yr) foregone to hold that headroom
            (the de-load opportunity cost) — a SIZING figure, advisory only.
        method: the screen method (``"pandapower_zbus"`` when the frequency-domain
            bus-impedance scan ran, else ``"closed_form"``).
        disclaimer: the fixed SCR-coupled-screening caveat (a distinct field so downstream
            reports cannot drop it).
    """

    scr: float
    isc_il_ratio: float
    worst_harmonic_order: int | None
    worst_harmonic_voltage_pct: float | None
    harmonic_voltage_limit_pct: float
    thd_voltage_pct: float | None
    thd_voltage_limit_pct: float
    current_tdd_pct: float | None
    current_tdd_limit_pct: float
    flicker_pst: float | None
    flicker_pst_limit: float
    poc_ssc_mva: float
    harmonic_within_limits: bool | None = None
    flicker_within_limits: bool | None = None
    freq_response_headroom_mw: float | None = None
    energy_foregone_mwh_yr: float | None = None
    method: str = "closed_form"
    bankable: bool = False
    disclaimer: str = _HARMONIC_SCREEN_DISCLAIMER
    provenance: str = _HARMONIC_SCREEN_PROVENANCE
    notes: str = ""

    @classmethod
    def from_screen(
        cls,
        *,
        scr: float,
        isc_il_ratio: float,
        worst_harmonic_order: int | None,
        worst_harmonic_voltage_pct: float | None,
        harmonic_voltage_limit_pct: float,
        thd_voltage_pct: float | None,
        thd_voltage_limit_pct: float,
        current_tdd_pct: float | None,
        current_tdd_limit_pct: float,
        flicker_pst: float | None,
        flicker_pst_limit: float,
        poc_ssc_mva: float,
        freq_response_headroom_mw: float | None = None,
        energy_foregone_mwh_yr: float | None = None,
        method: str = "closed_form",
        provenance: str = _HARMONIC_SCREEN_PROVENANCE,
        notes: str = "",
    ) -> "HarmonicComplianceResult":
        """Build the advisory harmonics/flicker result, deriving the per-domain verdicts.

        The per-domain SCREENING verdicts are derived from PHYSICAL evidence, never
        assumed:

          * ``harmonic_within_limits`` is ``None`` (NOT-RUN) when neither a worst-order
            harmonic voltage NOR a THD_v estimate is available (no current-emission
            spectrum was supplied) — an honest NOT-RUN, not a spurious pass. Otherwise it
            is True iff BOTH the worst per-order V_h ≤ the IEEE 519 individual limit AND
            the THD_v ≤ the THD_v limit AND (when a current TDD was computed) the current
            TDD ≤ the SCR-indexed current-TDD limit.
          * ``flicker_within_limits`` is ``None`` (NOT-RUN) when no flicker Pst could be
            computed (no flicker coefficient), else True iff ``flicker_pst`` ≤ the limit.

        ``bankable`` is always ``False`` (in-house SCR-coupled screen) and the fixed
        SCR-coupled-screening ``disclaimer`` is always stamped.
        """
        harmonic_verdict: bool | None
        if worst_harmonic_voltage_pct is None and thd_voltage_pct is None:
            harmonic_verdict = None
        else:
            ok = True
            if worst_harmonic_voltage_pct is not None:
                ok = ok and worst_harmonic_voltage_pct <= harmonic_voltage_limit_pct
            if thd_voltage_pct is not None:
                ok = ok and thd_voltage_pct <= thd_voltage_limit_pct
            if current_tdd_pct is not None:
                ok = ok and current_tdd_pct <= current_tdd_limit_pct
            harmonic_verdict = ok

        flicker_verdict: bool | None
        if flicker_pst is None:
            flicker_verdict = None
        else:
            flicker_verdict = flicker_pst <= flicker_pst_limit

        return cls(
            scr=scr,
            isc_il_ratio=isc_il_ratio,
            worst_harmonic_order=worst_harmonic_order,
            worst_harmonic_voltage_pct=worst_harmonic_voltage_pct,
            harmonic_voltage_limit_pct=harmonic_voltage_limit_pct,
            thd_voltage_pct=thd_voltage_pct,
            thd_voltage_limit_pct=thd_voltage_limit_pct,
            current_tdd_pct=current_tdd_pct,
            current_tdd_limit_pct=current_tdd_limit_pct,
            flicker_pst=flicker_pst,
            flicker_pst_limit=flicker_pst_limit,
            poc_ssc_mva=poc_ssc_mva,
            harmonic_within_limits=harmonic_verdict,
            flicker_within_limits=flicker_verdict,
            freq_response_headroom_mw=freq_response_headroom_mw,
            energy_foregone_mwh_yr=energy_foregone_mwh_yr,
            method=method,
            bankable=False,
            disclaimer=_HARMONIC_SCREEN_DISCLAIMER,
            provenance=provenance,
            notes=notes,
        )


# ─────────────────────────────────────────────────────────────────────────────
# D5c (#881) — combined frequency-droop study with an ENPPC plant controller.
#
# The D7 sizer (:mod:`analytics.grid.frequency_response`) answers the STATIC
# de-load COST of a droop obligation; D5c adds the COMBINED-FLEET, EVENT question:
# for a given frequency event Δf, how does the plant power controller SPLIT the
# required P(f) response across the multiple droop-capable groups behind one POC
# (the ENPPC 6-group logic — per-group freq_droop_pct, dispatched in a p_priority
# _order), is each group's share physically deliverable (wind spinning/de-load
# headroom; a BESS group's SOC-limited discharge energy via the ONE shared D5a
# SOC / frequency reserve — no double-count), and does the settling frequency sit
# inside the grid-code ride-through band? Both verdicts (band compliance, response
# adequacy) derive from PHYSICAL evidence, never a solver flag; the un-modelled
# dynamic ANDES nadir is returned NOT-RUN. Like the other grid contracts this is
# design-stage ADVISORY (``bankable=False``): it is NOT a dynamic RMS/EMT
# primary-frequency-response study against the utility base case. It NEVER feeds
# the finance engine (committed scenarios stay byte-identical / KPI-neutral).
# ─────────────────────────────────────────────────────────────────────────────

_FREQ_RESPONSE_PROVENANCE = (
    "In-house Python design-stage COMBINED frequency-droop study with an ENPPC-style "
    "plant controller: a frequency event Δf is split across the droop-capable groups "
    "(per-group freq_droop_pct, dispatched in p_priority_order), each group's "
    "droop-commanded P(f) capped at its physical headroom (wind spinning/de-load; BESS via "
    "the ONE shared D5a SOC / frequency reserve — no double-count), and the settling "
    "frequency screened against the grid-code ride-through band. Closed-form per-group "
    "split + band compliance are physical; the ANDES dynamic nadir is now measured by the "
    "D4b ride-through frequency excursion when the dynamic gate is on (else NOT-RUN). "
    "ADVISORY / design-stage ONLY — NOT a dynamic RMS/EMT "
    "primary-frequency-response study against the utility base case, and NOT bankable."
)


@dataclass(frozen=True)
class GroupDroopContribution(ContractMixin):
    """The P(f) contribution of ONE ENPPC dispatch group for a frequency event (#881).

    A pure line item in the :class:`FreqResponseResult` per-group split — the audit trail of
    the PPC aggregate-fill dispatch: each group's own droop share, the maximum headroom the
    PPC could dispatch it to, and what it actually delivered. ADVISORY / config-level
    (``bankable=False``).

    Fields
        name: the group identifier (from ``ppc.groups[].name`` / its index).
        tech: the group's technology token (``wind`` | ``solar`` | ``bess`` | ...).
        rated_mw: the group's rated active power (MW) — the droop base.
        droop: the group's governor droop fraction (``freq_droop_pct`` / 100).
        commanded_mw: the group's OWN droop share of the plant obligation for this Δf
            (``(|Δf|/f_n)/droop · rated_mw``), a positive magnitude. The PLANT obligation the
            PPC fills is the SUM of these shares; a group may be DISPATCHED above or below its
            own share (up to its headroom) by the PPC to cover the plant residual.
        headroom_mw: the MAXIMUM |ΔP| the PPC could dispatch this group to in the required
            direction (up-regulation = rating minus current output, further SOC-energy-capped
            for a BESS group; down-regulation = current output shed toward zero).
        delivered_mw: the |ΔP| the PPC actually dispatched this group to — its headroom or the
            residual plant obligation still unmet by higher-priority groups, whichever binds.
        soc_limited: True iff a BESS group was DISPATCHED up to its SOC-bound headroom (the
            shared D5a dischargeable ENERGY — not its converter power rating — capped what it
            could deliver). A group the PPC never pushed to its cap is not flagged, so this is
            physical evidence of an actual energy-limited dispatch, not a hypothetical.
    """

    name: str
    tech: str
    rated_mw: float
    droop: float
    commanded_mw: float
    headroom_mw: float
    delivered_mw: float
    soc_limited: bool = False


@dataclass(frozen=True)
class FreqResponseResult(ContractMixin):
    """Advisory combined frequency-droop study for a hybrid plant (issue #881).

    Emitted by :mod:`analytics.grid.hybrid.frequency_response`. For a frequency event Δf it
    reports how the ENPPC plant controller met the PLANT-LEVEL P(f) obligation (the SUM of the
    groups' droop shares) by dispatching the droop-capable groups behind one POC in
    ``p_priority_order`` — each group dispatched up to its physical HEADROOM (wind
    spinning/de-load; BESS via the ONE shared D5a SOC / frequency reserve, honouring the
    no-double-count invariant), a higher-priority group covering the shortfall a lower-priority
    group cannot (so the priority order is load-bearing) — the estimated SETTLING frequency,
    and whether it sits inside the grid-code ride-through band.

    Both verdicts are derived from PHYSICAL evidence, never a solver flag:
      * ``band_compliant`` — the settling frequency vs the continuous band. ``None`` (NOT-RUN)
        when there was no command to respond to (no settling point to judge).
      * ``response_adequate`` — the delivered response met the aggregate droop command.
        ``None`` (NOT-RUN) for a zero-deviation / zero-command event.
    The dynamic ANDES frequency nadir is NOT modelled by the D4a core yet (a shunt fault
    cannot apply a frequency excursion), so ``dynamic_nadir_hz`` is an explicit ``None``
    (NOT-RUN) even when the dynamic gate is on — never a fabricated value. ADVISORY only
    (``bankable=False``): a true primary-frequency-response study is a dynamic RMS/EMT run
    against the utility base case. It never feeds the finance engine (KPI-neutral).

    Fields
        contributions: the per-group :class:`GroupDroopContribution` line items, in
            ``p_priority_order`` — the audit trail of the split.
        deviation_hz: the SIGNED event deviation Δf (Hz; negative = under-frequency /
            up-regulation, positive = over-frequency / down-regulation).
        nominal_hz: the nominal system frequency (Hz) the droop is referred to.
        sustain_s: the mandated response sustain window (s) a BESS group's SOC must cover.
        total_commanded_mw / total_delivered_mw: the aggregate droop-commanded vs
            physically-delivered |ΔP| (MW) summed over the groups.
        settling_frequency_hz: the estimated post-response settling frequency (Hz), or
            ``None`` when there was no command to respond to.
        band_under_hz / band_over_hz: the grid-code continuous ride-through band edges (Hz)
            the settling frequency is screened against.
        band_compliant: the settling frequency sits inside the band (``None`` = NOT-RUN).
        response_adequate: the delivered response met the aggregate command
            (``None`` = NOT-RUN for a zero-command event).
        dynamic_ran: whether the ANDES dynamic solve EXECUTED (the D4a frequency case is
            NOT-RUN / unmodelled, so this is False unless a later dolphin models it).
        dynamic_nadir_hz: the measured dynamic frequency nadir/zenith (Hz) — ``None``
            (NOT-RUN) because the frequency-excursion dynamics are not modelled yet.
        n_groups: the number of dispatch groups in the split.
        n_soc_limited: how many BESS groups were SOC-energy-limited (delivered below their
            droop command because their dischargeable energy could not sustain it).
    """

    contributions: tuple["GroupDroopContribution", ...]
    deviation_hz: float
    nominal_hz: float
    sustain_s: float
    total_commanded_mw: float
    total_delivered_mw: float
    settling_frequency_hz: float | None
    band_under_hz: float
    band_over_hz: float
    band_compliant: bool | None = None
    response_adequate: bool | None = None
    dynamic_ran: bool = False
    dynamic_nadir_hz: float | None = None
    n_groups: int = 0
    n_soc_limited: int = 0
    method: str = "enppc_group_droop"
    bankable: bool = False
    provenance: str = _FREQ_RESPONSE_PROVENANCE
    notes: str = ""


@dataclass(frozen=True)
class CurtailmentShareResult(ContractMixin):
    """Advisory QSTS curtailment split — deemed-paid vs self-curtailed (issue #882).

    Emitted by :mod:`analytics.grid.curtailment_qsts`. A hybrid plant behind ONE export
    cap loses energy for two physically distinct reasons, and the CEB SPPA treats them
    OPPOSITELY, so they MUST be split:

      (a) **deemed-paid / grid-instructed** curtailment — an operator dispatch /
          upstream-feeder-limit instruction. Under the CEB standardised PPA this is PAID as
          *deemed energy*, so it must NOT haircut revenue → KPI-NEUTRAL. It is an EXPLICIT
          INPUT (the committed ``grid.qsts.grid_instructed_profile_mw`` schedule, or zeros),
          NOT inferred from a QSTS monitor heuristic — deriving it from an export-cap breach
          would double-count the plant's own self-curtailment. Reported for the record; never
          subtracted from generation.
      (b) **self-curtailed** — the plant physically sheds its OWN excess above the export
          cap (the combined instantaneous output exceeds the POC export limit and there is
          nowhere for the surplus to go). This is a REAL energy loss — the SOLE future
          KPI-mover — but it is NOT wired to finance HERE (D6b does that); this result is
          advisory only.

    **BESS charge-from-surplus (energy-conserved).** When a co-located BESS has charge
    headroom, surplus that would be self-curtailed is instead ABSORBED into the shared D5a
    SoC model (:func:`analytics.grid.capabilities.bess_soc.split_reserves`, the
    curtailment-absorption CHARGE-direction reserve). Absorbed MWh is RECOVERED energy, so
    ``self_curtailed_energy_mwh`` is the self-shed surplus MINUS ``bess_absorbed_energy_mwh``
    — the battery converts a would-be loss into stored energy WITHOUT creating energy from
    nothing (``bess_absorbed_energy_mwh <= chargeable headroom``, enforced by the D5a
    no-double-count invariant).

    **Energy is conserved** and the invariant is asserted at emit:
    ``curtailed_total = deemed_paid + self_curtailed_pre_bess`` and
    ``self_curtailed = self_curtailed_pre_bess - bess_absorbed`` (≥ 0). None of these come
    from a solver convergence flag — every MWh is an INTEGRAL of physical evidence
    (export-cap breaches of the injected generation → self-shed; the committed grid-instruction
    schedule → deemed; SoC headroom → recovery).

    **NOT-RUN honesty (``ran`` + ``None``).** A run is only meaningful against a REAL
    feeder. When the QSTS did not run — default-off (``grid.qsts.enabled`` False), no
    ``feeder_model_path``, or a SYNTHETIC/demo feeder (which is a smoke test only) — the
    energy fields are ``None`` and ``ran`` is False, with ``reason`` explaining why. A
    synthetic feeder NEVER masquerades as a real curtailment figure and NEVER overwrites the
    real loss placeholder (NO SPURIOUS PASS: a fabricated zero-loss "pass" is refused).

    Fields
        ran: True only when the QSTS solved against a REAL feeder and produced integrated
            energy. False for every inert / NOT-RUN / synthetic-feeder path (energy fields
            then ``None``).
        feeder_source: the resolved feeder provenance — the real ``feeder_model_path``, or
            ``"synthetic_demo"`` / ``"none"`` for the non-bankable paths.
        export_cap_mw: the POC export limit the self-curtailment is measured against.
        gross_energy_mwh: total generation injected over the horizon BEFORE any curtailment.
        curtailed_total_mwh: total curtailed energy = deemed_paid + self_curtailed_pre_bess.
        deemed_paid_energy_mwh: grid-instructed curtailment — PAID as deemed energy
            (KPI-neutral; never haircuts revenue).
        self_curtailed_pre_bess_mwh: physical export-cap surplus shed BEFORE BESS recovery.
        bess_absorbed_energy_mwh: surplus recovered into the BESS (energy-conserved; bounded
            by the D5a chargeable headroom).
        self_curtailed_energy_mwh: the NET real self-curtailment loss AFTER BESS recovery
            (``self_curtailed_pre_bess - bess_absorbed``) — the D6b KPI-mover, ≥ 0.
        deemed_paid_pct / self_curtailed_pct: the deemed / net-self shares of gross energy.
        hours_self_curtailed / hours_total: QSTS timestep counts (export-cap-breach hours,
            total horizon hours).
        reason: a human string; for NOT-RUN paths it states WHY the QSTS did not run.
    """

    ran: bool
    feeder_source: str
    export_cap_mw: float | None = None
    gross_energy_mwh: float | None = None
    curtailed_total_mwh: float | None = None
    deemed_paid_energy_mwh: float | None = None
    self_curtailed_pre_bess_mwh: float | None = None
    bess_absorbed_energy_mwh: float | None = None
    self_curtailed_energy_mwh: float | None = None
    deemed_paid_pct: float | None = None
    self_curtailed_pct: float | None = None
    hours_self_curtailed: int | None = None
    hours_total: int | None = None
    method: str = "opendss_qsts"
    bankable: bool = False
    provenance: str = _CURTAILMENT_SHARE_PROVENANCE
    reason: str = ""
    notes: str = ""


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


# ---------------------------------------------------------------------------
# Capital-structure optimizer contracts (#740)
#
# Opt-in ANALYSIS surfaces: the debt-tranche-mix optimizer and the
# capex-contingency optimizer search a candidate space against a return
# objective subject to covenant constraints, scoring each candidate through the
# ``analytics.evaluation_v14.evaluate_with_overrides`` gateway (CCCDIR / ARCH-04
# — no re-implemented pipeline, no IRR/NPV redefinition). They are NEVER wired
# into ``run_v14_pipeline``, so committed scenarios stay byte-identical. The
# rich infeasibility diagnostics + full optimization audit log are a separate
# issue (#741); these carry only the minimal result surface (#740).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DebtTrancheMix(ContractMixin):
    """One point in the debt-tranche-mix search space: the lkr/usd/dfi split.

    The three shares are financing PROPORTIONS of the auto-sized total debt, not
    absolute principals (the engine sizes total debt via ``dual_dscr`` and then
    splits it by ``Financing_Terms.mix``). By construction
    ``lkr_share + usd_share + dfi_share == 1`` to within ``_SHARE_SUM_TOL``;
    ``usd_share`` is the residual (``1 - lkr_share - dfi_share``), mirroring the
    engine's ``_solve_mix`` where the USD_Commercial tranche absorbs the balance.
    """

    lkr_share: float
    dfi_share: float
    usd_share: float


@dataclass(frozen=True)
class CapitalStructurePoint(ContractMixin):
    """One evaluated candidate: the decision value, its objective and constraints.

    ``value`` is a JSON-safe scalar/tuple encoding of the candidate (a
    ``(lkr_share, dfi_share)`` pair for the debt-mix optimizer, a scalar
    contingency fraction for the contingency optimizer). ``objective`` is the
    read-back objective KPI; ``constraints`` records every constrained KPI's
    value; ``feasible`` reflects whether ALL constraint bounds were satisfied
    within tolerance; ``binding_constraints`` names the constraint keys that were
    violated (empty when feasible) — a minimal diagnostic (rich diagnostics: #741).
    """

    value: tuple[float, ...]
    mix: DebtTrancheMix | None
    objective: float
    constraints: dict[str, float] = field(default_factory=dict)
    feasible: bool = True
    binding_constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class CovenantConstraint(ContractMixin):
    """A single covenant bound applied to a KPI during the optimizer search.

    ``minimum`` / ``maximum`` are inclusive bounds (either may be ``None``); at
    least one is set. A candidate satisfies the constraint when its KPI value
    lies within ``[minimum, maximum]`` to within the optimizer's shared
    floating-point ``_bound_slack`` tolerance (the same tolerance
    ``optimization_v14`` uses so DSCR-sculpt plateaus are not spuriously
    marked infeasible).
    """

    key: str
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class CapitalStructureOptimizationResult(ContractMixin):
    """Outcome of a debt-mix or capex-contingency optimizer run (#740).

    ``kind`` is ``"debt_mix"`` or ``"capex_contingency"``. ``best`` is the
    highest-scoring FEASIBLE candidate in the requested ``direction`` (or
    ``None`` when the search is infeasible everywhere). ``curve`` is the full
    evaluated candidate set in evaluation order (the objective/feasibility
    surface). ``feasible`` is ``True`` iff at least one candidate was feasible;
    when it is ``False`` the search failed loud and ``infeasible_reason`` names
    the constraint(s) that bound every candidate (a minimal diagnostic — the
    full infeasibility register is #741).

    ``diagnostics`` / ``audit_log`` (#741) are populated ONLY on the infeasible
    path (``feasible=False``) with the structured why-infeasible register
    (per-covenant bound + achieved vs required) and a lightweight optimization
    audit trail. On a feasible solve BOTH stay ``None`` so the numeric result is
    byte-identical to the #740 surface. They are typed ``Any`` to avoid an
    import cycle (``analytics.infeasibility_diagnostics`` imports nothing from
    this module); their concrete types are that module's
    ``InfeasibilityDiagnostics`` / ``OptimizationAuditLog``, which serialize
    cleanly via ``asdict`` / ``model_dump``.
    """

    kind: str
    objective_key: str
    direction: str
    constraints: list[CovenantConstraint]
    best: CapitalStructurePoint | None
    curve: list[CapitalStructurePoint] = field(default_factory=list)
    feasible: bool = True
    infeasible_reason: str | None = None
    diagnostics: Any = None
    audit_log: Any = None


__all__ = [
    "CASPER_CONTRACT_VERSION",
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
    "TwoFactorInteractionGrid",
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
    "GridStrengthResult",
    "ReactiveCapabilityResult",
    "PowerFlowResult",
    "GridStudyResult",
    "RideThroughResult",
    "BessSocState",
    "ReserveSplitResult",
    "ResourceReactiveContribution",
    "PocCapabilityEnvelope",
    "HarmonicComplianceResult",
    "CurtailmentShareResult",
    "GroupDroopContribution",
    "FreqResponseResult",
    "grid_scr_band",
    "grid_gfl_gfm_recommendation",
    "GRID_SCR_WEAK_BELOW",
    "GRID_SCR_STRONG_ABOVE",
    "GRID_EMT_CONFIRMATION_SCR",
    "IrrBridgeComponent",
    "ProjectEquityIrrBridge",
    "DebtTrancheMix",
    "CapitalStructurePoint",
    "CovenantConstraint",
    "CapitalStructureOptimizationResult",
    "ResourceAssessment",
]
