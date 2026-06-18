# Sprint 18 - Dolphin Strategy Implementation Plan

**Generation Date:** 2024-12-24T19:41:00+05:30
**Sprint:** Sprint 18 - DutchBay EPC Model (Enhanced with Local Dev Feedback)
**Status:** READY FOR IMPLEMENTATION

## Executive Summary

This document outlines the comprehensive implementation strategy for Sprint 18, incorporating extensive feedback from local developers. The Dolphin Strategy provides a phased, incremental approach to refactoring the DutchBay EPC Model codebase while maintaining compliance with GWTF, CASPER, CESSPIT, and CCCDIR frameworks.

## User Decisions Confirmed

### Orchestrator TODOs
- **Decision:** Complete cashflow logic BEFORE D04 runs
- **Priority:** CRITICAL (Phase 0)
- **Rationale:** Blocks all subsequent Dolphins

### Scanner Implementation  
- **Decision:** Full scanner exists and is comprehensive (D01)
- **Status:** COMPLETE (691 lines)
- **Features:** File inventory, dependency graph, technical debt, migration readiness

### Frozen Formulas Authority
- **Decision:** User has final authority - no second approval needed
- **Approach:** Run optimization + external research for best values
- **Formulas:** IRR, NPV, DSCR, Capacity Factor

### Execution Pace
- **Decision:** Conservative - let Dolphin strategy decide
- **Rationale:** Avoid rushing, maintain quality

### PR Strategy
- **Decision:** Incremental PRs per phase after local testing
- **Approval:** Each PR requires local dev approval before main merge
- **Compliance:** Follows GWTF R25 (branch-based development)

### Golden Test Approach
- **Decision:** Auto-generate with optimization-derived expected values
- **Methodology:** Research + optimization to establish ground truth

## Local Dev Feedback Integration

### 1. Orchestrator Improvements
- Use Hydra/OmegaConf for config instead of hardcoded Python dicts
- Add monitoring/alerting on orchestration failures
- Capture approver identity in logs (not just yes/no)
- Ensure idempotency - Dolphins should check if work already done
- Add RBAC for approvals (role-based access control)
- Include error logging with structured format
- Add dry-run flags to all Dolphin scripts

### 2. Contract Validation Enhancements
- Backup existing models before overwrite
- Version control for contract evolution (CHANGELOG)
- Full coverage of all contract types and versions
- Migration guide for contract changes

### 3. Pipeline Safety
- Automated smoke test with dummy data before sign-off
- End-to-end regression tests after import changes
- Verify all data flows (wind data, DSCR, NetCDF handling)

### 4. Testing Completeness
- Populate golden test TODOs - no skipped tests
- Dedicated unit tests for: cashflow, DSCR, IRR, Monte Carlo
- Integrate FX/data regression tester (D12) into CI pipeline
- Enforce coverage checks in CI (GWTF R21)

### 5. CLI/Config Consistency
- Standardize all Dolphin CLIs with Click or Hydra
- Schema-based config validation (YAML with JSON Schema)
- Example configs for all tools
- Help text and examples for all CLIs

### 6. Governance Logging
- Log approver identity in manifest
- Formal approval record (who approved, when, which phase)
- Track deliverables per phase to prevent gate stalls
- Audit trail for all config changes

## Enhanced Dolphins

### D00: Orchestrator TODO Completion
**Enhancements:**
- Manual review checklist added
- Cashflow logic completion template provided
- Verification script to confirm no TODOs remain
- Pytest suite for orchestrator logic

### D01: Enhanced GitHub Repo Scanner
**Enhancements:**
- Comprehensive file listing with categorization
- Structure report with dependency graph
- Technical debt metrics (TODOs, code complexity)
- Migration readiness score
- Outputs: migration_status_report.md + dependency_graph.json

**New Features:**
- Detect circular dependencies
- Flag deprecated imports
- Identify orphaned files
- Calculate refactor risk score per module

### D02: Contract Generator with Versioning
**Enhancements:**
- Auto-backup existing contracts before generation
- Generate CHANGELOG.md for contract evolution
- Version tagging (v14.0.0) in generated files
- Pydantic v2 validation with frozen=True
- Generate migration guide for contract changes

### D04: Pipeline Consolidator (Complete)
**Enhancements:**
- NO TODO comments - cashflow logic fully implemented
- Smoke test suite with dummy data
- End-to-end validation before commit
- Performance benchmarking (memory + runtime)

**Validation Enhanced:**
- Cashflow waterfall completeness check
- DSCR calculation verification
- NetCDF data flow validation
- AEP/capacity factor integration test

### D08: Utils Consolidator with Golden Tests
**Enhancements:**
- NPV/IRR frozen formulas with optimization-derived values
- External research citations for formula parameters
- Golden test suite with 0.01% tolerance
- Backward compatibility aliases for old import paths

### D09: Test Suite Generator (Complete)
**Enhancements:**
- NO TODO placeholders - all tests implemented
- Dedicated unit tests for: cashflow, DSCR, IRR, Monte Carlo
- Coverage target: 85% minimum
- CI integration with pytest + coverage report

### D12: FX Data Regression Tester (Integrated)
**Enhancements:**
- Integrated into CI pipeline
- Real checksum calculation (no PLACEHOLDERs)
- Automated alert on checksum drift
- FX optimization with external market data research

## New Components

### Hydra Config System
**Purpose:** Replace hardcoded DOLPHINS_CONFIG with Hydra

**Files:**
- `config/dolphins.yaml` - Phase/Dolphin definitions
- `config/validation_rules.yaml` - Validation gates
- `config/golden_test_params.yaml` - Frozen formula parameters

**Benefits:**
- Dynamic config composition
- Built-in help text and CLI generation
- Version control for config changes
- Schema validation via OmegaConf

### Optimization Engine
**Purpose:** Derive optimal golden test values via research + optimization

**Approach:**
- NPV/IRR: Research industry standards (WACC, discount rates)
- DSCR: Optimize for lender requirements (1.2x minimum)
- Capacity factor: Run sensitivity analysis on wind data
- FX rates: Use IMF/World Bank historical data for depreciation

**Output:** `golden_test_optimized_params.json`

### Approval Logger
**Purpose:** Capture approver identity and formal approval records

**Fields:**
- approver_github_username
- approval_timestamp
- phase_id
- approval_comment (optional)
- approval_sha (git commit after approval)

**Output:** `.dolphin_approvals.jsonl`

### Idempotency Checker
**Purpose:** Ensure Dolphins safe to re-run

**Mechanism:**
- Check for `.dolphin_D{id}_complete` marker files
- Verify backup existence before overwrite
- Compare file checksums to detect prior runs
- Skip if work already completed

## Implementation Priorities

### CRITICAL (Must complete first)
1. **Complete orchestrator cashflow logic** (D00) - blocks all Dolphins
2. **Add idempotency checks** to all Dolphins - prevents corruption
3. **Populate golden test TODOs** - ensures test coverage
4. **Implement Hydra config system** - standardizes CLI/config

### HIGH (Next phase)
5. **Create approval logger** - captures formal approvals
6. **Add smoke test to D04** - validates end-to-end pipeline
7. **Run optimization for frozen formulas** - derives best golden values

### MEDIUM (Continuous improvement)
8. **Integrate D12 into CI** - automates regression detection
9. **Add monitoring/alerting** - detects failures faster
10. **Generate contract CHANGELOG** - tracks evolution

## Phase Execution Plan

### Phase 0: Pre-Work (CURRENT)
**Goal:** Complete orchestrator TODOs and verify baseline

**Tasks:**
- [ ] Complete cashflow logic in orchestrator
- [ ] Run D01 scanner to generate migration report
- [ ] Review technical debt and blocking issues
- [ ] Verify no critical TODOs remain
- [ ] Obtain user approval for Phase 1

**Success Criteria:**
- All orchestrator TODOs resolved
- Migration readiness score > 70/100
- No blocking circular dependencies
- All unit tests passing

### Phase 1: Discovery & Contracts
**Goal:** Generate type-safe contracts and inventory codebase

**Dolphins:**
- D01: Repository Scanner
- D02: Contract Generator
- D10: Contract Validator

**Success Criteria:**
- All contracts generated and validated
- Mypy passes with no errors
- Contract CHANGELOG generated
- Backup of original contracts created

### Phase 2: Dependency Injection & Pipeline
**Goal:** Refactor DI and consolidate pipeline code

**Dolphins:**
- D03: DI Refactor
- D04: Pipeline Consolidator
- D05: Engine Namespace Separator
- D06: Import Updater

**Success Criteria:**
- Pipeline smoke test passes with dummy data
- All imports updated and working
- End-to-end test validates data flows
- Performance benchmarks within acceptable range

### Phase 3: Testing & Documentation
**Goal:** Build test frameworks and documentation

**Dolphins:**
- D07: Documentation Generator
- D08: Utils Consolidator
- D09: Test Suite Generator
- D11: Migration Guide Generator

**Success Criteria:**
- Test coverage > 85%
- All golden tests implemented (no TODOs)
- Documentation up-to-date
- Migration guide reviewed and approved

### Phase 4: Validation & Regression
**Goal:** Run comprehensive validation and regression tests

**Dolphins:**
- D12: FX Data Regression Tester
- Golden test suite execution
- End-to-end pipeline validation

**Success Criteria:**
- All regression tests pass
- FX checksums match expectations
- IRR/NPV/DSCR frozen formulas verified
- Capacity factor calculations validated

## Compliance Framework Alignment

### GWTF (Go With The Flow Rules)
- **R23:** Clean commit history - each Dolphin = atomic commit
- **R25:** Branch-based development - feature branches per phase
- **R21:** Coverage enforcement - pytest with 85% minimum
- **TEST-01:** Strong test coverage - dedicated unit tests

### CASPER (Capital, API, Structure, Parametrize, Engine, Rigor)
- **Capital:** Contract generation with versioning (D02)
- **API:** Schema validation and backward compatibility
- **Structure:** Dependency graph analysis (D01)
- **Parametrize:** Hydra config system
- **Engine:** Pipeline consolidation (D04)
- **Rigor:** Golden tests with optimization (D08/D09)

### CESSPIT (Config, Entity, Schema, Structure, Pipeline, Integration, Testing)
- **Config:** Hydra-based configuration management
- **Entity:** Type-safe dataclass contracts
- **Schema:** Pydantic v2 validation
- **Structure:** Modular refactoring
- **Pipeline:** Consolidated orchestration
- **Integration:** End-to-end testing
- **Testing:** Comprehensive test suite (D09)

### CCCDIR (Contracts, Config, CLI, Dependencies, Integration, Rigor)
- **Contracts:** Frozen formulas with validation
- **Config:** YAML-based with schema validation
- **CLI:** Standardized with Hydra
- **Dependencies:** Dependency injection refactoring (D03)
- **Integration:** Smoke tests and regression
- **Rigor:** Golden tests with 0.01% tolerance

## Next Immediate Actions

1. **Push generated files** to GitHub
   - `scripts/01_github_repo_scanner.py`
   - `docs/SPRINT_18_IMPLEMENTATION_PLAN.md`
   - Orchestrator files

2. **Run Phase 0**:
   - Complete orchestrator cashflow logic TODOs
   - Run D01 scanner to generate migration report
   - Review technical debt and blocking issues

3. **Research for frozen formulas** (parallel work):
   - IRR/NPV: Industry WACC standards, discount rate research
   - DSCR: Lender requirement optimization (1.2x minimum)
   - Capacity factor: Sensitivity analysis on wind data
   - FX rates: IMF/World Bank historical data

4. **Obtain approval** for Phase 1 after Phase 0 completion

---

**Implementation Status:** READY FOR DEPLOYMENT
**Compliance:** GWTF R25 (branch-based), CASPER, CESSPIT, CCCDIR
**Approval Required:** Local dev team before PR to main
