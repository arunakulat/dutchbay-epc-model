# Sprint 9 Completion + Sprint 10 Foundation: Fully Typed To-Do List
## CASPER/GWTF Aligned, Design-Review Structured, Executable

**Date:** December 9, 2025
**Sprints:** 9 (Completion) + 10 (Foundation)
**Status:** Ready for Team Execution
**Alignment Level:** Full (All guru feedback incorporated)

---

## SECTION A: SPRINT 9 COMPLETION (Freeze Multi-Tech Contracts First)

### ✅ A.1: Freeze CasperResult JSON Contract (Design Phase - No Code Yet)

**Owner:** You (Architecture Lead)
**Effort:** 2 hours (documentation only)
**Blocking:** Nothing (design artifact)
**Status:** ☐ TODO

#### Task A.1.1: Document Exact CasperResult JSON Shape
- **File to create:** `docs/api_contract_casper_result_v1.md` (or `.json`)
- **Content:** Exact JSON structure with field names, types, examples
- **Reference:** Use the frozen JSON from previous discussion:
  ```json
  {
    "scenario": { ... },
    "kpis": { "project_irr": 0.135, ... },
    "sensitivity": { ... } or null,
    "monte_carlo": { ... } or null,
    "analytics_summary": { ... } or null,
    "generation": { ... } or null,  // NEW for Sprint 10
    "technology_breakdown": [ ... ] or null,  // NEW for Sprint 10
    "metadata": {
      "casper_version": "v1",
      ...
    }
  }
  ```
- **Acceptance Criteria:**
  - [ ] All top-level keys documented with type and optionality
  - [ ] Every nested object has explicit field list
  - [ ] `casper_version` always present and versioned
  - [ ] Example JSON is valid and parseable
  - [ ] Comment on versioning policy (breaking changes → version bump)
- **Test:** None (design artifact)
- **Review:** Get team sign-off before coding starts

---

### ✅ A.2: Commit Sprint 9 Phase 1 Baseline to Main

**Owner:** Dev Lead
**Effort:** 1 hour
**Blocking:** Everything in Section B and C
**Status:** ☐ TODO

#### Task A.2.1: Merge sprint-9/integration-design to main
```bash
# On main branch
git checkout main
git pull origin main

# Merge feature branch
git merge --no-ff sprint-9/integration-design

# Verify all tests pass
pytest -q

# Push
git push origin main

# Tag baseline
git tag -a sprint9-phase1-baseline -m "Sprint 9 Phase 1 baseline: CASPER contracts frozen"
git push origin sprint9-phase1-baseline
```
- **Acceptance Criteria:**
  - [ ] All 324 tests pass
  - [ ] No linting errors (`mypy`, `ruff`, `black`)
  - [ ] VERSION file is at 0.3.0
  - [ ] CHANGELOG.md updated with v0.3.0 entry
  - [ ] Tag created and pushed
- **Test:** Full CI/CD pipeline runs green
- **Blocking note:** Do NOT proceed to B.1 until this is committed to main

---

## SECTION B: SPRINT 9 PHASE 2 - Core CASPER Additions (2 weeks)

### ✅ B.1: Extend CasperResult in contracts_v14.py

**Owner:** You (Architecture)
**Effort:** 3 hours
**Blocking:** B.2, B.3, C.1
**Status:** ☐ TODO
**Branch:** `sprint-9/casper-result-extension`

#### Task B.1.1: Add TechnologyBreakdown dataclass
**File:** `analytics/contracts_v14.py`

```python
@dataclass(frozen=True)
class TechnologyBreakdown:
    """Per-technology KPI breakdown for lender visibility."""
    technology: str  # "wind", "solar", etc.
    annual_aep_kwh: float
    annual_cfads_usd: float
    dscr_min: Optional[float]
    capex_usd: float
    capex_per_mw: float
    # Future: warranty_years, degradation_pct, etc.
```

- **Acceptance Criteria:**
  - [ ] Dataclass is frozen (immutable)
  - [ ] All fields are typed
  - [ ] Imports work without circular dependencies
  - [ ] `__all__` includes new class
- **Test:** `tests/test_generation_contracts_v14.py::test_technology_breakdown_instantiation`
  ```python
  def test_technology_breakdown_instantiation():
      tb = TechnologyBreakdown(
          technology="wind",
          annual_aep_kwh=450e6,
          annual_cfads_usd=45e6,
          dscr_min=1.28,
          capex_usd=150e6,
          capex_per_mw=1.5e6,
      )
      assert tb.technology == "wind"
      assert tb.annual_aep_kwh == 450e6
  ```

---

#### Task B.1.2: Extend CasperResult with generation fields
**File:** `analytics/contracts_v14.py` (same file)

```python
from typing import Optional

@dataclass(frozen=True)
class CasperResult:
    # Existing fields
    scenario: ScenarioResult
    kpis: dict[str, float]
    sensitivity: Optional[SensitivitySuite] = None
    monte_carlo: Optional[MonteCarloResult] = None
    analytics_summary: Optional[dict[str, Any]] = None

    # NEW Sprint 10 fields (optional, for multi-tech support)
    generation: Optional['MultiTechGenerationResult'] = None  # Forward ref
    technology_breakdown: Optional[list[TechnologyBreakdown]] = None

    # Always present
    metadata: dict[str, Any] = field(default_factory=dict)
```

- **Acceptance Criteria:**
  - [ ] New fields are Optional (backward compatible)
  - [ ] Type hints are correct (use forward ref for Sprint 10 types)
  - [ ] Field defaults allow easy construction
  - [ ] `asdict(casper_result)` produces valid JSON-serializable dict
- **Test:** `tests/test_contracts_casper_v14.py::test_casper_result_with_generation_fields`
  ```python
  def test_casper_result_with_generation_fields():
      result = CasperResult(
          scenario=dummy_scenario(),
          kpis={"project_irr": 0.135},
          generation=None,  # Optional
          technology_breakdown=None,
          metadata={"casper_version": "v1"}
      )
      assert result.generation is None
      assert result.technology_breakdown is None

      # Verify JSON serialization works
      from dataclasses import asdict
      json_dict = asdict(result)
      assert "generation" in json_dict
  ```

---

#### Task B.1.3: Update __all__ and imports
**File:** `analytics/contracts_v14.py` (same)

```python
__all__ = [
    "ScenarioResult",
    "CashflowResult",
    # ... existing ...
    "TechnologyBreakdown",  # NEW
    "CasperResult",  # Already in __all__, confirm present
]
```

- **Acceptance Criteria:**
  - [ ] New classes exported in `__all__`
  - [ ] Imports at top of file are organized (stdlib, third-party, local)
  - [ ] `ruff` and `isort` compliant (auto-format if needed)
- **Test:** `tests/test_contracts_imports_v14.py`
  ```python
  def test_generation_contracts_importable():
      from analytics.contracts_v14 import (
          TechnologyBreakdown,
          CasperResult,
      )
      assert TechnologyBreakdown is not None
      assert CasperResult is not None
  ```

---

### ✅ B.2: Add `run()` Façade to sensitivity_v14.py

**Owner:** Analytics Dev
**Effort:** 1 hour
**Blocking:** B.3
**Status:** ☐ TODO
**Branch:** Same as B.1 or `sprint-9/sensitivity-run-facade`

#### Task B.2.1: Implement run() function
**File:** `analytics/sensitivity_v14.py` (at end, before __all__)

```python
def run(request: SensitivityRequest) -> SensitivitySuite:
    """
    Canonical entry point for tornado sensitivity analysis.

    This is a thin wrapper preserved for API compatibility and
    CASPER-style orchestration. It delegates directly to
    run_tornado_sensitivity(request).

    Args:
        request: SensitivityRequest with base config path and parameters.

    Returns:
        SensitivitySuite with tornado results, base metric, and config path.

    Raises:
        ValueError: If config or parameters are invalid.
        KeyError: If base KPI metric not found.
    """
    return run_tornado_sensitivity(request)
```

- **Acceptance Criteria:**
  - [ ] Function signature matches design review spec
  - [ ] Docstring follows Google style (Args, Returns, Raises)
  - [ ] Function is at module level (not nested)
  - [ ] No side effects (pure function)
- **Test:** `tests/test_sensitivity_v14_run_facade.py`
  ```python
  def test_run_sensitivity_delegation():
      request = SensitivityRequest(
          base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
          parameters=[
              ParameterRangeConfig(
                  variable_name="project.capex_usd_per_kw",
                  base_value=850,
                  low_pct=-20,
                  high_pct=20,
              )
          ],
          metric="project_irr",
      )
      result = run(request)
      assert isinstance(result, SensitivitySuite)
      assert result.metric == "project_irr"
  ```

---

#### Task B.2.2: Add run to __all__
**File:** `analytics/sensitivity_v14.py`

```python
__all__ = [
    "run",  # NEW
    "run_tornado_sensitivity",
    "build_sensitivity_suite",
    # ... rest ...
]
```

- **Acceptance Criteria:**
  - [ ] `run` is first in `__all__` (primary API)
  - [ ] Imports remain organized
- **Test:** `tests/test_sensitivity_v14_imports.py::test_run_exported`
  ```python
  def test_run_exported_in_all():
      from analytics.sensitivity_v14 import run
      assert callable(run)
  ```

---

#### Task B.2.3: Remove type: ignore from sensitivity_api.py
**File:** `analytics/sensitivity_api.py` (if it exists)

```python
# OLD (before)
from analytics.sensitivity_v14 import run_tornado_sensitivity as run_sensitivity  # type: ignore[attr-defined]

# NEW (after)
from analytics.sensitivity_v14 import run as run_sensitivity
```

- **Acceptance Criteria:**
  - [ ] No `# type: ignore` comments left in imports
  - [ ] `mypy analytics/sensitivity_api.py` passes without errors
  - [ ] API functionality unchanged
- **Test:** Run `mypy` and `pytest tests/test_sensitivity_api.py`

---

### ✅ B.3: Implement analytics/casper_v14.py Orchestrator

**Owner:** You + Analytics Dev
**Effort:** 4 hours
**Blocking:** B.4, C.1
**Status:** ☐ TODO
**Branch:** `sprint-9/casper-orchestrator`

#### Task B.3.1: Create module skeleton
**File:** `analytics/casper_v14.py` (New)

```python
"""
CASPER v14 Orchestrator - Full Analysis Pipeline.

Orchestrates the complete v14 analysis stack:
  1. Config validation
  2. Core DCF (run_v14_pipeline)
  3. KPI façade (evaluate_with_overrides)
  4. Sensitivity (optional)
  5. Monte Carlo (optional)
  6. Scenario analytics (optional)
  7. Result assembly into CasperResult

GWTF Compliance:
  - Never imports finance.* directly
  - Uses analytics gateways only (pipeline_v14, evaluation_v14, etc.)
  - All parameters explicit in config
"""

from __future__ import annotations

import logging
from dataclasses import asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Analytics gateways only (GWTF rule)
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.pipeline_v14 import run_v14_pipeline
from analytics.sensitivity_v14 import run as run_sensitivity
from analytics.contracts_v14 import (
    CasperResult,
    SensitivitySuite,
    MonteCarloResult,
    ParameterRangeConfig,
)

logger = logging.getLogger(__name__)


def run_casper_analysis(
    config_path: str | Path,
    *,
    include_sensitivity: bool = True,
    include_monte_carlo: bool = False,
    include_scenario_analytics: bool = False,
    sensitivity_params: Optional[list[ParameterRangeConfig]] = None,
    monte_carlo_config_path: Optional[str | Path] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> CasperResult:
    """
    Execute full CASPER v14 analysis pipeline.

    Orchestrates:
      1. Core DCF → engine dict + ScenarioResult
      2. KPI façade → flattened KPI dict (single source of truth)
      3. Optional: Sensitivity analysis
      4. Optional: Monte Carlo simulation
      5. Optional: Scenario analytics batch

    Args:
        config_path: Path to scenario YAML (or dict-like object).
        include_sensitivity: Run tornado sensitivity (default: True).
        include_monte_carlo: Run MC simulation (default: False).
        include_scenario_analytics: Run batch analytics (default: False).
        sensitivity_params: Custom sensitivity parameters (else use defaults).
        monte_carlo_config_path: Path to MC config YAML.
        overrides: Config overrides dict.

    Returns:
        CasperResult: Unified analysis result with scenario, KPIs, risks, metadata.

    Raises:
        ValueError: If config invalid or core analysis fails.
        FileNotFoundError: If config_path or MC config not found.
    """
    start_time = datetime.now()
    config_path = Path(config_path)

    logger.info(f"Starting CASPER analysis: {config_path}")

    # --- Phase 1: KPI Evaluation (Single Source of Truth) ---
    logger.info(">> Phase 1: KPI evaluation (evaluate_with_overrides)...")
    kpis = evaluate_with_overrides(str(config_path), overrides)

    # --- Phase 2: Engine Evaluation (ScenarioResult) ---
    logger.info(">> Phase 2: Core pipeline (run_v14_pipeline)...")
    pipeline_result = run_v14_pipeline(
        config=str(config_path),
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )

    # Extract ScenarioResult (or reconstruct if pipeline returns dict)
    if isinstance(pipeline_result, dict):
        scenario_result = ScenarioResult(
            scenario_name=pipeline_result.get("scenario_name", "Unknown"),
            project_irr=pipeline_result.get("project_irr", 0.0),
            min_dscr=pipeline_result.get("min_dscr", 0.0),
            # ... map other fields as needed ...
        )
    else:
        scenario_result = pipeline_result

    # --- Phase 3: Sensitivity (Optional) ---
    sensitivity = None
    if include_sensitivity:
        logger.info(">> Phase 3: Sensitivity analysis...")
        try:
            # Load default params if not provided
            if sensitivity_params is None:
                sensitivity_params = _load_default_sensitivity_params()

            from analytics.sensitivity_v14 import SensitivityRequest
            request = SensitivityRequest(
                base_config_path=str(config_path),
                parameters=sensitivity_params,
                metric="project_irr",
            )
            sensitivity = run_sensitivity(request)
        except Exception as e:
            logger.warning(f"Sensitivity analysis failed: {e}")
            # Don't fail the whole pipeline; sensitivity is optional

    # --- Phase 4: Monte Carlo (Optional) ---
    monte_carlo = None
    if include_monte_carlo:
        logger.info(">> Phase 4: Monte Carlo simulation...")
        try:
            # This will be implemented in Sprint 9 Phase 2
            # Placeholder for now
            monte_carlo = None
        except Exception as e:
            logger.warning(f"Monte Carlo failed: {e}")

    # --- Phase 5: Scenario Analytics (Optional) ---
    analytics_summary = None
    if include_scenario_analytics:
        logger.info(">> Phase 5: Scenario analytics...")
        try:
            # This will be implemented in Sprint 9 Phase 2
            analytics_summary = None
        except Exception as e:
            logger.warning(f"Scenario analytics failed: {e}")

    # --- Phase 6: Assemble CasperResult ---
    logger.info(">> Phase 6: Assembling CasperResult...")

    metadata = {
        "config_path": str(config_path),
        "run_mode": "casper_v14",
        "pipeline_version": "v14.0.1",
        "casper_version": "v1",
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
        "include_sensitivity": include_sensitivity,
        "include_monte_carlo": include_monte_carlo,
        "include_scenario_analytics": include_scenario_analytics,
    }

    result = CasperResult(
        scenario=scenario_result,
        kpis=kpis,
        sensitivity=sensitivity,
        monte_carlo=monte_carlo,
        analytics_summary=analytics_summary,
        generation=None,  # Sprint 10
        technology_breakdown=None,  # Sprint 10
        metadata=metadata,
    )

    logger.info(f"CASPER analysis complete in {metadata['duration_seconds']:.2f}s")
    return result


def _load_default_sensitivity_params() -> list[ParameterRangeConfig]:
    """Load default sensitivity parameters from YAML config."""
    # TODO: Load from config/sensitivity_defaults.yaml
    # Placeholder for now
    return []


__all__ = [
    "run_casper_analysis",
]
```

- **Acceptance Criteria:**
  - [ ] Function signature matches design review
  - [ ] No imports from `finance.*` (GWTF rule)
  - [ ] Proper error handling (log warnings, don't crash)
  - [ ] Metadata always populated correctly
  - [ ] Docstring complete with Args, Returns, Raises
  - [ ] Module-level imports are clean and organized
- **Test:** None yet (covered by B.4)

---

#### Task B.3.2: Handle ScenarioResult reconstruction
**File:** `analytics/casper_v14.py` (update Phase 2 section)

- **Refine logic:** Make sure `run_v14_pipeline` returns a type that can be converted to `ScenarioResult`
- **Alternative:** If `pipeline_v14` doesn't return `ScenarioResult`, create a helper function:
  ```python
  def _reconstruct_scenario_result(pipeline_dict: dict[str, Any]) -> ScenarioResult:
      """Convert pipeline dict output to ScenarioResult contract."""
      return ScenarioResult(
          scenario_name=pipeline_dict.get("scenario_name", "Unknown"),
          project_irr=pipeline_dict["kpis"].get("project_irr", 0.0),
          # ... other mappings ...
      )
  ```
- **Acceptance Criteria:**
  - [ ] Logic is explicit and traceable
  - [ ] Type conversion is safe (no silent failures)
  - [ ] Tests confirm ScenarioResult is always valid

---

### ✅ B.4: Create test_casper_v14_smoke.py

**Owner:** QA Engineer
**Effort:** 2 hours
**Blocking:** B.5 (but not critical)
**Status:** ☐ TODO
**File:** `tests/test_casper_v14_smoke.py`

```python
"""Smoke tests for CASPER v14 orchestrator."""

import pytest
from analytics.casper_v14 import run_casper_analysis
from analytics.contracts_v14 import CasperResult


def test_casper_smoke_basic():
    """Run CASPER analysis on a known scenario YAML."""
    result = run_casper_analysis(
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        include_sensitivity=False,
        include_monte_carlo=False,
        include_scenario_analytics=False,
    )

    # Assert top-level structure
    assert isinstance(result, CasperResult)
    assert result.scenario is not None
    assert result.kpis is not None
    assert isinstance(result.kpis, dict)
    assert result.metadata is not None

    # Assert KPI presence
    assert "project_irr" in result.kpis
    assert "min_dscr" in result.kpis

    # Assert metadata
    assert result.metadata["casper_version"] == "v1"
    assert result.metadata["pipeline_version"] == "v14.0.1"


def test_casper_smoke_with_sensitivity():
    """Run CASPER with sensitivity enabled."""
    result = run_casper_analysis(
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        include_sensitivity=True,
        include_monte_carlo=False,
    )

    assert isinstance(result, CasperResult)
    # Sensitivity may be None if it fails (logged but doesn't crash)
    # or SensitivitySuite if successful
    assert result.sensitivity is None or hasattr(result.sensitivity, "metric")


def test_casper_json_serializable():
    """Verify CasperResult can be serialized to JSON."""
    from dataclasses import asdict
    import json

    result = run_casper_analysis(
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        include_sensitivity=False,
    )

    # Convert to dict
    result_dict = asdict(result)

    # Verify JSON serializable (will raise TypeError if not)
    json_str = json.dumps(result_dict, default=str)
    assert isinstance(json_str, str)

    # Verify can be parsed back
    parsed = json.loads(json_str)
    assert parsed["metadata"]["casper_version"] == "v1"


def test_casper_metadata_complete():
    """Verify metadata is complete and well-formed."""
    result = run_casper_analysis(
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
    )

    required_metadata_keys = {
        "config_path",
        "run_mode",
        "pipeline_version",
        "casper_version",
        "timestamp",
        "duration_seconds",
        "include_sensitivity",
    }

    assert all(key in result.metadata for key in required_metadata_keys)
    assert result.metadata["run_mode"] == "casper_v14"
    assert result.metadata["casper_version"] == "v1"


@pytest.mark.parametrize("include_sensitivity,include_mc", [
    (False, False),
    (True, False),
    (False, True),
    (True, True),
])
def test_casper_option_combinations(include_sensitivity, include_mc):
    """Test various combinations of optional features."""
    result = run_casper_analysis(
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        include_sensitivity=include_sensitivity,
        include_monte_carlo=include_mc,
    )

    assert isinstance(result, CasperResult)
    assert result.scenario is not None
    assert result.kpis is not None
```

- **Acceptance Criteria:**
  - [ ] All tests pass
  - [ ] Tests cover happy path and optional features
  - [ ] JSON serialization test passes
  - [ ] Metadata verification test passes
- **Test Execution:** `pytest tests/test_casper_v14_smoke.py -v`

---

### ✅ B.5: Update Documentation

**Owner:** Tech Writer + You
**Effort:** 2 hours
**Blocking:** Nothing (can run in parallel)
**Status:** ☐ TODO

#### Task B.5.1: Create CASPER v1 API Contract Doc
**File:** `docs/api_contract_casper_result_v1.md`

- **Content:** Exact JSON shape, field types, versioning policy
- **Example:** Valid CasperResult JSON with all optional fields populated
- **Versioning:** Document the breaking change policy:
  - Minor: Add new optional fields (no version bump)
  - Major: Remove/rename fields → bump `casper_version` from "v1" to "v2"
- **Review:** Get architecture approval before publishing

#### Task B.5.2: Update architecture_v14.md
**File:** `docs/architecture_v14.md` (if exists) or create new

- **Section:** Add "CASPER Orchestration Layer"
- **Explain:**
  - What CasperResult is (unified analysis result)
  - How it relates to ScenarioResult, KPIs, sensitivity, MC
  - Where tests anchor (contracts are law)
- **Reference:** Link to API contract doc

#### Task B.5.3: Update CHANGELOG.md
**File:** `CHANGELOG.md`

```markdown
## [0.4.0] - 2025-12-XX

### Added
- **CasperResult:** Extended with `generation` and `technology_breakdown` fields (Sprint 10 compatible)
- **CASPER Orchestrator:** `analytics/casper_v14.py::run_casper_analysis()` for full analysis pipeline
- **Sensitivity Façade:** `analytics/sensitivity_v14.run()` for API compatibility
- **API Contract:** Versioned `CasperResult` JSON contract (v1)

### Changed
- CasperResult now the canonical multi-module result object
- Metadata includes `casper_version` for versioning

### Tests
- Added `tests/test_casper_v14_smoke.py` (smoke tests)
- All existing tests remain green (no regressions)
```

---

## SECTION C: SPRINT 10 FOUNDATION - Multi-Tech Contracts (2 weeks)

### ✅ C.1: Define Multi-Tech Generation Contracts

**Owner:** Analytics Dev + You
**Effort:** 3 hours
**Blocking:** C.2, C.3
**Status:** ☐ TODO
**Branch:** `sprint-10/generation-contracts`

#### Task C.1.1: Create generation_contracts_v14.py (or add to contracts_v14.py)
**File:** `analytics/generation_contracts_v14.py` (new, safer) OR extend `contracts_v14.py`

```python
"""Multi-tech generation contracts (Wind + Solar + Future storage)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class GenerationProfile:
    """Single-technology generation output profile."""

    technology: str  # "wind", "solar", "battery", etc.
    annual_aep_kwh: float  # Annual energy production (kWh)
    hourly_generation_kwh: list[float]  # 8760 hourly values (kWh)
    availability_pct: float  # Mechanical availability (0-100)
    losses_breakdown: Dict[str, float]  # {loss_type: pct}, e.g., {"wake": 4.0, "availability": 4.0}

    def __post_init__(self):
        """Validate generation data."""
        if len(self.hourly_generation_kwh) != 8760:
            raise ValueError(f"Expected 8760 hourly values, got {len(self.hourly_generation_kwh)}")
        if not (0 <= self.availability_pct <= 100):
            raise ValueError(f"Availability must be 0-100%, got {self.availability_pct}")


@dataclass(frozen=True)
class MultiTechGenerationResult:
    """Portfolio-level multi-technology generation result."""

    wind: Optional[GenerationProfile] = None
    solar: Optional[GenerationProfile] = None
    # battery: Optional[GenerationProfile] = None  # Future

    portfolio_aep_kwh: float = 0.0  # Combined annual generation
    combined_hourly_kwh: list[float] = field(default_factory=list)  # Combined 8760 profile
    correlation_factor: float = 1.0  # Wind-solar correlation (0.8-1.0, typical -0.3 in monsoon)

    def __post_init__(self):
        """Validate portfolio data."""
        if not self.wind and not self.solar:
            raise ValueError("At least one technology must be enabled")
        if len(self.combined_hourly_kwh) != 8760 and len(self.combined_hourly_kwh) > 0:
            raise ValueError(f"Combined profile must be 8760 values, got {len(self.combined_hourly_kwh)}")


__all__ = [
    "GenerationProfile",
    "MultiTechGenerationResult",
]
```

- **Acceptance Criteria:**
  - [ ] Both dataclasses are frozen (immutable)
  - [ ] `__post_init__` validation works correctly
  - [ ] All fields have clear types
  - [ ] Docstrings explain purpose and units
  - [ ] Forward-refs resolved (no circular imports)
- **Test:** `tests/test_generation_contracts_v14.py`
  ```python
  def test_generation_profile_valid():
      profile = GenerationProfile(
          technology="wind",
          annual_aep_kwh=450e6,
          hourly_generation_kwh=[54000] * 8760,  # Constant 54k kWh/hr
          availability_pct=96.0,
          losses_breakdown={"wake": 4.0},
      )
      assert profile.technology == "wind"

  def test_generation_profile_invalid_hours():
      with pytest.raises(ValueError, match="Expected 8760 hourly values"):
          GenerationProfile(
              technology="wind",
              annual_aep_kwh=450e6,
              hourly_generation_kwh=[54000] * 8759,  # Too few
              availability_pct=96.0,
              losses_breakdown={},
          )

  def test_multi_tech_generation_result_valid():
      wind = GenerationProfile(...)
      solar = GenerationProfile(...)
      result = MultiTechGenerationResult(
          wind=wind,
          solar=solar,
          portfolio_aep_kwh=530e6,
          combined_hourly_kwh=[...],  # 8760 values
      )
      assert result.wind is not None

  def test_multi_tech_generation_at_least_one():
      with pytest.raises(ValueError, match="At least one technology"):
          MultiTechGenerationResult(
              wind=None,
              solar=None,
          )
  ```

---

#### Task C.1.2: Extend CasperResult to use new types
**File:** `analytics/contracts_v14.py` (update task B.1.2 to use proper types)

```python
from analytics.generation_contracts_v14 import (
    GenerationProfile,
    MultiTechGenerationResult,
)

@dataclass(frozen=True)
class CasperResult:
    # ... existing fields ...

    # Multi-tech support (Sprint 10)
    generation: Optional[MultiTechGenerationResult] = None
    technology_breakdown: Optional[list[TechnologyBreakdown]] = None
```

- **Acceptance Criteria:**
  - [ ] Import works without circular dependency
  - [ ] Type hints are correct
  - [ ] CasperResult can still be instantiated with just scenario + kpis (backward compat)

---

### ✅ C.2: Extend Config Schema for Multi-Tech

**Owner:** Config/Ops Dev
**Effort:** 2 hours
**Blocking:** C.3, C.4
**Status:** ☐ TODO
**Branch:** Same as C.1 or separate

#### Task C.2.1: Update constants.py with multi-tech ranges
**File:** `analytics/constants.py` (or `config/constants.py`)

```python
from typing import Dict, Final, Tuple

# Wind resource and technology parameters
WIND_SENSITIVITY_RANGES: Final[Dict[str, Tuple[float, float]]] = {
    "hub_height_m": (80.0, 150.0),
    "wind_shear_exponent": (0.15, 0.35),
    "wake_loss_pct": (2.0, 10.0),
    "availability_pct": (92.0, 98.0),
    "power_curve_scaling": (0.9, 1.1),  # Confidence in power curve
}

# Solar PV parameters
SOLAR_SENSITIVITY_RANGES: Final[Dict[str, Tuple[float, float]]] = {
    "module_efficiency_pct": (20.0, 25.0),
    "soiling_rate_pct": (0.3, 1.0),
    "temperature_coefficient": (-0.5, -0.2),  # %/°C (negative)
    "dc_ac_ratio": (1.0, 1.3),
    "availability_pct": (96.0, 99.0),
}

# Portfolio/hybrid parameters
PORTFOLIO_SENSITIVITY_RANGES: Final[Dict[str, Tuple[float, float]]] = {
    "wind_solar_correlation": (-0.5, 0.1),
    "curtailment_rate_pct": (0.0, 10.0),
}

# Defaults
WIND_DEFAULTS = {
    "hub_height_m": 110,
    "wind_shear_exponent": 0.2,
    "wake_loss_pct": 4.0,
    "availability_pct": 96.0,
}

SOLAR_DEFAULTS = {
    "module_efficiency_pct": 22.5,
    "soiling_rate_pct": 0.5,
    "temperature_coefficient": -0.35,
    "dc_ac_ratio": 1.2,
    "availability_pct": 98.0,
}
```

- **Acceptance Criteria:**
  - [ ] All ranges are `Final` (immutable)
  - [ ] Ranges are physically plausible (checked via unit test)
  - [ ] Defaults fall within ranges
  - [ ] Docstrings explain units
- **Test:** `tests/test_constants_multi_tech.py`
  ```python
  def test_wind_ranges_valid():
      for param, (low, high) in WIND_SENSITIVITY_RANGES.items():
          assert low < high, f"{param}: low >= high"
          assert WIND_DEFAULTS[param] in range(low - 10, high + 10)  # Loose check

  def test_solar_ranges_valid():
      for param, (low, high) in SOLAR_SENSITIVITY_RANGES.items():
          assert low < high

  def test_temperature_coefficient_negative():
      # Temperature coefficient must be negative (efficiency decreases with temp)
      coeff_range = SOLAR_SENSITIVITY_RANGES["temperature_coefficient"]
      assert coeff_range[0] < 0 and coeff_range[1] < 0
  ```

---

#### Task C.2.2: Extend dutchbay_master_config_v14.yaml with generation block
**File:** `config/dutchbay_master_config_v14.yaml` (or test config)

```yaml
generation:
  technologies:
    wind:
      enabled: true
      capacity_mw: 100
      turbine:
        model: "Siemens SG 10.0-193"
        power_curve_source: "manufacturer"
        hub_height_m: 120
        rotor_diameter_m: 193
      resource:
        data_source: "nrel_india_toolkit"  # or "era5"
        wind_shear_exponent: 0.2
        wake_loss_pct: 4.0
        availability_pct: 96.0

    solar:
      enabled: true
      capacity_mw: 50
      module:
        type: "MonoFacial"
        efficiency_pct: 22.5
        temperature_coefficient: -0.35
      inverter:
        efficiency_pct: 98.5
        dc_ac_ratio: 1.2
      layout:
        tilt_degrees: 20
        tracking: "fixed"
        soiling_rate_pct: 0.5
      resource:
        data_source: "pvwatts"  # or "cams"
        availability_pct: 98.0

  shared:
    curtailment_rules:
      max_injection_mw: 140
      seasonal_limits:
        monsoon: 0.9
        dry: 1.0
    correlation:
      wind_solar_rho: -0.3
```

- **Acceptance Criteria:**
  - [ ] YAML is valid and parseable
  - [ ] Can be loaded via `scenario_loader.load_scenario_config()`
  - [ ] `schema_guard` validates it (new schema rules added)
  - [ ] Backward compatible (old configs without `generation` block still work)
- **Test:** `tests/test_config_multi_tech.py`
  ```python
  def test_multi_tech_config_loads():
      config = load_scenario_config("config/dutchbay_master_config_v14.yaml")
      assert "generation" in config
      assert config["generation"]["technologies"]["wind"]["enabled"]
      assert config["generation"]["technologies"]["solar"]["enabled"]

  def test_backward_compat_old_config():
      # Old config without generation block should still load
      config = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")
      # generation block may not exist, but config should load
      assert config is not None
  ```

---

## SECTION D: CRITICAL GWTF GUARDRAILS (Throughout All Work)

### ✅ D.1: No Regressions - Existing Tests Must Pass

**Owner:** QA/DevOps
**Effort:** Continuous
**Status:** ☐ ENFORCED AT EACH PR

Run these before EVERY commit:

```bash
# Unit tests (must all pass)
pytest -xvs tests/test_v14_lender_suite.py
pytest -xvs tests/test_sensitivity_v14_all.py
pytest -xvs tests/test_sensitivity_v14_behavioral_imports.py
pytest -xvs tests/test_scenario_analytics_smoke.py

# Linting (must be clean)
mypy analytics/ finance/ --strict
ruff check analytics/ finance/ tests/
black --check analytics/ finance/ tests/

# Full test suite
pytest tests/ -q --tb=short

# Coverage (must not decrease)
pytest tests/ --cov=analytics --cov=finance --cov-report=term-missing
```

- **Acceptance Criteria:**
  - [ ] 0 failing tests
  - [ ] 0 mypy errors
  - [ ] 0 ruff violations
  - [ ] Coverage ≥ 75%

---

### ✅ D.2: Architecture Lint Test (GWTF Rule: No Finance Imports in Analytics)

**Owner:** You (Architecture)
**Effort:** 1 hour (one-time)
**Status:** ☐ TODO

Create `tests/test_gwtf_architecture.py`:

```python
"""GWTF architecture guardrails - enforce module boundaries."""

import ast
import os
from pathlib import Path


def test_analytics_no_finance_imports():
    """Ensure analytics modules never import finance.* directly."""
    analytics_dir = Path("analytics")
    prohibited_imports = {"finance", "dutchbay.finance"}

    for py_file in analytics_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        with open(py_file) as f:
            tree = ast.parse(f.read())

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        bad_imports = imports & prohibited_imports
        assert not bad_imports, (
            f"{py_file}: Cannot import {bad_imports}. "
            f"Use analytics gateways (pipeline_v14, evaluation_v14) instead."
        )


def test_sensitivity_imports_evaluation_not_pipeline():
    """Sensitivity must use evaluation_v14, not pipeline_v14 directly."""
    sensitivity_file = Path("analytics/sensitivity_v14.py")

    with open(sensitivity_file) as f:
        content = f.read()

    # Check imports
    assert "from analytics.evaluation_v14 import" in content or "import analytics.evaluation_v14" in content, \
        "sensitivity_v14 must import evaluation_v14 for config handling"

    # Should NOT directly import pipeline (except via evaluation)
    # (relaxed check: pipeline imports are OK as long as evaluation is primary)


def test_casper_orchestrator_no_finance():
    """casper_v14 must never import finance.* directly."""
    casper_file = Path("analytics/casper_v14.py")

    with open(casper_file) as f:
        tree = ast.parse(f.read())

    finance_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "finance" in node.module:
                finance_imports.add(node.module)

    assert not finance_imports, f"casper_v14 cannot import: {finance_imports}"
```

- **Acceptance Criteria:**
  - [ ] Test passes
  - [ ] Run before every PR that touches analytics/
  - [ ] Catches violations early

---

### ✅ D.3: Type Compliance (GWTF Rule: All Code is Typed)

**Owner:** Dev Lead
**Effort:** Ongoing
**Status:** ☐ ENFORCED AT EACH COMMIT

Add to pre-commit hook or CI:

```bash
mypy analytics/ finance/ --strict --ignore-missing-imports
# Must pass with 0 errors
```

- **Acceptance Criteria:**
  - [ ] All new functions have type hints (args and return)
  - [ ] All new dataclasses have typed fields
  - [ ] `mypy --strict` passes with no errors

---

## SECTION E: RELEASE & DEPLOYMENT

### ✅ E.1: Merge to Main and Tag

**Owner:** Dev Lead
**Effort:** 1 hour
**Status:** ☐ TODO (after all sections pass)

```bash
# Ensure all feature branches merged
git checkout main
git pull origin main

# Merge feature branches in order
git merge --no-ff sprint-9/casper-result-extension
git merge --no-ff sprint-9/sensitivity-run-facade
git merge --no-ff sprint-9/casper-orchestrator
git merge --no-ff sprint-10/generation-contracts
git merge --no-ff sprint-10/config-multi-tech

# Run full test suite
pytest -q
mypy analytics/ finance/ --strict

# Tag release
git tag -a v0.5.0-casper-multi-tech -m "Sprint 9 Phase 2 + Sprint 10 Foundation: Full CASPER orchestrator + multi-tech contracts"
git push origin main
git push origin v0.5.0-casper-multi-tech

# Update VERSION file
echo "0.5.0" > VERSION
git add VERSION
git commit -m "Bump version to 0.5.0"
git push origin main
```

- **Acceptance Criteria:**
  - [ ] All tests pass
  - [ ] Tag created and pushed
  - [ ] VERSION file updated
  - [ ] CHANGELOG.md updated with v0.5.0 entry

---

## SUMMARY TABLE: Who Does What, When

| Section | Task | Owner | Hours | Blocking | Status |
|---------|------|-------|-------|----------|--------|
| A.1 | Freeze CasperResult JSON | You | 2 | Nothing | ☐ TODO |
| A.2 | Commit Sprint 9 Phase 1 to main | Dev Lead | 1 | B,C | ☐ TODO |
| B.1 | Extend CasperResult + TechnologyBreakdown | You | 3 | B.2,B.3,C.1 | ☐ TODO |
| B.2 | Add `run()` façade to sensitivity | Analytics | 1 | B.3 | ☐ TODO |
| B.3 | Implement casper_v14.py orchestrator | You + Analytics | 4 | B.4,C.1 | ☐ TODO |
| B.4 | Test suite (test_casper_v14_smoke.py) | QA | 2 | Nothing | ☐ TODO |
| B.5 | Documentation updates | Tech Writer | 2 | Nothing | ☐ TODO |
| C.1 | Define generation contracts | Analytics | 3 | C.2,C.3 | ☐ TODO |
| C.2 | Update config schema (constants + YAML) | Config/Ops | 2 | C.3,C.4 | ☐ TODO |
| D.1 | Ensure no regressions | QA | Continuous | All | ☐ TODO |
| D.2 | Architecture lint test | You | 1 | Nothing | ☐ TODO |
| D.3 | Type compliance | Dev Lead | Ongoing | All | ☐ TODO |
| E.1 | Merge & tag v0.5.0 | Dev Lead | 1 | All | ☐ TODO |
| **TOTAL** | | | **~28 hours** | | |

---

## EXECUTION ORDER (Critical Path)

1. **A.1 → A.2** (Design, then commit baseline)
2. **B.1 in parallel with C.2** (Contracts can start independently)
3. **B.2 → B.3 → B.4** (Sequential, short duration)
4. **C.1 → (C.2 in progress)** (Generation contracts, then config)
5. **D.1, D.2, D.3** (Run continuously, don't block)
6. **B.5** (Docs once B.1–B.4 done)
7. **E.1** (Final merge when all sections complete)

**Estimated timeline:** 2 weeks (4-person team, working in parallel where possible)

---

## NEXT IMMEDIATE STEP

**→ You start with A.1: Document the exact CasperResult JSON contract.**

Once that's signed off by the team, everyone starts their assigned work in parallel.
