"""Golden regression: the base scenario produces NON-ZERO corporate tax (#59).

Guards against the legacy "$0 tax" artifact at the production tax-engine level,
using the **canonical** ``finance.cashflow_v14_tax`` engine (the lender pipeline's
engine). Migrated from the retired ``finance.tax_profile_v14_hydra`` as part of the
CCCDIR tax-engine de-duplication.

Under the current (post-2025 SL) regime the base scenario carries NO statutory tax
holiday, so corporate tax is shaped by the split (plant/civil) depreciation + TLCF
and turns positive once early-year depreciation tapers — a non-zero total.

Operating inputs (CFADS, depreciable base, interest) are derived from the scenario
config rather than hardcoded (CESSPIT / ARCH-01); interest is a *declining*
amortizing schedule (a flat schedule was the #59 root cause). Magnitudes only need
to leave taxable income positive after depreciation tapers; the assertion is
non-zero, not a pinned value.

Framework Compliance:
- TEST-01: regression guard (non-zero total corporate tax).
- CESSPIT / ARCH-01: tax + economic assumptions come from the scenario YAML.
- CCCDIR: single canonical tax contract (``finance.cashflow_v14_tax``).
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from omegaconf import OmegaConf

from finance.cashflow_v14_tax import (
    DepreciationSchedule,
    TaxConfig,
    build_tax_holiday_map,
    build_tax_profile,
    calculate_tax,
)

BASE_SCENARIO = "scenarios/dutchbay_basecase_2025Q4.yaml"
HOURS_PER_YEAR = 8760.0
# Fallback financing terms, used only if the scenario omits Financing_Terms
# (these defaults equal the base scenario's own values).
DEFAULT_GEARING = 0.7
DEFAULT_DEBT_RATE = 0.08
DEFAULT_DEBT_TENOR_YEARS = 15


@pytest.fixture
def base_cfg() -> Dict[str, Any]:
    """Load the canonical base scenario (config-first / ARCH-01) as a plain dict."""
    return OmegaConf.to_container(  # type: ignore[return-value]
        OmegaConf.load(BASE_SCENARIO), resolve=True
    )


def _capex_lkr(cfg: Dict[str, Any]) -> float:
    return float(cfg["capex"]["usd_total"]) * float(cfg["fx"]["start_lkr_per_usd"])


def _depreciation_schedule(
    cfg: Dict[str, Any], tc: TaxConfig, life: int
) -> DepreciationSchedule:
    """Build the production depreciation schedule: split when the config is split-mode."""
    capex = _capex_lkr(cfg)
    if (
        tc.plant_capex_share is not None
        and tc.plant_depreciation_years is not None
        and tc.civil_depreciation_years is not None
    ):
        return DepreciationSchedule.build_split_straight_line(
            total_capex=capex,
            plant_capex_share=tc.plant_capex_share,
            plant_useful_life=tc.plant_depreciation_years,
            civil_useful_life=tc.civil_depreciation_years,
            project_life=life,
        )
    return DepreciationSchedule.build_straight_line(
        capex_lkr=capex, useful_life=tc.depreciation_years, project_life=life
    )


def _pretax_cfads_lkr(cfg: Dict[str, Any]) -> float:
    """Approximate annual pre-tax CFADS (LKR) from the scenario economics."""
    gen_kwh = (
        float(cfg["project"]["capacity_mw"])
        * 1000.0
        * HOURS_PER_YEAR
        * float(cfg["project"]["capacity_factor"])
    )
    revenue_lkr = gen_kwh * float(cfg["tariff"]["lkr_per_kwh"])
    opex_lkr = float(cfg["opex"]["usd_per_year"]) * float(
        cfg["fx"]["start_lkr_per_usd"]
    )
    return revenue_lkr - opex_lkr


def _declining_interest_lkr(cfg: Dict[str, Any], life: int) -> List[float]:
    """Amortizing (declining) annual interest in LKR, geared from the scenario.

    Gearing, rate and tenor come from the scenario's Financing_Terms (config-first /
    ARCH-01), falling back to documented defaults only if absent.
    """
    ft = cfg.get("Financing_Terms", {}) or {}
    gearing = float(ft.get("debt_ratio", DEFAULT_GEARING))
    rate = float(ft.get("interest_rate_nominal", DEFAULT_DEBT_RATE))
    tenor = int(ft.get("tenor_years", DEFAULT_DEBT_TENOR_YEARS))
    debt_lkr = _capex_lkr(cfg) * gearing
    principal = debt_lkr / tenor
    interest: List[float] = []
    balance = debt_lkr
    for _ in range(life):
        interest.append(max(0.0, balance) * rate)
        balance = max(0.0, balance - principal)
    return interest


def _annual_taxes(cfg: Dict[str, Any]) -> List[float]:
    """Per-year corporate tax (LKR) over the full life, threading TLCF carried
    losses through the canonical ``calculate_tax`` engine."""
    life = int(cfg["returns"]["project_life_years"])
    tc = TaxConfig.from_yaml(cfg)
    sched = _depreciation_schedule(cfg, tc, life)
    tp = build_tax_profile(
        config=tc, depreciation_schedule=sched, project_life_years=life
    )
    cfads = _pretax_cfads_lkr(cfg)
    interest = _declining_interest_lkr(cfg, life)

    taxes: List[float] = []
    carried = 0.0
    for year in range(1, life + 1):
        result = calculate_tax(
            year=year,
            ebit=cfads,
            interest_expense=interest[year - 1],
            depreciation=sched.annual_amounts[year - 1],
            tax_profile=tp,
            prior_year_losses=carried,
        )
        taxes.append(result.tax_liability)
        carried = result.carried_forward_losses
    return taxes


def test_base_scenario_total_corporate_tax_is_nonzero(base_cfg: Dict[str, Any]) -> None:
    """GOLDEN (TEST-01): base scenario yields non-zero, non-negative total tax."""
    taxes = _annual_taxes(base_cfg)
    total_tax = float(sum(taxes))

    assert total_tax > 0.0, (
        f"Base scenario total corporate tax must be > 0 (current regime: no holiday, "
        f"tax emerges once split depreciation tapers); got {total_tax:,.0f} LKR"
    )
    assert all(t >= 0.0 for t in taxes), "Per-year corporate tax must be non-negative"


def test_base_scenario_no_statutory_holiday(base_cfg: Dict[str, Any]) -> None:
    """Current regime (post-2025 SL): the base scenario carries NO statutory tax
    holiday — no untaxed holiday window; tax is shaped by depreciation/TLCF (cf. the
    removed 12-year renewable holiday), and the total stays positive."""
    life = int(base_cfg["returns"]["project_life_years"])
    tc = TaxConfig.from_yaml(base_cfg)
    holidays = build_tax_holiday_map(tc, project_life_years=life)

    assert not any(
        holidays[y] for y in range(1, life + 1)
    ), "Base scenario should have no statutory tax holiday under the post-2025 regime"
    taxes = _annual_taxes(base_cfg)
    assert sum(taxes) > 0.0
    assert any(
        t > 0.0 for t in taxes
    ), "At least one year must carry positive corporate tax"
