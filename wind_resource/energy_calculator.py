"""Wind Farm Energy Production and Revenue Calculator.

Calculates Annual Energy Production (AEP) from wind speed data using:
- Turbine power curves
- Loss factors (availability, wake, electrical, etc.)
- P-level scenarios (P50, P75, P90)
- Revenue projections with configurable tariffs

All configuration loaded from YAML files (config-first, GWTF ARCH-01).

SCOPE / WIND-4 (#484): this is the TIMESERIES-INTEGRATION AEP path used by the
``wind_resource`` diagnostic pipeline (``wind_pipeline.WindPipeline``,
``era5_retrieval.compute_site_aep``). It is NOT on the lender FINANCE path — the canonical
bankable headline (net P50 464.3 GWh, frozen into ``scenarios/aep_summary_dutchbay_10mw.json``)
is produced by the analytic-Weibull integrator
``analytics.wind.aep_summary_builder → analytics.wind.aep_tornado.gross_aep_farm_gwh``, which
``run_v14_pipeline`` consumes. The 2026 deep-research audit (WIND-4) alleged this calculator
"double-counts wake and mislabels gross"; that was re-verified against the code and is NOT the
case: ``calculate_gross_aep`` integrates the power curve over the raw wind timeseries to a TRUE
gross AEP, ``calculate_net_aep`` then applies the loss stack (wake, availability, electrical,
curtailment, other) exactly ONCE as a single multiplicative ``total_loss_factor`` — there is no
wake-adjusted wind speed and therefore no double-loss path — and the pre-loss result is labelled
``gross``/``windfarm_aep_mwh`` correctly. So no fix is required here; this note records the
verified disposition so the unfounded claim is not re-litigated.

Typical usage:
    >>> from wind_resource import EnergyCalculator
    >>> import pandas as pd
    >>> df = pd.read_csv('dutchbay_wind_150m.csv')
    >>> calculator = EnergyCalculator(
    ...     df=df,
    ...     ws_column='ws_150m',
    ...     turbine_model='envision_en171_6p5',
    ...     num_turbines=15
    ... )
    >>> results = calculator.generate_complete_assessment()
    >>> print(f"Net AEP P75: {results['net_aep']['net_aep_p75_mwh']:,.0f} MWh/year")

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (CCCDIR Compliant)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml
from scipy import interpolate

from wind_resource.bankable_aep import UncertaintyBudget, exceedance_levels

logger = logging.getLogger(__name__)


class EnergyCalculator:
    """Calculate Annual Energy Production from wind data.

    Applies power curves, loss factors, and P-level scenarios to
    compute gross/net AEP and revenue projections. All configuration
    loaded from YAML files (CCCDIR compliant).

    Attributes:
        df: DataFrame with wind speed data.
        ws_column: Wind speed column name.
        power_curve_func: Interpolated power curve function.
        rated_capacity: Rated capacity per turbine (kW).
        num_turbines: Number of turbines in wind farm.
        losses: Loss factors dict from config.
        p_levels: P-level adjustment factors from config.
        tariff: Electricity tariff (LKR/kWh) from config.
        exchange_rate: LKR to USD exchange rate from config.

    Example:
        >>> calc = EnergyCalculator(df, turbine_model='envision_en171_6p5')
        >>> gross = calc.calculate_gross_aep()
        >>> print(f"Capacity Factor: {gross['capacity_factor_gross']:.1f}%")
    """

    def __init__(
        self,
        df: pd.DataFrame,
        ws_column: str = "ws_150m",
        turbine_model: Optional[str] = None,
        power_curve: Optional[Dict[str, List[float]]] = None,
        num_turbines: Optional[int] = None,
        config_path: Optional[str] = None,
        power_curves_path: Optional[str] = None,
    ) -> None:
        """Initialize energy calculator with configuration.

        Args:
            df: DataFrame with wind speed data and timestamp index.
            ws_column: Wind speed column name. Default 'ws_150m'.
            turbine_model: Turbine model name from power_curves.yaml.
                Example: 'envision_en171_6p5'. If None, must provide power_curve.
            power_curve: Manual power curve dict with 'ws' and 'power' lists.
                Only used if turbine_model is None.
            num_turbines: Number of turbines in wind farm. Required (config-driven;
                no default — raises ValueError if omitted).
            config_path: Path to era5_config.yaml. If None, uses default.
            power_curves_path: Path to power_curves.yaml. If None, uses default.

        Raises:
            ValueError: If neither turbine_model nor power_curve provided,
                or if DataFrame is invalid.
            FileNotFoundError: If config files not found.
        """
        # Validate inputs
        if turbine_model is None and power_curve is None:
            raise ValueError(
                "Must provide either 'turbine_model' or 'power_curve'. "
                "Example: turbine_model='envision_en171_6p5'"
            )

        # ARCH-01 / CESSPIT: num_turbines must be supplied by the caller from config —
        # no silent default (a hidden 15 would masquerade as a wrong farm size).
        if num_turbines is None:
            raise ValueError(
                "num_turbines is required (config-driven; no silent default). "
                "Pass it from resource.turbines.count / turbine.n_turbines."
            )

        if ws_column not in df.columns:
            raise ValueError(f"Wind speed column '{ws_column}' not found in DataFrame.")

        self.df = df
        self.ws_column = ws_column
        self.num_turbines = num_turbines

        # Load configurations (CCCDIR compliance)
        self._load_config(config_path)

        # Load power curve
        if turbine_model is not None:
            self._load_power_curve_from_config(turbine_model, power_curves_path)
        else:
            # turbine_model is None here, so power_curve is non-None (validated above)
            assert power_curve is not None
            self._load_power_curve_manual(power_curve)

        logger.info("EnergyCalculator v1.0.0 initialized (CCCDIR compliant)")
        logger.info(f"  Turbines: {num_turbines}")
        logger.info(f"  Rated capacity: {self.rated_capacity} kW")
        logger.info(
            f"  Total capacity: {self.rated_capacity * num_turbines / 1000:.1f} MW"
        )

    def _load_config(self, config_path: Optional[str]) -> None:
        """Load configuration from era5_config.yaml.

        Args:
            config_path: Path to config file, or None for default.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            KeyError: If required config sections are missing.
        """
        config_file = (
            Path(__file__).parent / "config" / "era5_config.yaml"
            if config_path is None
            else Path(config_path)
        )

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_file) as f:
            self.config = yaml.safe_load(f)

        # Extract values (CCCDIR: no hardcoded values)
        try:
            self.losses = self.config["losses"]
            self.p_levels = self.config["p_levels"]
            self.tariff = self.config["revenue"]["default_tariff_lkr_kwh"]
            self.exchange_rate = self.config["revenue"]["default_exchange_rate_lkr_usd"]
            self.ppa_years = self.config["revenue"]["ppa_years"]
        except KeyError as e:
            raise KeyError(
                f"Missing required config key: {e}. "
                "Check era5_config.yaml structure."
            ) from e

        logger.debug(
            f"Config loaded: total_loss_factor={self._calculate_total_loss():.3f}"
        )

    def _load_power_curve_from_config(
        self, turbine_model: str, power_curves_path: Optional[str]
    ) -> None:
        """Load power curve from power_curves.yaml.

        Args:
            turbine_model: Turbine model name.
            power_curves_path: Path to power curves file, or None for default.

        Raises:
            FileNotFoundError: If power curves file not found.
            KeyError: If turbine model not in config.
        """
        curves_file = (
            Path(__file__).parent / "config" / "power_curves.yaml"
            if power_curves_path is None
            else Path(power_curves_path)
        )

        if not curves_file.exists():
            raise FileNotFoundError(f"Power curves file not found: {curves_file}")

        with open(curves_file) as f:
            power_curves = yaml.safe_load(f)

        if turbine_model not in power_curves:
            available = list(power_curves.keys())
            raise KeyError(
                f"Turbine model '{turbine_model}' not found in power_curves.yaml. "
                f"Available models: {available}"
            )

        turbine_data = power_curves[turbine_model]
        self.rated_capacity = turbine_data["rated_capacity_kw"]

        # Create interpolation function
        ws = np.array(turbine_data["power_curve"]["ws"])
        power = np.array(turbine_data["power_curve"]["power"])

        self.power_curve_func = interpolate.interp1d(
            ws,
            power,
            kind="linear",
            bounds_error=False,
            fill_value=(0, 0),  # 0 power outside range
        )

        logger.info(f"Loaded power curve: {turbine_model}")
        logger.info(f"  Cut-in: {turbine_data['cut_in']} m/s")
        logger.info(f"  Rated: {turbine_data['rated']} m/s")
        logger.info(f"  Cut-out: {turbine_data['cut_out']} m/s")

    def _load_power_curve_manual(self, power_curve: Dict[str, List[float]]) -> None:
        """Load manually provided power curve.

        Args:
            power_curve: Dict with 'ws' and 'power' lists.

        Raises:
            ValueError: If power curve format is invalid.
        """
        if "ws" not in power_curve or "power" not in power_curve:
            raise ValueError(
                "power_curve must have 'ws' and 'power' keys. "
                f"Got: {list(power_curve.keys())}"
            )

        ws = np.array(power_curve["ws"])
        power = np.array(power_curve["power"])

        if len(ws) != len(power):
            raise ValueError(
                f"ws and power arrays must have same length. "
                f"Got: {len(ws)} vs {len(power)}"
            )

        self.rated_capacity = float(max(power))

        self.power_curve_func = interpolate.interp1d(
            ws, power, kind="linear", bounds_error=False, fill_value=(0, 0)
        )

        logger.info(f"Loaded manual power curve: {len(ws)} points")

    def _calculate_total_loss(self) -> float:
        """Calculate total loss factor from individual losses.

        Returns:
            Total loss factor (0-1). Example: 0.876 = 12.4% total loss.
        """
        total = 1.0
        for loss_factor in self.losses.values():
            total *= loss_factor
        return total

    def calculate_gross_aep(self) -> Dict[str, float]:
        """Calculate gross Annual Energy Production (no losses).

        Returns:
            Dict with keys:
                - average_power_kw: Mean power output per turbine (kW).
                - capacity_factor_gross: Gross capacity factor (%).
                - single_turbine_aep_mwh: AEP for one turbine (MWh/year).
                - windfarm_aep_mwh: Total AEP for all turbines (MWh/year).

        Example:
            >>> gross = calc.calculate_gross_aep()
            >>> print(f"Gross CF: {gross['capacity_factor_gross']:.1f}%")
            Gross CF: 42.5%
        """
        # Apply power curve to wind speeds
        wind_speeds = self.df[self.ws_column].to_numpy()
        power_output = self.power_curve_func(wind_speeds)

        # Average power (kW)
        average_power_kw = float(np.mean(power_output))

        # Capacity factor (%)
        capacity_factor_gross = (average_power_kw / self.rated_capacity) * 100

        # Annual energy (MWh/year)
        hours_per_year = 8760
        single_turbine_aep_mwh = (average_power_kw * hours_per_year) / 1000
        windfarm_aep_mwh = single_turbine_aep_mwh * self.num_turbines

        results = {
            "average_power_kw": average_power_kw,
            "capacity_factor_gross": capacity_factor_gross,
            "single_turbine_aep_mwh": single_turbine_aep_mwh,
            "windfarm_aep_mwh": windfarm_aep_mwh,
        }

        logger.info(
            f"Gross AEP: {windfarm_aep_mwh:,.0f} MWh/year, CF: {capacity_factor_gross:.1f}%"
        )

        return results

    def calculate_net_aep(
        self, gross_aep_mwh: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculate net AEP with losses for P50/P75/P90 scenarios.

        Args:
            gross_aep_mwh: Gross AEP in MWh/year. If None, calculates it.

        Returns:
            Dict with keys:
                - gross_aep_mwh: Gross AEP (MWh/year).
                - total_loss_factor: Combined loss factor (0-1).
                - individual_losses: Dict of individual loss factors.
                - net_aep_p50_mwh: Net AEP at P50 (MWh/year).
                - net_aep_p75_mwh: Net AEP at P75 (MWh/year).
                - net_aep_p90_mwh: Net AEP at P90 (MWh/year).
                - capacity_factor_net_p50: Net CF at P50 (%).
                - capacity_factor_net_p75: Net CF at P75 (%).
                - capacity_factor_net_p90: Net CF at P90 (%).

        Example:
            >>> net = calc.calculate_net_aep()
            >>> print(f"Net AEP P75: {net['net_aep_p75_mwh']:,.0f} MWh/year")
            Net AEP P75: 286,320 MWh/year
        """
        if gross_aep_mwh is None:
            gross_results = self.calculate_gross_aep()
            gross_aep_mwh = gross_results["windfarm_aep_mwh"]

        # Calculate total loss factor (CCCDIR: from config)
        total_loss = self._calculate_total_loss()

        # Net P50 (base case). P75/P90 come from the canonical IEC 61400-15-2
        # exceedance build-up (single source of truth: wind_resource.bankable_aep),
        # NOT a flat planning haircut that mislabeled a crude multiplier (e.g. 0.80
        # ~= P99) as an exceedance P-value. Finance does not consume this timeseries
        # path (it uses the bankable aep_summary), so headline economics are
        # unaffected; this corrects the secondary wind-diagnostic P-values only.
        net_p50 = gross_aep_mwh * total_loss * self.p_levels["p50"]
        _exc = exceedance_levels(
            net_p50 / 1000.0, UncertaintyBudget(), life_years=int(self.ppa_years)
        )
        net_p75 = _exc.p75_gwh * 1000.0
        net_p90 = _exc.p90_1yr_gwh * 1000.0

        # Net capacity factors
        total_capacity_mw = (self.rated_capacity * self.num_turbines) / 1000
        cf_net_p50 = (net_p50 / (total_capacity_mw * 8760)) * 100
        cf_net_p75 = (net_p75 / (total_capacity_mw * 8760)) * 100
        cf_net_p90 = (net_p90 / (total_capacity_mw * 8760)) * 100

        results = {
            "gross_aep_mwh": gross_aep_mwh,
            "total_loss_factor": total_loss,
            "individual_losses": self.losses,
            "net_aep_p50_mwh": net_p50,
            "net_aep_p75_mwh": net_p75,
            "net_aep_p90_mwh": net_p90,
            "capacity_factor_net_p50": cf_net_p50,
            "capacity_factor_net_p75": cf_net_p75,
            "capacity_factor_net_p90": cf_net_p90,
            "pvalue_method": "iec_61400_15_2",
            "uncertainty_sigma_1yr_pct": _exc.sigma_1yr_pct,
        }

        logger.info(f"Net AEP P50: {net_p50:,.0f} MWh/year (CF: {cf_net_p50:.1f}%)")
        logger.info(f"Net AEP P75: {net_p75:,.0f} MWh/year (CF: {cf_net_p75:.1f}%)")
        logger.info(f"Net AEP P90: {net_p90:,.0f} MWh/year (CF: {cf_net_p90:.1f}%)")

        return results

    @staticmethod
    def _month_of_row(index: pd.Index) -> np.ndarray:
        """Return the calendar month (1-12) for each hourly row.

        A ``DatetimeIndex`` is used directly. A positional/integer index (the
        ``WindPipeline`` orchestrator feeds a ``RangeIndex``) is a contiguous hourly
        series, so a reference non-leap-year hourly calendar is synthesized and each
        row mapped to its true month.

        The previous ``pd.to_datetime(df.index).month`` silently read an integer
        ``RangeIndex`` as epoch-nanoseconds, so all 8760 hours landed in month 1 and
        the emitted ``monthly_profile`` was meaningless (audit D3, #574).
        """
        if isinstance(index, pd.DatetimeIndex):
            return np.asarray(index.month)
        calendar = pd.date_range("2001-01-01", periods=len(index), freq="h")
        return np.asarray(calendar.month)

    def calculate_monthly_energy(self) -> pd.DataFrame:
        """Calculate monthly energy production profile.

        Returns:
            DataFrame with columns:
                - month: Month number (1-12).
                - energy_mwh: Monthly energy production (MWh).
                - cf_percent: Monthly capacity factor (%).

        Example:
            >>> monthly = calc.calculate_monthly_energy()
            >>> print(monthly.head())
        """
        df = self.df.copy()
        df["month"] = self._month_of_row(df.index)
        df["power_kw"] = self.power_curve_func(df[self.ws_column])

        # Monthly averages
        monthly = df.groupby("month")["power_kw"].mean().reset_index()
        monthly.columns = ["month", "avg_power_kw"]

        # Hours per month (approximate)
        monthly["hours"] = 730  # ~30.4 days * 24 hours
        monthly["energy_mwh"] = (
            monthly["avg_power_kw"] * monthly["hours"] * self.num_turbines / 1000
        )

        # Capacity factor
        total_capacity_mw = (self.rated_capacity * self.num_turbines) / 1000
        monthly["cf_percent"] = (
            monthly["energy_mwh"] / (total_capacity_mw * monthly["hours"])
        ) * 100

        return monthly[["month", "energy_mwh", "cf_percent"]]

    def calculate_revenue(
        self,
        net_aep_results: Dict[str, float],
        tariff_lkr_per_kwh: Optional[float] = None,
        exchange_rate_lkr_usd: Optional[float] = None,
    ) -> Dict[str, float]:
        """Calculate revenue projections for PPA period.

        Args:
            net_aep_results: Output from calculate_net_aep().
            tariff_lkr_per_kwh: Electricity tariff. If None, uses config.
            exchange_rate_lkr_usd: Exchange rate. If None, uses config.

        Returns:
            Dict with annual and cumulative revenues for P50/P75/P90.

        Example:
            >>> net = calc.calculate_net_aep()
            >>> revenue = calc.calculate_revenue(net)
            >>> print(f"Annual Revenue P75: ${revenue['annual_revenue_p75_usd']:,.0f}")
        """
        # Use config values if not provided (CCCDIR: no hardcoded values)
        if tariff_lkr_per_kwh is None:
            tariff_lkr_per_kwh = self.tariff
        if exchange_rate_lkr_usd is None:
            exchange_rate_lkr_usd = self.exchange_rate

        # Annual revenue (USD)
        annual_p50_usd = (
            net_aep_results["net_aep_p50_mwh"]
            * 1000
            * tariff_lkr_per_kwh
            / exchange_rate_lkr_usd
        )
        annual_p75_usd = (
            net_aep_results["net_aep_p75_mwh"]
            * 1000
            * tariff_lkr_per_kwh
            / exchange_rate_lkr_usd
        )
        annual_p90_usd = (
            net_aep_results["net_aep_p90_mwh"]
            * 1000
            * tariff_lkr_per_kwh
            / exchange_rate_lkr_usd
        )

        # Cumulative revenue over PPA period (CCCDIR: from config)
        ppa_years = self.ppa_years
        cumulative_p50_usd = annual_p50_usd * ppa_years
        cumulative_p75_usd = annual_p75_usd * ppa_years
        cumulative_p90_usd = annual_p90_usd * ppa_years

        results = {
            "tariff_lkr_per_kwh": tariff_lkr_per_kwh,
            "exchange_rate_lkr_usd": exchange_rate_lkr_usd,
            "ppa_years": ppa_years,
            "annual_revenue_p50_usd": annual_p50_usd,
            "annual_revenue_p75_usd": annual_p75_usd,
            "annual_revenue_p90_usd": annual_p90_usd,
            "cumulative_revenue_p50_usd": cumulative_p50_usd,
            "cumulative_revenue_p75_usd": cumulative_p75_usd,
            "cumulative_revenue_p90_usd": cumulative_p90_usd,
        }

        logger.info(f"Annual revenue P75: ${annual_p75_usd:,.0f} USD")
        logger.info(f"{ppa_years}-year revenue P75: ${cumulative_p75_usd:,.0f} USD")

        return results

    def generate_complete_assessment(self) -> Dict[str, Any]:
        """Run complete energy assessment.

        Returns:
            Complete assessment with gross_aep, net_aep, monthly, revenue.

        Example:
            >>> assessment = calc.generate_complete_assessment()
            >>> print(assessment['net_aep']['net_aep_p75_mwh'])
        """
        logger.info("Running complete energy assessment...")

        gross = self.calculate_gross_aep()
        net = self.calculate_net_aep(gross["windfarm_aep_mwh"])
        monthly = self.calculate_monthly_energy()
        revenue = self.calculate_revenue(net)

        results = {
            "gross_aep": gross,
            "net_aep": net,
            "monthly_profile": monthly.to_dict("records"),
            "revenue": revenue,
            "config": {
                "num_turbines": self.num_turbines,
                "rated_capacity_kw": self.rated_capacity,
                "total_capacity_mw": (self.rated_capacity * self.num_turbines) / 1000,
            },
        }

        logger.info("Complete assessment finished")

        return results
