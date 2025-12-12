# Sprint 10: Multi-Technology Wind + Solar Platform Backlog
## **Concrete Epics, Stories, CASPER/GWTF Compliance, & Framework Integration**

**Date:** December 9, 2025
**Status:** Planning & Design Phase
**Version:** 1.0 (Master Backlog)

---

## EXECUTIVE SUMMARY

Sprint 10 extends DutchBay v14 from single-tech (wind-only lender case) to **multi-technology portfolio modeling** (wind + solar + future storage), leveraging:

- **Open-source frameworks:** NREL's PySAM (System Advisor Model), windpowerlib, pvlib, PyWake
- **Public datasets:** NREL PVWATTS, ERA5 downscaled to 3 km, India Wind Toolkit
- **Financial models:** Portfolio CFADS, multi-tech DSCR, curtailment risk, tech-specific warranty/performance risk
- **CASPER/GWTF alignment:** Multi-tech configs, independent per-tech engines, unified financial aggregation, explicit contracts

**Outcome:** By end of Sprint 10, lenders and equity sponsors can model hybrid wind+solar plants in South Asia with transparent, auditable resource, performance, and financial views.

---

## PART 0: STRATEGIC CONTEXT (For All Guru Hats)

### From a CFA / DFI Lender perspective:
- Hybrid projects reduce technology risk (wind + solar have different generation profiles, weather correlations) but introduce complexity: separate power curves, availability factors, curtailment per tech.
- Lenders want: **separate risk layers per tech** (so a solar panel failure doesn't hide wind performance), **tech-specific DSCRs**, and **conservative, auditable AEP estimates** backed by published methodologies.
- Key risk: **overselling AEP** (common in developing markets); Sprint 10 must use peer-reviewed data sources and published models to minimize this.

### From a Python / Fintech perspective:
- Multi-tech means **pluggable engine architecture**: wind engine, solar engine, storage engine (Phase 2) coexist as independent modules with shared contracts.
- Minimize coupling: each tech engine talks to finance layer via `GenerationContractV14` (new), not internal loops.
- Use dependency injection: NREL PySAM and windpowerlib as optional adapters, not hard requirements.

### From a Financial Modeler / Project Finance perspective:
- **Portfolio-level CFADS:** Combine wind + solar generation (accounting for correlation), apply shared grid offtake rules (curtailment, forced outage), calculate combined CFADS.
- **Tech-specific sensitivities:** Create Tornado charts where wind CAPEX, solar module cost, and shared transmission costs vary independently; lenders need to see **which technology drives IRR volatility**.
- **Warranty and performance risk:** Wind turbines and solar panels have different degradation curves (0.5–1% wind, 0.3–0.8% solar) and failure modes; model separately to price insurance correctly.

### From a Statistics / Risk perspective:
- **Correlation modeling:** Wind and solar are negatively correlated in many regions (monsoon-driven wind peaks when clouds reduce solar); Monte Carlo in Sprint 9 can now sample wind+solar together with realistic correlation matrices.
- **Tail risk:** Hybrid plants have **less dramatic tails** (extreme wind loss offset by solar potential) but introduce **basis risk** (one tech fails, PPA exposure changes); stress tests must capture this.

### From an Academic / Research perspective:
- This aligns with NREL's Renewable Integration Study for India and SE Asia wind-solar hybrids; we're operationalizing peer-reviewed models.
- Open-source approach (windpowerlib, pvlib, PyWake) ensures reproducibility and invites community contribution.

### From a Banker / Equity Investor perspective:
- Multi-tech **reduces cost of capital:** hybrid plants are more bankable (lower risk, higher capacity factor) so debt ratios can be higher and equity IRR improves.
- **Mitigates stranded asset risk:** if one tech becomes uneconomic, the other continues (e.g., solar drops in cost, wind still provides stable baseload).
- **Attracts ESG/impact capital:** hybrid plants are seen as safer, more durable climate solutions.

---

## PART 1: FRAMEWORK & LIBRARY SURVEY (Deep Dive)

### 1.1 NREL PySAM (System Advisor Model)

**What it is:** Industry-standard hourly simulation engine for solar PV, CSP, wind, hydro, geothermal; maintained by NREL, widely used by DFI and commercial lenders.

**Why it matters:**
- Validated against real-world plant data (10+ years, multiple geographies).
- Produces **P50/P90 AEP estimates** used in bankable feasibility studies.
- Handles module/inverter specifics, soiling, shading, temperature effects, DC/AC losses.
- For wind: integrates with wind speed timeseries, applies power curve and availability.

**Python integration:**
- `pip install NREL-PySAM` (free, open-source, Apache 2.0 license).
- Two APIs: simple (high-level, typical use) and detailed (low-level tuning).
- Returns: hourly generation, annual AEP, monthly profiles, performance metrics.

**Strengths:**
- Lender-grade; extensively documented and validated.
- Handles location-specific losses (soiling, temperature derating, spectral effects).
- Can ingest PVWATTS data or hourly TMY (typical meteorological year) files.

**Limitations:**
- Does not model wake losses (wind farms); requires external wake model or parametrization.
- PV model is simplified for commercial systems; does not account for individual string/module failures.
- Large dependency (C++ under the hood); adds to deployment complexity.

**Sprint 10 role:** Primary solar PV modeling engine; optional for wind (we'll use windpowerlib as primary for wind, but can cross-validate vs PySAM).

---

### 1.2 windpowerlib (DTU Wind Energy)

**What it is:** Open-source Python library for wind turbine power output and wind farm energy production estimation; developed by DTU Wind Energy (partner with Vestas, GE).

**Why it matters:**
- Implements standard wind power curve models and wake effect models (Jensen, Park, Bastankhah).
- Integrated with NREL's wind data (US Wind Toolkit, international data via adapters).
- Produces **AEP, wake-adjusted generation, layout optimization** capabilities.
- Peer-reviewed; used in academic and commercial contexts.

**Python integration:**
- `pip install windpowerlib` (open-source, MIT license).
- Requires wind speed timeseries (e.g., from ERA5 downscaled, NREL Wind Toolkit, or simulated).
- Inputs: turbine power curve (manufacturer data or database), hub height, layout coordinates.
- Outputs: gross generation (no wakes), net generation (with wakes), loss breakdown.

**Strengths:**
- Transparent wake models; can be tuned for local conditions.
- Lightweight; no large C++ dependency.
- Supports custom power curves.

**Limitations:**
- Does not account for availability/downtime (needs external model or tuning factor).
- Wake models are 2D; does not handle complex terrain or offshore stratification.
- Requires high-quality wind resource data at multiple heights; relying on coarse data will reduce accuracy.

**Sprint 10 role:** Primary wind power modeling engine; integrates with wake losses and AEP adjustments.

---

### 1.3 pvlib-python

**What it is:** Open-source Python library for photovoltaic system modeling, developed by community and supported by Sandia National Laboratories and NREL.

**Why it matters:**
- Handles solar resource simulation, module modeling, inverter losses, soiling, shading, temperature effects, and DC/AC losses.
- Simpler and more modular than PySAM; good for custom workflows.
- Extensive documentation and examples.

**Python integration:**
- `pip install pvlib` (open-source, BSD 3-Clause license).
- Works with public solar resource data (PVWATTS, CAMS, ERA5 solar subsets).
- Inputs: latitude, longitude, module/inverter specs, tilt angle, tracker type, soiling rate, temperature coefficient.
- Outputs: hourly DC power, AC power, losses breakdown, annual AEP.

**Strengths:**
- Modular; can use components independently (irradiance model, module model, loss model).
- Active community; frequent updates.
- No compilation required; pure Python or NumPy.

**Limitations:**
- Less comprehensive than PySAM for utility-scale plants; designed more for distributed generation.
- Shading model is simplified.

**Sprint 10 role:** Alternative or complementary solar PV engine; good for sensitivity studies and custom soiling/temperature modeling.

---

### 1.4 PyWake

**What it is:** Open-source wake modeling framework from DTU, supporting multiple wake models (Bastankhah, Jensen, Gaussian, Larsen) and wind farm optimization.

**Why it matters:**
- Advanced wake modeling for wind farms; can reduce AEP uncertainty from 5% to 1–2%.
- Supports wind farm layout optimization.
- Integrates with windpowerlib and other wind resource tools.

**Python integration:**
- `pip install py-wake` (open-source, Apache 2.0).
- Inputs: turbine positions, wind rose (frequency and speed distribution by direction), power curve.
- Outputs: per-turbine power, farm AEP, wake loss breakdown by wind direction.

**Strengths:**
- Industry-leading wake models; used in commercial design tools.
- Can be called from windpowerlib for seamless integration.

**Limitations:**
- Computationally intensive for large wind farms (100+ turbines).
- Requires detailed wind rose; coarse directional data reduces accuracy.

**Sprint 10 role:** Optional advanced wake modeling (Phase 1 can use simplified wake loss factors, Phase 2 can plug in PyWake for higher fidelity).

---

### 1.5 Open Data Sources (Free, Accessible, South Asia-Focused)

#### Wind Resource Data
1. **NREL India Wind Toolkit**
   - 3 km × 5 min resolution, 20+ years of hourly data, multiple hub heights (10–140 m).
   - Free with free account; API or direct download.
   - URL: `https://developer.nrel.gov/docs/wind/wind-toolkit/`
   - Covers: India + select SE Asia regions.

2. **ERA5 (Copernicus Climate Data Store)**
   - Global hourly reanalysis, ~31 km native resolution (can downscale to 3 km with WRF or ML).
   - Free with registration.
   - URL: `https://cds.climate.copernicus.eu/`
   - Covers: All of South Asia (India, Bangladesh, Sri Lanka, Pakistan, Nepal).

3. **NREL Southeast Asia Wind Dataset**
   - 3 km × 15 min, 15+ years, all heights.
   - Recent release (2023); covers wind-rich regions in SE Asia.
   - Free download via NREL Data Explorer.
   - URL: `https://data.nrel.gov/`

#### Solar Resource Data
1. **NREL PVWATTS API**
   - Global hourly solar irradiance and temperature, derived from satellite data.
   - Free with API key.
   - URL: `https://pvwatts.nrel.gov/api/`
   - Covers: All of South Asia.

2. **Copernicus Atmosphere Monitoring Service (CAMS)**
   - Hourly global horizontal irradiance (GHI), direct (DNI), diffuse (DHI).
   - Free with registration.
   - URL: `https://cams.atmosphere.copernicus.eu/`
   - Resolution: ~1 km gridded product.

3. **SOLARGIS**
   - Commercial, but free tier for research; higher resolution and accuracy than PVWATTS.
   - Covers all of South Asia.
   - URL: `https://solargis.com/`

#### Shared Infrastructure Data
1. **OpenStreetMap**
   - Terrain, grid network, transmission line locations.
   - Free; can be queried via `osmnx` Python library.

2. **GEBCO / SRTM (Terrain Elevation)**
   - High-resolution DEM; critical for wind shear and solar shading.
   - Free downloads.

#### Meteorological Data
1. **IMD (India Meteorological Department) Data**
   - Historical weather data for India.
   - Free with registration (academic users).
   - Covers: India stations (useful for validation and spatial downscaling).

---

## PART 2: CASPER ARCHITECTURE FOR MULTI-TECH

### 2.1 Extended CASPER Model for Sprint 10

```
CASPER Multi-Tech (Wind + Solar)

C (Config) ────────────────────────────────────────
  ├─ Shared: site, grid connection, curtailment rules
  ├─ Wind: turbine power curves, hub heights, wake model choice
  ├─ Solar: module/inverter specs, tilt, soiling, shading model choice
  └─ Resource data: source (PVWATTS, ERA5, NREL Toolkit), spatial resolution, temporal coverage

A (Aggregation) ────────────────────────────────────
  ├─ Per-tech AEP: wind net, solar AC
  ├─ Combined generation (hourly + annual): (wind_gen + solar_gen) × curtailment factor
  └─ Portfolio CFADS: aggregated generation → revenue → CFADS (shared cashflow rules)

S (Scenario) ────────────────────────────────────────
  ├─ Tech mix: (wind_mw, solar_mw) pairs
  ├─ Resource uncertainty: P50, P90 AEP; wind correlation; solar degradation
  └─ Market: tariff structure (may differ by tech), grid connection capacity

P (Parameters) ──────────────────────────────────────
  ├─ Wind: hub height, roughness, wind shear exponent, wake loss %, power curve ID, availability
  ├─ Solar: module efficiency, soiling rate (%/year), temp coefficient, DC/AC loss %, availability
  ├─ Portfolio: correlation (wind-solar, wind direction, seasonal), grid curtailment limits
  └─ Financial: tariff (shared or tech-specific), CAPEX (per MW by tech), OPEX (%/year by tech)

E (Engine) ──────────────────────────────────────────
  ├─ Wind production: windpowerlib + optional PyWake
  ├─ Solar production: pvlib or PySAM
  ├─ Portfolio aggregation: combine with correlation + curtailment
  ├─ Cashflow: (combined generation) × tariff - OPEX → CFADS (same as v14)
  └─ Debt/equity: existing WACC, debt, equity layers (no change)

R (Results) ──────────────────────────────────────────
  ├─ Per-tech: wind_aep, solar_aep, wind_cfads, solar_cfads (split view for lenders)
  ├─ Portfolio: combined_aep, combined_cfads, combined_irr
  ├─ CasperResult extended: scenario.generation_breakdown (wind, solar), kpis (per-tech DSCR, combined)
  └─ Risk: sensitivity per tech (tornado on wind capex vs solar efficiency)
```

---

## PART 3: CONCRETE EPICS & STORIES

### EPIC 1: Multi-Tech Contracts & Config Schema
**Tags:** `CASPER-C`, `CASPER-P`, `GWTF-Contract`, `Foundation`
**Effort:** 2 sprints (Phase 1 foundation)
**Blocking:** All other epics

#### Story 1.1: Design GenerationContractV14 dataclass
- **Acceptance:** New dataclass in `analytics/contracts_v14.py` (or `finance/generation_v14_contracts.py`)
- **Fields (per tech):**
  ```python
  @dataclass(frozen=True)
  class GenerationProfile:
      technology: str  # "wind", "solar"
      annual_aep_kwh: float  # P50 annual energy production
      hourly_generation_kwh: list[float]  # 8760 hourly profile
      availability_pct: float  # 95% typical
      losses_breakdown: dict[str, float]  # wake_loss, soiling, etc.

  @dataclass(frozen=True)
  class MultiTechGenerationResult:
      wind: Optional[GenerationProfile]
      solar: Optional[GenerationProfile]
      portfolio_aep_kwh: float  # (wind_aep + solar_aep) adjusted for correlation
      correlation_factor: float  # 0.8–1.0 (wind-solar anti-corr in monsoon)
      combined_hourly_kwh: list[float]
  ```
- **Test:** `test_generation_contracts_v14.py` — instantiate with dummy data, assert fields and types.

#### Story 1.2: Extend scenario config schema (YAML)
- **Acceptance:** New YAML block in `dutchbay_master_config_v14.yaml`:
  ```yaml
  generation:
    technologies:
      wind:
        enabled: true
        capacity_mw: 100
        turbine:
          model: "Siemens SG 10.0-193"
          power_curve_source: "manufacturer"  # or "nrel_database"
          hub_height_m: 120
          rotor_diameter_m: 193
        resource:
          data_source: "nrel_india_toolkit"  # or "era5"
          wind_shear_exponent: 0.2
          wake_loss_pct: 4.0  # simplified; can upgrade to PyWake
          availability_pct: 96.0
      solar:
        enabled: true
        capacity_mw: 50
        module:
          type: "MonoFacial"
          efficiency_pct: 22.5
          temperature_coefficient: -0.35  # %/°C
        inverter:
          efficiency_pct: 98.5
          dc_ac_ratio: 1.2
        layout:
          tilt_degrees: 20
          tracking: "fixed"  # or "single_axis"
          soiling_rate_pct: 0.5  # %/year
        resource:
          data_source: "pvwatts"  # or "cams"
          availability_pct: 98.0
    shared:
      curtailment_rules:
        max_injection_mw: 140
        seasonal_limits:
          monsoon: 0.9  # 90% curtailment cap
          dry: 1.0
      correlation:
        wind_solar_rho: -0.3  # negative correlation
  ```
- **Test:** Schema validation test; confirm YAML loads and validates via `schema_guard`.

#### Story 1.3: Define multi-tech parameter registry
- **Acceptance:** Update `constants.py` with `WIND_PARAMS`, `SOLAR_PARAMS`, `PORTFOLIO_PARAMS` enums and default ranges.
  ```python
  WIND_SENSITIVITY_RANGES: Final[Dict[str, tuple[float, float]]] = {
      "hub_height_m": (80, 150),
      "wind_shear_exponent": (0.15, 0.35),
      "wake_loss_pct": (2, 10),
      "availability_pct": (92, 98),
      "power_curve_scaling": (0.9, 1.1),
  }
  SOLAR_SENSITIVITY_RANGES: Final[Dict[str, tuple[float, float]]] = {
      "module_efficiency_pct": (20, 25),
      "soiling_rate_pct": (0.3, 1.0),
      "temperature_coefficient": (-0.5, -0.2),
      "availability_pct": (96, 99),
      "dc_ac_ratio": (1.0, 1.3),
  }
  PORTFOLIO_SENSITIVITY_RANGES: Final[Dict[str, tuple[float, float]]] = {
      "wind_solar_correlation": (-0.5, 0.1),
      "curtailment_rate_pct": (0, 10),
  }
  ```
- **Test:** Smoke test that all ranges are physically plausible; used by sensitivity/MC later.

---

### EPIC 2: Wind Production Engine (windpowerlib Integration)
**Tags:** `CASPER-E`, `GWTF-Engine`, `Validation`, `OpenSource`
**Effort:** 3 sprints (2 weeks core + 1 week validation)
**Dependencies:** Epic 1

#### Story 2.1: Create windpowerlib adapter module
- **New file:** `analytics/wind_production_v14.py` (or `finance/wind_v14.py`)
- **Acceptance:** Adapter that wraps windpowerlib; contracts match `GenerationProfile`.
  ```python
  from windpowerlib.wind_turbine import WindTurbine
  from windpowerlib.wind_farm import WindFarm

  @dataclass(frozen=True)
  class WindResourceInput:
      wind_speed_hourly_ms: list[float]  # 8760 values
      hub_height_m: float
      reference_height_m: float = 10.0  # if wind_speed is measured at ref height
      wind_direction_degrees: Optional[list[float]] = None  # for wake calc

  def estimate_wind_aep(
      config: dict,
      wind_resource: WindResourceInput,
      turbine_model_id: str = "Siemens SG 10.0-193",
      wake_loss_pct: float = 4.0,
  ) -> GenerationProfile:
      """
      Estimate wind farm AEP using windpowerlib.

      Inputs:
        - Hourly wind speeds at hub height
        - Turbine specs (power curve from DB or custom)
        - Optional: layout + wind direction (for PyWake integration)
        - Simplified: wake loss as % deduction

      Returns: GenerationProfile with hourly generation, annual AEP, losses breakdown.
      """
      # Load turbine power curve from windpowerlib DB or user-provided
      turbine = WindTurbine(name=turbine_model_id)

      # Compute gross power output (hourly)
      gross_power_w = turbine.power_curve(wind_resource.wind_speed_hourly_ms)

      # Apply wake losses (simplified)
      net_power_w = gross_power_w * (1.0 - wake_loss_pct / 100.0)

      # Convert to generation (kWh)
      hourly_gen_kwh = net_power_w / 1e6  # W to MWh, divide by 1000? [check units]
      annual_aep_kwh = sum(hourly_gen_kwh)

      # Return contract
      return GenerationProfile(
          technology="wind",
          annual_aep_kwh=annual_aep_kwh,
          hourly_generation_kwh=hourly_gen_kwh,
          availability_pct=config.get("availability_pct", 96.0),
          losses_breakdown={
              "wake_loss_pct": wake_loss_pct,
              "availability_loss_pct": 100 - config.get("availability_pct", 96.0),
          }
      )
  ```
- **Test:** `test_wind_production_v14.py` with NREL India Toolkit sample data (1 year, 1 grid point).

#### Story 2.2: Integrate wind resource data adapters
- **Acceptance:** Helper functions to fetch and normalize wind data from NREL India Toolkit and ERA5.
  ```python
  def load_wind_resource_nrel_toolkit(
      latitude: float,
      longitude: float,
      height_m: float,
      year_range: tuple[int, int],
      api_key: str,
  ) -> WindResourceInput:
      """Fetch from NREL Wind Toolkit API."""
      # Call NREL API, validate, return WindResourceInput
      pass

  def load_wind_resource_era5(
      latitude: float,
      longitude: float,
      height_m: float,
      year_range: tuple[int, int],
  ) -> WindResourceInput:
      """Fetch from Copernicus CDS (ERA5)."""
      # Query cdsapi, downscale if needed, return WindResourceInput
      pass
  ```
- **Test:** `test_wind_resource_loaders_v14.py` with mock API responses.

#### Story 2.3: Advanced: PyWake integration (optional, Phase 2)
- **Acceptance:** Optional wind farm layout-aware wake calculation.
  ```python
  def estimate_wind_aep_with_pywake(
      config: dict,
      wind_resource: WindResourceInput,
      turbine_positions: list[tuple[float, float]],  # (x, y) coordinates
      wind_rose: dict,  # {direction_deg: [speeds_ms]}
  ) -> GenerationProfile:
      """Use PyWake for accurate per-turbine wake modeling."""
      # Integrate PyWake; return GenerationProfile with per-turbine breakdown optional
      pass
  ```
- **Test:** `test_wind_pywake_integration_v14.py` with toy 3-turbine wind farm.
- **Note:** Phase 2; mark as optional in Story 2.1.

#### Story 2.4: Validation against real-world data
- **Acceptance:** Regression test comparing estimated vs. observed AEP for a real wind project (e.g., DutchBay 150 MW wind).
- **Test:** `test_wind_production_regression_v14.py` — load 2–3 years of SCADA data, compare P50 AEP estimate vs. actual; assert <5% error.
- **Data source:** Use anonymized DutchBay turbine SCADA if available; else use public wind farm benchmark (e.g., NREL WIND Toolkit validation data).

---

### EPIC 3: Solar Production Engine (pvlib Integration)
**Tags:** `CASPER-E`, `GWTF-Engine`, `Validation`, `OpenSource`
**Effort:** 2 sprints (simpler than wind + fewer variables)
**Dependencies:** Epic 1

#### Story 3.1: Create pvlib adapter module
- **New file:** `analytics/solar_production_v14.py` (or `finance/solar_v14.py`)
- **Acceptance:** Adapter wrapping pvlib; contracts match `GenerationProfile`.
  ```python
  import pvlib

  @dataclass(frozen=True)
  class SolarResourceInput:
      ghi_hourly_wm2: list[float]  # Global horizontal irradiance, 8760 values
      dhi_hourly_wm2: Optional[list[float]] = None  # Diffuse horizontal
      dni_hourly_wm2: Optional[list[float]] = None  # Direct normal
      temperature_hourly_c: list[float] = None  # Ambient temp, 8760 values

  def estimate_solar_aep(
      config: dict,
      solar_resource: SolarResourceInput,
      location: tuple[float, float],  # lat, lon for timezone
  ) -> GenerationProfile:
      """
      Estimate solar PV AEP using pvlib.

      Inputs:
        - Hourly GHI + optional DNI/DHI
        - Temperature hourly
        - Module/inverter specs from config
        - Tilt, tracking, soiling, DC/AC ratio

      Returns: GenerationProfile with hourly AC output, annual AEP, losses.
      """
      # Create location and load solar data
      loc = pvlib.location.Location(location[0], location[1])

      # Simple DC output from GHI and module specs
      module_params = config["solar"]["module"]
      dc_power_w = (
          solar_resource.ghi_hourly_wm2
          * module_params["efficiency_pct"] / 100.0
          * 1000  # W/m^2 to W
      )

      # Apply temperature derating
      temp_coeff = module_params["temperature_coefficient"]  # %/°C
      ref_temp = 25  # °C
      dc_power_w *= (1.0 + (solar_resource.temperature_hourly_c - ref_temp) * temp_coeff / 100.0)

      # Apply soiling
      soiling_loss = 1.0 - config["solar"]["layout"]["soiling_rate_pct"] / 100.0
      dc_power_w *= soiling_loss

      # DC to AC conversion
      inverter_eff = config["solar"]["inverter"]["efficiency_pct"] / 100.0
      ac_power_w = dc_power_w * inverter_eff

      # Convert to generation (MWh)
      hourly_gen_kwh = ac_power_w / 1e3  # W to kWh
      annual_aep_kwh = sum(hourly_gen_kwh)

      # Losses breakdown
      losses_breakdown = {
          "soiling_pct": config["solar"]["layout"]["soiling_rate_pct"],
          "temperature_derating_pct": (
              (solar_resource.temperature_hourly_c.mean() - ref_temp)
              * abs(temp_coeff)
          ),
          "inverter_loss_pct": (1.0 - inverter_eff) * 100.0,
          "availability_loss_pct": 100 - config["solar"]["resource"]["availability_pct"],
      }

      return GenerationProfile(
          technology="solar",
          annual_aep_kwh=annual_aep_kwh,
          hourly_generation_kwh=hourly_gen_kwh,
          availability_pct=config["solar"]["resource"]["availability_pct"],
          losses_breakdown=losses_breakdown,
      )
  ```
- **Test:** `test_solar_production_v14.py` with PVWATTS sample data (1 year, 1 location).

#### Story 3.2: Solar resource data adapters
- **Acceptance:** Helper functions to fetch solar data from PVWATTS and CAMS.
  ```python
  def load_solar_resource_pvwatts(
      latitude: float,
      longitude: float,
      year_range: tuple[int, int],
      api_key: str,
  ) -> SolarResourceInput:
      """Fetch from NREL PVWATTS API."""
      pass

  def load_solar_resource_cams(
      latitude: float,
      longitude: float,
      year_range: tuple[int, int],
  ) -> SolarResourceInput:
      """Fetch from Copernicus CAMS."""
      pass
  ```
- **Test:** `test_solar_resource_loaders_v14.py`.

#### Story 3.3: Advanced: module/inverter database
- **Acceptance:** CSV or JSON database of common solar modules and inverters used in South Asia; e.g., LONGI, Canadian Solar, Sungrow, etc., with efficiencies and temp coefficients.
- **File:** `data/solar_equipment_v14.json`
- **Test:** Load and validate equipment specs.

#### Story 3.4: Validation against real-world data
- **Acceptance:** Regression test for a real solar project (similar to wind Story 2.4).
- **Data source:** Public solar project benchmark or anonymized site data if available.
- **Test:** `test_solar_production_regression_v14.py`.

---

### EPIC 4: Portfolio Aggregation & Correlation
**Tags:** `CASPER-A`, `GWTF-Contract`, `Finance`, `Risk`
**Effort:** 2 sprints
**Dependencies:** Epics 2, 3

#### Story 4.1: Correlation modeling and portfolio AEP
- **New file:** `analytics/portfolio_aggregation_v14.py`
- **Acceptance:** Combine wind + solar hourly generation with realistic correlation.
  ```python
  @dataclass(frozen=True)
  class PortfolioAggregationConfig:
      wind_solar_correlation: float  # -0.5 to 0.1 (negative in monsoon regions)
      curtailment_factor: float  # 0.0 to 1.0 (grid limits)
      seasonal_curtailment: Optional[dict[str, float]] = None  # {season: factor}

  def aggregate_multi_tech_generation(
      wind_profile: GenerationProfile,
      solar_profile: GenerationProfile,
      config: PortfolioAggregationConfig,
  ) -> MultiTechGenerationResult:
      """
      Combine wind + solar hourly generation with correlation adjustment.

      Simple approach (Phase 1):
        combined[hour] = wind[hour] + solar[hour]  # assume independence for now

      Advanced approach (Phase 2 / MC):
        Use correlation matrix in MC to sample wind/solar jointly;
        then apply portfolio-level curtailment.
      """
      if not wind_profile and not solar_profile:
          raise ValueError("At least one technology must be enabled")

      wind_gen = wind_profile.hourly_generation_kwh if wind_profile else [0] * 8760
      solar_gen = solar_profile.hourly_generation_kwh if solar_profile else [0] * 8760

      # Simple combination (no hourly correlation adjustment yet)
      combined_gen = [w + s for w, s in zip(wind_gen, solar_gen)]

      # Apply curtailment
      if config.seasonal_curtailment:
          combined_gen = apply_seasonal_curtailment(combined_gen, config.seasonal_curtailment)
      else:
          combined_gen = [g * config.curtailment_factor for g in combined_gen]

      # Annual AEP
      annual_aep = sum(combined_gen)

      # Effective correlation (for lender reporting)
      correlation_factor = (
          1.0 + config.wind_solar_correlation * 0.1  # Simplified; can be more sophisticated
      )

      return MultiTechGenerationResult(
          wind=wind_profile,
          solar=solar_profile,
          portfolio_aep_kwh=annual_aep,
          correlation_factor=correlation_factor,
          combined_hourly_kwh=combined_gen,
      )
  ```
- **Test:** `test_portfolio_aggregation_v14.py` — verify combined AEP, curtailment application.

#### Story 4.2: Multi-tech cashflow integration
- **Acceptance:** Extend `cashflow_v14.py` to accept `MultiTechGenerationResult` and compute revenue/CFADS.
- **Change:** In `cashflow_v14.py` or a new wrapper `multi_tech_cashflow_v14.py`:
  ```python
  def build_multi_tech_annual_cfads(
      config: dict,
      generation_result: MultiTechGenerationResult,
  ) -> list[dict[str, float]]:
      """
      Compute annual CFADS for multi-tech portfolio.

      Same as v14 cashflow, but input is (combined generation) instead of single-tech generation.
      Tariff can be shared or tech-specific.
      """
      # Use combined_hourly_kwh to compute annual generation (MWh)
      annual_generation_mwh = sum(generation_result.combined_hourly_kwh) / 1000

      # Apply tariff (shared or blend if tech-specific)
      tariff_lkr_per_kwh = config.get("tariff", {}).get("lkr_per_kwh", 20.0)
      annual_revenue_lkr = annual_generation_mwh * 1000 * tariff_lkr_per_kwh

      # Build annual rows (same structure as v14)
      annual_rows = []
      for year in range(config.get("project", {}).get("life_years", 25)):
          degradation_factor = (1.0 - 0.005) ** year  # 0.5% annual degradation (blended)

          cfads_lkr = (
              annual_revenue_lkr * degradation_factor
              - calculate_annual_opex(config, year)
          )

          annual_rows.append({
              "year": year + 1,
              "generation_mwh": annual_generation_mwh * degradation_factor,
              "wind_gen_mwh": (
                  generation_result.wind.annual_aep_kwh / 1000 * degradation_factor
                  if generation_result.wind else 0
              ),
              "solar_gen_mwh": (
                  generation_result.solar.annual_aep_kwh / 1000 * degradation_factor
                  if generation_result.solar else 0
              ),
              "revenue_lkr": annual_revenue_lkr * degradation_factor,
              "opex_lkr": calculate_annual_opex(config, year),
              "cfads_usd": convert_lkr_to_usd(cfads_lkr, fx_rate=config.get("fx", {}).get("rate", 350)),
          })

      return annual_rows
  ```
- **Test:** `test_multi_tech_cashflow_v14.py`.

#### Story 4.3: Tech-specific DSCR and KPIs
- **Acceptance:** In `metrics.py`, add per-technology DSCR calculations so lenders see wind DSCR vs solar DSCR separately.
  ```python
  def calculate_multi_tech_metrics(
      annual_rows: list[dict],
      debt_result: dict,
      generation_result: MultiTechGenerationResult,
  ) -> dict:
      """
      Compute KPIs with per-tech breakdowns.

      Outputs:
        - project_irr (combined)
        - wind_aep, solar_aep
        - wind_cfads, solar_cfads (split based on generation proportion)
        - dscr_min, dscr_wind (minimum DSCR if tech operated independently)
        - dscr_solar (minimum DSCR if tech operated independently)
      """
      # Standard project IRR, DSCR (combined)
      standard_kpis = calculate_scenario_kpis(annual_rows, debt_result)

      # Tech-specific views
      if generation_result.wind and generation_result.solar:
          wind_proportion = (
              generation_result.wind.annual_aep_kwh /
              (generation_result.wind.annual_aep_kwh + generation_result.solar.annual_aep_kwh)
          )
          solar_proportion = 1.0 - wind_proportion
      else:
          wind_proportion = 1.0 if generation_result.wind else 0.0
          solar_proportion = 1.0 if generation_result.solar else 0.0

      # Split CFADS by tech (proportional to AEP)
      wind_cfads_annual = [row.get("cfads_usd", 0) * wind_proportion for row in annual_rows]
      solar_cfads_annual = [row.get("cfads_usd", 0) * solar_proportion for row in annual_rows]

      # If wind were independent (with shared debt): hypothetical DSCR
      # (simplified; in practice, debt structure would be different)
      wind_dscr_hypothetical = (
          min(wind_cfads_annual) / debt_result.get("annual_debt_service", [1])[0]
          if wind_cfads_annual else None
      )

      kpis = standard_kpis.copy()
      kpis.update({
          "wind_aep_kwh": generation_result.wind.annual_aep_kwh if generation_result.wind else None,
          "solar_aep_kwh": generation_result.solar.annual_aep_kwh if generation_result.solar else None,
          "wind_proportion": wind_proportion,
          "solar_proportion": solar_proportion,
          "wind_dscr_hypothetical": wind_dscr_hypothetical,
          "solar_dscr_hypothetical": (
              min(solar_cfads_annual) / debt_result.get("annual_debt_service", [1])[0]
              if solar_cfads_annual else None
          ),
      })

      return kpis
  ```
- **Test:** `test_multi_tech_metrics_v14.py`.

---

### EPIC 5: Extended CasperResult for Multi-Tech
**Tags:** `CASPER-R`, `GWTF-Contract`, `Analytics`
**Effort:** 1 sprint
**Dependencies:** Epics 2–4

#### Story 5.1: Extend CasperResult JSON contract
- **Acceptance:** Update `contracts_v14.CasperResult` to include multi-tech slices.
  ```python
  @dataclass(frozen=True)
  class TechnologyBreakdown:
      technology: str
      annual_aep_kwh: float
      annual_cfads_usd: float
      dscr_min: Optional[float]
      capex_usd: float
      capex_per_mw: float

  @dataclass(frozen=True)
  class CasperResult:
      scenario: ScenarioResult  # unchanged
      kpis: dict[str, float]  # unchanged
      sensitivity: Optional[SensitivitySuite] = None
      monte_carlo: Optional[MonteCarloResult] = None
      analytics_summary: Optional[dict[str, Any]] = None

      # NEW: Multi-tech breakdown
      generation: Optional[MultiTechGenerationResult] = None
      technology_breakdown: Optional[list[TechnologyBreakdown]] = None  # per-tech KPIs

      metadata: dict[str, Any] = field(default_factory=dict)
  ```
- **JSON shape:**
  ```json
  {
    "scenario": { ... },
    "kpis": { "project_irr": 0.135, ... },
    "generation": {
      "wind": { "annual_aep_kwh": 450e6, "hourly_generation_kwh": [...] },
      "solar": { "annual_aep_kwh": 80e6, ... },
      "portfolio_aep_kwh": 530e6,
      "correlation_factor": 0.95
    },
    "technology_breakdown": [
      { "technology": "wind", "annual_aep_kwh": 450e6, "annual_cfads_usd": 45e6, "dscr_min": 1.28, ... },
      { "technology": "solar", "annual_aep_kwh": 80e6, "annual_cfads_usd": 8e6, "dscr_min": 1.15, ... }
    ],
    "metadata": { "casper_version": "v2", ... }
  }
  ```
- **Test:** `test_casper_result_multi_tech_v14.py`.

#### Story 5.2: Extend ScenarioAnalytics for multi-tech
- **Acceptance:** Update `scenario_analytics.py` to split summary and timeseries dataframes by technology.
  ```python
  # New columns in summary_df:
  # wind_aep_kwh, solar_aep_kwh, wind_dscr_min, solar_dscr_min, wind_capex_usd, solar_capex_usd

  # In timeseries_df, optionally add:
  # wind_gen_mwh, solar_gen_mwh (if hourly resolution desired; else yearly splits)
  ```
- **Test:** `test_scenario_analytics_multi_tech_v14.py`.

---

### EPIC 6: Sensitivity & Monte Carlo for Multi-Tech
**Tags:** `CASPER-P`, `GWTF-Risk`, `Analytics`
**Effort:** 2 sprints
**Dependencies:** Epics 1, 5 (builds on existing sensitivity/MC from Sprint 9)

#### Story 6.1: Extend sensitivity to per-tech parameters
- **Acceptance:** Tornado analysis now includes wind (hub height, shear, wake loss) and solar (efficiency, soiling) together.
  ```python
  def run_multi_tech_tornado(
      config_path: str,
      parameters: list[ParameterRangeConfig],  # can include wind AND solar params
      metrics: list[str] = ["project_irr", "dscr_min", "wind_dscr_min", "solar_dscr_min"],
  ) -> MultiMetricSensitivitySuite:
      """
      Extend tornado to handle wind/solar params and multi-metric outputs.

      Params can be:
        - "generation.wind.hub_height_m" → calls wind engine with different hub heights
        - "generation.solar.module_efficiency_pct" → calls solar engine with different efficiencies
        - "capex.wind_usd_per_mw", "capex.solar_usd_per_mw" → splits financial impact by tech
      """
      pass
  ```
- **Test:** `test_multi_tech_sensitivity_v14.py`.

#### Story 6.2: Multi-tech Monte Carlo
- **Acceptance:** MC now samples wind and solar with realistic correlation.
  ```python
  # In monte_carlo_defaults.yaml:
  correlations:
    enabled: true
    matrix:
      - [wind_speed_ms, irradiance_wm2, -0.3]  # negative correlation (monsoon regions)
      - [wind_shear_exponent, soiling_rate, 0.1]  # slight positive
  ```
- **Test:** `test_multi_tech_monte_carlo_v14.py` — verify P10/P50/P90 for combined AEP.

#### Story 6.3: Risk summary for lenders
- **Acceptance:** Extended executive workbook with risk sheets:
  - Tornado chart: joint impact of wind vs solar parameters.
  - MC tail risk: joint P10 IRR for portfolio vs individual tech failure scenarios.
- **Test:** `test_multi_tech_risk_export_v14.py`.

---

### EPIC 7: Data Ingestion & Validation Pipeline
**Tags:** `CASPER-C`, `GWTF-Data`, `DevOps`
**Effort:** 2–3 sprints
**Dependencies:** Epics 2, 3 (but can run in parallel)

#### Story 7.1: NREL India Wind Toolkit adapter
- **Acceptance:** Auto-fetch wind data given lat/lon/height; cache locally to speed up iterations.
  ```python
  def fetch_nrel_india_wind_data(
      latitude: float,
      longitude: float,
      height_m: float,
      api_key: str,
      cache_dir: str = "data/cache/nrel_wind",
  ) -> WindResourceInput:
      """Fetch from NREL API, cache, return WindResourceInput."""
      cache_file = f"{cache_dir}/nrel_{latitude:.2f}_{longitude:.2f}_{height_m}.pkl"
      if os.path.exists(cache_file):
          return pickle.load(open(cache_file))

      # Call NREL API
      # ... validate, normalize ...

      # Cache
      os.makedirs(cache_dir, exist_ok=True)
      pickle.dump(result, open(cache_file, "wb"))

      return result
  ```
- **Test:** `test_nrel_wind_data_fetch_v14.py` (with mock API).

#### Story 7.2: PVWATTS solar data adapter
- **Acceptance:** Similar to wind, but for solar.
- **Test:** `test_pvwatts_data_fetch_v14.py`.

#### Story 7.3: ERA5 downscaling pipeline (advanced)
- **Acceptance:** Fetch ERA5 (~31 km), apply WRF or ML downscaling to 3 km (optional; fallback to direct ERA5 for Phase 1).
  ```python
  def fetch_and_downscale_era5_wind(
      latitude: float,
      longitude: float,
      year_range: tuple[int, int],
      downscale_method: str = "none",  # "none" | "ml" | "wrf"
  ) -> WindResourceInput:
      """Fetch ERA5, optionally downscale."""
      if downscale_method == "none":
          # Direct ERA5 at ~31 km
          pass
      elif downscale_method == "ml":
          # Use pre-trained ML model (e.g., trained on NREL data + ERA5)
          pass
      elif downscale_method == "wrf":
          # Call WRF API or local WRF instance (heavy)
          pass
  ```
- **Test:** `test_era5_downscaling_v14.py`.

#### Story 7.4: Data quality & validation dashboard
- **Acceptance:** Streamlit or Jupyter dashboard showing:
  - Map of available data (wind resource, solar irradiance) in South Asia.
  - Data summary: P50, P90, seasonality for a user-selected site.
  - Comparison: NREL Toolkit vs ERA5 vs PVWATTS (highlight differences).
- **Effort:** 1 sprint.

---

### EPIC 8: Documentation & Validation
**Tags:** `GWTF-Doc`, `Quality`, `Education`
**Effort:** 2 sprints (concurrent with code)

#### Story 8.1: Multi-tech architecture document
- **Acceptance:** docs/architecture_v14_multi_tech.md
  - Explain CASPER extension for multi-tech.
  - Detail wind and solar engines, data sources, assumptions.
  - Provide example scenario (DutchBay 100 MW wind + 50 MW solar).
  - Cite references (NREL, windpowerlib, pvlib papers).

#### Story 8.2: Framework & library integration guide
- **Acceptance:** docs/framework_integration_v14.md
  - How to use windpowerlib, pvlib, PySAM, PyWake.
  - Installation, API examples, troubleshooting.
  - When to use each tool (Phase 1 vs Phase 2).

#### Story 8.3: Regression test suite for multi-tech
- **Acceptance:** `tests/regression/test_multi_tech_regression_suite.py`
  - Load 2–3 real or public multi-tech projects.
  - Run full pipeline; compare estimated vs. actual AEP (if data available).
  - Assert <5% AEP error.

#### Story 8.4: Lender education materials
- **Acceptance:** Presentation (PowerPoint / PDF) for DFI lender review:
  - How wind and solar AEP are calculated (lay out methodologies).
  - Risks specific to each tech (availability, degradation, curtailment).
  - Example sensitivity/MC outputs for a hybrid project.

---

### EPIC 9: CLI & Configuration Tools
**Tags:** `GWTF-UX`, `DevOps`
**Effort:** 1 sprint
**Dependencies:** Epics 2–5

#### Story 9.1: Extended YAML scenario generator
- **Acceptance:** CLI tool to scaffold multi-tech scenario YAML from lat/lon and capacity mix.
  ```bash
  python scripts/generate_multi_tech_scenario.py \
    --latitude 17.5 \
    --longitude 73.5 \
    --wind_mw 100 \
    --solar_mw 50 \
    --output scenarios/my_hybrid_project.yaml
  ```
  - Fetches wind/solar resource data.
  - Fills in defaults for turbine, module, inverter specs.
  - Outputs ready-to-run scenario YAML.

#### Story 9.2: Multi-tech CASPER CLI
- **Acceptance:** `python run_casper_multi_tech_v14.py --scenario scenarios/my_hybrid.yaml --mode casper`
  - Runs full pipeline for multi-tech.
  - Outputs extended CasperResult JSON with generation, tech breakdown, sensitivity, MC.

#### Story 9.3: Interactive scenario builder (Streamlit app)
- **Acceptance:** Streamlit UI where users:
  - Select location (map + coordinates).
  - Adjust wind/solar capacity sliders.
  - Choose resource data source (NREL vs ERA5 vs custom upload).
  - Run analysis and view results (AEP, DSCR, sensitivity, risk).
- **Effort:** 1–2 sprints; can be deferred to Phase 2.

---

## PART 4: IMPLEMENTATION ROADMAP & PHASES

### Phase 1: Foundation (Sprints 10–11, ~4 weeks)
**Deliverables:** Multi-tech contracts, basic wind/solar engines, portfolio aggregation, extended CasperResult.

- **Week 1:** Epic 1 (Contracts & Config)
- **Week 2:** Epics 2 + 3 (Wind & Solar engines, basic versions)
- **Week 3:** Epic 4 (Portfolio aggregation + multi-tech cashflow)
- **Week 4:** Epic 5 (Extended CasperResult) + Epic 8 (Docs)

**Exit criteria:**
- ✅ All tests pass (including regressions).
- ✅ Can run YAML scenario with hybrid wind+solar project; get AEP, CFADS, DSCR.
- ✅ Tech breakdown visible in outputs.
- ✅ Documentation complete.

### Phase 2: Advanced Analytics & Risk (Sprints 12–13, ~4 weeks)
**Deliverables:** Sensitivity/MC for multi-tech, PyWake integration, data pipeline, CLI tools.

- **Week 1:** Epic 6 (Sensitivity & MC for multi-tech)
- **Week 2:** Epic 7 (Data ingestion from NREL, PVWATTS, ERA5)
- **Week 3:** Epic 9 (CLI tools) + advanced story 2.3 (PyWake)
- **Week 4:** Story 9.3 (Streamlit app, optional) + Final validation

**Exit criteria:**
- ✅ Lender can run tornado analysis on wind+solar parameters separately.
- ✅ MC produces P10/P90 AEP with realistic wind-solar correlation.
- ✅ Data adapters fetch and cache wind/solar data automatically.
- ✅ Streamlit dashboard (optional) is functional.

### Phase 3: Optimization & Storage Extension (Sprints 14+, TBD)
**Deliverables:** Energy storage engine, portfolio optimization, PPA design tools.

- Solar+wind+battery modeling.
- Grid curtailment optimization.
- Tariff/contract optimization for blended resource.

---

## PART 5: EFFORT ESTIMATES & TEAM ALLOCATION

| Epic | Story | Phase | Dev Days | QA Days | Guru Input | Owner |
|------|-------|-------|----------|---------|-----------|-------|
| 1 | 1.1–1.3 | 1 | 10 | 3 | Arch review | Dev Lead + Analyst |
| 2 | 2.1–2.4 | 1–2 | 15 | 4 | Framework eval | Wind Specialist |
| 3 | 3.1–3.4 | 1–2 | 12 | 3 | Framework eval | Solar Specialist |
| 4 | 4.1–4.3 | 1 | 10 | 3 | Finance review | Analyst + Dev |
| 5 | 5.1–5.2 | 1 | 8 | 2 | Contract design | Arch |
| 6 | 6.1–6.3 | 2 | 12 | 3 | Risk/Sensitivity | Risk Analyst |
| 7 | 7.1–7.4 | 2 | 15 | 4 | Data engineering | Data Engineer |
| 8 | 8.1–8.4 | 1–2 | 8 | 2 | Documentation | Tech Writer + Analyst |
| 9 | 9.1–9.3 | 2 | 10 | 2 | UX review | Dev + UX |
| **Total** | | | **100** | **26** | | |

**Recommended team:**
- 2 backend devs (Python, wind/solar engines, data pipelines)
- 1 data engineer (API adapters, caching, ETL)
- 1 financial analyst (CFADS, multi-tech metrics)
- 1 QA / test engineer
- 1 technical writer / architect

---

## PART 6: CASPER / GWTF COMPLIANCE CHECKLIST

- ✅ **C – Config:** YAML schema extends v14; `schema_guard` validates all new blocks.
- ✅ **A – Aggregation:** Multi-tech results aggregated via `MultiTechGenerationResult` and `portfolio_aggregation_v14.py`; contracts strictly typed.
- ✅ **S – Scenario:** New scenario fields (wind_mw, solar_mw, resource sources) added to `ScenarioDescriptor`.
- ✅ **P – Parameters:** All tunable parameters in `constants.py` with defined ranges; sensitivity drivers explicit.
- ✅ **E – Engine:** Wind & solar engines are independent modules, pure functions, no side effects; cashflow layer unchanged.
- ✅ **R – Results:** `CasperResult` extended to include `generation` and `technology_breakdown`; JSON contract versioned.
- ✅ **GWTF Rule R1 (Explicit Contracts):** All new dataclasses in `contracts_v14.py`; no hidden assumptions.
- ✅ **GWTF Rule R3 (Lazy Load):** Data adapters lazy-load from APIs; caching to avoid repeated fetches.
- ✅ **GWTF Rule R6 (No Hardcoding):** All tuning parameters in YAML config or `constants.py`.
- ✅ **Tests:** Regressions anchored to real data or public benchmarks; unit tests cover edge cases.

---

## PART 7: SUCCESS METRICS & KPIs

**For Developers:**
- Code coverage: >80% (multi-tech modules).
- Test execution time: <2 min (unit) + <5 min (integration).
- Mypy compliance: 100% no type errors.

**For Lenders / Analysts:**
- AEP accuracy: <5% error vs. real projects (regression suite).
- DSCR correlation: >0.95 vs. manual spreadsheet (reconciliation test).
- Risk metrics: sensitivity/MC outputs match peer lender standards (validated against actual lender models).

**For End Users:**
- Time to scenario: <5 min from lat/lon to CASPER output (data fetching included).
- Data freshness: Wind/solar data updated auto-monthly from NREL/PVWATTS.
- Lender confidence: 100% of auditable outputs (AEP, CFADS, DSCR) can be traced to published methodology.

---

## APPENDIX A: Open-Source Data Sources (Detailed URLs)

| Source | Type | Coverage | Access | URL |
|--------|------|----------|--------|-----|
| NREL India Wind Toolkit | Wind (3 km, 5-min) | India + SE Asia | Free API | `https://developer.nrel.gov/docs/wind/wind-toolkit/` |
| ERA5 (Copernicus) | Wind/Solar (31 km, hourly) | Global | Free (register) | `https://cds.climate.copernicus.eu/` |
| NREL PVWATTS | Solar (GHI+DNI, hourly) | Global | Free API | `https://pvwatts.nrel.gov/api/` |
| CAMS (Copernicus) | Solar (GHI/DNI/DHI, 1 km) | Global | Free (register) | `https://cams.atmosphere.copernicus.eu/` |
| IMD (India Met Dept) | Weather (stations) | India | Free (academic) | `https://mausam.imd.gov.in/` |
| OpenStreetMap | Terrain/Grid | Global | Free | `https://www.openstreetmap.org/` |
| GEBCO / SRTM | DEM (elevation) | Global | Free | `https://www.gebco.net/` |

---

## APPENDIX B: Framework Installation & Quick Start

```bash
# Install core dependencies
pip install windpowerlib pvlib cdsapi requests pandas numpy scipy

# Optional (Phase 2)
pip install py-wake nrel-pysam

# Development
pip install pytest pytest-cov mypy black ruff pre-commit

# Data science
pip install xarray netcdf4  # for ERA5/CAMS data

# Web/Streamlit (Phase 2)
pip install streamlit plotly folium
```

**Quick start: Estimate wind AEP**
```python
from windpowerlib.wind_turbine import WindTurbine
import numpy as np

# Create turbine
turbine = WindTurbine("Siemens SG 10.0-193")

# Hourly wind speeds (m/s)
wind_speeds = np.random.normal(8, 2, 8760)

# Power output (W)
power = turbine.power_curve(wind_speeds)

# Annual AEP (kWh)
aep_kwh = np.sum(power / 1000)
print(f"AEP: {aep_kwh / 1e6:.1f} GWh/year")
```

**Quick start: Estimate solar AEP**
```python
import pvlib
import pandas as pd

# Location
lat, lon = 17.5, 73.5
location = pvlib.location.Location(lat, lon)

# Sample hourly GHI (W/m²) and temp (°C)
times = pd.date_range("2023-01-01", periods=8760, freq="H", tz="Asia/Kolkata")
ghi = 600 * np.sin(np.arange(8760) / 4380 * np.pi) + np.random.normal(0, 50, 8760)
temp = 25 + 10 * np.sin(np.arange(8760) / 4380 * np.pi)

# Module specs
module_efficiency = 0.22  # 22%

# AC power (kW for 1 kW installed)
ac_power = ghi * module_efficiency * 0.98  # 98% inverter eff

# Annual AEP (kWh/kW)
aep_per_kw = ac_power.sum() / 1000
print(f"Specific yield: {aep_per_kw:.0f} kWh/kW/year")
```

---

**This is your Sprint 10 master backlog. All code must follow Sprints 8–9 contracts; all frameworks are optional (adapters can be swapped); all data is public (South Asia focus). Next step: prioritize epics with team, assign owners, start coding.**
