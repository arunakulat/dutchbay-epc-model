# Wind Resource Module - Implementation Plan

**Branch:** `feature/add-finance-contracts-pydantic-v2-20251219`  
**Date:** December 21, 2025  
**Current Status:** Phase 2A Complete (Core Config & ERA5 Fetcher)

## ✅ COMPLETED (8 commits)

### Phase 1: Foundation
1. ✅ wind_resource/__init__.py
2. ✅ wind_resource/config/__init__.py
3. ✅ wind_resource/config/locations.yaml
4. ✅ wind_resource/README.md (with validated results)
5. ✅ WIND_RESOURCE_STATUS.md

### Phase 2A: Core Modules & Config  
6. ✅ **wind_resource/era5_fetcher.py** (commit: d1acc58)
   - Full Google-style docstrings
   - Comprehensive type hints
   - 13.5 KB, ~400 lines
   - Ready for mypy strict mode

7. ✅ wind_resource/config/power_curves.yaml (commit: 4bbe621)
   - 3 turbine models (Envision, Vestas, GE)

8. ✅ wind_resource/config/era5_config.yaml (commit: 8dacf1f)
   - API settings, loss factors, P-levels

## 🚧 REMAINING WORK

### Phase 2B: Core Analyzers (NEXT - 3 files)

These need to be created with same quality as era5_fetcher.py:

#### 1. wind_resource/wind_analyzer.py (HIGH PRIORITY)
**Purpose:** Statistical analysis of wind data

**Required Functions:**
```python
class WindAnalyzer:
    """Comprehensive wind resource statistical analysis.
    
    Performs Weibull fitting, temporal pattern analysis, variability
    assessment, and generates summary statistics.
    """
    
    def __init__(self, df: pd.DataFrame, ws_column: str = 'ws_150m') -> None:
        """Initialize analyzer with wind speed DataFrame.
        
        Args:
            df: DataFrame with timestamp and wind speed columns.
            ws_column: Name of wind speed column to analyze.
        """
    
    def fit_weibull(self) -> Dict[str, float]:
        """Fit 2-parameter Weibull distribution to wind speeds.
        
        Returns:
            Dict with keys: shape_k, scale_c, r_squared, ks_pvalue.
        """
    
    def analyze_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze monthly, diurnal, and seasonal patterns.
        
        Returns:
            Dict with monthly/hourly/seasonal statistics.
        """
    
    def calculate_interannual_variability(self) -> Dict[str, float]:
        """Calculate year-to-year wind speed variability.
        
        Returns:
            Dict with mean_annual_ws, std, cov, etc.
        """
    
    def analyze_all(self) -> Dict[str, Any]:
        """Run complete analysis suite.
        
        Returns:
            Complete analysis results dictionary.
        """
    
    def generate_summary_report(self) -> str:
        """Generate human-readable text summary.
        
        Returns:
            Multi-line string report.
        """
```

**GWTF Requirements:**
- ✅ Google-style docstrings for ALL methods
- ✅ Full type hints (-> Dict[str, float], etc.)
- ✅ Args, Returns, Raises sections
- ✅ Example usage in docstrings
- ✅ from __future__ import annotations

**Estimated Size:** ~250 lines, ~8 KB

#### 2. wind_resource/energy_calculator.py (HIGH PRIORITY)
**Purpose:** Energy production and revenue calculations

**Required Functions:**
```python
class EnergyCalculator:
    """Calculate Annual Energy Production from wind data.
    
    Applies power curves, loss factors, and P-level scenarios to
    compute gross/net AEP and revenue projections.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        ws_column: str = 'ws_150m',
        power_curve: Optional[Dict[str, List[float]]] = None,
        losses: Optional[Dict[str, float]] = None,
        num_turbines: int = 15,
        rated_capacity: float = 6500
    ) -> None:
        """Initialize energy calculator.
        
        Args:
            df: DataFrame with wind speed data.
            ws_column: Wind speed column name.
            power_curve: Dict with 'ws' and 'power' lists.
            losses: Loss factors dict.
            num_turbines: Number of turbines.
            rated_capacity: Rated capacity per turbine (kW).
        """
    
    def calculate_gross_aep(self) -> Dict[str, float]:
        """Calculate gross Annual Energy Production.
        
        Returns:
            Dict with average_power_kw, capacity_factor_gross,
            single_turbine_aep_mwh, windfarm_aep_mwh.
        """
    
    def calculate_net_aep(
        self,
        gross_aep_mwh: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculate net AEP with losses for P50/P75/P90.
        
        Args:
            gross_aep_mwh: Gross AEP in MWh. If None, calculates.
        
        Returns:
            Dict with net_aep_p50/p75/p90_mwh and capacity factors.
        """
    
    def calculate_monthly_energy(self) -> pd.DataFrame:
        """Calculate monthly energy production profile.
        
        Returns:
            DataFrame with month, energy_mwh, cf_percent columns.
        """
    
    def calculate_revenue(
        self,
        net_aep_results: Dict[str, float],
        tariff_lkr_per_kwh: float = 20.30,
        exchange_rate_lkr_usd: float = 300.0
    ) -> Dict[str, float]:
        """Calculate revenue projections for 20-year PPA.
        
        Args:
            net_aep_results: Output from calculate_net_aep().
            tariff_lkr_per_kwh: Electricity tariff (LKR/kWh).
            exchange_rate_lkr_usd: LKR to USD exchange rate.
        
        Returns:
            Dict with annual and cumulative revenues.
        """
    
    def generate_complete_assessment(self) -> Dict[str, Any]:
        """Run complete energy assessment.
        
        Returns:
            Complete assessment with gross_aep, net_aep, monthly, revenue.
        """
```

**GWTF Requirements:** Same as wind_analyzer.py

**Estimated Size:** ~280 lines, ~10 KB

#### 3. wind_resource/wind_pipeline.py (MEDIUM PRIORITY)
**Purpose:** Main orchestrator for complete workflow

**Required Functions:**
```python
class WindPipeline:
    """Complete wind resource assessment pipeline.
    
    Coordinates ERA5 fetching, wind analysis, and energy calculations
    into a streamlined workflow with JSON export.
    """
    
    def __init__(
        self,
        location: Dict[str, float],
        hub_height: float = 150.0,
        num_turbines: int = 15,
        rated_capacity: float = 6500,
        cache_dir: str = "inputs/wind_data",
        output_dir: str = "outputs/wind_assessment"
    ) -> None:
        """Initialize wind assessment pipeline.
        
        Args:
            location: Dict with 'name', 'lat', 'lon'.
            hub_height: Turbine hub height (m).
            num_turbines: Number of turbines.
            rated_capacity: Rated capacity per turbine (kW).
            cache_dir: Directory for cached ERA5 data.
            output_dir: Directory for analysis outputs.
        """
    
    def run_complete_assessment(
        self,
        start_date: str = '2014-12-01',
        end_date: str = '2025-12-31',
        force_download: bool = False
    ) -> Dict[str, Any]:
        """Run complete wind resource assessment pipeline.
        
        Args:
            start_date: Start date for ERA5 data (YYYY-MM-DD).
            end_date: End date for ERA5 data (YYYY-MM-DD).
            force_download: Force re-download of ERA5 data.
        
        Returns:
            Complete assessment results dict.
        """
    
    def export_for_cashflow_model(
        self,
        scenario: str = 'P75'
    ) -> Dict[str, Any]:
        """Export key metrics for integration with cashflow model.
        
        Args:
            scenario: P50, P75, or P90.
        
        Returns:
            Dict with cashflow model inputs.
        """
```

**GWTF Requirements:** Same as above

**Estimated Size:** ~220 lines, ~8 KB

### Phase 3: Hydra-Based CLI Tools (CRITICAL - 4 files)

**CRITICAL:** These MUST use Hydra (argparse is BANNED by R3, CLI-01)

#### Pattern to Follow:
See [run_full_pipeline_v14.py](https://github.com/arunakulat/dutchbay-epc-model/blob/feature/add-finance-contracts-pydantic-v2-20251219/run_full_pipeline_v14.py)

#### 1. conf/wind_download.yaml
```yaml
# Hydra config for ERA5 download
location: ""  # Override: location=dutchbay
start_date: "2014-12-01"
end_date: "2025-12-31"
hub_height: 150.0
force_download: false
cache_dir: "inputs/wind_data"
```

#### 2. run_wind_download_v14.py
```python
from __future__ import annotations

import json
import logging
from pathlib import Path

import hydra
from omegaconf import DictConfig
import yaml

from wind_resource import ERA5Fetcher

logger = logging.getLogger(__name__)
_ORIG_CWD = Path.cwd()

@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="wind_download",
)
def cli(cfg: DictConfig) -> None:
    """Hydra CLI for ERA5 wind data download.
    
    Usage:
        python run_wind_download_v14.py location=dutchbay
        python run_wind_download_v14.py location=dutchbay force_download=true
    
    Args:
        cfg: Hydra configuration from conf/wind_download.yaml.
    """
    os.chdir(_ORIG_CWD)
    
    # Load location from config
    location_name = cfg.get("location")
    if not location_name:
        raise SystemExit("Missing 'location'. Use: location=dutchbay")
    
    # Load location details
    with open("wind_resource/config/locations.yaml") as f:
        locations = yaml.safe_load(f)
    
    if location_name not in locations:
        raise SystemExit(f"Unknown location: {location_name}")
    
    location = locations[location_name]
    
    # Download data
    fetcher = ERA5Fetcher(cache_dir=cfg.cache_dir)
    
    data_file = fetcher.download_wind_data(
        location=location,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        force_download=cfg.force_download
    )
    
    # Extrapolate to hub height
    import pandas as pd
    df = pd.read_csv(data_file)
    df = fetcher.extrapolate_to_hub_height(df, hub_height=cfg.hub_height)
    
    output_file = data_file.parent / f"{data_file.stem}_{int(cfg.hub_height)}m.csv"
    df.to_csv(output_file, index=False)
    
    # JSON output (CLI-03 compliance)
    result = {
        "status": "success",
        "location": location_name,
        "data_file": str(output_file),
        "start_date": cfg.start_date,
        "end_date": cfg.end_date,
        "hub_height": cfg.hub_height,
        "mean_ws": float(df[f'ws_{int(cfg.hub_height)}m'].mean())
    }
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    cli()
```

#### Similar pattern for:
3. **conf/wind_analysis.yaml** + **run_wind_analysis_v14.py**
4. **conf/wind_integration.yaml** + **run_wind_integration_v14.py**

### Phase 4: Testing & Documentation (3 files)

1. **tests/wind_resource/test_era5_fetcher.py**
   - pytest unit tests
   - Mock CDS API calls
   - Test extrapolation

2. **tests/wind_resource/test_wind_analyzer.py**
   - Test Weibull fitting
   - Test temporal analysis

3. **tests/wind_resource/test_integration.py**
   - End-to-end pipeline test
   - Validate P75 results

## 📋 GWTF Compliance Checklist

### For ALL New Files:
- [ ] Google-style docstrings (R24)
- [ ] Full type hints with `from __future__ import annotations` (TYPE-01)
- [ ] Args, Returns, Raises, Example sections
- [ ] Functions are help()-discoverable
- [ ] Pass mypy strict mode
- [ ] Pass black formatting
- [ ] Pass isort import sorting
- [ ] No argparse usage (R3)
- [ ] Hydra-based CLIs only (CLI-01)
- [ ] JSON-first outputs (CLI-03)
- [ ] Config-first architecture (ARCH-01)

## 🎯 Immediate Next Steps

1. **Create wind_analyzer.py** with full docstrings
2. **Create energy_calculator.py** with full docstrings
3. **Create wind_pipeline.py** with full docstrings
4. **Create Hydra CLI configs** (conf/*.yaml)
5. **Create Hydra CLI scripts** (run_*_v14.py)
6. **Add pytest tests**
7. **Update WIND_RESOURCE_STATUS.md**

## 📊 Progress Tracking

```
Phase 1: Foundation           ✅ 100% (5/5 files)
Phase 2A: Config & Fetcher    ✅ 100% (3/3 files)
Phase 2B: Core Analyzers      ⏳ 0% (0/3 files)
Phase 3: Hydra CLIs           ⏳ 0% (0/4 files)
Phase 4: Testing              ⏳ 0% (0/3 files)

Total Progress: 53% (8/15 core files)
```

## 🔗 Resources

- **Hydra Pattern:** [run_full_pipeline_v14.py](https://github.com/arunakulat/dutchbay-epc-model/blob/feature/add-finance-contracts-pydantic-v2-20251219/run_full_pipeline_v14.py)
- **GWTF Rules:** [go_with_the_flow_rules_v3_0_clean.csv](https://github.com/arunakulat/dutchbay-epc-model/blob/feature/add-finance-contracts-pydantic-v2-20251219/go_with_the_flow_rules_v3_0_clean.csv)
- **Completed ERA5 Fetcher:** [wind_resource/era5_fetcher.py](https://github.com/arunakulat/dutchbay-epc-model/blob/feature/add-finance-contracts-pydantic-v2-20251219/wind_resource/era5_fetcher.py) ← USE AS TEMPLATE

---

**Next Action:** Create wind_analyzer.py following era5_fetcher.py pattern  
**Branch:** feature/add-finance-contracts-pydantic-v2-20251219  
**Commits So Far:** 8 successful
