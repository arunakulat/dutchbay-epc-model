"""Golden regression: the base scenario produces NON-ZERO corporate tax (#59).

Guards against the legacy "$0 tax" artifact at the production tax-engine level.
Uses the LKR tax engine (``finance.tax_profile_v14_hydra``) configured from
``scenarios/dutchbay_basecase_2025Q4.yaml`` (config-first / ARCH-01). Under the
current (post-2025 SL) regime the base scenario carries NO statutory tax holiday,
so corporate tax is shaped by depreciation/TLCF and turns positive once early-year
depreciation tapers — a non-zero total.

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
# Fallback financing terms, used only if the scenario omits Financing_Terms
# (these defaults equal the base scenario's own values).
DEFAULT_GEARING = 0.7
DEFAULT_DEBT_RATE = 0.08
DEFAULT_DEBT_TENOR_YEARS = 15


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
    """Amortizing (declining) annual interest in LKR, geared from the scenario.

    Gearing, rate and tenor are sourced from the scenario's Financing_Terms
    (config-first / ARCH-01), falling back to documented defaults only if absent.
    """
    gearing = float(
        OmegaConf.select(cfg, "Financing_Terms.debt_ratio", default=DEFAULT_GEARING)
    )
    rate = float(
        OmegaConf.select(
            cfg, "Financing_Terms.interest_rate_nominal", default=DEFAULT_DEBT_RATE
        )
    )
    tenor = int(
        OmegaConf.select(
            cfg, "Financing_Terms.tenor_years", default=DEFAULT_DEBT_TENOR_YEARS
        )
    )
    debt_lkr = float(cfg.capex.usd_total) * float(cfg.fx.start_lkr_per_usd) * gearing
    principal = debt_lkr / tenor
    interest: List[float] = []
    balance = debt_lkr
    for _ in range(project_life):
        interest.append(max(0.0, balance) * rate)
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


def test_base_scenario_no_statutory_holiday(base_case_config: object) -> None:
    """Current regime (post-2025 SL): the base scenario carries NO statutory tax
    holiday — no untaxed holiday window; tax is shaped by depreciation/TLCF (cf. the
    removed 12-year renewable holiday), and the total stays positive."""
    profile = _build_profile(base_case_config)
    taxes = _annual_taxes(base_case_config)
    life = int(base_case_config.returns.project_life_years)

    # No holiday window under the current regime.
    assert not any(profile.is_in_tax_holiday(y) for y in range(life)), (
        "Base scenario should have no statutory tax holiday under the post-2025 regime"
    )
    # Positive total tax, and at least one year taxed once depreciation tapers.
    assert sum(taxes) > 0.0
    assert any(t > 0.0 for t in taxes), (
        "At least one year must carry positive corporate tax"
    )
