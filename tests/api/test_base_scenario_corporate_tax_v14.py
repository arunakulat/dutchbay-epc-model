"""Golden regression: the base scenario produces NON-ZERO corporate tax (#59).

Guards against the legacy "$0 tax" artifact at the production tax-engine level.
Uses the canonical LKR tax engine (``finance.tax_profile_v14_hydra``) configured
from ``scenarios/dutchbay_basecase_2025Q4.yaml`` (config-first / ARCH-01). The base
scenario applies a 12-year tax holiday over a 20-year operating life, so corporate
tax is zero in years 1-12 and POSITIVE in years 13-20 — a non-zero total.

Operating inputs (CFADS, depreciable base, interest) are derived from the scenario
config rather than hardcoded, and interest is a *declining* amortizing schedule
(a flat schedule was the #59 root cause). Magnitudes only need to leave taxable
income positive after the holiday; the assertion is non-zero, not a pinned value.

Framework Compliance:
- TEST-01: regression guard (non-zero total corporate tax).
- CESSPIT / ARCH-01: tax + economic assumptions come from the scenario YAML.
"""

from __future__ import annotations

from typing import List

import pytest
from omegaconf import OmegaConf

from finance.tax_profile_v14_hydra import (
    build_tax_profile,
    calculate_tax_for_year,
    extract_tax_config_from_full_config,
)

BASE_SCENARIO = "scenarios/dutchbay_basecase_2025Q4.yaml"
HOURS_PER_YEAR = 8760.0
# Documented test approximations for the interest shield only (not scenario params):
TYPICAL_GEARING = 0.7
TYPICAL_DEBT_RATE = 0.08
DEBT_TENOR_YEARS = 15


@pytest.fixture
def base_case_config() -> object:
    """Load the canonical base scenario config (config-first / ARCH-01)."""
    return OmegaConf.load(BASE_SCENARIO)


def _build_profile(cfg: object) -> object:
    """Build the production TaxProfile from the base scenario tax block."""
    return build_tax_profile(
        config_tax=extract_tax_config_from_full_config(cfg),
        capex_depreciable_lkr=float(cfg.capex.usd_total) * float(cfg.fx.start_lkr_per_usd),
        project_life_years=int(cfg.returns.project_life_years),
        config_source=BASE_SCENARIO,
    )


def _pretax_cfads_lkr(cfg: object) -> float:
    """Approximate annual pre-tax CFADS (LKR) from the scenario's economics."""
    gen_kwh = (
        float(cfg.project.capacity_mw)
        * 1000.0
        * HOURS_PER_YEAR
        * float(cfg.project.capacity_factor)
    )
    revenue_lkr = gen_kwh * float(cfg.tariff.lkr_per_kwh)
    opex_lkr = float(cfg.opex.usd_per_year) * float(cfg.fx.start_lkr_per_usd)
    return revenue_lkr - opex_lkr


def _declining_interest_lkr(cfg: object, project_life: int) -> List[float]:
    """Amortizing (declining) annual interest in LKR over the project life."""
    debt_lkr = (
        float(cfg.capex.usd_total)
        * float(cfg.fx.start_lkr_per_usd)
        * TYPICAL_GEARING
    )
    principal = debt_lkr / DEBT_TENOR_YEARS
    interest: List[float] = []
    balance = debt_lkr
    for _ in range(project_life):
        interest.append(max(0.0, balance) * TYPICAL_DEBT_RATE)
        balance = max(0.0, balance - principal)
    return interest


def _annual_taxes(cfg: object) -> List[float]:
    """Per-year corporate tax (LKR) for the base scenario over its full life."""
    profile = _build_profile(cfg)
    life = int(cfg.returns.project_life_years)
    cfads = _pretax_cfads_lkr(cfg)
    interest = _declining_interest_lkr(cfg, life)
    return [
        calculate_tax_for_year(profile, cfads, interest[y], y)[0]
        for y in range(life)
    ]


def test_base_scenario_total_corporate_tax_is_nonzero(base_case_config: object) -> None:
    """GOLDEN (TEST-01): base scenario yields non-zero, non-negative total tax."""
    taxes = _annual_taxes(base_case_config)
    total_tax = float(sum(taxes))

    assert total_tax > 0.0, (
        f"Base scenario total corporate tax must be > 0 "
        f"(12-yr holiday over 20 ops years => years 13-20 taxed); got {total_tax:,.0f} LKR"
    )
    assert all(t >= 0.0 for t in taxes), "Per-year corporate tax must be non-negative"


def test_base_scenario_holiday_then_taxed(base_case_config: object) -> None:
    """Holiday years (1-12) are untaxed; at least one later year is taxed."""
    profile = _build_profile(base_case_config)
    taxes = _annual_taxes(base_case_config)
    life = int(base_case_config.returns.project_life_years)

    holiday = [taxes[y] for y in range(life) if profile.is_in_tax_holiday(y)]
    post_holiday = [taxes[y] for y in range(life) if not profile.is_in_tax_holiday(y)]

    assert holiday and all(t == pytest.approx(0.0) for t in holiday), (
        "Corporate tax must be zero during the 12-year tax holiday"
    )
    assert any(t > 0.0 for t in post_holiday), (
        "At least one post-holiday year must carry positive corporate tax"
    )
