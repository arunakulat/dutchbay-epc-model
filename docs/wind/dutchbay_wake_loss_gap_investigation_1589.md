# DutchBay PyWake Aerodynamic Wake Deficit Investigation (#1589)

**Work Item**: #1589
**Related**: #1568, #1577, #1587
**Status**: DRAFT TECHNICAL NOTE

---

## 1. Context and Problem Statement

In #1587 (resolving #1577), the DutchBay wind farm layout dropped from 15 to 14 turbines because the Blue Whale machine replaces DutchBay T2 (#1568). To maintain historical bankability calibration, the farm wake loss was re-baselined by scaling the committed 15-turbine frozen value (**7.28%**) by the ratio of two live PyWake Bastankhah-PorteAgel runs on the recorded WGS84 layout (`conf/dutchbay_wake_14_turbines.yaml`, `docs/wind/dutchbay_14_turbine_wake_summary.json`):
$$\text{Wake}_{14} = 7.28\% \times \frac{19.435\%}{19.332\%} = 7.32\%$$

However, the live PyWake engine itself reports an absolute wake loss of **19.33%** (15 turbines) and **19.44%** (14 counted DutchBay turbines with T2 waking in the flow field). This produces an unexplained **~12 percentage point gap** between the bankable calibration basis (~7.3%) and the unscaled physics-based aerodynamic simulation (~19.4%).

Issue #1589 asks:
1. Which inputs drive the gap: layout geometry/spacing, wind rose and sector weighting, deficit model/closure ($k^*$), or turbine proxy (IEA 10 MW)?
2. Is the frozen 7.28% still the right calibration for the recorded layout?
3. What is the impact on bankable P50/P90 energy yield as a disclosed sensitivity?

---

## 2. Quantitative Gap Attribution

A systematic factorial decomposition was executed using `wind_resource.bankable_aep.model_wake_loss`:

### 2.1 Turbine Spacing & Geometry
In the recorded WGS84 layout (`analytics.gis.shadow_flicker.LocalFrame` projection):
- Adjacent turbine spacing across almost the entire array is **450 m to 550 m** (mean nearest-neighbor distance = 494.5 m).
- For the IEA 10 MW reference machine ($D = 198\text{ m}$), this separation is **2.28 D to 2.82 D**.
- In contrast, the synthetic single-row layout cited in the baseline calibration assumed **650 m** spacing ($3.28\text{ D}$) in an ideal North-South line.
- Standard utility-scale wind farm spacing along prevailing flow is typically **7 D to 10 D** (and 3 D to 5 D crosswind). Dense 2.3–2.8 D downwind spacing creates severe velocity deficits and strong wake interactions.

| Layout Configuration | Wind Rose | Wake Loss (%) | Gross AEP (GWh) | Net AEP (GWh) |
|---|---|---|---|---|
| **Synthetic Single Row (650m N-S)** | SW-dominant (Sector 7 = 20%) | **8.19%** | 575.80 | 528.64 |
| **Synthetic Single Row (650m N-S)** | Omnidirectional (uniform) | **7.76%** | 575.80 | 531.11 |
| **Recorded WGS84 Layout** | Omnidirectional (uniform) | **17.39%** | 575.80 | 475.64 |
| **Recorded WGS84 Layout** | SW-dominant (Sector 7 = 20%) | **19.33%** | 575.80 | 464.48 |

**Finding**: Layout geometry alone (staggered 2.3–2.8 D spacing vs 3.28 D straight line) accounts for **+9.63 pp** of the gap under uniform wind, and **+11.14 pp** under the actual directional rose.

### 2.2 Directional Alignment with Prevailing SW Monsoon
- The Kalpitiya peninsula experiences strong Southwest monsoon winds. The 12-sector wind rose concentrates **50% of annual wind frequency in Sectors 6, 7, and 8** (180°, 210°, and 240°), with Sector 7 (210°) alone carrying **20.0%**.
- Pairwise geometric analysis of the recorded layout reveals that adjacent turbine strings align directly along bearings of **190° to 203°**:
  - T1 $\rightarrow$ T2: bearing **200.7°**, distance 621.1 m ($3.14\text{ D}$)
  - T2 $\rightarrow$ T3: bearing **202.3°**, distance 526.2 m ($2.66\text{ D}$)
  - T3 $\rightarrow$ T4: bearing **200.1°**, distance 656.7 m ($3.32\text{ D}$)
  - T5 $\rightarrow$ T7: bearing **203.2°**, distance 461.8 m ($2.33\text{ D}$)
  - T8 $\rightarrow$ T10: bearing **202.4°**, distance 619.1 m ($3.13\text{ D}$)
  - T12 $\rightarrow$ T13: bearing **189.9°**, distance 495.1 m ($2.50\text{ D}$)
- When monsoon winds blow from 200°–210°, each downwind turbine operates directly in the near wake of its upwind neighbor. This directional alignment adds an additional **+1.94 pp** of wake deficit over an omnidirectional wind distribution.

### 2.3 Machine Size / Rotor Diameter Proxy Scaling
The recorded coordinates were originally surveyed from developer site road plans (`ENVISION_ROAD-DATA.pdf`) designed for ~3.3 MW or 4 MW turbines ($D \approx 120\text{ m} - 140\text{ m}$).
When the model substituted the **IEA 10 MW reference machine ($D = 198\text{ m}$)**:
- Rotor swept area increased by $(198 / 120)^2 = \mathbf{2.72\times}$.
- Physical spacing in terms of rotor diameters dropped from **~4.2 D** down to **2.5 D**.

Simulating machine diameter sweeps across the fixed recorded layout shows:
- $D = 120\text{ m}$ (3.3 MW class): wake loss = **9.79%** (close to the historical 7.28% basis).
- $D = 140\text{ m}$ (4.0 MW class): wake loss = **12.22%**.
- $D = 160\text{ m}$: wake loss = **14.68%**.
- $D = 180\text{ m}$: wake loss = **17.14%**.
- $D = 198\text{ m}$ (IEA 10 MW): wake loss = **19.33%**.

**Conclusion**: The historical 7.28% frozen calibration reflects the aerodynamic performance of smaller-rotor turbines (~120 m). Placing 198 m rotors into a layout spaced at 450–550 m mechanically drives aerodynamic wake loss to ~19.3%.

### 2.4 Deficit Models & Atmospheric Turbulence
- **Turbulence Intensity**: Coastal sites have lower ambient turbulence ($TI \approx 0.06 - 0.08$), which slows wake recovery (smaller expansion coefficient $k^*$). At $TI = 0.06$, live wake loss rises to **22.23%**. At engine default $TI = 0.10$, wake loss is **19.33%**.
- **Deficit Model**: TurbOPark (TurboGaussian) predicts **23.75%** wake loss on the recorded layout, confirming that Bastankhah-PorteAgel (19.33%) is not an outlier over-prediction.

---

## 3. Bankable P50/P90 Sensitivity Disclosure

Applying the standard DutchBay non-wake loss retention chain (97% availability $\times$ 98% electrical $\times$ 98% curtailment $\times$ 99% other = **92.24% retention**) and the default IEC 20-year uncertainty budget (`wind_resource.bankable_aep.exceedance_levels`):

| Metric | Frozen Calibration (7.32% Wake Loss) | Live PyWake (19.44% Wake Loss) | Delta ($\Delta$) | Rel. Change (%) |
|---|---|---|---|---|
| **Wake Retention** | 92.68% | 80.56% | -12.12 pp | -13.08% |
| **Total Retention** | 85.48% | 74.30% | -11.18 pp | -13.08% |
| **Gross Energy (14 Turbines)** | 537.41 GWh/yr | 537.41 GWh/yr | 0.00 GWh/yr | 0.00% |
| **P50 Net Energy** | **459.36 GWh/yr** | **399.29 GWh/yr** | **-60.07 GWh/yr** | **-13.08%** |
| **P90 1-Year Net Energy** | **400.05 GWh/yr** | **347.73 GWh/yr** | **-52.32 GWh/yr** | **-13.08%** |
| **P90 20-Year Life Net Energy** | **404.67 GWh/yr** | **351.75 GWh/yr** | **-52.92 GWh/yr** | **-13.08%** |

---

## 4. Engineering Recommendations

1. **Retain 7.32% for Lender Case / P50 Baseline Under GWTF Governance**: Any un-gated mutation of committed project AEP would violate lender-grade change protocols and move committed equity IRRs.
2. **Disclose as Formal Scenario Sensitivity**: Provide `conf/sensitivity/wake_live_pywake.yaml` or an explicit sensitivity flag exposing the 19.44% wake loss and -60.07 GWh/yr P50 variance.
3. **Site Suitability & Loads Clearance (#1568 domain N-1)**: 2.28–2.82 D spacing along prevailing wind corridors creates severe effective turbulence ($\sigma_{\text{eff}}$ / IEC 61400-1 ed. 4 wake-added turbulence) on downwind machines (especially T2/T3/T4 and T5/T7/T9). OEM approval and structural fatigue analysis are mandatory prior to physical procurement.
