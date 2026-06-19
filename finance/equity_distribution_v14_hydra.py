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

import json
import logging
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from omegaconf import DictConfig, OmegaConf
from pydantic import BaseModel, ConfigDict, Field, field_validator

from analytics.schema_guard import validate_config_for_v14
from finance.equity_v14 import (
    calculate_cash_on_cash,
    calculate_equity_irr,
    calculate_equity_npv,
    calculate_moic,
    calculate_payback_period,
)

logger = logging.getLogger(__name__)


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

    annual_distributable_cash_usd: float = Field(default=5e6, ge=0)
    equity_stake_pct: float = Field(default=25.0, ge=0, le=100)
    target_equity_irr_pct: float = Field(default=16.0, ge=0, le=50)

    priority_senior_debt_usd: float = Field(default=100e6, ge=0)
    priority_mezzanine_usd: float = Field(default=50e6, ge=0)
    reserve_fund_pct: float = Field(default=10.0, ge=0, le=100)

    min_dscr_threshold: float = Field(default=1.25, ge=0.0, le=5.0)
    min_llcr_threshold: float = Field(default=1.5, ge=0.0, le=5.0)
    min_reserve_months: int = Field(default=6, ge=0, le=24)

    distribution_sweep_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    holdback_pct: float = Field(default=0.0, ge=0.0, le=100.0)
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

    @field_validator("equity_stake_pct")
    @classmethod
    def validate_equity_stake(cls, v: float) -> float:
        """Validate equity stake percentage."""
        if not (0 <= v <= 100):
            raise ValueError(f"Equity stake % must be 0-100, got {v}")
        return v

    @field_validator("min_dscr_threshold")
    @classmethod
    def validate_dscr_threshold(cls, v: float) -> float:
        """Validate DSCR threshold."""
        if not (0.0 <= v <= 5.0):
            raise ValueError(f"DSCR threshold must be 0.0-5.0, got {v}")
        return v

    @field_validator("min_llcr_threshold")
    @classmethod
    def validate_llcr_threshold(cls, v: float) -> float:
        """Validate LLCR threshold."""
        if not (0.0 <= v <= 5.0):
            raise ValueError(f"LLCR threshold must be 0.0-5.0, got {v}")
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
    """Extract total CAPEX from canonical, compact, or legacy v14 schemas."""
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
        project = _section_case_insensitive(config, "Project") or _section_case_insensitive(
            config, "project"
        )
        if project:
            project_life = _lookup_case_insensitive(project, "project_life_years")

    return EquityDistributionConfig(
        scenario_name=scenario_name,
        enabled=bool(equity_section.get("enabled", True)),
        project_life_years=_as_int(project_life, 25),
        annual_distributable_cash_usd=float(
            _as_float(equity_section.get("annual_distributable_cash_usd"), 5e6)
            or 0.0
        ),
        equity_stake_pct=_normalise_percent(
            equity_section.get("equity_stake_pct"), 25.0
        ),
        target_equity_irr_pct=_normalise_percent(
            equity_section.get("target_equity_irr_pct"), 16.0
        ),
        priority_senior_debt_usd=float(
            _as_float(equity_section.get("priority_senior_debt_usd"), 100e6) or 0.0
        ),
        priority_mezzanine_usd=float(
            _as_float(equity_section.get("priority_mezzanine_usd"), 50e6) or 0.0
        ),
        reserve_fund_pct=_normalise_percent(equity_section.get("reserve_fund_pct"), 10.0),
        min_dscr_threshold=float(
            _as_float(equity_section.get("min_dscr_threshold"), 1.25) or 0.0
        ),
        min_llcr_threshold=float(
            _as_float(equity_section.get("min_llcr_threshold"), 1.5) or 0.0
        ),
        min_reserve_months=_as_int(equity_section.get("min_reserve_months"), 6),
        distribution_sweep_pct=_normalise_percent(
            equity_section.get("distribution_sweep_pct"), 100.0
        ),
        holdback_pct=_normalise_percent(equity_section.get("holdback_pct"), 0.0),
        terminal_value_usd=float(
            _as_float(equity_section.get("terminal_value_usd"), 0.0) or 0.0
        ),
        discount_rate=float(_as_float(equity_section.get("discount_rate"), 0.10) or 0.0),
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
    if distribution_config.equity_investment_usd is not None:
        return float(distribution_config.equity_investment_usd), "explicit"

    capex_usd = _extract_capex_usd(config)
    debt_total = _as_float(
        debt_result.get("debt_total")
        or debt_result.get("max_debt_usd")
        or debt_result.get("final_debt_usd")
    )

    if capex_usd is not None and debt_total is not None:
        return max(0.0, float(capex_usd) - float(debt_total)), "capex_less_debt"

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


def _extract_dscr(row: Mapping[str, Any], cf_pre_debt: float, debt_service: float) -> Optional[float]:
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
    reserve_balance = 0.0
    schedule: List[Dict[str, Any]] = []

    sweep = distribution_config.distribution_sweep_pct / 100.0
    holdback = distribution_config.holdback_pct / 100.0

    for index, row in enumerate(annual_rows):
        year_value = row.get("year", index + 1)
        year = int(float(year_value)) if year_value is not None else index + 1

        cf_pre_debt = _extract_cf_pre_debt(row)
        debt_service = _extract_debt_service(row, debt_service_series, index)
        cf_after_debt = max(0.0, cf_pre_debt - debt_service)
        dscr = _extract_dscr(row, cf_pre_debt, debt_service)

        reserve_required = debt_service * (
            float(distribution_config.min_reserve_months) / 12.0
        )
        reserve_topup_required = max(0.0, reserve_required - reserve_balance)
        reserve_funded = min(cf_after_debt, reserve_topup_required)
        reserve_balance += reserve_funded

        cash_after_reserve = max(0.0, cf_after_debt - reserve_funded)
        covenant_locked = bool(
            dscr is not None
            and distribution_config.min_dscr_threshold > 0.0
            and dscr < distribution_config.min_dscr_threshold
        )

        if covenant_locked:
            equity_distribution = 0.0
            retained_cash = cash_after_reserve
        else:
            gross_distribution = cash_after_reserve * sweep
            retained_cash = cash_after_reserve - gross_distribution
            holdback_amount = gross_distribution * holdback
            equity_distribution = max(0.0, gross_distribution - holdback_amount)
            retained_cash += holdback_amount

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
                "cf_after_debt_usd": cf_after_debt,
                "dscr": dscr,
                "covenant_locked": covenant_locked,
                "reserve_required_usd": reserve_required,
                "reserve_funded_usd": reserve_funded,
                "reserve_balance_usd": reserve_balance,
                "retained_cash_usd": retained_cash,
                "equity_distribution_usd": equity_distribution,
                "debt_outstanding_usd": debt_outstanding,
            }
        )

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
        annual_distributions[-1]["terminal_value_usd"] = (
            distribution_config.terminal_value_usd
        )
        annual_distributions[-1]["equity_distribution_usd"] = distribution_values[-1]

    cashflows = [-float(equity_investment)] + distribution_values

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
    payback = calculate_payback_period(distribution_values, float(equity_investment))
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
            "min_llcr_threshold": distribution_config.min_llcr_threshold,
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


def load_config(config_path: str) -> DictConfig:
    """Load and validate a Hydra/OmegaConf YAML config.

    Args:
        config_path: Path to YAML config file.

    Returns:
        Validated OmegaConf DictConfig object.

    Raises:
        ValueError: If config validation fails.
    """
    cfg = OmegaConf.load(config_path)
    if not isinstance(cfg, DictConfig):
        raise TypeError(
            f"Config root must be a mapping (DictConfig), got {type(cfg).__name__}"
        )
    logger.info("Loaded config from: %s", config_path)

    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(cfg_dict, dict):
        raise ValueError("Config must be a mapping (dict)")

    validate_config_for_v14(
        raw_config=cast("Mapping[str, Any]", cfg_dict),
        config_path=config_path,
        modules=["cashflow", "debt"],
    )
    logger.info("Schema validation passed (R5, R22)")

    return cfg


class EquityDistributionEngine:
    """Engine for legacy standalone equity distribution scenarios.

    The production integration should call
    calculate_equity_distribution_from_pipeline() with canonical v14 payload
    components. This class remains to support historical API tests and simple
    standalone equity-only scenarios.
    """

    def __init__(self, config: DictConfig) -> None:
        """Initialize equity distribution engine.

        Args:
            config: OmegaConf DictConfig with an equity section.

        Raises:
            ValueError: If config is missing the legacy equity section.
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        if not hasattr(config, "equity") or config.equity is None:
            raise ValueError("Config missing 'equity' section (R22)")

        self.equity_config = EquityDistributionConfig(
            scenario_name=config.equity.get("scenario_name", "default"),
            project_life_years=config.equity.get("project_life_years", 25),
            annual_distributable_cash_usd=config.equity.get(
                "annual_distributable_cash_usd", 5e6
            ),
            equity_stake_pct=config.equity.get("equity_stake_pct", 25.0),
            target_equity_irr_pct=config.equity.get("target_equity_irr_pct", 16.0),
            priority_senior_debt_usd=config.equity.get(
                "priority_senior_debt_usd", 100e6
            ),
            priority_mezzanine_usd=config.equity.get("priority_mezzanine_usd", 50e6),
            reserve_fund_pct=config.equity.get("reserve_fund_pct", 10.0),
            min_dscr_threshold=config.equity.get("min_dscr_threshold", 1.25),
            min_llcr_threshold=config.equity.get("min_llcr_threshold", 1.5),
            min_reserve_months=config.equity.get("min_reserve_months", 6),
            distribution_sweep_pct=config.equity.get("distribution_sweep_pct", 100.0),
            holdback_pct=config.equity.get("holdback_pct", 0.0),
            terminal_value_usd=config.equity.get("terminal_value_usd", 0.0),
            discount_rate=config.equity.get("discount_rate", 0.10),
        )
        self.config.min_dscr_threshold = self.equity_config.min_dscr_threshold
        self.config.min_llcr_threshold = self.equity_config.min_llcr_threshold
        self.config.min_reserve_months = self.equity_config.min_reserve_months
        self.logger.info(
            "Initialized EquityDistributionEngine: %s",
            self.equity_config.scenario_name,
        )

    def calculate_distributions(
        self,
        total_distributable_cash_usd: float,
        senior_debt_balance_usd: float,
        mezzanine_balance_usd: float,
    ) -> Dict[str, Any]:
        """Calculate legacy senior/mezzanine/equity distribution amounts."""
        remaining = total_distributable_cash_usd

        senior_payment = min(remaining, senior_debt_balance_usd)
        remaining -= senior_payment

        mezz_payment = min(remaining, mezzanine_balance_usd)
        remaining -= mezz_payment

        reserve_requirement = total_distributable_cash_usd * (
            self.equity_config.reserve_fund_pct / 100.0
        )
        reserve_funded = min(remaining, reserve_requirement)
        remaining -= reserve_funded

        equity_payment = remaining

        result: Dict[str, Any] = {
            "senior_debt_dist_usd": senior_payment,
            "mezzanine_dist_usd": mezz_payment,
            "reserve_fund_usd": reserve_funded,
            "equity_distribution_usd": max(0.0, equity_payment),
            "waterfall_complete": equity_payment >= 0.0,
        }

        self.logger.info(
            "Distributions: senior=%.2fM, mezz=%.2fM, equity=%.2fM",
            senior_payment / 1e6,
            mezz_payment / 1e6,
            equity_payment / 1e6,
        )

        return result

    def run(self) -> Dict[str, Any]:
        """Execute a legacy standalone equity distribution scenario."""
        try:
            self.logger.info("Starting: %s", self.equity_config.scenario_name)

            annual_distributions: List[Dict[str, Any]] = []
            remaining_senior = self.equity_config.priority_senior_debt_usd
            remaining_mezz = self.equity_config.priority_mezzanine_usd

            for year in range(1, self.equity_config.project_life_years + 1):
                dist = self.calculate_distributions(
                    self.equity_config.annual_distributable_cash_usd,
                    remaining_senior,
                    remaining_mezz,
                )
                dist["year"] = year
                annual_distributions.append(dist)
                remaining_senior = max(
                    0.0, remaining_senior - dist["senior_debt_dist_usd"]
                )
                remaining_mezz = max(0.0, remaining_mezz - dist["mezzanine_dist_usd"])

            total_equity_dist = sum(
                float(d["equity_distribution_usd"]) for d in annual_distributions
            )

            result: Dict[str, Any] = {
                "scenario_name": self.equity_config.scenario_name,
                "project_life_years": self.equity_config.project_life_years,
                "distributions": {
                    "annual_distributions": annual_distributions,
                    "total_equity_distributed_usd": total_equity_dist,
                },
                "equity_summary": {
                    "equity_irr_pct": self.equity_config.target_equity_irr_pct,
                    "total_distributions_usd": total_equity_dist,
                    "equity_stake_pct": self.equity_config.equity_stake_pct,
                    "min_dscr_threshold": self.equity_config.min_dscr_threshold,
                    "min_llcr_threshold": self.equity_config.min_llcr_threshold,
                },
                "success": True,
                "status": "computed",
            }

            self.logger.info("Completed: %s", self.equity_config.scenario_name)
            return result

        except Exception as e:
            self.logger.error("Failed: %s", str(e))
            return {
                "scenario_name": self.equity_config.scenario_name,
                "success": False,
                "status": "failed",
                "error": str(e),
            }


def main(config_path: str = "conf/scenarios/equity_base.yaml") -> None:
    """Run the standalone equity distribution CLI and write JSON to stdout.

    Args:
        config_path: Path to Hydra/OmegaConf configuration file.

    Raises:
        Exception: If execution fails.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger_main = logging.getLogger("equity_main")

    try:
        logger_main.info("Loading config: %s", config_path)
        cfg = load_config(config_path)
        engine = EquityDistributionEngine(cfg)
        result = engine.run()
        json_output = json.dumps(result, indent=2)
        logger_main.info("Results computed successfully")
        sys.stdout.write(json_output + "\n")
        logger_main.info("Results output to stdout (JSON)")

    except Exception as e:
        logger_main.error("Fatal error: %s", str(e), exc_info=True)
        error_result: Dict[str, Any] = {
            "success": False,
            "status": "failed",
            "error": str(e),
        }
        sys.stdout.write(json.dumps(error_result, indent=2) + "\n")
        raise


__all__ = [
    "EquityDistributionConfig",
    "EquityDistributionEngine",
    "build_equity_distribution_schedule",
    "calculate_equity_distribution_from_pipeline",
    "load_config",
    "main",
]


if __name__ == "__main__":
    from hydra import main as hydra_main

    @hydra_main(config_path="conf", config_name="equity", version_base="1.3")
    def cli(cfg: DictConfig) -> None:
        """CLI entry point via Hydra."""
        tmp_path = str(cfg.get("config_path", "conf/scenarios/equity_base.yaml"))
        main(tmp_path)

    cli()
