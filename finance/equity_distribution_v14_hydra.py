#!/usr/bin/env python
"""Equity Distribution Module - v14 production integration.

This module turns canonical v14 pipeline output into an equity distribution
waterfall. It is deliberately downstream of the v14 finance gateway:

    load_scenario_config -> validate_config_for_v14 -> run_v14_pipeline

The production path consumes the canonical payload shape:

    {config, annual_rows, debt_result, kpis}

and returns a JSON-safe equity distribution result. It does not run cashflow or
debt internals directly. IRR/NPV calculations are delegated through
finance.equity_v14, which in turn uses finance.irr as the singleton IRR/NPV
implementation.

GWTF Compliance:
    - Config-first thresholds and sweep rules.
    - Pydantic v2 validation via ConfigDict and field_validator.
    - Hydra CLI compatibility without argparse or Typer.
    - JSON-safe output and no print calls in library code.
    - No direct analytics-layer dependency on finance internals except through
      the main v14 pipeline integration point.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finance.equity_v14 import (
    calculate_cash_on_cash,
    calculate_equity_irr,
    calculate_equity_npv,
    calculate_moic,
    calculate_payback_period,
)

logger = logging.getLogger(__name__)

# Floating-point tolerance for the distribution-lockup DSCR comparison. The debt sizer
# sculpts the floor year to the covenant target but lands it at ~target − 2e-16; a DSCR
# within this band of the covenant is treated as MEETING it (not a breach), so the lockup
# never fires on sub-ULP rounding at the sculpt floor. Far below any covenant margin that
# matters, so genuine sub-covenant years still lock.
_DSCR_LOCKUP_EPS = 1e-9


class EquityDistributionConfig(BaseModel):
    """Configuration for equity distribution calculations.

    The legacy fields remain available for older tests and standalone scenarios.
    Production pipeline integration uses the fields under
    ``equity_distribution`` or ``equity`` when present, otherwise it derives
    investment size from CAPEX and debt result.
    """

    model_config = ConfigDict(validate_default=True, validate_assignment=True)

    scenario_name: str = Field(default="default", min_length=1)
    enabled: bool = Field(default=True)
    project_life_years: int = Field(default=25, ge=1, le=50)

    min_dscr_threshold: float = Field(default=1.25, ge=0.0, le=5.0)
    min_reserve_months: int = Field(default=6, ge=0, le=24)

    distribution_sweep_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    holdback_pct: float = Field(default=0.0, ge=0.0, le=100.0)

    # Withholding tax on non-resident interest. When wht_gross_up is True the SPV grosses
    # up the WHT (bears interest * rate on TOP of interest, as a real cash cost reducing
    # cash to equity); when False the lender bears it (no incremental SPV cost). The rate is
    # tax.wht_on_interest_to_nonresidents gated by tax.wht_on_interest_enabled. Default-off
    # (rate 0 / gross_up False) -> byte-identical.
    wht_gross_up: bool = Field(default=False)
    wht_on_interest_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Dividend/distribution withholding tax (#81). When enabled, positive distributions to
    # the sponsor (including the terminal close-out release) are paid NET of this rate — the
    # sponsor receives distribution * (1 - rate); the withheld amount leaves the SPV to the
    # tax authority (it is NOT retained). It bites equity cash only — project IRR/DSCR are
    # upstream of the equity waterfall — mirroring the SL 15% statutory dividend WHT. Rate is
    # tax.wht_on_dividends gated by tax.wht_on_dividends_enabled; default-off -> byte-identical.
    wht_on_dividends_enabled: bool = Field(default=False)
    wht_on_dividends_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    terminal_value_usd: float = Field(default=0.0, ge=0.0)
    discount_rate: float = Field(default=0.10, ge=0.0, le=1.0)

    equity_investment_usd: Optional[float] = Field(default=None, ge=0.0)
    allow_default_equity_investment: bool = Field(default=False)
    default_equity_investment_usd: float = Field(default=0.0, ge=0.0)

    success: bool = Field(default=True)

    @field_validator("project_life_years")
    @classmethod
    def validate_project_life(cls, v: int) -> int:
        """Validate project life years."""
        if not (1 <= v <= 50):
            raise ValueError(f"Project life must be 1-50 years, got {v}")
        return v

    @field_validator("min_dscr_threshold")
    @classmethod
    def validate_dscr_threshold(cls, v: float) -> float:
        """Validate DSCR threshold."""
        if not (0.0 <= v <= 5.0):
            raise ValueError(f"DSCR threshold must be 0.0-5.0, got {v}")
        return v

    @field_validator("discount_rate")
    @classmethod
    def validate_discount_rate(cls, v: float) -> float:
        """Validate discount rate as a decimal."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"discount_rate must be 0.0-1.0, got {v}")
        return v


def _lookup_case_insensitive(mapping: Mapping[str, Any], key: str) -> Any:
    """Return a mapping value by exact or case-insensitive key."""
    if key in mapping:
        return mapping[key]
    key_lower = key.lower()
    for existing_key, value in mapping.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def _section_case_insensitive(
    mapping: Mapping[str, Any], key: str
) -> Optional[Mapping[str, Any]]:
    """Return a nested mapping section by exact or case-insensitive key."""
    value = _lookup_case_insensitive(mapping, key)
    return value if isinstance(value, Mapping) else None


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Convert a value to float without hiding invalid numeric text."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    """Convert a value to int with an explicit default."""
    numeric = _as_float(value, float(default))
    return int(numeric if numeric is not None else default)


def _extract_capex_usd(config: Mapping[str, Any]) -> Optional[float]:
    """Extract total CAPEX from canonical, compact, or legacy v14 schemas.

    CCCDIR: when ``capex.derive_from_breakdown`` is set, the equity base MUST use the same
    bottom-up resolver the debt engine and ``analytics.core.metrics`` use, or the equity
    CAPEX (and thus the derived equity investment) could silently diverge from the financed
    CAPEX (up to the 0.5% breakdown tolerance / QRA delta). Delegating here keeps a single
    source of truth — mirrors ``analytics.core.metrics._derive_capex_usd``. The flat
    multi-section lookup below is unchanged for scenarios that do NOT derive from breakdown
    (e.g. the canonical lendercase), so they stay byte-identical.
    """
    capex_section = _section_case_insensitive(config, "capex")
    if capex_section and _lookup_case_insensitive(
        capex_section, "derive_from_breakdown"
    ):
        from finance.debt_v14 import _extract_capex_usd as _resolve_capex_bottom_up

        return float(_resolve_capex_bottom_up(dict(config)))

    section_candidates: Sequence[tuple[str, Sequence[str]]] = (
        ("finance", ("capex_total_usd", "capex_usd")),
        ("capex", ("usd_total", "capex_total_usd", "total_capex_usd", "total_capex")),
        ("costs", ("capex_total_usd", "capex_usd", "total_capex_usd", "total_capex")),
        ("Project", ("capex_usd", "capex_total_usd", "total_capex_usd")),
    )
    for section_name, keys in section_candidates:
        section = _section_case_insensitive(config, section_name)
        if not section:
            continue
        for key in keys:
            value = _as_float(_lookup_case_insensitive(section, key))
            if value is not None:
                return value

    for key in ("capex_usd_total", "capex_total_usd", "total_capex_usd"):
        value = _as_float(_lookup_case_insensitive(config, key))
        if value is not None:
            return value
    return None


def _extract_scenario_name(config: Mapping[str, Any]) -> str:
    """Extract scenario name from canonical locations."""
    for key in ("scenario_name", "name", "id"):
        value = _lookup_case_insensitive(config, key)
        if value is not None:
            return str(value)
    meta = _section_case_insensitive(config, "meta")
    if meta:
        for key in ("scenario_name", "name", "id"):
            value = _lookup_case_insensitive(meta, key)
            if value is not None:
                return str(value)
    project = _section_case_insensitive(config, "Project") or _section_case_insensitive(
        config, "project"
    )
    if project:
        value = _lookup_case_insensitive(project, "name")
        if value is not None:
            return str(value)
    return "default"


def _extract_equity_section(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract equity distribution configuration from supported sections."""
    for section_name in ("equity_distribution", "Equity_Distribution", "equity"):
        section = _section_case_insensitive(config, section_name)
        if section:
            return dict(section)
    return {}


def _normalise_percent(value: Any, default: float) -> float:
    """Normalize percentage inputs that may arrive as decimals or percent points."""
    numeric = _as_float(value, default)
    if numeric is None:
        return default
    return numeric * 100.0 if 0.0 <= numeric <= 1.0 else numeric


def _build_distribution_config(config: Mapping[str, Any]) -> EquityDistributionConfig:
    """Build a validated EquityDistributionConfig from a scenario mapping."""
    equity_section = _extract_equity_section(config)
    scenario_name = str(
        equity_section.get("scenario_name")
        or equity_section.get("name")
        or _extract_scenario_name(config)
    )

    project_life = (
        equity_section.get("project_life_years")
        or equity_section.get("life_years")
        or _lookup_case_insensitive(config, "project_life_years")
    )

    if project_life is None:
        project = _section_case_insensitive(
            config, "Project"
        ) or _section_case_insensitive(config, "project")
        if project:
            project_life = _lookup_case_insensitive(project, "project_life_years")

    # Non-resident interest WHT (same derivation as finance.cashflow_v14_tax.build_tax_profile,
    # CCCDIR: one rule for the rate). Rate applies only when wht_on_interest_enabled; the SPV
    # bears it as a cash cost only when wht_gross_up. Both default off -> byte-identical.
    tax_section = _section_case_insensitive(config, "tax") or {}
    wht_enabled = bool(_lookup_case_insensitive(tax_section, "wht_on_interest_enabled"))
    # FIN-12 (#482): fail loud on an ENABLED-but-rate-ABSENT inconsistency. With the rate key
    # missing the gated idiom below silently resolves to 0.0, so the equity waterfall would
    # under-charge WHT and OVERSTATE equity_irr/npv (the public-API footgun — a raw config can
    # enable WHT without supplying the rate). An explicit 0.0 rate is legitimate (no charge);
    # only an absent key while enabled is the bug.
    if wht_enabled and (
        _lookup_case_insensitive(tax_section, "wht_on_interest_to_nonresidents") is None
    ):
        raise ValueError(
            "tax.wht_on_interest_enabled is true but tax.wht_on_interest_to_nonresidents "
            "(the rate) is absent — interest WHT would silently resolve to 0 and the equity "
            "waterfall would under-charge. Declare the rate (e.g. 0.10) or disable the flag."
        )
    wht_rate = (
        float(
            _as_float(
                _lookup_case_insensitive(
                    tax_section, "wht_on_interest_to_nonresidents"
                ),
                0.0,
            )
            or 0.0
        )
        if wht_enabled
        else 0.0
    )
    wht_gross_up = bool(_lookup_case_insensitive(tax_section, "wht_gross_up"))

    # Dividend WHT (#81): same gated-rate idiom as interest WHT above. Default-off.
    div_wht_enabled = bool(
        _lookup_case_insensitive(tax_section, "wht_on_dividends_enabled")
    )
    # FIN-12 (#482): symmetric guard — enabled dividend WHT must declare its rate.
    if div_wht_enabled and (
        _lookup_case_insensitive(tax_section, "wht_on_dividends") is None
    ):
        raise ValueError(
            "tax.wht_on_dividends_enabled is true but tax.wht_on_dividends (the rate) is "
            "absent — dividend WHT would silently resolve to 0 and the equity waterfall "
            "would under-charge the sponsor. Declare the rate (e.g. 0.15) or disable the flag."
        )
    div_wht_rate = (
        float(
            _as_float(_lookup_case_insensitive(tax_section, "wht_on_dividends"), 0.0)
            or 0.0
        )
        if div_wht_enabled
        else 0.0
    )

    # A2b/#33: the distribution-lockup DSCR covenant is the scenario's AUTHORED covenant,
    # not an orphan library default. Resolve a fallback chain:
    #   equity_distribution.min_dscr_threshold -> constraints.min_dscr_covenant -> 1.25
    # so the lockup tests distributions against the value the debt sizer / covenant report
    # actually use (1.30) instead of an unauthored 1.25 that matches no stated covenant.
    # Paired with the FP-tolerant lockup comparison (_DSCR_LOCKUP_EPS), this is KPI-neutral
    # for every real scenario: their dual-DSCR sculpt holds the floor AT the covenant, which
    # MEETS (does not breach) the 1.30 lockup, so zero years lock and equity_irr/npv are
    # byte-identical. The reconcile only bites where a year's DSCR is MATERIALLY below the
    # covenant — a genuine breach (e.g. the synthetic edge_extreme_stress fixture), which is
    # exactly when a lender lockup SHOULD trap distributions. (Finding #33 assumed the orphan
    # 1.25-vs-1.30 gap was inert; it is real but only engages on genuine sub-covenant years —
    # and naively raising it WITHOUT the FP tolerance would have spuriously locked the sculpt
    # floor on sub-ULP rounding, a fake +27bps equity re-baseline.)
    constraints_section = _section_case_insensitive(config, "constraints") or {}
    lockup_threshold = equity_section.get("min_dscr_threshold")
    if lockup_threshold is None:
        lockup_threshold = _lookup_case_insensitive(
            constraints_section, "min_dscr_covenant"
        )

    # The financed schedule (build_equity_distribution_schedule) consumes only the fields
    # parsed below. (The former priority-waterfall fields — target_equity_irr_pct,
    # equity_stake_pct, reserve_fund_pct, priority_senior/mezzanine_usd,
    # annual_distributable_cash_usd — were consumed only by the retired legacy
    # EquityDistributionEngine and have been removed from the config.)
    return EquityDistributionConfig(
        scenario_name=scenario_name,
        enabled=bool(equity_section.get("enabled", True)),
        project_life_years=_as_int(project_life, 25),
        min_dscr_threshold=float(_as_float(lockup_threshold, 1.25) or 0.0),
        min_reserve_months=_as_int(equity_section.get("min_reserve_months"), 6),
        distribution_sweep_pct=_normalise_percent(
            equity_section.get("distribution_sweep_pct"), 100.0
        ),
        holdback_pct=_normalise_percent(equity_section.get("holdback_pct"), 0.0),
        wht_gross_up=wht_gross_up,
        wht_on_interest_rate=wht_rate,
        wht_on_dividends_enabled=div_wht_enabled,
        wht_on_dividends_rate=div_wht_rate,
        terminal_value_usd=float(
            _as_float(equity_section.get("terminal_value_usd"), 0.0) or 0.0
        ),
        discount_rate=float(
            _as_float(equity_section.get("discount_rate"), 0.10) or 0.0
        ),
        equity_investment_usd=_as_float(
            equity_section.get("equity_investment_usd")
            or equity_section.get("equity_contribution_usd")
            or equity_section.get("initial_equity_usd")
        ),
        allow_default_equity_investment=bool(
            equity_section.get("allow_default_equity_investment", False)
        ),
        default_equity_investment_usd=float(
            _as_float(equity_section.get("default_equity_investment_usd"), 0.0) or 0.0
        ),
    )


def _derive_equity_investment_usd(
    *,
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    distribution_config: EquityDistributionConfig,
) -> tuple[Optional[float], str]:
    """Derive the initial equity investment and status metadata."""
    # When the DSRA is funded at financial close (Financing_Terms.dsra.fund_at_close), the
    # reserve is an additional EQUITY use at t0 (prudent-lender structure), so it raises the
    # initial equity drawn. This applies SYMMETRICALLY whether equity is given explicitly or
    # derived (previously only the derived path added it, asymmetrically boosting the equity
    # IRR of an explicit-equity + fund_at_close scenario). Default-off -> dsra 0 (unchanged).
    funding = debt_result.get("funding") or {}
    dsra = (
        float(_as_float(funding.get("initial_dsra_usd"), 0.0) or 0.0)
        if bool(funding.get("fund_at_close"))
        else 0.0
    )

    if distribution_config.equity_investment_usd is not None:
        equity = float(distribution_config.equity_investment_usd) + dsra
        return equity, "explicit_plus_dsra" if dsra > 0.0 else "explicit"

    capex_usd = _extract_capex_usd(config)
    debt_total = _as_float(
        debt_result.get("debt_total")
        or debt_result.get("max_debt_usd")
        or debt_result.get("final_debt_usd")
    )

    if capex_usd is not None and debt_total is not None:
        base = max(0.0, float(capex_usd) - float(debt_total))
        if dsra > 0.0:
            return base + dsra, "capex_less_debt_plus_dsra"
        return base, "capex_less_debt"

    if distribution_config.allow_default_equity_investment:
        return float(distribution_config.default_equity_investment_usd), "defaulted"

    return None, "failed"


def _extract_cf_pre_debt(row: Mapping[str, Any]) -> float:
    """Extract CFADS/pre-debt cash in USD from an annual row."""
    for key in ("cf_pre_debt", "cfads_usd", "cash_available_for_debt_service_usd"):
        value = _as_float(row.get(key))
        if value is not None:
            return value

    cfads_lkr = _as_float(
        row.get("cfads_final_lkr") or row.get("cfads_lkr") or row.get("cfads")
    )
    fx_rate = _as_float(row.get("fx_rate") or row.get("start_lkr_per_usd"))
    if cfads_lkr is not None and fx_rate is not None and fx_rate != 0.0:
        return cfads_lkr / fx_rate
    return 0.0


def _extract_debt_service(
    row: Mapping[str, Any],
    debt_service_series: Sequence[Any],
    index: int,
) -> float:
    """Extract annual debt service from row or aligned debt_result series."""
    # Use presence, not truthiness: a legitimate 0.0 (post-debt years) must NOT
    # fall through to the positional series (which is period-indexed and would
    # mis-attribute an earlier year's service).
    raw = row.get("debt_service_total")
    if raw is None:
        raw = row.get("total_service")
    row_value = _as_float(raw)
    if row_value is not None:
        return row_value
    if index < len(debt_service_series):
        value = _as_float(debt_service_series[index])
        if value is not None:
            return value
    return 0.0


def _extract_dscr(
    row: Mapping[str, Any], cf_pre_debt: float, debt_service: float
) -> Optional[float]:
    """Extract or compute DSCR for an annual row."""
    row_dscr = _as_float(row.get("dscr"))
    if row_dscr is not None and row_dscr > 0.0:
        return row_dscr
    if debt_service > 0.0:
        return cf_pre_debt / debt_service
    return None


def build_equity_distribution_schedule(
    *,
    annual_rows: Sequence[Mapping[str, Any]],
    debt_result: Mapping[str, Any],
    distribution_config: EquityDistributionConfig,
) -> List[Dict[str, Any]]:
    """Build annual equity distributions from debt-enriched annual rows."""
    debt_service_series = list(debt_result.get("debt_service_total") or [])
    debt_outstanding_series = list(debt_result.get("debt_outstanding") or [])
    # When the DSRA is funded at close it is already full at t0, so the operating top-up
    # only has to REBUILD it after a drawdown rather than fund it from year-1 cash.
    # Default-off -> seed 0 (the reserve is built from operating cash, as before).
    _funding = debt_result.get("funding") or {}
    reserve_balance = (
        float(_as_float(_funding.get("initial_dsra_usd"), 0.0) or 0.0)
        if bool(_funding.get("fund_at_close"))
        else 0.0
    )
    schedule: List[Dict[str, Any]] = []

    sweep = distribution_config.distribution_sweep_pct / 100.0
    holdback = distribution_config.holdback_pct / 100.0
    # Dividend WHT (#81): positive distributions are paid net of this rate; 0.0 when disabled.
    div_wht_rate = (
        distribution_config.wht_on_dividends_rate
        if distribution_config.wht_on_dividends_enabled
        else 0.0
    )

    # Cash that is retained rather than distributed must not be DESTROYED — it belongs to
    # the sponsor and is released to equity, not lost (which would understate equity IRR):
    #  * locked_cash_balance: cash trapped during a covenant lockup, released once the
    #    covenant cures (the next unlocked year);
    #  * retained_balance: per-year holdback + un-swept cash, released at project end.
    locked_cash_balance = 0.0
    retained_balance = 0.0

    for index, row in enumerate(annual_rows):
        year_value = row.get("year", index + 1)
        year = int(float(year_value)) if year_value is not None else index + 1

        cf_pre_debt = _extract_cf_pre_debt(row)
        debt_service = _extract_debt_service(row, debt_service_series, index)
        # Grossed-up non-resident interest WHT is a real cash cost senior to equity (the SPV
        # tops it up alongside interest). It reduces cash to equity but is NOT scheduled debt
        # service, so — like the balloon resolution — it stays out of the DSCR (the row's own
        # cf_after_debt, used for covenant reporting, is untouched upstream).
        # FIN-12 (#482): the gross-up needs per-year interest_usd (an enricher-only key the
        # equity pass adds, not present on a raw row). If wht_gross_up is on but the row lacks
        # it, the cost would silently be 0 and equity_irr/npv would be overstated — fail loud
        # rather than under-charge. (Dormant when wht_gross_up is off, as all committed
        # scenarios have it; an explicit 0.0 interest_usd is fine, only an absent key raises.)
        if distribution_config.wht_gross_up and row.get("interest_usd") is None:
            raise ValueError(
                f"Equity distribution: wht_gross_up is enabled but annual row {year} lacks "
                "interest_usd (the per-year non-resident interest the SPV grosses up). The "
                "WHT cash cost would silently be 0 — supply interest_usd on the rows (the "
                "levered equity pass enriches it) or disable wht_gross_up."
            )
        interest_usd = _as_float(row.get("interest_usd"), 0.0) or 0.0
        wht_cost = (
            interest_usd * distribution_config.wht_on_interest_rate
            if distribution_config.wht_gross_up
            else 0.0
        )
        cf_after_debt = max(0.0, cf_pre_debt - debt_service - wht_cost)
        dscr = _extract_dscr(row, cf_pre_debt, debt_service)

        # Reserve: top up toward the requirement; RELEASE the excess back to equity as the
        # requirement falls (debt amortizes) — the reserve cash is the sponsor's, not lost.
        reserve_required = debt_service * (
            float(distribution_config.min_reserve_months) / 12.0
        )
        if reserve_required >= reserve_balance:
            reserve_funded = min(cf_after_debt, reserve_required - reserve_balance)
            reserve_balance += reserve_funded
            reserve_released = 0.0
        else:
            reserve_funded = 0.0
            reserve_released = reserve_balance - reserve_required
            reserve_balance = reserve_required

        cash_after_reserve = max(0.0, cf_after_debt - reserve_funded) + reserve_released

        # Balloon repayment (cash_sweep / refinance / bullet) is senior to equity
        # but is NOT scheduled senior debt service, so it never enters the DSCR.
        # cash_sweep is bounded by available cash; refinance/bullet may exceed it,
        # in which case the shortfall is a sponsor cash call (negative equity CF).
        balloon_resolution = _as_float(row.get("balloon_resolution"), 0.0) or 0.0
        cash_for_equity = cash_after_reserve - balloon_resolution

        # FP-tolerant lockup: a DSCR that MEETS the covenant to machine precision is not a
        # breach. The dual-DSCR sculpt lands the floor year at the covenant target but in
        # floating point that is ~1.2999999999999998, so a strict `dscr < 1.30` would lock
        # the floor year on sub-ULP noise (re-baselining KPIs on rounding — the exact
        # boundary-flip anti-pattern). Subtracting _DSCR_LOCKUP_EPS locks only when DSCR is
        # MATERIALLY below the covenant (a real breach), keeping sculpted-to-floor scenarios
        # byte-identical while still trapping genuine sub-covenant years (stress cases).
        covenant_locked = bool(
            dscr is not None
            and distribution_config.min_dscr_threshold > 0.0
            and dscr < distribution_config.min_dscr_threshold - _DSCR_LOCKUP_EPS
        )

        # Dividend WHT applies only to positive distributions actually paid to the sponsor
        # (the two non-distributing branches below are a lockup or a cash call -> no WHT).
        dividend_wht = 0.0
        if covenant_locked:
            # No positive distribution while locked; the trapped cash is carried (not lost)
            # and released once the covenant cures. A balloon shortfall is still a cash call.
            equity_distribution = min(0.0, cash_for_equity)
            trapped = max(0.0, cash_for_equity)
            locked_cash_balance += trapped
            retained_cash = trapped
        elif cash_for_equity < 0.0:
            equity_distribution = (
                cash_for_equity  # sponsor cash call to fund the balloon
            )
            retained_cash = 0.0
        else:
            # Unlocked: release any lockup-trapped cash now that the covenant has cured.
            available = cash_for_equity + locked_cash_balance
            locked_cash_balance = 0.0
            gross_distribution = available * sweep
            holdback_amount = gross_distribution * holdback
            # Pre-WHT distribution to the sponsor; the WHT is withheld from this and remitted
            # to the tax authority (it leaves the SPV, so it is NOT part of retained cash).
            distribution_pre_wht = max(0.0, gross_distribution - holdback_amount)
            dividend_wht = distribution_pre_wht * div_wht_rate
            equity_distribution = distribution_pre_wht - dividend_wht
            # Un-swept + held-back cash is retained in the SPV and released at project end —
            # measured against the PRE-WHT distribution (the WHT is paid out, not retained).
            retained_cash = available - distribution_pre_wht
            retained_balance += retained_cash

        debt_outstanding = (
            _as_float(debt_outstanding_series[index])
            if index < len(debt_outstanding_series)
            else None
        )

        schedule.append(
            {
                "year": year,
                "cf_pre_debt_usd": cf_pre_debt,
                "debt_service_usd": debt_service,
                "wht_on_interest_usd": wht_cost,
                "wht_on_dividends_usd": dividend_wht,
                "cf_after_debt_usd": cf_after_debt,
                "balloon_resolution_usd": balloon_resolution,
                "dscr": dscr,
                "covenant_locked": covenant_locked,
                "reserve_required_usd": reserve_required,
                "reserve_funded_usd": reserve_funded,
                "reserve_balance_usd": reserve_balance,
                "retained_cash_usd": retained_cash,
                "equity_distribution_usd": equity_distribution,
                "terminal_release_usd": 0.0,
                "debt_outstanding_usd": debt_outstanding,
            }
        )

    # Terminal release: at project end the DSRA is no longer needed and any cash still held
    # in the SPV (un-swept retentions, holdbacks, cash trapped by a terminal lockup) belongs
    # to the sponsor — release it all into the final distribution so it is not destroyed.
    # This is a discrete close-out event folded into the final period's distribution; the
    # per-row retained_cash_usd remains the within-year flow and is left untouched.
    if schedule:
        residual = reserve_balance + retained_balance + locked_cash_balance
        if residual > 1e-9:
            last = schedule[-1]
            prior_dist = _as_float(last.get("equity_distribution_usd"), 0.0) or 0.0
            # The terminal release is cash distributed to the sponsor -> it bears dividend
            # WHT too; the sponsor receives the residual net (0.0 rate -> byte-identical).
            terminal_wht = residual * div_wht_rate
            net_residual = residual - terminal_wht
            last["equity_distribution_usd"] = prior_dist + net_residual
            last["terminal_release_usd"] = residual
            last["wht_on_dividends_usd"] = (
                _as_float(last.get("wht_on_dividends_usd"), 0.0) or 0.0
            ) + terminal_wht
            last["reserve_balance_usd"] = 0.0

    return schedule


def calculate_equity_distribution_from_pipeline(
    *,
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    debt_result: Mapping[str, Any],
    kpis: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculate equity distribution from canonical v14 pipeline payload."""
    del kpis

    distribution_config = _build_distribution_config(config)
    if not distribution_config.enabled:
        return {
            "success": True,
            "status": "disabled",
            "scenario_name": distribution_config.scenario_name,
            "equity_summary": {},
            "annual_distributions": [],
            "metadata": {"computed_from": "canonical_v14_pipeline"},
        }

    if not annual_rows:
        return {
            "success": False,
            "status": "failed",
            "scenario_name": distribution_config.scenario_name,
            "error": "annual_rows is empty; cannot compute equity distributions",
            "equity_summary": {},
            "annual_distributions": [],
            "metadata": {"computed_from": "canonical_v14_pipeline"},
        }

    equity_investment, investment_source = _derive_equity_investment_usd(
        config=config,
        debt_result=debt_result,
        distribution_config=distribution_config,
    )
    if equity_investment is None or equity_investment <= 0.0:
        return {
            "success": False,
            "status": "failed",
            "scenario_name": distribution_config.scenario_name,
            "error": "equity investment could not be derived from config and debt_result",
            "equity_summary": {},
            "annual_distributions": [],
            "metadata": {
                "computed_from": "canonical_v14_pipeline",
                "equity_investment_source": investment_source,
            },
        }

    annual_distributions = build_equity_distribution_schedule(
        annual_rows=annual_rows,
        debt_result=debt_result,
        distribution_config=distribution_config,
    )

    distribution_values = [
        float(row["equity_distribution_usd"]) for row in annual_distributions
    ]
    if distribution_config.terminal_value_usd > 0.0 and distribution_values:
        distribution_values[-1] += distribution_config.terminal_value_usd
        annual_distributions[-1][
            "terminal_value_usd"
        ] = distribution_config.terminal_value_usd
        annual_distributions[-1]["equity_distribution_usd"] = distribution_values[-1]

    # Match the PROJECT IRR/NPV convention (finance.irr / analytics.core.metrics): capex AND
    # equity are committed at FINANCIAL CLOSE (construction start), and operating cash is
    # discounted AFTER the build. annual_rows are operating years only (no construction zeros),
    # so prepend construction_years zeros to the equity return vector — otherwise the equity
    # timeline LEADS the project timeline by construction_years, crediting the first operating
    # distribution at t=1 instead of t=construction_years+1 (round-3 re-audit fix). Sourced
    # from the same debt_result['construction_years'] metrics.py uses, so the two IRRs of one
    # project share a single timeline.
    construction_years = int(debt_result.get("construction_years", 0) or 0)
    if construction_years == 0:
        # Mirror analytics.core.metrics' project-IRR sourcing: when debt_result omits the
        # key (partial/stubbed callers of this public API), fall back to the config so the
        # equity timeline matches what the project IRR would use for the same project.
        construction_years = int(
            _as_float(_lookup_case_insensitive(config, "construction_years"), 0.0)
            or 0.0
        )
    cashflows = (
        [-float(equity_investment)] + [0.0] * construction_years + distribution_values
    )

    equity_irr = calculate_equity_irr(cashflows)
    equity_npv = calculate_equity_npv(
        cashflows, discount_rate=distribution_config.discount_rate
    )
    total_distributed = float(sum(distribution_values))
    equity_multiple = (
        total_distributed / float(equity_investment) if equity_investment > 0 else None
    )
    moic = calculate_moic(
        cumulative_distributions=total_distributed,
        current_nav=0.0,
        total_invested=float(equity_investment),
    )
    # Payback is measured from FINANCIAL CLOSE, matching the equity IRR/NPV above: the
    # construction_years zeros precede the operating distributions so the cumulative-recovery
    # crossing lands at the true year-from-close (was operating-year-only, understating
    # payback by construction_years and disagreeing with the lagged IRR it sits beside).
    # cash_on_cash / MOIC / equity_multiple are ratios (timeline-invariant) and stay on
    # distribution_values.
    payback = calculate_payback_period(
        [0.0] * construction_years + distribution_values, float(equity_investment)
    )
    cash_on_cash = calculate_cash_on_cash(distribution_values, float(equity_investment))
    average_cash_on_cash = (
        float(sum(cash_on_cash) / len(cash_on_cash)) if cash_on_cash else 0.0
    )

    covenant_locked_years = sum(
        1 for row in annual_distributions if bool(row.get("covenant_locked"))
    )
    status = "defaulted" if investment_source == "defaulted" else "computed"

    return {
        "success": True,
        "status": status,
        "scenario_name": distribution_config.scenario_name,
        "equity_cashflows_usd": cashflows,
        "annual_distributions": annual_distributions,
        "equity_summary": {
            "equity_investment_usd": float(equity_investment),
            "equity_investment_source": investment_source,
            "total_equity_distributed_usd": total_distributed,
            "equity_irr": equity_irr,
            "equity_irr_pct": equity_irr * 100.0 if equity_irr is not None else None,
            "equity_npv": equity_npv,
            "equity_multiple": equity_multiple,
            "moic": moic,
            "payback_period_years": payback,
            "annual_cash_on_cash": cash_on_cash,
            "average_cash_on_cash": average_cash_on_cash,
            "covenant_locked_years": covenant_locked_years,
            "min_dscr_threshold": distribution_config.min_dscr_threshold,
            "min_reserve_months": distribution_config.min_reserve_months,
        },
        "metadata": {
            "computed_from": "canonical_v14_pipeline",
            "kpi_status": status,
            "distribution_sweep_pct": distribution_config.distribution_sweep_pct,
            "holdback_pct": distribution_config.holdback_pct,
            "discount_rate": distribution_config.discount_rate,
        },
    }


__all__ = [
    "EquityDistributionConfig",
    "build_equity_distribution_schedule",
    "calculate_equity_distribution_from_pipeline",
]
