#!/usr/bin/env python3
"""
DUTCHBAY V13 - FX DATA PROCESSOR (DUAL-REGIME ANALYSIS)
Convert complete CSV to DUAL models:
  1. Recent Regime: 2016-2025 (5 granular periods for lender focus)
  2. Full Historical: 1975-2025 (5 true decades for tail-risk)

METHODOLOGY:
- Recent regime (2016-2025): Primary model for lender presentation
- Full historical (1975-2025): Tail-risk overlay & extreme scenario calibration
- Both outputs combined: Comprehensive risk assessment

Usage: python3 fx_data_processor.py <csv_file>
Output: 10 YAML files (5 recent periods + 5 historical decades)
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from datetime import datetime

def process_fx_csv_dual_regime(csv_file):
    """
    Load complete FX CSV and generate DUAL regime models:
    1. Recent Regime: 2016-2025 (5 periods, high granularity)
    2. Full Historical: 1975-2025 (5 decades, tail-risk)
    """
    
    print("\n" + "="*90)
    print("FX DATA PROCESSOR - DUAL REGIME ANALYSIS")
    print("Mode 1: Recent Regime (2016-2025) + Mode 2: Full Historical (1975-2025)")
    print("="*90)
    
    # Read complete CSV
    try:
        df = pd.read_csv(csv_file)
        
        # Handle both CSV formats
        if 'Date' in df.columns and 'Exchange Rate' in df.columns:
            df = df[['Date', 'Exchange Rate']].copy()
            df.columns = ['Date', 'Rate']
        elif len(df.columns) == 3:
            df.columns = ['Currency', 'Date', 'Rate']
            df = df[['Date', 'Rate']].copy()
        else:
            print(f"âœ— ERROR: Unexpected CSV format")
            return False
        
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        
        print(f"\nâœ“ CSV loaded: {len(df)} daily observations")
        print(f"  Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
        print(f"  Coverage: {(df['Date'].max() - df['Date'].min()).days / 365.25:.1f} years")
        print(f"  FX range: {df['Rate'].min():.2f} - {df['Rate'].max():.2f} LKR/USD")
        
    except Exception as e:
        print(f"âœ— ERROR loading CSV: {e}")
        return False
    
    # ==================================================================================
    # REGIME 1: RECENT REGIME (2016-2025) - 5 Granular Periods
    # ==================================================================================
    print("\n" + "â–ˆ"*90)
    print("REGIME 1: RECENT REGIME (2016-2025) - 5 Granular Periods")
    print("Purpose: Lender-focused analysis, current market dynamics")
    print("â–ˆ"*90)
    
    recent_periods = [
        {
            'name': 'Recent_Period1_2016_2017',
            'start_year': 2016, 'end_year': 2017,
            'description': 'Pre-Crisis Baseline (2016-2017)',
            'context': 'Pegged rate regime, controlled environment, baseline ~150 LKR/USD',
            'regime': 'Currency Board / Managed'
        },
        {
            'name': 'Recent_Period2_2018_2019',
            'start_year': 2018, 'end_year': 2019,
            'description': 'Major Crisis & Stabilization (2018-2019)',
            'context': '2018 major depreciation (50%+), gradual stabilization through 2019',
            'regime': 'Floating / Managed Float'
        },
        {
            'name': 'Recent_Period3_2020_2021',
            'start_year': 2020, 'end_year': 2021,
            'description': 'COVID Pressure (2020-2021)',
            'context': 'COVID-19 impacts, reserve pressure, controlled rate regime',
            'regime': 'Managed Float'
        },
        {
            'name': 'Recent_Period4_2022_2023',
            'start_year': 2022, 'end_year': 2023,
            'description': 'Extreme Crisis & Recovery (2022-2023)',
            'context': '2022 extreme crisis (pegged ~363 LKR/USD), 2023 gradual recovery',
            'regime': 'Floating (Post-CB)'
        },
        {
            'name': 'Recent_Period5_2024_2025',
            'start_year': 2024, 'end_year': 2025,
            'description': 'Stabilization & Current (2024-2025)',
            'context': 'Post-crisis stabilization, market-determined rates ~290-305 LKR/USD',
            'regime': 'Floating Market'
        }
    ]
    
    # Process recent periods
    recent_files = _process_periods(df, recent_periods, 'recent', 'LENDER-FOCUSED')
    
    # ==================================================================================
    # REGIME 2: FULL HISTORICAL (1975-2025) - 5 True Decades for Tail-Risk
    # ==================================================================================
    print("\n" + "â–ˆ"*90)
    print("REGIME 2: FULL HISTORICAL (1975-2025) - 5 True Decades")
    print("Purpose: Tail-risk calibration, extreme scenario modeling")
    print("â–ˆ"*90)
    
    historical_decades = [
        {
            'name': 'Historical_Decade1_1975_1984',
            'start_year': 1975, 'end_year': 1984,
            'description': 'Foundation Decade (1975-1984)',
            'context': 'Post-independence currency stabilization, fixed peg regime, baseline period',
            'regime': 'Fixed Peg',
            'note': 'Historical baseline - may have data quality issues'
        },
        {
            'name': 'Historical_Decade2_1985_1994',
            'start_year': 1985, 'end_year': 1994,
            'description': 'Pre-Crisis Decade (1985-1994)',
            'context': 'Exchange controls, civil war begins (1983), capital controls active',
            'regime': 'Fixed Peg with Controls',
            'note': 'Civil war period - significant disruption'
        },
        {
            'name': 'Historical_Decade3_1995_2004',
            'start_year': 1995, 'end_year': 2004,
            'description': 'Currency Board Decade (1995-2004)',
            'context': 'Currency Board introduced 1995, civil war ends 2002, strong peg constraints',
            'regime': 'Currency Board (Hard Peg)',
            'note': 'Artificial constraints - limited depreciation possible'
        },
        {
            'name': 'Historical_Decade4_2005_2014',
            'start_year': 2005, 'end_year': 2014,
            'description': 'Liberalization Decade (2005-2014)',
            'context': 'CB abolished 2005, managed float introduced, gradual liberalization',
            'regime': 'Managed Float',
            'note': '2008-09 Global Financial Crisis impact'
        },
        {
            'name': 'Historical_Decade5_2015_2025',
            'start_year': 2015, 'end_year': 2025,
            'description': 'Modern Crisis Decade (2015-2025)',
            'context': '2018 crisis, 2022 extreme crisis, floating market, IMF programs',
            'regime': 'Floating Market',
            'note': 'Most relevant for current dynamics - extreme events captured'
        }
    ]
    
    # Process historical decades
    historical_files = _process_periods(df, historical_decades, 'historical', 'TAIL-RISK FOCUS')
    
    # ==================================================================================
    # Summary
    # ==================================================================================
    print("\n" + "="*90)
    print("âœ“âœ“âœ“ DUAL REGIME PROCESSING COMPLETE âœ“âœ“âœ“")
    print("="*90)
    
    print(f"\nâœ“ Recent Regime Files (2016-2025): {len(recent_files)} files")
    for f in recent_files:
        print(f"  - {Path(f).name}")
    
    print(f"\nâœ“ Historical Decade Files (1975-2025): {len(historical_files)} files")
    for f in historical_files:
        print(f"  - {Path(f).name}")
    
    print(f"\nTotal: {len(recent_files) + len(historical_files)} YAML files generated")
    
    print("\n" + "="*90)
    print("USAGE GUIDANCE")
    print("="*90)
    print("""
LENDER PRESENTATION (Primary):
  Use: Recent regime files (2016-2025)
  Load: fx_data_recent_Period*.yaml
  Rationale: Current market dynamics, lender-relevant timeframe
  
STRESS TESTING (Comprehensive):
  Use: Historical decades (1975-2025)
  Load: fx_data_historical_Decade*.yaml
  Rationale: Tail-risk calibration, 50-year extremes
  
COMBINED ANALYSIS (Most Rigorous):
  Use: Both regimes
  Process:
    1. Base scenarios: Recent regime (primary)
    2. Stress scenarios: Recent + historical comparison
    3. Extreme scenarios: Historical tail risk
  Result: Comprehensive risk coverage

PYTHON CODE TO LOAD BOTH REGIMES:

import yaml
from glob import glob

# Load recent regime
recent_files = sorted(glob('fx_data_recent_Period*.yaml'))
recent_data = []
for f in recent_files:
    with open(f) as file:
        data = yaml.safe_load(file)
    recent_data.extend(data['fx_monthly_data'])

# Load historical decades
historical_files = sorted(glob('fx_data_historical_Decade*.yaml'))
historical_data = []
for f in historical_files:
    with open(f) as file:
        data = yaml.safe_load(file)
    historical_data.extend(data['fx_monthly_data'])

# Combined analysis
print(f"Recent regime: {len(recent_data)} months")
print(f"Historical: {len(historical_data)} months")
    """)
    
    return True

def _process_periods(df, periods_config, regime_type, regime_desc):
    """
    Helper function to process periods/decades
    """
    files_created = []
    
    for idx, period_cfg in enumerate(periods_config, 1):
        print(f"\n[{regime_desc} - Period/Decade {idx}] {period_cfg['description']}")
        print("-" * 90)
        
        # Filter data
        start_date = f"{period_cfg['start_year']}-01-01"
        end_date = f"{period_cfg['end_year']}-12-31"
        period_df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)].copy()
        
        if len(period_df) == 0:
            print(f"  âš  No data for period {period_cfg['start_year']}-{period_cfg['end_year']}")
            continue
        
        # Aggregate to monthly
        period_df['YearMonth'] = period_df['Date'].dt.to_period('M')
        monthly = period_df.groupby('YearMonth').agg({
            'Rate': ['mean', 'min', 'max', 'std']
        }).round(4)
        
        monthly.columns = ['avg_rate', 'min_rate', 'max_rate', 'std_rate']
        monthly = monthly.reset_index()
        monthly['date'] = monthly['YearMonth'].astype(str)
        monthly = monthly.sort_values('date').reset_index(drop=True)
        
        # Calculate metrics
        monthly['monthly_change_pct'] = monthly['avg_rate'].pct_change() * 100
        monthly['monthly_change_pct'] = monthly['monthly_change_pct'].round(2)
        monthly['rolling_12m_vol_pct'] = (monthly['std_rate'].rolling(window=12, min_periods=1).mean() 
                                          / monthly['avg_rate'] * 100).round(2)
        
        # Build YAML
        yaml_data = {
            'metadata': {
                'currency_pair': 'USD/LKR',
                'base_currency': 'USD',
                'quote_currency': 'LKR',
                'regime': regime_type.upper(),
                'period': f"{period_cfg['start_year']}-{period_cfg['end_year']}",
                'description': period_cfg['description'],
                'context': period_cfg['context'],
                'regime_name': period_cfg['regime'],
                'regime_note': period_cfg.get('note', ''),
                'version': '1.0-dual-regime',
                'date_range': f"{monthly['date'].iloc[0]} to {monthly['date'].iloc[-1]}",
                'total_months': len(monthly),
                'total_daily_obs': len(period_df),
                'analysis_purpose': regime_desc
            },
            'fx_monthly_data': []
        }
        
        # Add records
        for _, row in monthly.iterrows():
            yaml_data['fx_monthly_data'].append({
                'date': row['date'],
                'avg_rate': float(row['avg_rate']),
                'min_rate': float(row['min_rate']),
                'max_rate': float(row['max_rate']),
                'std_rate': float(row['std_rate']),
                'monthly_change_pct': float(row['monthly_change_pct']) if pd.notna(row['monthly_change_pct']) else 0.0,
                'rolling_12m_vol_pct': float(row['rolling_12m_vol_pct']) if pd.notna(row['rolling_12m_vol_pct']) else 0.0
            })
        
        # Save YAML
        yaml_filename = f"fx_data_{regime_type}_{period_cfg['name']}.yaml"
        with open(yaml_filename, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
        
        files_created.append(yaml_filename)
        
        # Print stats
        print(f"  âœ“ {len(monthly)} months, {len(period_df)} daily obs")
        print(f"  âœ“ FX range: {monthly['avg_rate'].min():.2f} - {monthly['avg_rate'].max():.2f}")
        print(f"  âœ“ Mean volatility: {monthly['rolling_12m_vol_pct'].mean():.2f}%")
        print(f"  âœ“ Regime: {period_cfg['regime']}")
        print(f"  âœ“ Saved: {yaml_filename}")
    
    return files_created

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        # Try common filenames
        for name in ['fxdata.csv', 'data.csv', 'fx_data.csv']:
            if Path(name).exists():
                csv_file = name
                break
        else:
            print("âœ— CSV file not found")
            print("Usage: python3 fx_data_processor.py <csv_file>")
            sys.exit(1)
    
    if not Path(csv_file).exists():
        print(f"âœ— CSV file not found: {csv_file}")
        sys.exit(1)
    
    success = process_fx_csv_dual_regime(csv_file)
    sys.exit(0 if success else 1)