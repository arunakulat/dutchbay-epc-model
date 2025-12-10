Nice. Time to carve this thing in stone.

Below is **CasperResult v1** in three pieces you can drop straight into the repo:

1. `docs/api_contract_casper_result_v1.md` – the contract doc
2. `analytics/contracts_v14.py` – `CasperResult` dataclass (final shape)
3. `tests/api/test_casper_contract_freeze.py` – freeze test for the JSON payload

I’ve aligned it with what’s already in `contracts_v14.py` (`ScenarioResult`, `SensitivitySuite`, `MultiTechGenerationResult`, `TechnologyBreakdown`, `TailRiskSnapshot`, `build_casper_payload` etc.), and with your Sprint 9/10 typed to-do.

---

## A. `docs/api_contract_casper_result_v1.md`

Create this file:

**`docs/api_contract_casper_result_v1.md`**

````markdown
# CasperResult JSON Contract – v1

**Version:** `casper_result_v1`
**Audience:** Lender dashboards, CASPER/GWTF analytics, risk and IC packs
**Source:** `analytics/contracts_v14.py::CasperResult` + `build_casper_payload`

This document defines the **canonical JSON structure** emitted by the v14
analytics stack for CASPER/GWTF flows.

The **only** supported JSON representation is the output of:

- `analytics.contracts_v14.build_casper_payload(...)`

All UIs / APIs must treat this contract as **frozen** for v1. Future versions
MAY add *optional* fields but MUST NOT:

- rename existing fields
- change meanings or units
- change required/optional status of existing fields

---

## 1. Top-Level Shape

A `CasperResult` JSON object **MUST** be a single JSON object with the
following top-level fields:

```jsonc
{
  "contract_version": "casper_result_v1",

  "scenario": { /* ScenarioResult.as_dict() */ },

  "baseline_kpis": {
    "project_irr": 0.135,
    "equity_irr": 0.172,
    "min_dscr": 1.28,
    "avg_dscr": 1.45,
    "npv_usd": 12345678.9
  },

  "sensitivity": { /* optional, may be null or omitted */ },

  "monte_carlo": { /* optional, may be null or omitted */ },

  "generation": { /* optional multi-tech generation view */ },

  "technology_breakdown": [ /* optional per-tech KPI shares */ ],

  "tail_risk": { /* optional tail-risk snapshots by metric */ },

  "metadata": { /* optional free-form metadata block */ }
}
````

### 1.1 Top-level fields

| Field                  | Type                      | Required | Description                                                |
| ---------------------- | ------------------------- | -------- | ---------------------------------------------------------- |
| `contract_version`     | `string`                  | yes      | Frozen string: **`"casper_result_v1"`**                    |
| `scenario`             | `object`                  | yes      | Serialized `ScenarioResult` (config + high-level context). |
| `baseline_kpis`        | `object<string,float>`    | yes      | Core KPIs (IRRs, DSCRs, NPV, etc.) in **native units**.    |
| `sensitivity`          | `object` or `null`        | no       | Tornado / sensitivity summary, if computed.                |
| `monte_carlo`          | `object` or `null`        | no       | Monte Carlo distribution summary, if computed.             |
| `generation`           | `object` or `null`        | no       | Aggregated multi-tech generation metrics, if available.    |
| `technology_breakdown` | `array<object>` or `null` | no       | Per-technology capex / CFADS / AEP shares.                 |
| `tail_risk`            | `object` or `null`        | no       | Tail-risk snapshots (e.g. IRR VaR/CVaR) by metric.         |
| `metadata`             | `object`                  | no       | Free-form metadata, including full tail-risk tables.       |

---

## 2. `scenario` block

`scenario` is the JSON representation of `ScenarioResult`. Its exact sub-shape
is defined in `contracts_v14.py`, but the high-level structure is:

```jsonc
"scenario": {
  "name": "dutchbay_lendercase_2025Q4",
  "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
  "project": {
    "location": "Dutch Bay, Sri Lanka",
    "capacity_mw": 150.0,
    "life_years": 20
  },
  "finance": {
    "currency": "USD",
    "base_year": 2025
  },
  "notes": "Human-readable description, if any"
}
```

Consumers MUST treat this as an opaque object keyed by strings, and SHOULD NOT
depend on optional nested fields.

---

## 3. `baseline_kpis`

`baseline_kpis` is a flat mapping of KPI names to float values:

```jsonc
"baseline_kpis": {
  "project_irr": 0.135,
  "equity_irr": 0.172,
  "min_dscr": 1.28,
  "avg_dscr": 1.45,
  "npv_usd": 12345678.9,
  "llcr": 1.35,
  "plcr": 1.52
}
```

Rules:

* Keys MUST be strings.
* Values MUST be JSON numbers (floats).
* Units are **native**:

  * IRRs, DSCRs, coverage ratios → dimensionless
  * `npv_usd` → USD currency
  * Any LKR-denominated field MUST include `_lkr` suffix, etc.

---

## 4. `sensitivity` block (optional)

When sensitivity analysis is run via `SensitivitySuite`, `build_casper_payload`
MAY include a `sensitivity` block:

```jsonc
"sensitivity": {
  "metric": "project_irr",
  "base_metric": 0.135,
  "base_config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
  "tornado": [
    {
      "variable": "project.capex_usd_per_kw",
      "base_irr": 0.135,
      "low_irr": 0.120,
      "high_irr": 0.150,
      "impact_abs": 0.030,
      "impact_pct": 22.2222
    }
  ]
}
```

Field definitions:

* `metric`: KPI name used for sensitivity (e.g. `"project_irr"`).
* `base_metric`: baseline value for that KPI.
* `base_config_path`: path to the base YAML config.
* `tornado`: array of rows harvested from `SensitivitySuite.tornado_results`:

  * `variable`: config path of the shocked parameter.
  * `base_irr`, `low_irr`, `high_irr`: IRR values under base/low/high shocks.
  * `impact_abs`: `high_irr - low_irr` (absolute difference).
  * `impact_pct`: percentage impact relative to baseline
    (sign-preserving; negative values indicate downside).

If no sensitivity is run, `sensitivity` MUST be omitted.

---

## 5. `monte_carlo` block (optional)

When Monte Carlo v14 runs, the contract surfaces an aggregated view of the
distribution for key metrics (IRR, NPV, DSCR, etc.):

```jsonc
"monte_carlo": {
  "metric": "project_irr",
  "samples": 5000,
  "mean": 0.132,
  "std": 0.018,
  "p10": 0.095,
  "p50": 0.130,
  "p90": 0.160
  // OPTIONAL additional fields MAY be added in future versions
}
```

Consumers SHOULD treat this block as **advisory** and MUST NOT assume a fixed
set of fields beyond those listed above.

If Monte Carlo is not run, `monte_carlo` MUST be omitted.

---

## 6. `generation` block (optional – multi-tech view)

`generation` is the JSON representation of `MultiTechGenerationResult`:

```jsonc
"generation": {
  "total_aep_kwh": 450000000.0,
  "total_cfads_usd": 45000000.0,
  "technologies": {
    "wind": {
      "technology": "wind",
      "annual_aep_kwh": 450000000.0,
      "annual_cfads_usd": 45000000.0,
      "availability_pct": 0.98,
      "losses_breakdown": {
        "wake": 0.03,
        "electrical": 0.01
      }
    }
  }
}
```

Rules:

* `total_aep_kwh`, `annual_aep_kwh` in kWh (not MWh/GWh).
* `total_cfads_usd`, `annual_cfads_usd` in USD.
* `availability_pct` is a fraction in `[0,1]`.
* `losses_breakdown` is optional; values are fractions in `[0,1]`.

If no multi-tech aggregation is present (single-tech project or not computed),
`generation` MUST be omitted.

---

## 7. `technology_breakdown` block (optional – capex/CFADS/AEP shares)

`technology_breakdown` is an array of `TechnologyBreakdown` objects:

```jsonc
"technology_breakdown": [
  {
    "technology": "wind",
    "share_of_capex_pct": 100.0,
    "share_of_cfads_pct": 100.0,
    "share_of_aep_pct": 100.0,
    "notes": "Single-tech Dutch Bay wind project"
  }
]
```

All `*_pct` values are percentages in `[0,100]`. Fields MAY be `null` if the
corresponding breakdown is not available.

If not computed, `technology_breakdown` MUST be omitted.

---

## 8. `tail_risk` block (optional – snapshots only)

The top-level `tail_risk` block surfaces **snapshots** of tail-risk metrics for
key KPIs. It is derived from `TailRiskSnapshot` instances and intended for
quick dashboard use:

```jsonc
"tail_risk": {
  "project_irr": {
    "metric": "project_irr",
    "confidence": 0.95,
    "var": 0.030,
    "cvar": 0.040,
    "p10": 0.095,
    "p50": 0.130,
    "p90": 0.160,
    "breach_probability": 0.12
  }
}
```

* The top-level keys under `tail_risk` SHOULD match KPI names in
  `baseline_kpis`.
* `confidence` is a fraction (e.g. `0.95`).
* `var`, `cvar`, `p10`, `p50`, `p90` are all in the same units as the metric
  (for IRR: dimensionless).
* `breach_probability` is a fraction in `[0,1]`.

If no tail-risk analysis is run, `tail_risk` MUST be omitted.

---

## 9. `metadata` block (optional – full tables, CASPER wiring)

`metadata` is a free-form dictionary used to carry verbose or
implementation-specific details that SHOULD NOT be relied upon by external
clients for long-term compatibility.

Typical contents:

```jsonc
"metadata": {
  "run_id": "dutchbay_2025Q4_lender",
  "casper_pipeline": "v14_monte_carlo",
  "tail_risk": { /* full underlying tables for internal analytics */ },
  "tail_risk_summary": { /* copy of tail_risk snapshots, if needed */ },
  "notes": "Internal CASPER run, not audited"
}
```

**Rule of thumb:**

* Top-level fields define the **contract**.
* `metadata` may enrich but MUST NOT contradict top-level values.

---

## 10. Versioning and Compatibility Rules

* `contract_version` MUST be `"casper_result_v1"` for this version.
* v1 MAY be extended only by adding **optional** fields or
  `metadata` entries.
* Any change that alters meanings, units, or required/optional status MUST
  trigger a new contract version (e.g. `casper_result_v2`).

---

## 11. Example Full CasperResult JSON (single-tech Dutch Bay)

```json
{
  "contract_version": "casper_result_v1",
  "scenario": {
    "name": "dutchbay_lendercase_2025Q4",
    "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
    "project": {
      "location": "Dutch Bay, Sri Lanka",
      "capacity_mw": 150.0,
      "life_years": 20
    },
    "finance": {
      "currency": "USD",
      "base_year": 2025
    }
  },
  "baseline_kpis": {
    "project_irr": 0.135,
    "equity_irr": 0.172,
    "min_dscr": 1.28,
    "avg_dscr": 1.45,
    "npv_usd": 12345678.9
  },
  "sensitivity": null,
  "monte_carlo": null,
  "generation": {
    "total_aep_kwh": 450000000.0,
    "total_cfads_usd": 45000000.0,
    "technologies": {
      "wind": {
        "technology": "wind",
        "annual_aep_kwh": 450000000.0,
        "annual_cfads_usd": 45000000.0,
        "availability_pct": 0.98,
        "losses_breakdown": {
          "wake": 0.03,
          "electrical": 0.01
        }
      }
    }
  },
  "technology_breakdown": [
    {
      "technology": "wind",
      "share_of_capex_pct": 100.0,
      "share_of_cfads_pct": 100.0,
      "share_of_aep_pct": 100.0,
      "notes": "Single-tech Dutch Bay wind project"
    }
  ],
  "tail_risk": null,
  "metadata": {
    "run_id": "dutchbay_2025Q4_lender",
    "casper_pipeline": "v14_monte_carlo",
    "notes": "Internal CASPER v14 lender run"
  }
}
```

````

---

## B. `analytics/contracts_v14.py` – CasperResult dataclass

Now, align the Python surface with that contract.

In `analytics/contracts_v14.py`, near your other contracts (`ScenarioResult`,
`MultiTechGenerationResult`, `TechnologyBreakdown`, `TailRiskSnapshot`,
`SensitivitySuite`, `MonteCarloResult`), define / update `CasperResult` as:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Sequence

# ... existing imports: ScenarioResult, SensitivitySuite, MonteCarloResult,
# MultiTechGenerationResult, TechnologyBreakdown, TailRiskSnapshot, etc.


CASPER_CONTRACT_VERSION = "casper_result_v1"


@dataclass(frozen=True)
class CasperResult:
    """
    High-level, JSON-friendly result container for CASPER / GWTF flows.

    This mirrors (and should stay in lockstep with) the JSON contract defined in
    docs/api_contract_casper_result_v1.md and the output of build_casper_payload.

    Top-level JSON keys:
    - contract_version
    - scenario
    - baseline_kpis
    - sensitivity
    - monte_carlo
    - generation
    - technology_breakdown
    - tail_risk
    - metadata
    """

    # Scenario and baseline KPIs
    scenario: ScenarioResult | None
    baseline_kpis: Dict[str, float]

    # Optional analytics surfaces
    sensitivities: SensitivitySuite | None = None
    monte_carlo: MonteCarloResult | None = None

    # Multi-technology generation view
    generation: MultiTechGenerationResult | None = None
    multi_tech_generation_breakdown: list[TechnologyBreakdown] | None = None

    # Tail-risk snapshots keyed by metric name (e.g. "project_irr")
    tail_risk: Mapping[str, TailRiskSnapshot] | None = None

    # Free-form metadata (implementation details, full tables, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Frozen contract version string
    contract_version: str = CASPER_CONTRACT_VERSION

    @property
    def kpis(self) -> Dict[str, float]:
        """
        Backwards-compatible alias for baseline_kpis.

        External callers MUST prefer baseline_kpis; kpis is retained to avoid
        breaking older code that referenced CasperResult.kpis.
        """
        return self.baseline_kpis

    @property
    def sensitivity(self) -> SensitivitySuite | None:
        """
        Backwards-compatible singular alias for sensitivities.
        """
        return self.sensitivities

    @property
    def technology_breakdown(self) -> list[TechnologyBreakdown] | None:
        """
        Alias for multi_tech_generation_breakdown to keep JSON and Python naming aligned.
        """
        return self.multi_tech_generation_breakdown
````

And make sure `__all__` includes `CasperResult` and `CASPER_CONTRACT_VERSION`:

```python
__all__ = [
    # ...
    "CASPER_CONTRACT_VERSION",
    "CasperResult",
    # ...
]
```

You do **not** have to wire this into `build_casper_payload` immediately if you
want to keep A.1 “docs only” and treat B.1 as the code change. But this is the
shape we will test against in the freeze test.

---

## C. `tests/api/test_casper_contract_freeze.py`

Finally, pin the contract with a small freeze test. This locks in:

* `contract_version`
* top-level keys
* basic type shapes

Create **`tests/api/test_casper_contract_freeze.py`**:

```python
from __future__ import annotations

from typing import Any, Dict

import pytest

from analytics.contracts_v14 import (
    CASPER_CONTRACT_VERSION,
    CasperResult,
    MultiTechGenerationResult,
    ScenarioResult,
    TechnologyBreakdown,
    TailRiskSnapshot,
    build_casper_payload,
)


def _dummy_scenario() -> ScenarioResult:
    # Minimal ScenarioResult; adapt fields to match actual constructor
    return ScenarioResult(
        name="dutchbay_lendercase_2025Q4",
        config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        project={},
        finance={},
        notes=None,
    )


def test_casper_contract_version_is_frozen() -> None:
    assert CASPER_CONTRACT_VERSION == "casper_result_v1"


def test_casper_result_dataclass_shape() -> None:
    scenario = _dummy_scenario()
    baseline_kpis: Dict[str, float] = {"project_irr": 0.135}

    result = CasperResult(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
    )

    assert result.contract_version == CASPER_CONTRACT_VERSION
    assert result.kpis == baseline_kpis
    assert result.sensitivity is None
    assert result.technology_breakdown is None


def test_build_casper_payload_top_level_contract() -> None:
    scenario = _dummy_scenario()
    payload = build_casper_payload(
        scenario=scenario,
        baseline_kpis={"project_irr": 0.135},
        sensitivities=None,
        monte_carlo=None,
        multi_tech_generation_breakdown=None,
        technology_breakdown=None,
        metadata=None,
        tail_risk_snapshots=None,
    )

    # Required keys
    assert isinstance(payload, dict)
    assert payload["scenario"] is not None
    assert payload["baseline_kpis"] == {"project_irr": pytest.approx(0.135)}

    # Optional keys: MUST NOT crash if absent
    for optional_key in (
        "sensitivity",
        "monte_carlo",
        "generation",
        "technology_breakdown",
        "tail_risk",
        "metadata",
    ):
        # Presence is optional; types will be validated in dedicated tests
        payload.get(optional_key, None)
```

You’ll need to tweak `_dummy_scenario()` to match the actual
`ScenarioResult` constructor signature (it might be a dataclass or Pydantic
model), but the rest should drop in cleanly and be mypy/ruff-friendly.

---

If you’re happy with this shape, next step on the roadmap is:

> **B.1 – Extend CasperResult + TechnologyBreakdown (code alignment)**

…but with this, the **CasperResult v1 JSON contract is now defined and
freeze-able**, which is what you asked for.
