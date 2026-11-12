# Financial Architecture Decision Record: Year-1 Bridge Debt Service & CFADS Waterfall Alignment

- **Status**: Proposal & Engine Implementation (Config-First, Default Backward-Compatible)
- **Date**: 2026-11-12
- **Issue**: [#1564](https://github.com/arunakulat/dutchbay-epc-model/issues/1564)
- **Predecessor References**: #1452 (Finding N-1), #806, #1395(c), #1508
- **Classification**: R3 Semantic Risk Class (moves equity KPIs in committed scenarios when non-default economic option is selected).

---

## 1. Problem Statement & Audit Diagnosis

### The Structural Asymmetry
In the DutchBay project finance modeling pipeline, a structural mismatch exists between how debt service is scheduled and how equity distributions are calculated:

1. **Debt Timeline (`finance/debt/terms.py::_build_cfads_timeline`)**:
   - For projects with a bridge period, a synthetic half-year debt period is inserted immediately post-construction.
   - The debt engine assigns this bridge period a CFADS of:
     $$\text{CFADS}_{\text{bridge}} = 0.5 \times \text{CFADS}_{\text{year 1}}$$
   - Debt sizing and amortization sculpt the bridge period's debt service ($DS_{\text{bridge}}$) against this synthetic CFADS.

2. **Equity Waterfall (`analytics/pipeline_v14_enhanced.py:267-295`)**:
   - Because annual financial rows are annual ($N$ operating years), the bridge half-year maps to no operating row.
   - To prevent $DS_{\text{bridge}}$ (~$8.5M) from being orphaned from the equity cashflow (Audit Finding 2.1), the engine folds $DS_{\text{bridge}}$ into **Operating Year 1** debt service:
     $$DS_{\text{equity, year 1}} = DS_{\text{year 1}} + DS_{\text{bridge}}$$
   - However, **no matching bridge CFADS** is credited to Year 1 equity cashflow:
     $$\text{CFADS}_{\text{equity, year 1}} = \text{CFADS}_{\text{year 1}}$$

### Impact on Sponsor Shortfall Cures
Following PR #1452, debt-service shortfalls ($\text{CFADS} < DS$) are funded via explicit sponsor equity injections rather than being clamped.
Because Operating Year 1 carries ~1.5 periods of debt service against only 1.0 period of CFADS, Year 1 exhibits an artificial shortfall:
$$\text{Shortfall}_{\text{year 1}} = \max(0, DS_{\text{year 1}} + DS_{\text{bridge}} - \text{CFADS}_{\text{year 1}})$$

In **11 of the 16 committed scenarios** affected by #1452:
- Year 1 is the *only* shortfall year in the entire project life.
- Every Year-1 shortfall is strictly smaller than $DS_{\text{bridge}}$ (ratio 0.01 to 0.62).
- The affected scenarios include the Blue Whale hybrid/wind screening cases, `ceb_solar_bess_nightpeak_10mw`, and eight NSO250 long-term-loan variants.
- In reality, no operating year has baseline CFADS below its own period debt service.

---

## 2. Economic Options for Owner Selection

To resolve this asymmetry, two coherent economic treatments exist:

### Option A: Operating Bridge Credit (`equity_cfads_match`)
- **Premise**: The bridge half-year represents a genuine early-generation operational period preceding full commercial operation.
- **Mechanism**: The equity waterfall credits the matching bridge CFADS ($0.5 \times \text{CFADS}_{\text{year 1}}$) to Operating Year 1:
  $$\text{CFADS}_{\text{equity, year 1}}^{\text{eff}} = \text{CFADS}_{\text{year 1}} + \text{CFADS}_{\text{bridge}}$$
- **Economic Effect**: Eliminates the synthetic Year-1 shortfall. The debt service $DS_{\text{bridge}}$ is funded by actual generation cashflow rather than a sponsor equity cure. Equity IRR increases moderately across the 11 scenarios to reflect actual project economics.

### Option B: Construction Funding Capitalization (`construction_capitalized`)
- **Premise**: The bridge period is a pre-COD testing/commissioning lead-in, not commercial operations.
- **Mechanism**: Debt service during the bridge period is treated as a construction/financing cost (IDC or equity at financial close) and capitalized into project capex. Operating Year 1 carries only its own 1.0 period of debt service:
  $$DS_{\text{equity, year 1}} = DS_{\text{year 1}}$$
- **Economic Effect**: Capex / funding requirement at close increases by $DS_{\text{bridge}}$; operating year 1 distributions are clean; no sponsor cure in Year 1.

---

## 3. Config-First Architecture Implementation

To adhere strictly to `GWTF ARCH-01`, `CESSPIT` (`FRAMEWORK-02`), and preserve baseline scenario reproducibility until formal owner sign-off:

1. **Configuration Key**:
   Added `finance.debt.bridge_period_treatment` in Hydra configuration:
   - `"historical_fold"` (**Default**): Preserves exact existing behavior, zero KPI change on committed baseline scenarios.
   - `"equity_cfads_match"` (Option A): Folds bridge CFADS into year-1 equity distributions, eliminating synthetic shortfalls.
   - `"construction_capitalized"` (Option B): Removes bridge debt service from operating year 1, leaving it to construction funding.

2. **Strict Validation**:
   Refuses any unknown string with a fail-loud `ValueError`.
