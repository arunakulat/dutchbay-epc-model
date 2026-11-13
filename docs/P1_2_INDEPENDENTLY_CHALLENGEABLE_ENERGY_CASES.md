# P1.2 — Independently Challengeable Wind & Solar Energy Cases

- **Status**: Formally Scoped (Tracker Milestone P1.2 / Issue [#1425](https://github.com/arunakulat/dutchbay-epc-model/issues/1425))
- **Date**: 2026-11-12
- **Governance & Authority**: `go_with_the_flow_rules_v3_0_clean.csv`, `docs/CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md` §5 P1.2, `docs/WIND_AEP_CHAIN_OF_CUSTODY.md`
- **Standing Holds**: #1110 remains OPEN with its Board/lender circulation HOLD and the F-5 bar stands; this document grants no writer lease, release, reliance, or HOLD change.

---

## 1. Context & Motivation

In project finance for utility-scale renewable energy assets, bankable yield and debt sizing cannot rest upon synthetic reanalysis or uncalibrated default curves alone.
As established in `docs/WIND_AEP_CHAIN_OF_CUSTODY.md` and Issue #1110:
- The existing financed path (`wind_resource/`) derives P50 from ERA5 reanalysis and a 15 × IEA-10MW characterization machine.
- Without on-site mast observations and verified Measure-Correlate-Predict (MCP) calibration, atmospheric models exhibit systematic uncertainty that exceeds DFI / lender tolerance.
- A second independent technical advisor (TA) must be able to independently audit, derive, or challenge every step of the energy bridge from raw source objects through to finance cashflow inputs.

Under **Milestone P1.2**, we establish the formal five-strand delivery framework, evidence request register, and labelled-fixture protocol ensuring all unevidenced data cuts remain explicitly identified as labelled fixtures until field evidence arrives.

---

## 2. The Five Challengeable Resource Strands

The energy yield methodology is partitioned into five distinct, independently verifiable strands:

```
[Strand 1: Site & Measurement Identity]
                  │
                  ▼
[Strand 2: Long-Term Correlation & MCP]
                  │
                  ▼
[Strand 3: Equipment, Loss Accounting & Yield Bridge]
                  │
                  ▼
[Strand 4: Statistical Uncertainty Build-up & P-Levels]
                  │
                  ▼
[Strand 5: Frozen Export & Finance Reconciliation]
```

### Strand 1: Measurement & Site Identity
- **Scope**: On-site meteorological mast identity, sensor calibration, and raw measurement QA.
- **Standards**: IEC 61400-12-1:2017 (Power performance measurements), MEASNET Site Assessment Guidelines.
- **Required Deliverables**:
  - Mast station metadata: WGS84 coordinates, ground elevation, mast height, boom geometry, orientation, and tower shadow sector exclusions.
  - Sensor calibration records: ISO 17025 accredited pre- and post-campaign anemometer calibration certificates with slope and offset pins.
  - Raw 10-minute time-series checksums: Immutable SHA-256 sidecars for raw mast data files with strict UTC timestamping.
  - QA filtering: Range checks, frozen sensor detection, icing/soiling exclusion flags, and turbulence intensity screening.
- **Done When**: A focused delivery issue exists specifying the site sensor metadata schema, and raw data ingestion scripts refuse any file lacking a cryptographically pinned calibration manifest.

### Strand 2: Long-Term Reference Selection & MCP Correlation
- **Scope**: Concurrent period correlation between on-site measurements and long-term reanalysis references.
- **Standards**: IEC 61400-15 (Resource assessment and energy yield analysis).
- **Required Deliverables**:
  - Reference dataset provenance: ERA5, MERRA-2, or certified local station time-series with grid cell coordinates, retrieval parameters, and version hashes.
  - Concurrent period alignment: Minimum 12-month continuous concurrent monitoring window with >= 90% valid data coverage per month.
  - Correlation methodology: Documented directional sector-wise regression (orthogonal distance regression, variance ratio, or matrix MCP) with R² correlation coefficients and uncertainty residuals.
  - Long-term Weibull derivation: 20+ year reconstructed hourly series fitted to Weibull $A$ (scale) and $k$ (shape) with seasonal stability validation.
- **Done When**: A focused delivery issue defines the MCP transfer harness, with explicit goodness-of-fit thresholds (e.g. directional $R^2 \ge 0.85$) required before long-term synthesis.

### Strand 3: Equipment, Loss Accounting & Yield Bridge
- **Scope**: Aerodynamic power curve transformation, spatial wake interaction, and balance-of-plant loss ledger.
- **Standards**: IEC 61400-12-1 (Density normalization), DTU PyWake wake modeling guidelines.
- **Required Deliverables**:
  - OEM-certified power curve: Guaranteed Power-Ct table with explicit hub-height air density ($\rho = 1.225 \text{ kg/m}^3$) and site density adjustment ($v_{\text{corr}} = v \times (\rho_{\text{site}} / \rho_{\text{ref}})^{1/3}$).
  - Wake loss ledger: Micro-siting layout ($X, Y$ UTM coordinates) evaluated via PyWake (Bastankhah-Porté-Agel Gaussian deficit model) with documented ambient turbulence intensity closure.
  - Loss attribution matrix: Explicitly documented line-item deductions:
    1. Aerodynamic wake loss (%)
    2. Electrical collection system & transformer losses (%)
    3. Turbine availability & balance-of-plant downtime (%)
    4. Environmental losses (blade degradation, soiling, icing, temperature derating) (%)
    5. Grid curtailment and utility operational restrictions (%)
- **Done When**: Every single loss is explicitly tracked in a reconciling waterfall ledger from gross yield to net P50 yield; flat unevidenced placeholders are rejected.

### Strand 4: Statistical Uncertainty Build-up & Exceedance Probabilities
- **Scope**: Comprehensive quadrature combination of systematic and random uncertainty components to derive statistical exceedance levels (P50, P75, P90).
- **Standards**: IEC 61400-15-2 (Uncertainty assessment framework).
- **Required Deliverables**:
  - Independent uncertainty budget components (1-sigma relative percentage):
    - Measurement uncertainty ($\sigma_{\text{meas}}$): anemometer calibration, boom distortion, mounting compliance.
    - Historical wind resource uncertainty ($\sigma_{\text{hist}}$): reanalysis data representation, reference length.
    - Future climate variability ($\sigma_{\text{clim}}$): multi-decadal wind regime shifts.
    - Wind shear extrapolation uncertainty ($\sigma_{\text{shear}}$): profile law drift from measurement to hub height.
    - Wake modeling uncertainty ($\sigma_{\text{wake}}$): terrain complexity, wake expansion parameterization.
    - Turbine performance uncertainty ($\sigma_{\text{power}}$): power curve warranty tolerance, air density variability.
    - Electrical & balance-of-plant loss uncertainty ($\sigma_{\text{elec}}$).
    - Interannual variability ($\sigma_{\text{iav}}$): site-specific coefficient of variation divided by $\sqrt{N}$ for project life $N$.
  - Exceedance derivation: Total uncertainty $\sigma_{\text{total}} = \sqrt{\sum \sigma_{\text{sys}}^2 + (\sigma_{\text{iav}}/\sqrt{N})^2}$. Statistical mapping:
    $$\text{P}XX = \text{P}50 \times (1 - z_{XX} \times \sigma_{\text{total}})$$
- **Done When**: Fixed deterministic scalar multipliers (e.g. 0.90 for P75, 0.80 for P90) are barred from bankable paths; all exceedance levels derive directly from an audited quadrature budget.

### Strand 5: Frozen-Export-to-Finance Reconciliation & Invariant Guards
- **Scope**: Cryptographic handoff from resource engine to financial cashflow modeling.
- **Standards**: GWTF CCCDIR (`FRAMEWORK-03`), `analytics/contracts_v14.py`.
- **Required Deliverables**:
  - Immutable export contract: `WindCashflowExport` emitting annual generation (MWh), capacity factor (%), tariff, and FX.
  - Strict adapter validation: `wind_resource/cashflow_adapter.py` validating boundary constraints (positivity, units, valid scenario names).
  - Scenario hash integrity: Verification that changes to resource fixtures preserve byte-identical outputs in committed scenarios or fail loudly.
  - Reconciling AEP-to-CFADS audit guard: Enforcing that `capacity_mw × CF × 8760` matches net P50 within numerical precision.
- **Done When**: Automated regression tests prove end-to-end reconciliation across all committed lender scenarios with zero silent drift.

---

## 3. Evidence Request Register (DFI / Lender Technical Due Diligence)

To transition from unevidenced fixtures to a fully challengeable bankable resource case, the following evidence items are registered and tracked:

| Evidence Request ID | Title | Description | Required Verification |
|---|---|---|---|
| **`EV-REQ-01`** | Met-Mast Anemometer Calibration & Geometry | ISO 17025 calibration certificates for all cup/sonic anemometers on DutchBay met mast (Station 617725), including mast boom drawings and tower shadow sector report. | Verified calibration slope/offset, certificate validity date within 12 months of campaign start. |
| **`EV-REQ-02`** | Raw 10-Minute Concurrent Mast Time-Series | Minimum 12 consecutive months of raw 10-minute wind speed, direction, temperature, and pressure observations from on-site mast. | SHA-256 sidecar manifest, missing timestamp audit (<10% missing), range and spike filtering. |
| **`EV-REQ-03`** | OEM-Certified Turbine Power & Thrust Curves | Certified IEC 61400-12-1 measured power and $C_t$ curve from manufacturer for selected turbine model, with density and turbulence matrices. | Manufacturer test report signed by accredited third-party certifier (DNV, UL, or TÜV). |
| **`EV-REQ-04`** | Solar GHI/DNI Ground Calibration Series | Co-located thermopile pyranometer ground measurements for solar PV cross-validation against satellite irradiance (PVGIS / ERA5). | ISO 9060 Class A calibration certificate, cleaning/soiling logs. |

---

## 4. Labelled Fixtures Protocol

Until empirical evidence fulfilling `EV-REQ-01` through `EV-REQ-04` is formally ingested and audited:
1. **Explicit Labelling Required**: All synthetic, ERA5-only, and extrapolated turbine data files in the repository MUST be explicitly tagged as `LABELLED_FIXTURE_UNBANKABLE` (or `PROVISIONAL_CALIBRATED`).
2. **No Silent Promotion**: No software build, pipeline run, or optimization pass can upgrade an asset from `LABELLED_FIXTURE` to `CERTIFIED_BANKABLE`.
3. **Fail-Closed Presentation**: Reports and exports generated from labelled fixtures must clearly display the unbankable fixture notice in their running metadata and caveat bands (`DBPL-01`).
4. **Governed Decision Gate**: Upgrading a resource claim to bankable requires a formal dated Architecture Decision Record citing evidence package hashes, independent two-lane review (`RECRUIT-01`), and owner authorization.
