# PySAM Sandbox Module

**Status**: Experimental / Optional
**Installation**: `pip install NREL-PySAM==5.1.0`
**Purpose**: Annual generation profile extraction for v14 cashflow

---

## Design Philosophy

This module is **isolated from core pipeline** to maintain v14 determinism and purity.

### Core Principles

1. **Optional Dependency** - PySAM is NOT in `requirements.txt`
2. **Graceful Fallback** - Module imports successfully even if PySAM absent
3. **Single Responsibility** - Only generates AEP profiles (no financial calc)
4. **Config-Driven** - Resource file paths from YAML, not hardcoded

---

## Installation



**Do NOT add to `requirements.txt`** - this is intentional isolation per senior dev review.

---

## Usage

### 1. Generate Resource File (External Tool)

PySAM requires `.srw` (Solar Resource Weather) wind resource files.

**Generate using**:
- NREL System Advisor Model (SAM)
- External MATLAB scripts
- NASA MERRA-2 data processors

Example output: `inputs/mannar_synthetic.srw`

### 2. Configure YAML


scenarios/example_pysam.yaml
generation:
engine: "pysam" # Options: "legacy" | "pysam"

pysam:
resource_file: "inputs/mannar_synthetic.srw"

project:
capacity_mw: 150.0
degradation: 0.006 # 0.6% per year (decimal)

### 3. Run Offline Validation


REQUIRED before integration
python scripts/validate_pysam_offline.py

Expected output:

✅ VALIDATION PASSED - PySAM approved for integration
Mean Deviation: 2.34%

**If validation fails (>5% deviation)**, DO NOT integrate into pipeline.

### 4. Use in Pipeline (After Validation Passes)


from analytics.scenario_analytics import ScenarioAnalytics

Normal usage - engine selection from config
analytics = ScenarioAnalytics(scenarios_dir="scenarios/")
summary, timeseries, metadata = analytics.run()

text

The `generation.engine` key in config determines mode:
- `engine: legacy` → Uses cashflow_v14 inline formula (default)
- `engine: pysam` → Uses PySAM sandbox runner

---

## Architecture

analytics/pysam_sandbox/
├── init.py # Graceful fallback if PySAM not installed
├── pysam_runner.py # Single-purpose AEP profile generator
└── README.md # This file

scripts/
└── validate_pysam_offline.py # Validation script (run BEFORE integration)

text

**Key isolation boundaries**:
- ❌ PySAM is NEVER imported by `finance/cashflow_v14.py`
- ❌ PySAM is NEVER imported unless `generation.engine=pysam`
- ✅ Legacy mode works identically with or without PySAM installed
- ✅ Schema guard validates `generation.engine` key

---

## Go-with-the-Flow Compliance

| Rule | Requirement | Compliance |
|------|-------------|------------|
| **ARCH-01** | Config-first architecture | ✅ Resource file from YAML |
| **VAL-01** | Schema guard validation | ✅ `generation.engine` validated |
| **TYPE-01** | Fully typed, mypy clean | ✅ All functions annotated |
| **FIN-01** | Numeric robustness | ✅ Explicit errors, no silent fallbacks |
| **FIN-02** | Explicit units | ✅ `capacity_mw`, `degradation_rate` |
| **R17** | Google-style docstrings | ✅ All public APIs documented |

---

## Testing

Run PySAM smoke tests (only if PySAM installed)
pytest tests/analytics/test_pysam_smoke.py -v

Tests are SKIPPED if PySAM not available (expected behavior)
text

---

## Limitations (By Design)

**What this module does NOT do**:
- ❌ Financial modeling (IRR, NPV, LCOE)
- ❌ Tax calculations
- ❌ Wake modeling configuration
- ❌ Monthly/hourly dispatch profiles
- ❌ Non-linear degradation models
- ❌ Turbine library management

**Rationale**: These belong in external tools or separate modules. This sandbox is **AEP extraction only**.

---

## Future Enhancements (If Needed)

1. **Turbine database** (JSON file, not hardcoded Python)
2. **Resource quality checks** (warn if wind speed range suspicious)
3. **Multi-tech support** (solar PV via PySAM.Pvwattsv8)

All enhancements require senior dev approval and validation gate passage.

---

## Support

**Senior Dev Review**: Required for any modifications
**Validation**: `scripts/validate_pysam_offline.py` must pass (<5% deviation)
**Issues**: Report in main repo issue tracker with `pysam` label
