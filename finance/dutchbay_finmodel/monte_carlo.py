#!/usr/bin/env python3
"""Monte Carlo engine for Dutch Bay financial model."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .core import ModelConfig, build_financial_model, calculate_irr_robust


def generate_mc_parameters(
    n: int,
    base_cfg: ModelConfig,
    seed: int | None = None,
) -> pd.DataFrame:
    """Sample parameter sets.

    Distributions are deliberately transparent and conservative:
    - Capacity factor ~ N(mu, 0.03) truncated [0.25, 0.55]
    - CAPEX ~ lognormal s.t. ~±15% (1 sd)
    - Fixed OPEX ~ lognormal ±20%
    - Tariff escalation ~ N(0, 1%) truncated [-1%, +3%]
    """
    rng = np.random.default_rng(seed)

    cf = np.clip(
        rng.normal(loc=base_cfg.capacity_factor_p50, scale=0.03, size=n),
        0.25,
        0.55,
    )

    capex_mult = np.exp(rng.normal(loc=0.0, scale=0.15, size=n))
    opex_mult = np.exp(rng.normal(loc=0.0, scale=0.20, size=n))

    tariff_esc = np.clip(
        rng.normal(loc=base_cfg.tariff_indexation_pct, scale=0.01, size=n),
        -0.01,
        0.03,
    )

    return pd.DataFrame(
        {
            "capacity_factor_p50": cf,
            "capex_usd_mn": base_cfg.capex_usd_mn * capex_mult,
            "fixed_opex_lkr_mn_year1": base_cfg.fixed_opex_lkr_mn_year1 * opex_mult,
            "tariff_indexation_pct": tariff_esc,
        }
    )


def run_monte_carlo(
    n: int,
    base_cfg: ModelConfig,
    param_df: pd.DataFrame | None = None,
    seed: int | None = None,
) -> pd.DataFrame:
    """Run Monte Carlo and return scenario-level equity IRRs & constraints."""
    if param_df is None:
        param_df = generate_mc_parameters(n=n, base_cfg=base_cfg, seed=seed)

    results = []
    for i, row in param_df.iterrows():
        cfg = replace(
            base_cfg,
            capacity_factor_p50=float(row["capacity_factor_p50"]),
            capex_usd_mn=float(row["capex_usd_mn"]),
            fixed_opex_lkr_mn_year1=float(row["fixed_opex_lkr_mn_year1"]),
            tariff_indexation_pct=float(row["tariff_indexation_pct"]),
        )
        df, proj_cf, eq_cf, _ = build_financial_model(cfg)
        irr_info = calculate_irr_robust(eq_cf)
        eq_irr = irr_info["irr"]
        min_dscr = float(df["DSCR"].replace(np.inf, 9999).min())
        results.append(
            {
                "scenario": int(i),
                "equity_irr": eq_irr,
                "min_dscr": min_dscr,
                "dscr_breach": min_dscr < base_cfg.min_dscr_covenant,
            }
        )

    return pd.DataFrame(results)
