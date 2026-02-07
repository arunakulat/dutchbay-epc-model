"""Wind Resource Statistical Analysis Module.

Provides comprehensive statistical analysis of wind speed data including:
- Weibull distribution fitting
- Temporal pattern analysis (monthly, seasonal, diurnal)
- Inter-annual variability assessment
- Quality metrics and summary reports

All configuration loaded from YAML files (CCCDIR compliant).

Typical usage:
    >>> from wind_resource import WindAnalyzer
    >>> import pandas as pd
    >>> df = pd.read_csv('dutchbay_wind_150m.csv')
    >>> analyzer = WindAnalyzer(df, ws_column='ws_150m')
    >>> results = analyzer.analyze_all()
    >>> print(analyzer.generate_summary_report())

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (CCCDIR Compliant)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yaml
from scipy import stats

logger = logging.getLogger(__name__)


class WindAnalyzer:
    """Comprehensive wind resource statistical analysis.
    
    Performs Weibull fitting, temporal pattern analysis, variability
    assessment, and generates summary statistics. All configuration
    loaded from era5_config.yaml (CCCDIR compliant).
    
    Attributes:
        df: DataFrame with timestamp and wind speed columns.
        ws_column: Name of wind speed column to analyze.
        config: Configuration dict loaded from era5_config.yaml.
        weibull_method: Method for Weibull fitting ('mle' from config).
        ws_min: Minimum valid wind speed (from config).
        ws_max: Maximum valid wind speed (from config).
        
    Example:
        >>> analyzer = WindAnalyzer(df, ws_column='ws_150m')
        >>> weibull_params = analyzer.fit_weibull()
        >>> print(f"Shape k: {weibull_params['shape_k']:.3f}")
        >>> print(f"Scale c: {weibull_params['scale_c']:.3f} m/s")
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        ws_column: str = 'ws_150m',
        config_path: Optional[str] = None
    ) -> None:
        """Initialize wind analyzer with data and configuration.
        
        Args:
            df: DataFrame with 'timestamp' and wind speed columns.
                Must have DatetimeIndex or 'timestamp' column.
            ws_column: Name of wind speed column to analyze.
                Default is 'ws_150m'.
            config_path: Path to era5_config.yaml. If None, uses default
                location at wind_resource/config/era5_config.yaml.
                
        Raises:
            ValueError: If DataFrame is missing required columns.
            FileNotFoundError: If config file not found.
            KeyError: If required config keys are missing.
        """
        # Validate DataFrame
        if ws_column not in df.columns:
            raise ValueError(
                f"Wind speed column '{ws_column}' not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )
        
        if 'timestamp' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(
                "DataFrame must have 'timestamp' column or DatetimeIndex."
            )
        
        # Prepare data
        self.df = df.copy()
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df = self.df.set_index('timestamp')
        
        self.ws_column = ws_column
        
        # Load configuration (CCCDIR compliance)
        self._load_config(config_path)
        
        logger.info(f"WindAnalyzer v1.0.0 initialized")
        logger.info(f"  Data points: {len(self.df):,}")
        logger.info(f"  Wind speed column: {ws_column}")
        logger.info(f"  Mean WS: {self.df[ws_column].mean():.2f} m/s")
    
    def _load_config(self, config_path: Optional[str]) -> None:
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to config file, or None for default.
            
        Raises:
            FileNotFoundError: If config file doesn't exist.
            KeyError: If required config sections are missing.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config" / "era5_config.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}"
            )
        
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Extract config values (CCCDIR: no hardcoded values)
        try:
            self.weibull_method = self.config['weibull']['method']
            self.ws_min = self.config['quality_control']['ws_min']
            self.ws_max = self.config['quality_control']['ws_max']
        except KeyError as e:
            raise KeyError(
                f"Missing required config key: {e}. "
                "Check era5_config.yaml structure."
            ) from e
        
        logger.debug(f"Config loaded: weibull_method={self.weibull_method}")
    
    def fit_weibull(self) -> Dict[str, float]:
        """Fit 2-parameter Weibull distribution to wind speeds.
        
        Uses maximum likelihood estimation (MLE) method from scipy.stats.
        The Weibull distribution models wind speed probability:
        f(v) = (k/c) * (v/c)^(k-1) * exp(-(v/c)^k)
        
        Returns:
            Dict with keys:
                - shape_k: Weibull shape parameter (dimensionless).
                - scale_c: Weibull scale parameter (m/s).
                - r_squared: R² goodness-of-fit.
                - ks_pvalue: Kolmogorov-Smirnov test p-value.
                - mean_ws: Mean wind speed (m/s).
                
        Example:
            >>> params = analyzer.fit_weibull()
            >>> print(f"Shape k={params['shape_k']:.2f}, Scale c={params['scale_c']:.2f}")
            Shape k=2.65, Scale c=8.27
        """
        ws_data = self.df[self.ws_column].dropna()
        
        # Fit Weibull using config method (CCCDIR: no hardcoded 'mle')
        if self.weibull_method == 'mle':
            # scipy.stats.weibull_min uses (c, loc, scale) parameterization
            # We want scale = c (Weibull scale), shape = k
            shape_k, loc, scale_c = stats.weibull_min.fit(ws_data, floc=0)
        else:
            raise ValueError(f"Unsupported Weibull method: {self.weibull_method}")
        
        # Calculate goodness-of-fit
        # Theoretical CDF
        sorted_ws = np.sort(ws_data)
        theoretical_cdf = stats.weibull_min.cdf(sorted_ws, shape_k, loc=0, scale=scale_c)
        
        # Empirical CDF
        empirical_cdf = np.arange(1, len(sorted_ws) + 1) / len(sorted_ws)
        
        # R-squared
        ss_res = np.sum((empirical_cdf - theoretical_cdf) ** 2)
        ss_tot = np.sum((empirical_cdf - np.mean(empirical_cdf)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)
        
        # Kolmogorov-Smirnov test
        ks_statistic, ks_pvalue = stats.kstest(
            ws_data,
            lambda x: stats.weibull_min.cdf(x, shape_k, loc=0, scale=scale_c)
        )
        
        results = {
            'shape_k': float(shape_k),
            'scale_c': float(scale_c),
            'r_squared': float(r_squared),
            'ks_pvalue': float(ks_pvalue),
            'mean_ws': float(ws_data.mean())
        }
        
        logger.info(f"Weibull fit: k={shape_k:.3f}, c={scale_c:.2f} m/s, R²={r_squared:.4f}")
        
        return results
    
    def analyze_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze monthly, seasonal, and diurnal patterns.
        
        Returns:
            Dict with keys:
                - monthly: Dict mapping month (1-12) to mean WS (m/s).
                - seasonal: Dict mapping season to mean WS (m/s).
                - hourly: Dict mapping hour (0-23) to mean WS (m/s).
                - windiest_month: Month with highest mean WS.
                - calmest_month: Month with lowest mean WS.
                - monthly_range_ratio: Max/min monthly WS ratio.
                
        Example:
            >>> patterns = analyzer.analyze_temporal_patterns()
            >>> print(f"Windiest month: {patterns['windiest_month']}")
            >>> print(f"Monthly WS range: {patterns['monthly_range_ratio']:.2f}x")
        """
        df = self.df.copy()
        df['month'] = df.index.month
        df['season'] = df.index.month.map(self._month_to_season)
        df['hour'] = df.index.hour
        
        # Monthly averages
        monthly = df.groupby('month')[self.ws_column].mean().to_dict()
        
        # Seasonal averages
        seasonal = df.groupby('season')[self.ws_column].mean().to_dict()
        
        # Hourly averages (diurnal pattern)
        hourly = df.groupby('hour')[self.ws_column].mean().to_dict()
        
        # Identify extremes
        windiest_month = max(monthly, key=monthly.get)
        calmest_month = min(monthly, key=monthly.get)
        monthly_range_ratio = monthly[windiest_month] / monthly[calmest_month]
        
        results = {
            'monthly': monthly,
            'seasonal': seasonal,
            'hourly': hourly,
            'windiest_month': windiest_month,
            'calmest_month': calmest_month,
            'monthly_range_ratio': float(monthly_range_ratio)
        }
        
        logger.info(f"Temporal patterns: windiest month={windiest_month}, "
                   f"range ratio={monthly_range_ratio:.2f}x")
        
        return results
    
    @staticmethod
    def _month_to_season(month: int) -> str:
        """Map month number to season (Northern Hemisphere).
        
        Args:
            month: Month number (1-12).
            
        Returns:
            Season name: 'DJF', 'MAM', 'JJA', or 'SON'.
        """
        if month in [12, 1, 2]:
            return 'DJF'  # Winter
        elif month in [3, 4, 5]:
            return 'MAM'  # Spring
        elif month in [6, 7, 8]:
            return 'JJA'  # Summer
        else:
            return 'SON'  # Autumn
    
    def calculate_interannual_variability(self) -> Dict[str, float]:
        """Calculate year-to-year wind speed variability.
        
        Returns:
            Dict with keys:
                - mean_annual_ws: Mean of annual averages (m/s).
                - std_annual_ws: Std deviation of annual averages (m/s).
                - cov_annual_ws: Coefficient of variation (%).
                - min_year: Year with lowest mean WS.
                - max_year: Year with highest mean WS.
                - min_year_ws: Lowest annual mean WS (m/s).
                - max_year_ws: Highest annual mean WS (m/s).
                
        Example:
            >>> variability = analyzer.calculate_interannual_variability()
            >>> print(f"CoV: {variability['cov_annual_ws']:.1f}%")
            CoV: 2.9%
        """
        df = self.df.copy()
        df['year'] = df.index.year
        
        annual_means = df.groupby('year')[self.ws_column].mean()
        
        mean_annual = annual_means.mean()
        std_annual = annual_means.std()
        cov_annual = (std_annual / mean_annual) * 100
        
        min_year = annual_means.idxmin()
        max_year = annual_means.idxmax()
        
        results = {
            'mean_annual_ws': float(mean_annual),
            'std_annual_ws': float(std_annual),
            'cov_annual_ws': float(cov_annual),
            'min_year': int(min_year),
            'max_year': int(max_year),
            'min_year_ws': float(annual_means.min()),
            'max_year_ws': float(annual_means.max())
        }
        
        logger.info(f"Inter-annual variability: CoV={cov_annual:.2f}%")
        
        return results
    
    def analyze_all(self) -> Dict[str, Any]:
        """Run complete analysis suite.
        
        Returns:
            Complete analysis results dictionary with keys:
                - weibull: Weibull fit parameters.
                - temporal: Temporal pattern analysis.
                - variability: Inter-annual variability metrics.
                - summary_stats: Basic statistics.
                
        Example:
            >>> results = analyzer.analyze_all()
            >>> print(results['weibull']['shape_k'])
            2.650
        """
        logger.info("Running complete wind analysis...")
        
        results = {
            'weibull': self.fit_weibull(),
            'temporal': self.analyze_temporal_patterns(),
            'variability': self.calculate_interannual_variability(),
            'summary_stats': self._calculate_summary_stats()
        }
        
        logger.info("Complete analysis finished")
        
        return results
    
    def _calculate_summary_stats(self) -> Dict[str, float]:
        """Calculate basic summary statistics.
        
        Returns:
            Dict with mean, std, min, max, percentiles.
        """
        ws = self.df[self.ws_column]
        
        return {
            'mean': float(ws.mean()),
            'std': float(ws.std()),
            'min': float(ws.min()),
            'max': float(ws.max()),
            'p10': float(ws.quantile(0.10)),
            'p50': float(ws.quantile(0.50)),
            'p90': float(ws.quantile(0.90)),
            'count': int(ws.count())
        }
    
    def generate_summary_report(self) -> str:
        """Generate human-readable text summary.
        
        Returns:
            Multi-line string report summarizing all analysis results.
            
        Example:
            >>> report = analyzer.generate_summary_report()
            >>> print(report)
        """
        results = self.analyze_all()
        
        report = []
        report.append("=" * 70)
        report.append("WIND RESOURCE ANALYSIS SUMMARY")
        report.append("=" * 70)
        
        # Weibull
        report.append("\n[1] WEIBULL DISTRIBUTION")
        report.append("-" * 70)
        wb = results['weibull']
        report.append(f"  Shape k: {wb['shape_k']:.3f}")
        report.append(f"  Scale c: {wb['scale_c']:.2f} m/s")
        report.append(f"  R-squared: {wb['r_squared']:.4f}")
        report.append(f"  KS p-value: {wb['ks_pvalue']:.4f}")
        
        # Summary stats
        report.append("\n[2] SUMMARY STATISTICS")
        report.append("-" * 70)
        stats = results['summary_stats']
        report.append(f"  Mean: {stats['mean']:.2f} m/s")
        report.append(f"  Std Dev: {stats['std']:.2f} m/s")
        report.append(f"  Range: {stats['min']:.2f} - {stats['max']:.2f} m/s")
        report.append(f"  P50: {stats['p50']:.2f} m/s")
        report.append(f"  P90: {stats['p90']:.2f} m/s")
        
        # Temporal
        report.append("\n[3] TEMPORAL PATTERNS")
        report.append("-" * 70)
        temp = results['temporal']
        report.append(f"  Windiest month: {temp['windiest_month']} "
                     f"({temp['monthly'][temp['windiest_month']]:.2f} m/s)")
        report.append(f"  Calmest month: {temp['calmest_month']} "
                     f"({temp['monthly'][temp['calmest_month']]:.2f} m/s)")
        report.append(f"  Monthly range ratio: {temp['monthly_range_ratio']:.2f}x")
        
        # Variability
        report.append("\n[4] INTER-ANNUAL VARIABILITY")
        report.append("-" * 70)
        var = results['variability']
        report.append(f"  Mean annual WS: {var['mean_annual_ws']:.2f} m/s")
        report.append(f"  Std deviation: {var['std_annual_ws']:.2f} m/s")
        report.append(f"  Coefficient of variation: {var['cov_annual_ws']:.2f}%")
        report.append(f"  Range: {var['min_year']} ({var['min_year_ws']:.2f} m/s) to "
                     f"{var['max_year']} ({var['max_year_ws']:.2f} m/s)")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)
