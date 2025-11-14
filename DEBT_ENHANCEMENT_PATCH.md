# Debt.py Enhancement Patch - Outstanding Balance Tracking

## Purpose
Add `debt_outstanding` series to debt.py output for LLCR/PLCR calculations.

## Current State
`apply_debt_layer()` returns:
```python
{
    'dscr_series': [...],
    'dscr_min': float,
    'debt_service_total': [...],
    'balloon_remaining': float,
    ...
}
```

## Required Addition
Add `debt_outstanding: [...]` tracking outstanding principal balance each year.

---

## MODIFICATION INSTRUCTIONS

### Step 1: Find the metric computation section

In `/Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/dutchbay_v13/finance/debt.py`

Locate this section (around line 520-540):

```python
# ========== COMPUTE METRICS ==========
years = max(len(s) for s in schedules.values())
dscr_series = []
debt_service_total = []

for i in range(years):
    total_service = sum((schedules[k][i][2] if i < len(schedules[k]) else 0.0) for k in schedules)
    opcf = cfads[i] if i < len(cfads) else 0.0
    dscr = opcf / total_service if total_service > 0 else float('inf')
    dscr_series.append(dscr)
    debt_service_total.append(total_service)
```

### Step 2: Replace with enhanced version

Replace the above section with:

```python
# ========== COMPUTE METRICS ==========
years = max(len(s) for s in schedules.values())
dscr_series = []
debt_service_total = []
debt_outstanding_series = []  # NEW: Track outstanding balance

# Initialize outstanding balances per tranche
outstanding_balances = {k: tr.principal for k, tr in tranches.items()}

for i in range(years):
    # Total outstanding at start of this year
    total_outstanding = sum(outstanding_balances.values())
    debt_outstanding_series.append(total_outstanding)  # NEW
    
    # Debt service for this year
    total_service = 0.0
    total_principal_paid = 0.0
    
    for k in schedules:
        if i < len(schedules[k]):
            interest, principal, service = schedules[k][i]
            total_service += service
            total_principal_paid += principal
            
            # Update outstanding balance for this tranche
            outstanding_balances[k] = max(0.0, outstanding_balances[k] - principal)
        else:
            total_service += 0.0
    
    # DSCR calculation
    opcf = cfads[i] if i < len(cfads) else 0.0
    dscr = opcf / total_service if total_service > 0 else float('inf')
    
    dscr_series.append(dscr)
    debt_service_total.append(total_service)
```

### Step 3: Add to return dictionary

Locate the return statement (around line 575):

```python
return {
    'dscr_series': dscr_series,
    'dscr_min': dscr_min,
    'debt_service_total': debt_service_total,
    'balloon_remaining': balloon_remaining,
    ...
}
```

Add one line:

```python
return {
    'dscr_series': dscr_series,
    'dscr_min': dscr_min,
    'debt_service_total': debt_service_total,
    'debt_outstanding': debt_outstanding_series,  # NEW LINE
    'balloon_remaining': balloon_remaining,
    ...
}
```

---

## Verification

After making changes, run:

```bash
source .venv311/bin/activate
python -m pytest tests/test_finance_debt.py -v
```

Expected: All tests pass + new `debt_outstanding` key in output

---

## Alternative: Full File Replacement

If manual patching is error-prone, I can generate the complete modified debt.py file.

Let me know if you want the full file instead of manual patching.
