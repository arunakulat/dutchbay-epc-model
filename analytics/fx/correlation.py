from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

"""
FX correlation and USD debt paydown analysis.

Corrected model:

    DSCR = LKR Revenue / [LKR Debt + (USD Debt × FX)]

Features:
- Fixed LKR tariff revenue
- Mixed currency debt structure (LKR + USD)
- Negative FX correlation (weaker LKR → worse DSCR)
- USD debt paydown scheduling
- Sensitivity and scenario analysis
- Simple Monte Carlo-style stress exploration
"""


@dataclass
class FXStats:
    mean_fx: float
    std_fx: float
    min_fx: float
    max_fx: float
    autocorr_lag1: float
    fx_column: str


class FXCorrelationModule:
    """
    FX correlation and USD debt paydown module.

    DSCR = LKR Revenue / [LKR Debt + (USD Debt × FX)]
    """

    def __init__(
        self,
        monthly_fx_df: pd.DataFrame,
        annual_lkr_revenue: float,
        annual_lkr_debt: float,
        annual_usd_debt: float,
        base_fx_rate: float = 305.0,
    ) -> None:
        """
        Initialize the FX correlation module.

        Args:
            monthly_fx_df: DataFrame with FX rate history.
            annual_lkr_revenue: Fixed annual revenue in LKR.
            annual_lkr_debt: Annual LKR debt service.
            annual_usd_debt: Annual USD debt service (USD nominal).
            base_fx_rate: Baseline FX rate (LKR / USD).
        """
        self.monthly_fx = monthly_fx_df.copy()

        # Normalize date column if present
        if "Year-Month" in self.monthly_fx.columns:
            self.monthly_fx["Year-Month"] = pd.to_datetime(
                self.monthly_fx["Year-Month"]
            )
            self.monthly_fx = self.monthly_fx.sort_values("Year-Month")

        # Financial structure
        self.annual_lkr_revenue = annual_lkr_revenue
        self.annual_lkr_debt = annual_lkr_debt
        self.annual_usd_debt_origination = annual_usd_debt
        self.base_fx_rate = base_fx_rate

        # Debt mix in USD-equivalent terms
        total_debt_usd_equiv = (annual_lkr_debt / base_fx_rate) + annual_usd_debt
        if total_debt_usd_equiv > 0:
            self.usd_debt_ratio = annual_usd_debt / total_debt_usd_equiv
            self.lkr_debt_ratio = (
                annual_lkr_debt / base_fx_rate
            ) / total_debt_usd_equiv
        else:
            self.usd_debt_ratio = 0.0
            self.lkr_debt_ratio = 0.0

        # Choose FX column
        if "avg_rate" in self.monthly_fx.columns:
            fx_col = "avg_rate"
        elif "Avg FX Rate" in self.monthly_fx.columns:
            fx_col = "Avg FX Rate"
        else:
            # Fallback to second column if nothing standard is present
            fx_col = self.monthly_fx.columns[1]

        self.fx_stats = FXStats(
            mean_fx=float(self.monthly_fx[fx_col].mean()),
            std_fx=float(self.monthly_fx[fx_col].std()),
            min_fx=float(self.monthly_fx[fx_col].min()),
            max_fx=float(self.monthly_fx[fx_col].max()),
            autocorr_lag1=float(self.monthly_fx[fx_col].autocorr(lag=1)),
            fx_column=fx_col,
        )

    # --------------------------------------------------------------------- #
    # Core DSCR logic
    # --------------------------------------------------------------------- #

    @staticmethod
    def calculate_dscr(
        annual_lkr_revenue: float,
        annual_lkr_debt: float,
        annual_usd_debt: float,
        fx_rate: float,
    ) -> float:
        """
        Compute DSCR given LKR and USD debt and an FX rate.

        DSCR = LKR Revenue / [LKR Debt + (USD Debt × FX)]
        """
        usd_debt_in_lkr = annual_usd_debt * fx_rate
        total_debt_lkr = annual_lkr_debt + usd_debt_in_lkr

        if total_debt_lkr == 0.0:
            return float("nan")

        return annual_lkr_revenue / total_debt_lkr

    # --------------------------------------------------------------------- #
    # Sensitivity analysis
    # --------------------------------------------------------------------- #

    def fx_sensitivity_analysis(
        self,
        fx_range_pct: Optional[List[float]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Sensitivity of DSCR to FX movements (negative correlation expected).

        Args:
            fx_range_pct: List of FX change percentages to test.
                Example default: [-30, -20, -10, -5, 0, 5, 10, 20, 30].

        Returns:
            Mapping from FX change label to metrics.
        """
        if fx_range_pct is None:
            fx_range_pct = [-30, -20, -10, -5, 0, 5, 10, 20, 30]

        results: Dict[str, Dict[str, float]] = {}

        base_dscr = self.calculate_dscr(
            self.annual_lkr_revenue,
            self.annual_lkr_debt,
            self.annual_usd_debt_origination,
            self.base_fx_rate,
        )

        for pct_change in fx_range_pct:
            fx_rate = self.base_fx_rate * (1.0 + pct_change / 100.0)
            dscr = self.calculate_dscr(
                self.annual_lkr_revenue,
                self.annual_lkr_debt,
                self.annual_usd_debt_origination,
                fx_rate,
            )

            if base_dscr != 0.0 and not np.isnan(base_dscr) and not np.isnan(dscr):
                dscr_change_pct = (dscr - base_dscr) / base_dscr * 100.0
            else:
                dscr_change_pct = 0.0

            results[f"{pct_change:+d}%"] = {
                "fx_rate": fx_rate,
                "dscr": dscr,
                "dscr_change_pct": dscr_change_pct,
            }

        return results

    # --------------------------------------------------------------------- #
    # Paydown schedule analysis
    # --------------------------------------------------------------------- #

    def paydown_schedule_analysis(
        self,
        paydown_scenarios: Optional[Dict[str, float]] = None,
        years: int = 15,
    ) -> Dict[str, List[Dict[str, float]]]:
        """
        Analyze DSCR improvement under different USD debt paydown schedules.

        Args:
            paydown_scenarios: Scenario → target cumulative USD debt reduction (0–1).
            years: Projection horizon in years.

        Returns:
            Mapping from scenario name to a list of yearly metrics.
        """
        if paydown_scenarios is None:
            paydown_scenarios = {
                "Current (55% USD)": 0.00,
                "Phase 1 (25% USD)": 0.55,  # reduce to ~25% of original
                "Phase 2 (10% USD)": 0.82,  # reduce to ~10% of original
                "Full Payoff (0% USD)": 1.00,  # eliminate USD debt
            }

        results: Dict[str, List[Dict[str, float]]] = {}

        for scenario_name, paydown_pct in paydown_scenarios.items():
            scenario_results: List[Dict[str, float]] = []

            for year in range(1, years + 1):
                # Linear paydown schedule
                usd_debt_remaining = self.annual_usd_debt_origination * (
                    1.0 - paydown_pct * (year / years)
                )

                dscr = self.calculate_dscr(
                    self.annual_lkr_revenue,
                    self.annual_lkr_debt,
                    usd_debt_remaining,
                    self.base_fx_rate,
                )

                total_debt_usd = (
                    self.annual_lkr_debt / self.base_fx_rate
                ) + usd_debt_remaining
                if total_debt_usd > 0.0:
                    usd_ratio = usd_debt_remaining / total_debt_usd
                else:
                    usd_ratio = 0.0

                scenario_results.append(
                    {
                        "year": float(year),
                        "usd_debt": usd_debt_remaining,
                        "usd_ratio_pct": usd_ratio * 100.0,
                        "dscr": dscr,
                    }
                )

            results[scenario_name] = scenario_results

        return results

    # --------------------------------------------------------------------- #
    # FX shock stress testing
    # --------------------------------------------------------------------- #

    def stress_test_paydown_scenarios(
        self,
        paydown_scenarios: Optional[Dict[str, float]] = None,
        fx_shocks: Optional[List[float]] = None,
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Stress test paydown scenarios against discrete FX rate levels.

        Args:
            paydown_scenarios: USD debt paydown targets (% reduction as 0–1).
            fx_shocks: FX levels to test, e.g. [220, 250, 305, 350, 365, 396].

        Returns:
            Nested mapping: scenario → FX description → metrics.
        """
        if paydown_scenarios is None:
            paydown_scenarios = {
                "Current (55% USD)": 0.00,
                "Phase 1 (25% USD)": 0.55,
                "Phase 2 (10% USD)": 0.82,
                "Full Payoff (0% USD)": 1.00,
            }

        if fx_shocks is None:
            fx_shocks = [220.0, 250.0, 305.0, 350.0, 365.0, 396.0]

        results: Dict[str, Dict[str, Dict[str, float]]] = {}

        for scenario_name, paydown_pct in paydown_scenarios.items():
            usd_debt = self.annual_usd_debt_origination * (1.0 - paydown_pct)
            fx_results: Dict[str, Dict[str, float]] = {}

            for fx_rate in fx_shocks:
                dscr = self.calculate_dscr(
                    self.annual_lkr_revenue,
                    self.annual_lkr_debt,
                    usd_debt,
                    fx_rate,
                )

                fx_description = self._interpret_fx_rate(fx_rate)
                key = f"{fx_rate:.0f} ({fx_description})"
                fx_results[key] = {
                    "fx_rate": fx_rate,
                    "dscr": dscr,
                    "viable": float(dscr >= 1.0),
                }

            results[scenario_name] = fx_results

        return results

    # --------------------------------------------------------------------- #
    # Simple Monte Carlo-style paydown exploration
    # --------------------------------------------------------------------- #

    def monte_carlo_paydown_optimization(
        self,
        fx_scenarios: int = 1000,
        years_ahead: int = 15,
        target_dscr: float = 1.25,
    ) -> Dict[str, object]:
        """
        Explore USD paydown speeds under random FX paths.

        Args:
            fx_scenarios: Number of FX paths.
            years_ahead: Projection horizon.
            target_dscr: Target DSCR guardrail.

        Returns:
            Summary with breach probabilities and suggested speeds.
        """
        results: Dict[str, object] = {
            "scenarios_tested": fx_scenarios,
            "years_ahead": years_ahead,
            "target_dscr": target_dscr,
            "paydown_recommendations": {},
        }

        paydown_speeds = np.linspace(0.0, 1.0, 11)  # 0% to 100% over period

        for paydown_speed in paydown_speeds:
            breaches = 0
            min_dscr = float("inf")

            for _ in range(fx_scenarios):
                fx_path = self._generate_fx_path(years_ahead)

                for year, fx_rate in enumerate(fx_path, start=1):
                    usd_debt = self.annual_usd_debt_origination * (
                        1.0 - paydown_speed * (year / years_ahead)
                    )

                    dscr = self.calculate_dscr(
                        self.annual_lkr_revenue,
                        self.annual_lkr_debt,
                        usd_debt,
                        float(fx_rate),
                    )

                    if dscr < 1.0:
                        breaches += 1
                    if dscr < min_dscr:
                        min_dscr = dscr

            total_periods = fx_scenarios * years_ahead
            breach_probability = breaches / total_periods if total_periods > 0 else 0.0
            recommendation = (
                "recommended"
                if breach_probability < 0.05 and min_dscr >= target_dscr
                else ""
            )

            results["paydown_recommendations"][
                f"{paydown_speed*100:.0f}% USD reduction"
            ] = {
                "paydown_speed": paydown_speed,
                "breach_probability": breach_probability,
                "min_dscr_observed": min_dscr,
                "recommendation": recommendation,
            }

        return results

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _generate_fx_path(self, months: int) -> np.ndarray:
        """
        Generate a synthetic FX path using a simple random-walk model
        with mean reversion and autoregressive component.
        """
        stats = self.fx_stats
        path = np.zeros(months, dtype=float)
        path[0] = self.base_fx_rate

        for t in range(1, months):
            # Mean reversion toward historical mean
            drift = (stats.mean_fx - self.base_fx_rate) / max(months * 12, 1)
            shock = float(np.random.normal(0.0, stats.std_fx / 100.0))
            correlation = (
                stats.autocorr_lag1
                * (path[t - 1] - self.base_fx_rate)
                / max(self.base_fx_rate, 1e-9)
            )

            pct_change = drift + shock + correlation * 0.01
            path[t] = path[t - 1] * (1.0 + pct_change)
            path[t] = float(np.clip(path[t], stats.min_fx * 0.8, stats.max_fx * 1.2))

        return path

    @staticmethod
    def _interpret_fx_rate(fx_rate: float) -> str:
        """Map FX level to a qualitative descriptor."""
        if fx_rate < 220.0:
            return "Strong LKR"
        if fx_rate < 280.0:
            return "Pre-2022"
        if fx_rate < 330.0:
            return "Current zone"
        if fx_rate < 365.0:
            return "Weak/Crisis"
        return "Extreme (2022-like)"

    # --------------------------------------------------------------------- #
    # Lightweight audit report
    # --------------------------------------------------------------------- #

    def generate_audit_report(self) -> Dict[str, object]:
        """Return a structured summary for logging or inspection."""
        base_dscr = self.calculate_dscr(
            self.annual_lkr_revenue,
            self.annual_lkr_debt,
            self.annual_usd_debt_origination,
            self.base_fx_rate,
        )

        return {
            "module": "FXCorrelationModule",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "financial_structure": {
                "annual_lkr_revenue": self.annual_lkr_revenue,
                "annual_lkr_debt": self.annual_lkr_debt,
                "annual_usd_debt": self.annual_usd_debt_origination,
                "usd_debt_ratio": self.usd_debt_ratio,
                "base_fx_rate": self.base_fx_rate,
                "base_dscr": base_dscr,
            },
            "fx_statistics": {
                "mean_fx": self.fx_stats.mean_fx,
                "std_fx": self.fx_stats.std_fx,
                "min_fx": self.fx_stats.min_fx,
                "max_fx": self.fx_stats.max_fx,
                "autocorr_lag1": self.fx_stats.autocorr_lag1,
                "fx_column": self.fx_stats.fx_column,
            },
            "model_type": "Negative FX correlation",
            "status": "production_ready",
        }
