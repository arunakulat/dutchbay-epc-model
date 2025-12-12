# Sprint 10 Master To-Do: Multi-Tech Foundation
## From Backlog to Code - Phase 1 Implementation Plan

**Date:** December 9, 2025
**Goal:** Implement Phase 1 of Sprint 10 (Epics 1, 2, 3, 4, 5) - Contracts, Engines, Aggregation, and Extended CasperResult.

---

## 1. PRE-FLIGHT CHECKLIST (Do this first)

1. **Clean Slate:** Ensure `main` is up to date and tests are green.
   ```bash
   git checkout main
   git pull origin main
   pytest -q
   ```
2. **Feature Branch:** Create `sprint-10/multi-tech-foundation` (or similar).
   ```bash
   git checkout -b sprint-10/multi-tech-foundation
   ```
3. **Dependencies:** Install required libraries (for dev/testing).
   ```bash
   pip install windpowerlib pvlib
   pip freeze > requirements.txt  # Commit updated requirements
   ```

---

## 2. STEP-BY-STEP IMPLEMENTATION (File by File)

### Step 1: Define Contracts (Epic 1)
**File:** `analytics/contracts_v14.py` (Modify) or `analytics/generation_contracts_v14.py` (New - safer)

*   [ ] **Create `GenerationProfile` dataclass:**
    *   Fields: `technology` (str), `annual_aep_kwh` (float), `hourly_generation_kwh` (list[float]), `availability_pct` (float), `losses_breakdown` (dict).
*   [ ] **Create `MultiTechGenerationResult` dataclass:**
    *   Fields: `wind` (Optional[GenerationProfile]), `solar` (Optional[GenerationProfile]), `portfolio_aep_kwh` (float), `combined_hourly_kwh` (list[float]).
*   [ ] **Update `CasperResult` dataclass (in `contracts_v14.py`):**
    *   Add fields: `generation` (Optional[MultiTechGenerationResult]), `technology_breakdown` (Optional[list]).

**Test:** Create `tests/test_generation_contracts_v14.py` to instantiate these dataclasses with dummy data.

---

### Step 2: Update Config Schema (Epic 1)
**File:** `config/constants.py` (or where your schema constants live)

*   [ ] **Define Defaults:** Add `WIND_DEFAULTS`, `SOLAR_DEFAULTS` dictionaries.
*   [ ] **Define Ranges:** Add `WIND_SENSITIVITY_RANGES`, `SOLAR_SENSITIVITY_RANGES`.

**Test:** Verify via `schema_guard` tests (if applicable) or a simple config loading test.

---

### Step 3: Wind Engine Adapter (Epic 2)
**File:** `analytics/wind_production_v14.py` (New)

*   [ ] **Import:** `windpowerlib` classes.
*   [ ] **Implement `estimate_wind_aep`:**
    *   Inputs: config dict, wind resource data (speed, height).
    *   Logic: Instantiate turbine, run `power_curve`, apply wake loss (simple factor for now).
    *   Return: `GenerationProfile`.
*   [ ] **Mock Resource Data:** Create a helper to generate synthetic wind data for testing (sine wave + noise).

**Test:** Create `tests/test_wind_production_v14.py` using synthetic data.

---

### Step 4: Solar Engine Adapter (Epic 3)
**File:** `analytics/solar_production_v14.py` (New)

*   [ ] **Import:** `pvlib` classes.
*   [ ] **Implement `estimate_solar_aep`:**
    *   Inputs: config dict, solar resource data (GHI, temp, location).
    *   Logic: `pvlib` model chain (irradiance -> DC -> AC).
    *   Return: `GenerationProfile`.

**Test:** Create `tests/test_solar_production_v14.py` using synthetic solar data.

---

### Step 5: Portfolio Aggregation (Epic 4)
**File:** `analytics/portfolio_aggregation_v14.py` (New)

*   [ ] **Implement `aggregate_multi_tech_generation`:**
    *   Inputs: `wind_profile`, `solar_profile`, aggregation config.
    *   Logic: Element-wise sum of hourly profiles (Phase 1: independent). Apply portfolio curtailment if config present.
    *   Return: `MultiTechGenerationResult`.

**Test:** `tests/test_portfolio_aggregation_v14.py`.

---

### Step 6: Multi-Tech Cashflow Integration (Epic 4)
**File:** `finance/multi_tech_cashflow_v14.py` (New wrapper) or extend `cashflow_v14.py`

*   [ ] **Implement `build_multi_tech_annual_cfads`:**
    *   Inputs: config, `MultiTechGenerationResult`.
    *   Logic:
        1. Calculate annual combined generation.
        2. Apply tariff (revenue).
        3. Subtract OPEX (sum of wind + solar + shared OPEX).
        4. Apply taxes/depreciation (tech-specific rules if needed, or blended).
        5. Return annual rows (CFADS).

**Test:** `tests/test_multi_tech_cashflow_v14.py`.

---

### Step 7: Update Casper Orchestrator (Epic 5)
**File:** `analytics/casper_v14.py`

*   [ ] **Update `run_casper_analysis`:**
    *   Add logic to check config for `generation.technologies`.
    *   If enabled:
        1. Fetch/Mock resource data.
        2. Run `estimate_wind_aep` and/or `estimate_solar_aep`.
        3. Run `aggregate_multi_tech_generation`.
        4. Run `build_multi_tech_annual_cfads`.
        5. Populate `CasperResult` with new generation data.

**Test:** `tests/test_casper_v14_smoke.py` (update to check for generation fields).

---

## 3. DEFINITION OF DONE (Phase 1)

1.  **Code:** All new modules created (`analytics/wind_production_v14.py`, etc.).
2.  **Contracts:** `CasperResult` updated and importable.
3.  **Tests:** All new unit tests pass (`pytest tests/`).
4.  **Smoke Test:** A script running `run_casper_analysis` with a hybrid config produces a JSON result containing `generation.wind.annual_aep_kwh`.

---

## 4. ASSIGNMENT

*   **You/Dev Lead:** Step 1 (Contracts) & Step 7 (Orchestrator).
*   **Wind Dev:** Step 3 (Wind Engine).
*   **Solar Dev:** Step 4 (Solar Engine).
*   **Finance Analyst:** Step 5 & 6 (Aggregation & Cashflow).

**Ready to start? Pick Step 1.**
