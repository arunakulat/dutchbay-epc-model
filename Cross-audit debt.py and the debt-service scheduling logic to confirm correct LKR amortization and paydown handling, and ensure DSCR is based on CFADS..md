# IMPLEMENTATION SCOPE CLARIFICATION
## Modules to Modify vs. Leave Untouched

**Date:** 2025-11-14 23:54 IST  
**Decision:** debt.py requires NO modifications

---

## EXECUTIVE DECISION

### ✓ DEBT.PY - APPROVED (Leave Unchanged)

**debt.py is PRODUCTION-GRADE and correctly implements all required logic:**

- ✓ Dynamic amortization schedules for both LKR and USD
- ✓ No hardcoded fixed annual debt amounts
- ✓ Tenor fully respected (debt paid off by end-of-tenor)
- ✓ YAML-driven configuration (all constraints, rates, mix ratios)
- ✓ Sculpted (target DSCR) amortization correctly references CFADS
- ✓ Multi-tranche support (LKR, USD, DFI) with pro-rata allocation
- ✓ Refinancing analysis, balloon monitoring, covenant validation
- ✓ Flexible amortization styles (annuity, sculpted)
- ✓ Interest-only periods fully supported
- ✓ Complete audit trail and validation framework

**No modifications needed. Leave as-is.**

---

## CRITICAL REQUIREMENT FOR CORRECT OUTPUT

debt.py requires input parameter: **CFADS** (Cash Flow Available for Debt Service)

This CFADS must be pre-calculated with **ALL deductions applied:**

```
Gross Production (kWh)
  ├─ Less: Grid Loss (%)
  └─ = Net Production (kWh)

Revenue (LKR) = Net Production × Tariff (LKR/kWh)
  ├─ Less: Success Fee (% of revenue)
  ├─ Less: Environmental Surcharge (% of revenue)
  ├─ Less: Social Services Levy (% of revenue)
  ├─ Less: OPEX (USD converted to LKR using annual FX)
  ├─ Less: Tax (if post-tax DSCR required)
  ├─ Less: Risk Adjustment Haircut (%)
  └─ = CFADS (in LKR)

DSCR = CFADS / [LKR Debt Service + (USD Debt Service × FX)]
```

**This is where the implementation work must be done—NOT in debt.py.**

---

## MODULES NEEDING MODIFICATION

### 1. CASHFLOW.PY (PRIMARY FOCUS)

**Current Status:** Partially correct

**What it does RIGHT:**
- Calculates gross kWh production (with capacity factor, degradation)
- Converts LKR revenue from PPA tariff
- Handles plant degradation over time
- Applies grid loss percentage
- Reports annual revenue in LKR

**What MUST BE ADDED:**
- ✗ Success fee calculation & deduction (from YAML)
- ✗ Environmental surcharge calculation & deduction (from YAML)
- ✗ Social services levy calculation & deduction (from YAML)
- ✗ OPEX deduction (USD portion converted to LKR using annual FX)
- ✗ Tax calculation & deduction
- ✗ Risk adjustment haircut application (from YAML)
- ✗ CFADS calculation (final output for debt module)
- ✗ FX application to USD OPEX conversion (using annual FX rates)

**Required Enhancements:**
```python
def build_annual_cfads(p: Dict[str, Any]) -> List[float]:
    """
    Calculate CFADS for each year with all YAML-configured deductions.
    
    Arguments:
        p: Configuration dict from full_model_variables_updated.yaml
    
    Returns:
        List of annual CFADS values in LKR
    """
    # Get YAML parameters
    capacity_factor = p['project']['capacity_factor']
    degradation = p['project']['degradation']
    tariff_lkr = p['tariff']['lkr_per_kwh']
    
    grid_loss_pct = p['regulatory']['grid_loss_pct']
    success_fee_pct = p['regulatory']['success_fee_pct']
    env_surcharge_pct = p['regulatory']['env_surcharge_pct']
    social_levy_pct = p['regulatory']['social_services_levy_pct']
    
    opex_usd_per_year = p['opex']['usd_per_year']
    tax_rate = p['tax']['corporate_tax_rate']
    risk_haircut = p['risk_adjustment']['cfads_haircut_pct']
    
    fx_path = get_fx_forecast(p)  # Array of annual FX rates
    
    cfads_list = []
    
    for year in range(project_life):
        # Production (kWh)
        gross_kwh = capacity_mw * 1000 * 8760 * capacity_factor * (1 - degradation) ** year
        net_kwh = gross_kwh * (1 - grid_loss_pct)
        
        # Revenue (LKR)
        revenue_lkr = net_kwh * tariff_lkr
        
        # Deductions
        success_fee = revenue_lkr * success_fee_pct
        env_surcharge = revenue_lkr * env_surcharge_pct
        social_levy = revenue_lkr * social_levy_pct
        
        opex_lkr = opex_usd_per_year * fx_path[year]  # Convert USD to LKR
        
        # Pre-tax CFADS (before tax)
        cfads_pretax = revenue_lkr - success_fee - env_surcharge - social_levy - opex_lkr
        
        # Apply risk haircut
        cfads = cfads_pretax * (1 - risk_haircut)
        
        cfads_list.append(cfads)
    
    return cfads_list
```

### 2. METRICS.PY (SECONDARY FOCUS)

**Current Status:** Unknown (not yet audited)

**Expected Responsibility:**
- Calculate DSCR from CFADS and debt service
- Reference debt.py for actual debt service amounts
- Apply DSCR covenants and validation
- Report year-by-year DSCR

**Required Verification:**
- Does it receive CFADS (not gross revenue)?
- Does it correctly obtain LKR + USD debt service from debt.py output for each year?
- Does it apply FX to USD debt service conversion?
- Does it report DSCR per-year correctly?
- Does it check against YAML covenant thresholds?

**To Audit Next Session**

### 3. FX_FORECAST_DSCR_INTEGRATION.PY (NEW MODULE - File 63)

**Current Status:** Framework designed, ready for implementation

**Purpose:**
- Extract FX statistics from historical data (302 months, 2005-2025)
- Generate 25-year FX forecast (data-driven, not 3% hardcoded)
- Model USD debt paydown schedule based on cash flow
- Calculate year-by-year DSCR impact as USD debt declines

**Integration Point:**
- Links FX forecast to debt module
- Shows USD debt declining with paydown strategy
- Demonstrates DSCR improves as FX exposure reduces

**To Implement After cashflow.py CFADS is complete**

---

## IMPLEMENTATION SEQUENCE

### IMMEDIATE (This Session)
1. ✓ debt.py: APPROVED - Leave as-is
2. Identify and document all missing CFADS deductions in cashflow.py

### CRITICAL (Next Session)
3. Modify cashflow.py to calculate CFADS correctly
4. Add all statutory levy calculations
5. Add OPEX conversion logic (USD to LKR)
6. Add tax calculation
7. Add risk haircut application
8. Test CFADS output against YAML parameters

### FOLLOWING SESSION
9. Audit metrics.py DSCR calculation
10. Verify CFADS + debt service integration
11. Fix metrics.py if needed

### IMPLEMENTATION PHASE
12. Implement FX forecast module (File 63)
13. Link to historical FX data (7 YAML files, 302 records)
14. Generate 25-year FX forecast
15. Calculate USD debt paydown schedule
16. Calculate 25-year DSCR projection
17. Validate full pipeline end-to-end

---

## PROJECT STATUS SUMMARY

| Module | Status | Action |
|--------|--------|--------|
| **debt.py** | ✓ CORRECT | **LEAVE UNCHANGED** |
| **cashflow.py** | ⚠ Incomplete | **AUDIT & MODIFY** |
| **metrics.py** | ? Unknown | **AUDIT NEXT** |
| **fx_forecast_integration** | ◐ Ready | **IMPLEMENT NEXT** |

---

## CONCLUSION

The debt module architecture is **production-grade and correct**. 

All implementation work focuses on:
1. **Upstream (cashflow.py):** Calculate correct CFADS with all YAML-configured deductions
2. **Integration (metrics.py):** Use CFADS + debt schedules for proper DSCR calculation
3. **Enhancement (FX integration):** Link FX forecast to debt paydown and DSCR trajectory

**No modifications to debt.py required.**

The pipeline will be: `YAML Config → cashflow.py (CFADS) → debt.py (amortization) → metrics.py (DSCR) → FX integration (paydown optimization)`
