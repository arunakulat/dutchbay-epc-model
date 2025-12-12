# Dutch Bay V14 - Complete Upgrade Specification
# From v13 + v2.4.2-v2.4.4 → v14
# Date: 2025-11-16

---

## Executive Summary

Version 14 represents a major upgrade integrating:
- **v13 base**: Advanced covenant system, Monte Carlo, multi-lender mix
- **v2.4.2**: Comprehensive equity analysis with FX/bank rates
- **v2.4.3**: Three tax/depreciation scenarios
- **v2.4.4**: Grace period and debt tranching
- **v14 new**: Complete construction period modeling

---

## Version Lineage

```
v13 (Base)
    ↓
v2.4.2 (Equity Analysis)
    ↓
v2.4.3 (Tax Scenarios)
    ↓
v2.4.4 (Grace & Tranching)
    ↓
v14 (Complete Integration)
```

---

## File Deduplication Results

### Files Consolidated:
- `check_all_py_files.py`: 2 → 1 (kept latest)
- `CHANGELOG.md`: 2 → 1
- `audit_report.json`: 2 → 1
- `data.csv`: 3 → 1 (kept 78967 chars version)
- `fxdata.csv`: 3 → 1
- `cashflow.py`: 2 → 1 (27179 chars)
- `metrics.py`: 2 → 1 (15400 chars)
- `debt.py`: Single version retained
- `full_model_variables`: v243 used as base for v14

### Total Files Analyzed: 64
### Duplicates Removed: 18
### Clean Files for v14: 46

---

## Architecture Analysis

### v13 Strengths Preserved:
1. ✅ Multi-lender mix (DFI, USD commercial, LKR)
2. ✅ Advanced covenant system with warnings
3. ✅ Monte Carlo simulation (100k scenarios)
4. ✅ Refinancing capabilities
5. ✅ Revenue guarantee options
6. ✅ Comprehensive constraint validation

### v2.4.x Features Integrated:
1. ✅ Construction period (2 years)
2. ✅ Debt drawdown tranches (equal split)
3. ✅ Interest-only grace period
4. ✅ Tax holiday scenarios (5yr/7yr)
5. ✅ Accelerated depreciation option
6. ✅ Comprehensive equity analysis table
7. ✅ USD/LKR dividend split
8. ✅ Bank-equivalent rate calculations

---

## Critical Integration Points

### 1. Timeline Extension

**Before (v13):**
- 15-year operational period only
- No construction modeling

**After (v14):**
```
Year -2: Construction Year 1 (40% capex, 33% debt drawn)
Year -1: Construction Year 2 (40% capex, 33% debt drawn)
Year 0:  COD (20% capex, 34% debt drawn)
Year 1-15: Operational period (principal repayment)
Year 16-20: Extended operational (if configured)
```

### 2. Debt Service Structure

**Grace Period Implementation:**
```python
def calculate_debt_service_v14(
    principal: float,
    rate: float,
    construction_years: int = 2,
    grace_years: int = 2,
    operational_years: int = 15,
    sculpting: bool = True
) -> Tuple[List[float], List[float]]:
    """
    Years -2 to 0: Interest only (capitalized or paid from equity)
    Years 1 to 15: Principal + Interest (sculpted to target DSCR)
    """
    pass
```

### 3. Tax Scenario Switching

**Scenario Manager:**
```python
class ScenarioManagerV14:
    def __init__(self, config: Dict):
        self.base_config = config
        self.scenarios = config['scenarios']
    
    def apply_scenario(self, scenario_name: str) -> Dict:
        """Apply tax scenario overlay to base config"""
        pass
```

---

## Module-by-Module Refactoring Guide

### Module 1: debt.py → debt_v14.py

**New Functions Required:**

```python
def calculate_drawdown_schedule(
    total_debt: float,
    tranches: int = 3,
    profile: str = 'equal_annual'
) -> List[float]:
    """
    Calculate debt drawdown by period.
    Returns: [yr-2, yr-1, yr0] amounts
    """
    if profile == 'equal_annual':
        return [total_debt / tranches] * tranches
    # Add front-loaded, back-loaded options

def calculate_idc(
    drawdowns: List[float],
    interest_rate: float,
    capitalize: bool = True
) -> Tuple[float, List[float]]:
    """
    Calculate Interest During Construction.
    Returns: (total_idc, period_interest)
    """
    outstanding = 0
    period_interest = []
    for drawdown in drawdowns:
        outstanding += drawdown
        interest = outstanding * interest_rate
        period_interest.append(interest)
        if capitalize:
            outstanding += interest
    return sum(period_interest), period_interest

def sculpt_with_grace(
    principal: float,
    rate: float,
    operational_years: int,
    cfads_projected: List[float],
    target_dscr: float = 1.30
) -> Tuple[List[float], List[float]]:
    """
    Sculpt principal payments starting after grace period.
    Accounts for IDC added to principal.
    """
    pass
```

**Integration Points:**
- Must handle IDC capitalization
- Preserve v13 multi-lender mix logic
- Maintain covenant checking
- Support refinancing pathways

---

### Module 2: cashflow.py → cashflow_v14.py

**Timeline Extension:**

```python
def generate_timeline_v14(config: Dict) -> List[int]:
    """
    Generate full project timeline including construction.
    
    Returns: [-2, -1, 0, 1, 2, ..., 20]
    Total periods: 23
    """
    construction_years = config['construction']['duration_years']
    operational_years = config['project']['operational_life_years']
    
    timeline = list(range(-construction_years, 0))  # [-2, -1]
    timeline += list(range(operational_years + 1))  # [0, 1, ..., 20]
    return timeline

def calculate_cfads_with_construction(
    timeline: List[int],
    revenue: List[float],
    opex: List[float],
    tax: List[float],
    capex_schedule: Dict[int, float],
    config: Dict
) -> List[float]:
    """
    Calculate CFADS including construction period.
    
    Construction years: Negative CFADS (capex outflows)
    Operational years: Positive CFADS (revenue - opex - tax)
    """
    cfads = []
    for period in timeline:
        if period < 0:  # Construction
            capex_key = f'year_minus_{abs(period)}'
            capex_pct = config['construction']['capex_schedule'][capex_key]
            total_capex = config['capex']['usd_total']
            cfads.append(-total_capex * capex_pct)
        else:  # Operational
            cfads.append(revenue[period] - opex[period] - tax[period])
    return cfads
```

**Key Changes:**
- Extend arrays to 23 periods (not 20)
- Handle negative CFADS during construction
- Track equity vs debt funding sources
- Maintain v13 revenue guarantee logic

---

### Module 3: metrics.py → metrics_v14.py

**No major structural changes**, but must handle:

```python
def calculate_dscr_v14(
    cfads: List[float],
    debt_service: List[float],
    timeline: List[int]
) -> List[float]:
    """
    Calculate DSCR only for operational years.
    Construction years: N/A or 0
    """
    dscr = []
    for i, period in enumerate(timeline):
        if period <= 0:  # Construction + COD
            dscr.append(None)  # Not applicable
        else:
            ds = debt_service[i]
            if ds > 0:
                dscr.append(cfads[i] / ds)
            else:
                dscr.append(float('inf'))
    return dscr
```

---

### Module 4: tax_calculator_v14.py (NEW)

**Purpose:** Handle tax scenarios

```python
from typing import Dict, List, Tuple

def calculate_depreciation_schedule(
    asset_value: float,
    method: str,
    years: int,
    enhanced_pct: float = 1.0
) -> List[float]:
    """
    Calculate annual depreciation.
    
    Args:
        method: 'straight_line' or 'accelerated'
        enhanced_pct: Multiplier for enhanced capital allowance
    """
    if method == 'straight_line':
        annual = (asset_value / years) * enhanced_pct
        return [annual] * years + [0] * (20 - years)
    
    elif method == 'accelerated':
        # Double declining balance or similar
        schedule = []
        remaining = asset_value
        rate = (2.0 / years) * enhanced_pct
        for _ in range(years):
            depr = remaining * rate
            schedule.append(depr)
            remaining -= depr
        # Pad to 20 years
        schedule += [0] * (20 - years)
        return schedule

def apply_tax_holiday(
    taxable_income: List[float],
    tax_rate: float,
    holiday_years: int,
    holiday_start: int = 1
) -> List[float]:
    """
    Apply tax holiday to operational years.
    
    Returns: List of tax amounts
    """
    tax = []
    for year, income in enumerate(taxable_income, start=1):
        if holiday_start <= year < (holiday_start + holiday_years):
            # Tax holiday - no tax
            tax.append(0)
        else:
            # Normal tax
            tax.append(max(income * tax_rate, 0))
    return tax

def calculate_tax_with_scenario(
    ebitda: List[float],
    depreciation: List[float],
    interest: List[float],
    scenario_config: Dict
) -> Tuple[List[float], List[float]]:
    """
    Full tax calculation with scenario parameters.
    
    Returns: (tax_paid, taxable_income)
    """
    taxable_income = []
    for i in range(len(ebitda)):
        ti = ebitda[i] - depreciation[i] - interest[i]
        taxable_income.append(ti)
    
    tax_paid = apply_tax_holiday(
        taxable_income,
        scenario_config['tax']['corporate_rate'],
        scenario_config['tax']['tax_holiday_years'],
        scenario_config['tax']['tax_holiday_start_year']
    )
    
    return tax_paid, taxable_income
```

---

### Module 5: scenario_manager_v14.py (NEW)

```python
import yaml
from typing import Dict, Any, List
from copy import deepcopy

class ScenarioManagerV14:
    """
    Manage and apply tax/depreciation scenarios for v14.
    """
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.base_config = deepcopy(self.config)
    
    def list_scenarios(self) -> List[str]:
        """Return available scenario names."""
        return list(self.config['scenarios'].keys())
    
    def get_scenario_info(self, scenario_name: str) -> Dict:
        """Get scenario description and parameters."""
        if scenario_name not in self.config['scenarios']:
            raise ValueError(f"Scenario '{scenario_name}' not found")
        return self.config['scenarios'][scenario_name]
    
    def apply_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """
        Apply scenario overlay to base configuration.
        
        Returns: Updated configuration with scenario parameters
        """
        if scenario_name not in self.config['scenarios']:
            raise ValueError(f"Scenario '{scenario_name}' not found")
        
        # Deep copy base config
        updated_config = deepcopy(self.base_config)
        
        # Get scenario parameters
        scenario = self.config['scenarios'][scenario_name]
        
        # Merge tax parameters
        if 'tax' in scenario:
            for key, value in scenario['tax'].items():
                updated_config['tax'][key] = value
        
        # Add scenario metadata
        updated_config['_active_scenario'] = scenario_name
        updated_config['_scenario_description'] = scenario['description']
        
        return updated_config
    
    def compare_scenarios(self, scenarios: List[str]) -> Dict:
        """
        Generate comparison matrix for scenarios.
        
        Returns: Dict with key metrics by scenario
        """
        comparison = {}
        for scenario_name in scenarios:
            config = self.apply_scenario(scenario_name)
            # Run model with this config
            # Store results
            comparison[scenario_name] = {
                'tax_holiday_years': config['tax']['tax_holiday_years'],
                'depreciation_method': config['tax']['depreciation_method'],
                'depreciation_years': config['tax']['depreciation_years']
            }
        return comparison
```

---

### Module 6: equity_analysis_v14.py (NEW)

```python
from typing import List, Dict, Tuple
import pandas as pd

def generate_comprehensive_equity_table_v14(
    timeline: List[int],
    gross_revenue: List[float],
    cfads: List[float],
    usd_debt_repayment_lkr: List[float],
    lkr_debt_repayment: List[float],
    tax: List[float],
    equity_dividend: List[float],
    equity_commitment_lkr: float,
    usd_equity_pct: float,
    lkr_equity_pct: float,
    usd_fx_rates: List[float]
) -> pd.DataFrame:
    """
    Generate the comprehensive 20-year equity analysis table
    from v2.4.2 thread specifications.
    
    Returns: DataFrame with all equity metrics
    """
    # Split equity commitment
    usd_equity_lkr = equity_commitment_lkr * usd_equity_pct
    lkr_equity_lkr = equity_commitment_lkr * lkr_equity_pct
    usd_equity_usd = usd_equity_lkr / usd_fx_rates[0]
    
    # Calculate declining balance
    declining_balance = []
    balance = equity_commitment_lkr
    for div in equity_dividend:
        balance = max(balance - div, 0)
        declining_balance.append(balance)
    
    # Split dividends by currency
    usd_equity_div_lkr = [div * usd_equity_pct for div in equity_dividend]
    lkr_equity_div_lkr = [div * lkr_equity_pct for div in equity_dividend]
    
    # Convert USD dividend to USD
    usd_equity_div_usd = [
        usd_equity_div_lkr[i] / usd_fx_rates[i] 
        for i in range(len(usd_equity_div_lkr))
    ]
    
    # Calculate bank-equivalent rates
    usd_bank_rate = [
        (usd_equity_div_usd[i] / usd_equity_usd * 100) 
        for i in range(len(usd_equity_div_usd))
    ]
    
    lkr_bank_rate = [
        (lkr_equity_div_lkr[i] / lkr_equity_lkr * 100)
        for i in range(len(lkr_equity_div_lkr))
    ]
    
    # Build DataFrame (operational years only)
    operational_years = [i for i in timeline if i > 0]
    df = pd.DataFrame({
        'Year': operational_years,
        'Gross Revenue': gross_revenue[:len(operational_years)],
        'CFADS': cfads[:len(operational_years)],
        'USD Debt Repayment (LKR)': usd_debt_repayment_lkr[:len(operational_years)],
        'LKR Debt Repayment': lkr_debt_repayment[:len(operational_years)],
        'Total Tax Amount': tax[:len(operational_years)],
        'Equity Dividend (LKR)': equity_dividend[:len(operational_years)],
        'Declining Equity Balance (LKR)': declining_balance[:len(operational_years)],
        'USD Equity Dividend (USD)': usd_equity_div_usd[:len(operational_years)],
        'USD Bank Rate (%)': usd_bank_rate[:len(operational_years)],
        'LKR Equity Dividend (LKR)': lkr_equity_div_lkr[:len(operational_years)],
        'LKR Bank Rate (%)': lkr_bank_rate[:len(operational_years)],
        'USD Spot Rate (LKR/USD)': usd_fx_rates[:len(operational_years)]
    })
    
    return df

def calculate_payback_period(
    equity_commitment: float,
    equity_dividends: List[float]
) -> float:
    """
    Calculate equity payback period in years.
    """
    cumulative = 0
    for year, dividend in enumerate(equity_dividends, start=1):
        cumulative += dividend
        if cumulative >= equity_commitment:
            # Interpolate for fractional year
            excess = cumulative - equity_commitment
            fraction = 1 - (excess / dividend)
            return year - 1 + fraction
    return float('inf')  # Not reached within period
```

---

## Testing Strategy

### Phase 1: Unit Tests

```bash
pytest tests/test_debt_v14.py -v
pytest tests/test_cashflow_v14.py -v
pytest tests/test_tax_calculator_v14.py -v
pytest tests/test_scenario_manager_v14.py -v
pytest tests/test_equity_analysis_v14.py -v
```

### Phase 2: Integration Tests

```bash
pytest tests/test_construction_period_integration.py -v
pytest tests/test_grace_period_integration.py -v
pytest tests/test_scenario_comparison.py -v
```

### Phase 3: Scenario Validation

```bash
# Run all three tax scenarios
python run_full_pipeline_v14.py --scenario five_year_tax_holiday_base
python run_full_pipeline_v14.py --scenario five_year_tax_holiday_accelerated
python run_full_pipeline_v14.py --scenario seven_year_tax_holiday_base

# Compare outputs
python compare_scenarios_v14.py --scenarios all
```

---

## Migration Checklist

### Configuration
- [x] Create v14 YAML with all integrated features
- [ ] Validate YAML structure
- [ ] Test scenario switching

### Core Modules
- [ ] Refactor debt.py → debt_v14.py
- [ ] Add drawdown schedule function
- [ ] Add IDC calculation
- [ ] Refactor cashflow.py → cashflow_v14.py
- [ ] Extend timeline to 23 periods
- [ ] Handle construction cashflows
- [ ] Update metrics.py → metrics_v14.py
- [ ] Adjust DSCR for construction period

### New Modules
- [ ] Create tax_calculator_v14.py
- [ ] Create scenario_manager_v14.py
- [ ] Create equity_analysis_v14.py

### Testing
- [ ] Write unit tests for all new functions
- [ ] Create integration test suite
- [ ] Validate against v13 baseline (for operational years)
- [ ] Validate against v2.4.4 equity table specs

### Documentation
- [ ] Update all docstrings
- [ ] Generate API documentation
- [ ] Create user guide for scenario switching
- [ ] Document construction period assumptions

### Deployment
- [ ] Run full test suite
- [ ] Generate all three scenario reports
- [ ] Board pack review
- [ ] Lock version for audit

---

## Success Criteria

✅ **All tests pass**
✅ **Three scenarios run successfully**
✅ **Equity analysis table matches v2.4.2 specifications**
✅ **Construction period cashflows balance**
✅ **IDC calculated correctly**
✅ **Grace period reflected in debt service**
✅ **DSCR covenants met in all scenarios**
✅ **v13 features preserved and functional**
✅ **Board/IC reports generated**
✅ **Audit trail complete**

---

## Version Control

```bash
# Tag v14 release
git tag -a v14.0.0 -m "Complete integration: v13 + v2.4.2-v2.4.4"
git push origin v14.0.0

# Create release branch
git checkout -b release/v14
git push origin release/v14
```

---

**STATUS: Ready for Implementation**
**NEXT STEPS: Begin module refactoring per specifications above**
