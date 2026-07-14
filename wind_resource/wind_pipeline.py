"""Wind Resource Assessment Pipeline Orchestrator.

Orchestrates the complete wind resource assessment workflow:
1. ERA5 data fetching (ERA5Fetcher)
2. Statistical analysis (WindAnalyzer)
3. Energy production calculations (EnergyCalculator)
4. JSON export for cashflow model integration

All configuration loaded from YAML files (CCCDIR compliant).

Typical usage (all turbine/site identity comes from YOUR scenario's config):
    >>> from wind_resource import WindPipeline
    >>> location = {'name': 'YourSite', 'lat': 8.33, 'lon': 79.76}
    >>> pipeline = WindPipeline(
    ...     location=location,
    ...     hub_height=cfg['turbine']['hub_height_m'],
    ...     turbine_model=cfg['turbine']['model'],
    ...     num_turbines=cfg['turbine']['n_turbines'],
    ... )
    >>> results = pipeline.run_complete_assessment(
    ...     start_date='2014-12-01',
    ...     end_date='2025-12-31'
    ... )
    >>> cashflow_data = pipeline.export_for_cashflow_model(scenario='P75')

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: tracks the repo ``VERSION`` file via ``analytics.run_manifest.engine_version()``
    (no per-module literal to go stale; #618).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pandas as pd
import yaml

from analytics.run_manifest import engine_version
from wind_resource.bankable_aep import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    interannual_variability_drift,
)
from wind_resource.energy_calculator import EnergyCalculator
from wind_resource.era5_fetcher import ERA5Fetcher
from wind_resource.wind_analyzer import WindAnalyzer

logger = logging.getLogger(__name__)


class WindPipeline:
    """Complete wind resource assessment pipeline.

    Coordinates ERA5 fetching, wind analysis, and energy calculations
    into a streamlined workflow with JSON export. All configuration
    loaded from YAML files (CCCDIR compliant).

    Attributes:
        location: Location dict with 'name', 'lat', 'lon'.
        hub_height: Turbine hub height (m).
        turbine_model: Turbine model from power_curves.yaml.
        num_turbines: Number of turbines.
        cache_dir: Directory for ERA5 data cache.
        output_dir: Directory for analysis outputs.
        fetcher: ERA5Fetcher instance.
        config: Configuration dict from era5_config.yaml.

    Example:
        >>> pipeline = WindPipeline(
        ...     location={'name': 'Site1', 'lat': 8.5, 'lon': 80.0},
        ...     hub_height=120.0,            # from your turbine.hub_height_m
        ...     turbine_model='iea_reference_10mw',  # from your turbine.model
        ...     num_turbines=15,             # from your turbine.n_turbines
        ... )
        >>> results = pipeline.run_complete_assessment()
    """

    def __init__(
        self,
        location: Dict[str, Any],
        hub_height: float,
        turbine_model: str,
        num_turbines: int,
        cache_dir: str = "inputs/wind_data",
        output_dir: str = "outputs/wind_assessment",
        config_path: Optional[str] = None,
        uncertainty: Optional[Mapping[str, Any]] = None,
        air_density_site_kgm3: Optional[float] = None,
        air_density_ref_kgm3: Optional[float] = None,
    ) -> None:
        """Initialize wind assessment pipeline.

        Turbine/site identity (``hub_height``, ``turbine_model``, ``num_turbines``) is
        REQUIRED and config-driven (ARCH-01) — this is a general-purpose tool, so there
        is no DutchBay/Kalpitiya default a different project could silently inherit.

        Args:
            location: Dict with 'name', 'lat', 'lon' keys.
                Example: {'name': 'Site', 'lat': 8.33, 'lon': 79.76}
            hub_height: Turbine hub height in meters (required; from turbine.hub_height_m).
            turbine_model: Turbine model name from power_curves.yaml (required;
                from turbine.model).
            num_turbines: Number of turbines in wind farm (required; from turbine.n_turbines).
            cache_dir: Directory for ERA5 data cache. Default 'inputs/wind_data'.
            output_dir: Directory for analysis outputs. Default 'outputs/wind_assessment'.
            config_path: Path to era5_config.yaml. If None, uses default.
            uncertainty: Optional ``resource.uncertainty.*``-shaped mapping passed
                through to :class:`EnergyCalculator` for the IEC 61400-15-2
                exceedance build-up (absent = the previous defaults; #618).
            air_density_site_kgm3: Optional site air density for the IEC 61400-12-1
                velocity correction, passed through to :class:`EnergyCalculator`
                (absent = no correction; #618).
            air_density_ref_kgm3: Optional reference density for the correction
                (absent = the IEC 1.225 kg/m^3 default).

        Raises:
            ValueError: If location dict is missing required keys.
            FileNotFoundError: If config file not found.
        """
        # Validate location
        required_keys = ["name", "lat", "lon"]
        if not all(k in location for k in required_keys):
            raise ValueError(
                f"location must contain keys: {required_keys}. "
                f"Got: {list(location.keys())}"
            )

        self.location = location
        self.hub_height = hub_height
        self.turbine_model = turbine_model
        self.num_turbines = num_turbines
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir)

        # #618 plumbing: exceedance-uncertainty mapping + air-density correction,
        # passed straight through to EnergyCalculator. All default to identity.
        self.uncertainty: Dict[str, Any] = dict(uncertainty or {})
        self.air_density_site_kgm3 = (
            float(air_density_site_kgm3) if air_density_site_kgm3 is not None else None
        )
        self.air_density_ref_kgm3 = (
            float(air_density_ref_kgm3)
            if air_density_ref_kgm3 is not None
            else IEC_REFERENCE_AIR_DENSITY_KGM3
        )

        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ERA5 fetcher
        self.fetcher = ERA5Fetcher(cache_dir=str(cache_dir), config_path=config_path)

        # Load config (CCCDIR compliance)
        self._load_config(config_path)

        logger.info(f"WindPipeline v{engine_version()} initialized (CCCDIR compliant)")
        logger.info(
            f"  Location: {location['name']} ({location['lat']:.2f}°N, {location['lon']:.2f}°E)"
        )
        logger.info(f"  Hub height: {hub_height}m")
        logger.info(f"  Turbine model: {turbine_model}")
        logger.info(f"  Number of turbines: {num_turbines}")

    def _load_config(self, config_path: Optional[str]) -> None:
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file, or None for default.
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

        logger.debug("Configuration loaded for pipeline")

    def run_complete_assessment(
        self,
        start_date: str = "2014-12-01",
        end_date: str = "2025-12-31",
        force_download: bool = False,
        analyze_trend: bool = False,
        hub_height_series: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """Run complete wind resource assessment pipeline.

        Executes the full workflow:
        1. Download/load ERA5 data
        2. Extrapolate to hub height
        3. Run statistical analysis (Weibull, temporal patterns, variability)
        4. Calculate energy production (gross/net AEP, P50/P75/P90)
        5. Calculate revenue projections
        6. Save results to JSON

        Args:
            start_date: Start date 'YYYY-MM-DD'. Default '2014-12-01'.
            end_date: End date 'YYYY-MM-DD'. Default '2025-12-31'.
            force_download: Force re-download of ERA5 data. Default False.
            analyze_trend: Opt-in (#656). When True, compute the long-term
                Mann-Kendall / Sen's-slope resource trend on the SAME already-built
                hub-height series (no second fetch) and attach a JSON-safe
                ``long_term_trend`` block to the results (and saved JSON) for the
                lender workbook's "ResourceTrend" sheet. DEFAULT OFF and
                report/VALIDATE-only: it changes no committed AEP or KPI, and a
                short record degrades explicitly (see
                ``wind_resource.long_term_trend.build_resource_trend_export_block``).
            hub_height_series: Optional pre-fetched hub-height wind series (#965).
                DEFAULT None — every existing caller (the CLI) takes the identical
                Step-1 (ERA5 fetch) + Step-2 (extrapolate) path, byte-identical. When
                provided (the async web path, which fetches the CDS ARCO single-point
                TIMESERIES product upstream because the legacy gridded fetcher's
                full-year AREA request is rejected by CDS as "too large"), Steps 1-2
                are SKIPPED and this series is used as ``df`` directly. The series is
                assumed ALREADY extrapolated to this pipeline's ``hub_height`` (as
                ``wind_resource.era5_retrieval.build_hub_height_series`` returns it) and
                MUST carry a column named exactly ``ws_{int(hub_height)}m``; it may be
                indexed by timestamp (index name ``timestamp``) or carry a ``timestamp``
                column. This is a SCREENING-grade path (single-cell ERA5, no on-site
                mast, MCP unwired — #961): its output is NOT bankable and must not
                re-pin any frozen KPI.

        Returns:
            Complete assessment results dictionary with keys:
                - metadata: Assessment metadata.
                - wind_data: Wind data summary.
                - statistical_analysis: Weibull fit, temporal patterns, variability.
                - energy_production: Gross/net AEP, capacity factors.
                - revenue: Revenue projections.
                - monthly_profile: Monthly energy production.

        Example:
            >>> results = pipeline.run_complete_assessment(
            ...     start_date='2020-01-01',
            ...     end_date='2020-12-31'
            ... )
            >>> print(results['energy_production']['net_aep']['net_aep_p75_mwh'])
        """
        logger.info("=" * 70)
        logger.info("WIND RESOURCE ASSESSMENT PIPELINE")
        logger.info("=" * 70)

        ws_column = f"ws_{int(self.hub_height)}m"

        if hub_height_series is None:
            # Step 1: Download ERA5 data (legacy gridded fetcher -> CSV path).
            logger.info("\n[Step 1/5] Downloading ERA5 data...")
            data_file = self.fetcher.download_wind_data(
                location=self.location,
                start_date=start_date,
                end_date=end_date,
                force_download=force_download,
            )

            # Step 2: Load and extrapolate to hub height.
            logger.info(
                f"\n[Step 2/5] Extrapolating to {self.hub_height}m hub height..."
            )
            df = pd.read_csv(data_file)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = self.fetcher.extrapolate_to_hub_height(df, hub_height=self.hub_height)
        else:
            # Injected pre-fetched hub-height series (#965): skip Steps 1-2. The async
            # web path fetches the CDS ARCO single-point TIMESERIES product upstream
            # (era5_retrieval.build_hub_height_series), which already extrapolates to
            # hub height, and passes the finished series here. Adapter: turn the
            # timestamp-named index into a ``timestamp`` column so WindAnalyzer and
            # EnergyCalculator (Steps 3-5) consume it unchanged. Screening-grade only.
            logger.info(
                "\n[Steps 1-2/5] Using injected pre-fetched hub-height series "
                "(ERA5 fetch + extrapolation skipped)..."
            )
            df = hub_height_series.reset_index()
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            if ws_column not in df.columns:
                raise ValueError(
                    f"Injected hub_height_series is missing the expected hub-height "
                    f"column '{ws_column}' (pipeline hub_height={self.hub_height}). "
                    f"Got columns: {list(df.columns)}. The series' hub height must "
                    "match the pipeline's."
                )

        # Step 3: Statistical analysis
        logger.info("\n[Step 3/5] Running statistical analysis...")
        analyzer = WindAnalyzer(df, ws_column=ws_column)
        statistical_analysis = analyzer.analyze_all()

        # Step 4: Energy production calculations
        logger.info("\n[Step 4/5] Calculating energy production...")
        calculator = EnergyCalculator(
            df=df,
            ws_column=ws_column,
            turbine_model=self.turbine_model,
            num_turbines=self.num_turbines,
            uncertainty=self.uncertainty,
            air_density_site_kgm3=self.air_density_site_kgm3,
            air_density_ref_kgm3=self.air_density_ref_kgm3,
        )
        energy_assessment = calculator.generate_complete_assessment()

        # Step 5: Compile results
        logger.info("\n[Step 5/5] Compiling results...")
        results = {
            "metadata": {
                "assessment_date": datetime.now().isoformat(),
                "location": self.location,
                "data_period": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_points": len(df),
                },
                "configuration": {
                    "hub_height_m": self.hub_height,
                    "turbine_model": self.turbine_model,
                    "num_turbines": self.num_turbines,
                    "rated_capacity_kw": calculator.rated_capacity,
                    "total_capacity_mw": (calculator.rated_capacity * self.num_turbines)
                    / 1000,
                },
                # Repo VERSION file via run_manifest (single source of truth, #618) —
                # replaces the stale hardcoded per-module version literal.
                "version": engine_version(),
            },
            "wind_data": {
                "mean_ws": float(df[ws_column].mean()),
                "std_ws": float(df[ws_column].std()),
                "min_ws": float(df[ws_column].min()),
                "max_ws": float(df[ws_column].max()),
                "p50_ws": float(df[ws_column].quantile(0.50)),
                "p90_ws": float(df[ws_column].quantile(0.90)),
            },
            "statistical_analysis": statistical_analysis,
            "energy_production": energy_assessment,
            "summary": self._generate_summary(statistical_analysis, energy_assessment),
        }

        # Opt-in long-term resource & trend (#656): reuse the SAME hub-height
        # series built above (no second CDS fetch) to compute the Mann-Kendall /
        # Sen's-slope trend and attach a JSON-safe long_term_trend block for the
        # lender workbook. DEFAULT OFF and report/VALIDATE-only — it never changes
        # the retrieved series, the committed AEP, or any KPI; every existing
        # caller leaves analyze_trend False and gets a byte-identical result.
        if analyze_trend:
            from wind_resource.era5_retrieval import ERA5RequestConfig
            from wind_resource.long_term_trend import (
                build_resource_trend_export_block,
            )

            trend_series = (
                df.set_index("timestamp") if "timestamp" in df.columns else df
            )
            years = pd.DatetimeIndex(trend_series.index).year
            trend_config = ERA5RequestConfig(
                project_name=str(self.location["name"]),
                latitude=float(self.location["lat"]),
                longitude=float(self.location["lon"]),
                start_year=int(years.min()),
                end_year=int(years.max()),
                hub_height_m=float(self.hub_height),
                turbine_model=str(self.turbine_model),
                num_turbines=int(self.num_turbines),
            )
            results["long_term_trend"] = build_resource_trend_export_block(
                trend_config, trend_series
            )

        # Save to JSON
        output_file = (
            self.output_dir
            / f"{self.location['name'].lower()}_assessment_{start_date}_to_{end_date}.json"
        )
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"\n✅ Assessment complete: {output_file}")
        logger.info("=" * 70)

        return results

    def _generate_summary(
        self, statistical: Dict[str, Any], energy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate executive summary of key metrics.

        Args:
            statistical: Statistical analysis results.
            energy: Energy assessment results.

        Returns:
            Summary dict with key metrics.
        """
        # WIND-6 (#484): validate the COMPUTED interannual CoV against the ASSUMED bankable
        # IAV sigma (UncertaintyBudget default 4.0%, config-overridable). Surfaces whether the
        # P90 build-up's interannual assumption is conservative or optimistic vs the site data;
        # validate-mode only (never mutates the committed P90).
        computed_iav = statistical["variability"]["cov_annual_ws"]
        iav_check = interannual_variability_drift(computed_iav)
        return {
            "wind_resource": {
                "mean_wind_speed_ms": statistical["summary_stats"]["mean"],
                "weibull_shape_k": statistical["weibull"]["shape_k"],
                "weibull_scale_c_ms": statistical["weibull"]["scale_c"],
                "interannual_cov_percent": computed_iav,
                "interannual_variability_check": iav_check,
            },
            "energy_production": {
                "gross_capacity_factor_percent": energy["gross_aep"][
                    "capacity_factor_gross"
                ],
                "net_aep_p50_gwh": energy["net_aep"]["net_aep_p50_mwh"] / 1000,
                "net_aep_p75_gwh": energy["net_aep"]["net_aep_p75_mwh"] / 1000,
                "net_aep_p90_gwh": energy["net_aep"]["net_aep_p90_mwh"] / 1000,
                "net_capacity_factor_p75_percent": energy["net_aep"][
                    "capacity_factor_net_p75"
                ],
            },
            "revenue": {
                "annual_revenue_p75_usd": energy["revenue"]["annual_revenue_p75_usd"],
                "ppa_years": energy["revenue"]["ppa_years"],
                "cumulative_revenue_p75_usd": energy["revenue"][
                    "cumulative_revenue_p75_usd"
                ],
            },
        }

    def export_for_cashflow_model(self, scenario: str = "P75") -> Dict[str, Any]:
        """Export key metrics for integration with cashflow model.

        Args:
            scenario: P-level scenario ('P50', 'P75', or 'P90'). Default 'P75'.

        Returns:
            Dict with cashflow model inputs:
                - annual_generation_mwh: Annual energy production.
                - capacity_factor_percent: Net capacity factor.
                - revenue_annual_usd: Annual revenue.
                - project_capacity_mw: Total installed capacity.

        Raises:
            ValueError: If scenario is not valid.
            RuntimeError: If assessment hasn't been run yet.

        Example:
            >>> pipeline.run_complete_assessment()
            >>> cashflow_data = pipeline.export_for_cashflow_model(scenario='P75')
            >>> print(cashflow_data['annual_generation_mwh'])
        """
        if scenario not in ["P50", "P75", "P90"]:
            raise ValueError(
                f"scenario must be 'P50', 'P75', or 'P90'. Got: {scenario}"
            )

        # Check if assessment file exists
        assessment_files = list(
            self.output_dir.glob(f"{self.location['name'].lower()}_assessment_*.json")
        )

        if not assessment_files:
            raise RuntimeError(
                "No assessment results found. Run run_complete_assessment() first."
            )

        # Load most recent assessment
        latest_file = sorted(assessment_files)[-1]
        with open(latest_file) as f:
            results = json.load(f)

        # Extract scenario-specific metrics
        scenario_lower = scenario.lower()
        energy = results["energy_production"]

        cashflow_export = {
            "scenario": scenario,
            "annual_generation_mwh": energy["net_aep"][f"net_aep_{scenario_lower}_mwh"],
            "capacity_factor_percent": energy["net_aep"][
                f"capacity_factor_net_{scenario_lower}"
            ],
            "revenue_annual_usd": energy["revenue"][
                f"annual_revenue_{scenario_lower}_usd"
            ],
            "revenue_cumulative_usd": energy["revenue"][
                f"cumulative_revenue_{scenario_lower}_usd"
            ],
            "project_capacity_mw": energy["config"]["total_capacity_mw"],
            "num_turbines": energy["config"]["num_turbines"],
            "rated_capacity_per_turbine_kw": energy["config"]["rated_capacity_kw"],
            "ppa_years": energy["revenue"]["ppa_years"],
            "tariff_lkr_per_kwh": energy["revenue"]["tariff_lkr_per_kwh"],
            "exchange_rate_lkr_usd": energy["revenue"]["exchange_rate_lkr_usd"],
        }

        # Save export
        export_file = (
            self.output_dir
            / f"{self.location['name'].lower()}_cashflow_export_{scenario}.json"
        )
        with open(export_file, "w") as f:
            json.dump(cashflow_export, f, indent=2)

        logger.info(f"Exported {scenario} data for cashflow model: {export_file}")

        return cashflow_export
