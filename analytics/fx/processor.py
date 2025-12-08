#!/usr/bin/env python3
"""
FX Data Processor - Dual-regime FX curve generation.

Migrated from: fx_data_processor_dual_regime.py (root)

Dual models:

1. Recent Regime: 2016–2025 (5 granular periods for lender focus)
2. Full Historical: 1975–2025 (5 true decades for tail-risk)

Methodology:
- Recent regime (2016–2025): Primary model for lender presentation.
- Full historical (1975–2025): Tail-risk overlay & extreme scenario calibration.
- Combined: Comprehensive FX risk assessment.

Outputs:
- YAML files under the current working directory:
  - fx_data_recent_*.yaml
  - fx_data_historical_*.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import pandas as pd
import yaml

PeriodConfig = Mapping[str, Any]
PeriodConfigList = Sequence[PeriodConfig]


def process_fx_csv_dual_regime(csv_file: str) -> bool:
    """
    Load complete FX CSV and generate dual‑regime YAML models.

    1. Recent Regime: 2016–2025 (5 periods, high granularity).
    2. Full Historical: 1975–2025 (5 decades, tail‑risk).

    Args:
        csv_file: Path to CSV with at least Date + FX rate columns.

    Returns:
        True if processing and file generation succeeded, otherwise False.
    """
    print("\n" + "=" * 90)
    print("FX DATA PROCESSOR - DUAL REGIME ANALYSIS")
    print("Mode 1: Recent Regime (2016–2025) + Mode 2: Full Historical (1975–2025)")
    print("=" * 90)

    # ------------------------------------------------------------------ #
    # Load and normalize CSV
    # ------------------------------------------------------------------ #
    try:
        df = pd.read_csv(csv_file)

        # Handle both CSV formats
        if "Date" in df.columns and "Exchange Rate" in df.columns:
            df = df[["Date", "Exchange Rate"]].copy()
            df.columns = ["Date", "Rate"]
        elif len(df.columns) == 3:
            # e.g. Currency, Date, Rate
            df.columns = ["Currency", "Date", "Rate"]
            df = df[["Date", "Rate"]].copy()
        else:
            print("✗ ERROR: Unexpected CSV format")
            return False

        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")

        print(f"\n✓ CSV loaded: {len(df)} daily observations")
        print(f"  Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
        coverage_years = (df["Date"].max() - df["Date"].min()).days / 365.25
        print(f"  Coverage: {coverage_years:.1f} years")
        print(f"  FX range: {df['Rate'].min():.2f} – {df['Rate'].max():.2f} LKR/USD")
    except Exception as exc:
        print(f"✗ ERROR loading CSV: {exc}")
        return False

    # ------------------------------------------------------------------ #
    # Regime 1: Recent regime (2016–2025)
    # ------------------------------------------------------------------ #
    print("\n" + "█" * 90)
    print("REGIME 1: RECENT REGIME (2016–2025) - 5 Granular Periods")
    print("Purpose: Lender-focused analysis, current market dynamics")
    print("█" * 90)

    recent_periods: PeriodConfigList = [
        {
            "name": "Recent_Period1_2016_2017",
            "start_year": 2016,
            "end_year": 2017,
            "description": "Pre-Crisis Baseline (2016–2017)",
            "context": "Pegged rate regime, controlled environment, baseline ~150 LKR/USD",
            "regime": "Currency Board / Managed",
        },
        {
            "name": "Recent_Period2_2018_2019",
            "start_year": 2018,
            "end_year": 2019,
            "description": "Major Crisis & Stabilization (2018–2019)",
            "context": "2018 major depreciation (50%+), gradual stabilization through 2019",
            "regime": "Floating / Managed Float",
        },
        {
            "name": "Recent_Period3_2020_2021",
            "start_year": 2020,
            "end_year": 2021,
            "description": "COVID Pressure (2020–2021)",
            "context": "COVID-19 impacts, reserve pressure, controlled rate regime",
            "regime": "Managed Float",
        },
        {
            "name": "Recent_Period4_2022_2023",
            "start_year": 2022,
            "end_year": 2023,
            "description": "Extreme Crisis & Recovery (2022–2023)",
            "context": "2022 extreme crisis (~363 LKR/USD), 2023 gradual recovery",
            "regime": "Floating (Post-CB)",
        },
        {
            "name": "Recent_Period5_2024_2025",
            "start_year": 2024,
            "end_year": 2025,
            "description": "Stabilization & Current (2024–2025)",
            "context": "Post-crisis stabilization, market-determined rates ~290–305 LKR/USD",
            "regime": "Floating Market",
        },
    ]

    recent_files = _process_periods(
        df=df,
        periods_config=recent_periods,
        regime_type="recent",
        regime_desc="LENDER-FOCUSED",
    )

    # ------------------------------------------------------------------ #
    # Regime 2: Full historical (1975–2025)
    # ------------------------------------------------------------------ #
    print("\n" + "█" * 90)
    print("REGIME 2: FULL HISTORICAL (1975–2025) - 5 True Decades")
    print("Purpose: Tail-risk calibration, extreme scenario modeling")
    print("█" * 90)

    historical_decades: PeriodConfigList = [
        {
            "name": "Historical_Decade1_1975_1984",
            "start_year": 1975,
            "end_year": 1984,
            "description": "Foundation Decade (1975–1984)",
            "context": "Post-independence currency stabilization, fixed peg regime",
            "regime": "Fixed Peg",
            "note": "Historical baseline – may have data quality issues",
        },
        {
            "name": "Historical_Decade2_1985_1994",
            "start_year": 1985,
            "end_year": 1994,
            "description": "Pre-Crisis Decade (1985–1994)",
            "context": "Exchange controls, civil war begins 1983, capital controls active",
            "regime": "Fixed Peg with Controls",
            "note": "Civil war period – significant disruption",
        },
        {
            "name": "Historical_Decade3_1995_2004",
            "start_year": 1995,
            "end_year": 2004,
            "description": "Currency Board Decade (1995–2004)",
            "context": "Currency Board introduced 1995, conflict winds down, strong peg constraints",
            "regime": "Currency Board (Hard Peg)",
            "note": "Artificial constraints – limited depreciation possible",
        },
        {
            "name": "Historical_Decade4_2005_2014",
            "start_year": 2005,
            "end_year": 2014,
            "description": "Liberalization Decade (2005–2014)",
            "context": "CB abolished 2005, managed float introduced, gradual liberalization",
            "regime": "Managed Float",
            "note": "2008–09 Global Financial Crisis impact",
        },
        {
            "name": "Historical_Decade5_2015_2025",
            "start_year": 2015,
            "end_year": 2025,
            "description": "Modern Crisis Decade (2015–2025)",
            "context": "2018 crisis, 2022 extreme crisis, floating market, IMF programs",
            "regime": "Floating Market",
            "note": "Most relevant for current dynamics – extreme events captured",
        },
    ]

    historical_files = _process_periods(
        df=df,
        periods_config=historical_decades,
        regime_type="historical",
        regime_desc="TAIL-RISK FOCUS",
    )

    # ------------------------------------------------------------------ #
    # Summary and usage guidance
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 90)
    print("✓✓✓ DUAL REGIME PROCESSING COMPLETE ✓✓✓")
    print("=" * 90)

    print(f"\n✓ Recent Regime Files (2016–2025): {len(recent_files)} files")
    for f in recent_files:
        print(f"  - {Path(f).name}")

    print(f"\n✓ Historical Decade Files (1975–2025): {len(historical_files)} files")
    for f in historical_files:
        print(f"  - {Path(f).name}")

    total_files = len(recent_files) + len(historical_files)
    print(f"\nTotal: {total_files} YAML files generated")

    print("\n" + "=" * 90)
    print("USAGE GUIDANCE")
    print("=" * 90)
    print(
        """
LENDER PRESENTATION (Primary)
- Use: Recent regime files (2016–2025)
- Load: fx_data_recent_Period*.yaml
- Rationale: Current market dynamics, lender-relevant timeframe

STRESS TESTING (Comprehensive)
- Use: Historical decades (1975–2025)
- Load: fx_data_historical_Decade*.yaml
- Rationale: Tail-risk calibration, 50-year extremes

COMBINED ANALYSIS (Most Rigorous)
- Use: Both regimes
- Process:
  1. Base scenarios: Recent regime (primary)
  2. Stress scenarios: Recent + historical comparison
  3. Extreme scenarios: Historical tail risk

Example loader snippet:

    import yaml
    from glob import glob

    # Load recent regime
    recent_files = sorted(glob("fx_data_recent_Period*.yaml"))
    recent_data = []
    for path in recent_files:
        with open(path) as fh:
            data = yaml.safe_load(fh)
            recent_data.extend(data["fx_monthly_data"])

    # Load historical decades
    historical_files = sorted(glob("fx_data_historical_Decade*.yaml"))
    historical_data = []
    for path in historical_files:
        with open(path) as fh:
            data = yaml.safe_load(fh)
            historical_data.extend(data["fx_monthly_data"])

    print(f"Recent regime: {len(recent_data)} months")
    print(f"Historical: {len(historical_data)} months")
"""
    )

    return True


def _process_periods(
    df: pd.DataFrame,
    periods_config: PeriodConfigList,
    regime_type: str,
    regime_desc: str,
) -> List[str]:
    """
    Process configured periods/decades and write YAML files.

    Args:
        df: Daily FX time series (Date, Rate).
        periods_config: List of period configuration mappings.
        regime_type: "recent" or "historical" (used in filenames).
        regime_desc: Human label for console logging.

    Returns:
        List of YAML file paths written.
    """
    files_created: List[str] = []

    for idx, period_cfg in enumerate(periods_config, start=1):
        description = str(period_cfg.get("description", ""))
        start_year = int(period_cfg["start_year"])
        end_year = int(period_cfg["end_year"])

        print(f"\n[{regime_desc} - Period/Decade {idx}] {description}")
        print("-" * 90)

        # Filter data
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"
        period_df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)].copy()

        if period_df.empty:
            print(f" ⚠ No data for period {start_year}-{end_year}")
            continue

        # Aggregate to monthly
        period_df["YearMonth"] = period_df["Date"].dt.to_period("M")
        monthly = (
            period_df.groupby("YearMonth")
            .agg({"Rate": ["mean", "min", "max", "std"]})
            .round(4)
        )
        monthly.columns = ["avg_rate", "min_rate", "max_rate", "std_rate"]
        monthly = monthly.reset_index()
        monthly["date"] = monthly["YearMonth"].astype(str)
        monthly = monthly.sort_values("date").reset_index(drop=True)

        # Monthly metrics
        monthly["monthly_change_pct"] = monthly["avg_rate"].pct_change() * 100.0
        monthly["monthly_change_pct"] = monthly["monthly_change_pct"].round(2)

        monthly["rolling_12m_vol_pct"] = (
            monthly["std_rate"].rolling(window=12, min_periods=1).mean()
            / monthly["avg_rate"]
            * 100.0
        ).round(2)

        # YAML structure
        yaml_data: Dict[str, Any] = {
            "metadata": {
                "currency_pair": "USD/LKR",
                "base_currency": "USD",
                "quote_currency": "LKR",
                "regime": regime_type.upper(),
                "period": f"{start_year}-{end_year}",
                "description": description,
                "context": period_cfg.get("context", ""),
                "regime_name": period_cfg.get("regime", ""),
                "regime_note": period_cfg.get("note", ""),
                "version": "1.0-dual-regime",
                "date_range": f"{monthly['date'].iloc[0]} to {monthly['date'].iloc[-1]}",
                "total_months": int(len(monthly)),
                "total_daily_obs": int(len(period_df)),
                "analysis_purpose": regime_desc,
            },
            "fx_monthly_data": [],
        }

        records: List[Dict[str, Any]] = []
        for _, row in monthly.iterrows():
            record: Dict[str, Any] = {
                "date": row["date"],
                "avg_rate": float(row["avg_rate"]),
                "min_rate": float(row["min_rate"]),
                "max_rate": float(row["max_rate"]),
                "std_rate": float(row["std_rate"]),
                "monthly_change_pct": (
                    float(row["monthly_change_pct"])
                    if pd.notna(row["monthly_change_pct"])
                    else 0.0
                ),
                "rolling_12m_vol_pct": (
                    float(row["rolling_12m_vol_pct"])
                    if pd.notna(row["rolling_12m_vol_pct"])
                    else 0.0
                ),
            }
            records.append(record)

        yaml_data["fx_monthly_data"] = records

        # Save YAML
        yaml_filename = f"fx_data_{regime_type}_{period_cfg['name']}.yaml"
        with open(yaml_filename, "w", encoding="utf-8") as fh:
            yaml.dump(yaml_data, fh, default_flow_style=False, sort_keys=False)

        files_created.append(yaml_filename)

        # Print stats
        print(f" ✓ {len(monthly)} months, {len(period_df)} daily obs")
        print(
            f" ✓ FX range: {monthly['avg_rate'].min():.2f} – {monthly['avg_rate'].max():.2f}"
        )
        print(f" ✓ Mean volatility: {monthly['rolling_12m_vol_pct'].mean():.2f}%")
        print(f" ✓ Regime: {period_cfg.get('regime', '')}")
        print(f" ✓ Saved: {yaml_filename}")

    return files_created


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = ""
        for candidate in ("fxdata.csv", "data.csv", "fx_data.csv"):
            if Path(candidate).exists():
                csv_path = candidate
                break

    if not csv_path or not Path(csv_path).exists():
        print("✗ CSV file not found")
        print("Usage: python3 fx_data_processor.py <path/to/fx_data.csv>")
        sys.exit(1)

    ok = process_fx_csv_dual_regime(csv_path)
    sys.exit(0 if ok else 1)
