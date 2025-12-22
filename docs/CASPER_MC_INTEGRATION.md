# CASPER Monte Carlo Integration Guide

**Sprint 18 - Lender-Grade Risk Analytics**

This guide explains how to integrate Monte Carlo lender analytics into CASPER payload structures.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Payload Structure](#payload-structure)
4. [API Reference](#api-reference)
5. [Examples](#examples)
6. [Testing & Validation](#testing--validation)
7. [Production Checklist](#production-checklist)

---

## Overview

### What is CASPER?

CASPER (Contract-Assured Scenario Pipeline for Energy & Renewables) is the unified payload structure for delivering project finance analytics to stakeholders.

### Monte Carlo Integration Points

The Sprint 18 MC refactoring provides lender-grade risk analytics through:

1. **`build_lender_risk_table()`** - pandas DataFrame with P50/P90/P95 metrics
2. **`build_casper_risk_blocks()`** - Complete CASPER-ready payload
3. **`CovenantSpec`** - Configurable covenant floors and thresholds

### Lender Pack Requirements

Lenders require:
- **Percentile statistics**: P50, P90, P95 for all key metrics
- **Breach probability**: Prob(DSCR < covenant_floor)
- **Worst-case downside**: Worst-year DSCR P95 (5th percentile)
- **Metadata**: Execution parameters (n_trials, seed, correlation)

---

## Quick Start

### 3-Step Integration

```python
from analytics.mc import (
    run_monte_carlo_analysis,
    build_casper_risk_blocks,
    CovenantSpec
)

# Step 1: Run Monte Carlo
result = run_monte_carlo_analysis(
    base_config=cfg,
    n_trials=1000,
    seed=42
)

# Step 2: Generate CASPER blocks
blocks = build_casper_risk_blocks(
    result,
    covenant=CovenantSpec(dscr_floor=1.30)
)

# Step 3: Insert into payload
payload["tables"]["lender_risk_table"] = blocks["lender_risk_table"].to_dict(orient="records")
payload["metrics"]["covenant"] = blocks["covenant"]
```

### Output Structure

```json
{
  "tables": {
    "lender_risk_table": [
      {
        "metric": "DSCR (min)",
        "P50": 1.45,
        "P90": 1.32,
        "P95": 1.28,
        "mean": 1.42,
        "std": 0.08
      },
      {
        "metric": "Prob(DSCR < 1.30)",
        "mean": 0.12
      },
      ...
    ]
  },
  "metrics": {
    "covenant": {
      "dscr_floor": 1.30,
      "prob_breach": 0.12,
      "worst_year_dscr_p95_downside": 1.22,
      "n_trials": 1000
    }
  }
}
```

---

## Payload Structure

### CASPER Payload Schema

```python
payload = {
    "scenario": "dutchbay_lendercase_2025Q4",
    "timestamp": "2025-12-23T04:30:00Z",
    "contract_version": "v1.0",
    
    # === TABLES SECTION ===
    "tables": {
        "lender_risk_table": [...],  # ← MC INTEGRATION POINT
        "cashflow": [...],
        "debt_service": [...],
    },
    
    # === METRICS SECTION ===
    "metrics": {
        "covenant": {...},  # ← MC INTEGRATION POINT
        "baseline_kpis": {...},
        "wacc": {...},
    },
    
    # === METADATA SECTION ===
    "metadata": {
        "mc_execution": {...},  # ← OPTIONAL MC METADATA
        "config_hash": "abc123...",
        "framework_compliance": ["CASPER", "CESSPIT", "GWTF"],
    },
}
```

### Lender Risk Table (tables.lender_risk_table)

**Type**: `List[Dict[str, Any]]`

Each row represents one metric with statistics:

```python
[
    {
        "metric": "DSCR (min)",
        "P50": 1.45,
        "P90": 1.32,
        "P95": 1.28,
        "mean": 1.42,
        "std": 0.08
    },
    {
        "metric": "Prob(DSCR < 1.30)",
        "P50": NaN,  # Not applicable
        "P90": NaN,
        "P95": NaN,
        "mean": 0.12,  # ← Breach probability
        "std": NaN
    },
    {
        "metric": "Worst-year DSCR (P95 downside)",
        "mean": 1.22,  # ← 5th percentile
    },
    {
        "metric": "LLCR",
        "P50": 1.65,
        "P90": 1.48,
        "mean": 1.61,
        "std": 0.11
    },
    ...
]
```

### Covenant Block (metrics.covenant)

**Type**: `Dict[str, float | int]`

```python
{
    "dscr_floor": 1.30,
    "prob_breach": 0.12,  # 12% of trials breach covenant
    "worst_year_dscr_p95_downside": 1.22,  # 5th percentile
    "n_trials": 1000,
}
```

---

## API Reference

### `build_casper_risk_blocks()`

```python
def build_casper_risk_blocks(
    result: MonteCarloResult,
    *,
    covenant: CovenantSpec = CovenantSpec(),
    metric_map: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Build CASPER-ready payload blocks.
    
    Args:
        result: MonteCarloResult with raw trials
        covenant: Covenant specification (floor, thresholds)
        metric_map: Optional mapping for custom metric names
    
    Returns:
        {
            "lender_risk_table": pd.DataFrame,
            "covenant": dict,
        }
    
    Raises:
        KeyError: If required trial data missing
    """
```

### `CovenantSpec`

```python
@dataclass(frozen=True)
class CovenantSpec:
    dscr_floor: float = 1.30
```

**Usage**:

```python
# Default covenant (DSCR ≥ 1.30)
blocks = build_casper_risk_blocks(result)

# Custom covenant floor
blocks = build_casper_risk_blocks(
    result,
    covenant=CovenantSpec(dscr_floor=1.25)
)
```

### Metric Name Mapping

If your KPI names differ from canonical names:

```python
metric_map = {
    "dscr_min": "custom_dscr_field",
    "project_irr": "unlevered_irr",
    "llcr": "loan_life_coverage",
}

blocks = build_casper_risk_blocks(
    result,
    metric_map=metric_map
)
```

---

## Examples

### Example 1: Basic Integration

```python
from analytics.mc import run_monte_carlo_analysis, build_casper_risk_blocks
import yaml

# Load config
with open("scenarios/dutchbay_lendercase_2025Q4.yaml") as f:
    cfg = yaml.safe_load(f)

# Run MC
result = run_monte_carlo_analysis(
    base_config=cfg,
    n_trials=1000,
    seed=42
)

# Build payload blocks
blocks = build_casper_risk_blocks(result)

# Construct payload
payload = {
    "scenario": "dutchbay_lendercase_2025Q4",
    "tables": {
        "lender_risk_table": blocks["lender_risk_table"].to_dict(orient="records")
    },
    "metrics": {
        "covenant": blocks["covenant"]
    },
}

# Export to JSON
import json
with open("casper_payload.json", "w") as f:
    json.dump(payload, f, indent=2, default=str)
```

### Example 2: Multi-Scenario Comparison

```python
scenarios = ["base", "upside", "downside"]
results = {}

for scenario in scenarios:
    cfg = load_scenario_config(scenario)
    result = run_monte_carlo_analysis(base_config=cfg, n_trials=1000)
    blocks = build_casper_risk_blocks(result)
    results[scenario] = blocks

# Compare breach probabilities
for scenario, blocks in results.items():
    prob = blocks["covenant"]["prob_breach"]
    print(f"{scenario}: {prob:.1%} breach probability")
```

### Example 3: Excel Export for Lenders

```python
import pandas as pd

blocks = build_casper_risk_blocks(result)

with pd.ExcelWriter("lender_pack.xlsx", engine="openpyxl") as writer:
    # Sheet 1: Risk Table
    blocks["lender_risk_table"].to_excel(
        writer, sheet_name="Risk Table", index=False
    )
    
    # Sheet 2: Covenant Summary
    covenant_df = pd.DataFrame([blocks["covenant"]])
    covenant_df.to_excel(
        writer, sheet_name="Covenant Summary", index=False
    )
```

---

## Testing & Validation

### Contract Validation

```python
from analytics.contracts_v14 import MonteCarloResult
from pydantic import ValidationError

try:
    result = MonteCarloResult(
        summary={...},
        metadata={...},
        trials={...},
    )
except ValidationError as e:
    print(f"Contract validation failed: {e}")
```

### JSON Serialization Test

```python
import json
import numpy as np

blocks = build_casper_risk_blocks(result)

# Test DataFrame serialization
table = blocks["lender_risk_table"].to_dict(orient="records")
json_str = json.dumps(table, default=str)  # Handle NaN with str conversion
assert json_str is not None

# Test covenant block
json.dumps(blocks["covenant"])  # Should work without default handler
```

### Payload Schema Compliance

```python
def validate_casper_payload(payload: dict) -> None:
    """Validate CASPER payload structure."""
    assert "tables" in payload
    assert "metrics" in payload
    assert "lender_risk_table" in payload["tables"]
    assert "covenant" in payload["metrics"]
    
    # Validate covenant block
    covenant = payload["metrics"]["covenant"]
    assert "dscr_floor" in covenant
    assert "prob_breach" in covenant
    assert 0.0 <= covenant["prob_breach"] <= 1.0
```

---

## Production Checklist

### ✅ Required Fields

- [ ] `MonteCarloResult.trials` populated with raw arrays
- [ ] All trial arrays have same length (validated by Pydantic)
- [ ] DSCR metric present (required for breach probability)
- [ ] CovenantSpec configured with appropriate floor

### ✅ Performance Considerations

- [ ] Use 1000+ trials for production lender packs
- [ ] Consider correlation if parameters are dependent
- [ ] Cache MonteCarloResult if generating multiple exports
- [ ] Use `to_dict(orient="records")` for efficient serialization

### ✅ Error Handling

```python
try:
    blocks = build_casper_risk_blocks(result)
except KeyError as e:
    # Missing trial data
    logger.error(f"Required trial metric missing: {e}")
    raise
except RuntimeError as e:
    # pandas not installed
    logger.error(f"pandas required for exports: {e}")
    raise
```

### ✅ Logging & Audit

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"MC simulation: {result.metadata['n_trials']} trials")
logger.info(f"Breach probability: {blocks['covenant']['prob_breach']:.2%}")
logger.info(f"Payload generated: {len(blocks['lender_risk_table'])} metrics")
```

---

## Framework Compliance

✅ **CASPER**: Contract-explicit payload structure  
✅ **CESSPIT**: Fail-fast validation on missing data  
✅ **GWTF**: Single source of truth for lender analytics  
✅ **CCCDIR**: Comprehensive documentation with examples  

---

## Support

For questions or issues:

1. Check [examples/monte_carlo_lender_pack_example.py](../examples/monte_carlo_lender_pack_example.py)
2. Review [tests/analytics_layer/test_mc_integration.py](../tests/analytics_layer/test_mc_integration.py)
3. Run example: `python examples/monte_carlo_lender_pack_example.py --help`

---

**Last Updated**: Sprint 18 - December 23, 2025  
**Contract Version**: v1.0  
**Status**: Production Ready
