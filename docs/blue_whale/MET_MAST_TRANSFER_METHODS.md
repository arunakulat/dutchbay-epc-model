# Blue Whale wind: met-mast 617725 transferred to the turbine site

**Prepared:** 1 November 2026, model 15.16.0, Blue Whale PR 5.

**Work item:** <https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6556910250>

**Status:** screening result. **HOLD: not lender-grade.** The met-mast package's HOLD on
annual, P50/P90 and lender use stands (`docs/source_materials/met_mast_617725_2025/README.md`).

Owner direction, 1 November 2026, verbatim: "use the kalpitiya met-mast evidence from RAG repo
and interpolate to obtain wind rose and more detailed wind evidence. the two locations are near
to each other on the same coastline"

Every figure below is in `met_mast_transfer_summary.json`, written by
`scripts/run_blue_whale_met_mast_transfer_v14.py` from `conf/blue_whale_met_mast_transfer.yaml`.
The method is `analytics/wind/met_mast_transfer.py`. Only aggregates are published: no
10-minute row, no hourly series derived from the mast and no power-curve value.

## Sources

| Input | Identity | Handling |
|---|---|---|
| Met-mast export 617725, 10-minute, 30-120 m, 8.056318 N 79.708150 E | SHA-256 `a1996369...2cd46`, 8,758,675 bytes; checked against the package's `PRIVATE_SOURCE_MANIFEST.sha256` before use (the run refuses a mismatch) | Private (DutchBay_RAG); read through `DUTCHBAY_MET_MAST_617725_SOURCE` |
| NASA POWER hourly, MERRA-2, WS50M, WD50M, WS10M, UTC, 2015-2025 | `https://power.larc.nasa.gov/api/temporal/hourly/point`, `community=RE`, `time-standard=UTC`, API v2.10.3, retrieved 1 November 2026, at the mast and at the turbine, now DutchBay T2 (8.292500 N 79.754700 E; until 2026-11-07 the #1530 position, 79.752666 E). Each year's data block is pinned by SHA-256 in the config. Re-fetched at T2 on 2026-11-07: all 11 data blocks are byte-identical to those at the #1530 position (the same MERRA-2 cell), so the pins and every wind result are unchanged. A local copy fetched at the old point must be re-fetched, because the run checks each file's coordinates against the config | Public; read through `DUTCHBAY_NASA_POWER_DIR`. The files carry a per-request timing field, so the data block, not the file, is pinned |
| Envision EN-206/10.5 curve, de-rated to 9.5 MW by clipping | Read at run time from outside the repository, as #1530 | Confidential; only derived AEP and CF are published (owner decision, #1353 comment 6554211155) |
| Density 1.15 kg/m3 and loss stack 7.77% | #1530's basis, read through `conf/blue_whale_wind_siting.yaml` | Public |

The two POWER points fall in different MERRA-2 cells (stated elevations 55.43 m and 41.24 m).
Their 2015-2025 WS50M means are 6.791 and 6.887 m/s, hourly correlation 0.969.

## Method

1. **QC.** The package's documented QC: the assessment window starts at 21 March 2025 18:00
   (after the commissioning block, QC-001); channel nulls (the 120 m speed outage QC-020, the
   120 m direction outages QC-021 to QC-024) are excluded per channel and never filled; the 97
   absent intervals of 28 October (QC-012) stay absent. Range checks (speed 0-50 m/s,
   direction 0-360 degrees) flag nothing. Temperature reset rows (QC-030, QC-031) are excluded
   from the density estimate. Hours are kept only when all six 10-minute values are present.
2. **Timezone.** The export states none. Three lines of evidence, recomputed and checked on
   every run (it refuses to run if they disagree with the configured offset):
   - the semidiurnal (S2) pressure tide, a solar-time clock independent of any reference,
     peaks at 09:47 on the mast clock (monthly 09:31 to 09:58). With the tropical S2 maximum
     near 10:00 local solar time and the mast at 79.708 E (UTC+5.31 h solar), the implied
     offset is UTC+5.10 h;
   - the 10 m temperature peaks at 13:43 on the mast clock, 13:31 local solar time under
     UTC+05:30;
   - against the UTC reference, the hourly speed correlation is flat from UTC+4 to UTC+7
     (0.78888 at +5.0 h, 0.78879 at +5.5 h), and the sub-daily wind-component anomalies
     (the sea-breeze cycle) correlate best near +4 to +5 h and worst at UTC (0.26) and
     UTC+8 (0.16).
   UTC and China Standard Time (UTC+8), the two other plausible clocks, are rejected. The
   finding is **UTC+05:30, Sri Lanka Standard Time**. A clock of UTC+5.0 or +6.0 h changes the
   long-term mean speed by 0.02%.
3. **Correlation (MCP).** Concurrent mast and reference-at-mast hours, binned in 16 sectors by
   the reference direction. The transfer is the variance ratio (`wind_resource.mcp`), which
   keeps the mast's variance and so the energy-bearing tail. OLS is a sensitivity. A sector fits
   its own transfer only with at least 200 hours and R^2 at least 0.3, otherwise the
   omnidirectional fit stands in. **Stop threshold:** hourly R^2 at least 0.49 and daily r at
   least 0.8. Observed: 120 m hourly R^2 0.610 (5,198 h), daily r 0.881 (216 days); 100 m 0.622
   and 0.888. `wind_resource.mcp.run_mcp` records the campaign as `below_iec_bankable`
   (3,562 hours short of 12 months).
4. **Direction.** Each long-term hour is carried as 10 equal copies, rotated by the mid-point
   deciles of the measured 80 m minus reference direction in its reference sector (pooled for
   sparse sectors). A single mean veer per sector would collapse the measured scatter: over the
   concurrent hours it misplaces up to 19.2 points of sector frequency, the decile method 3.2.
5. **Long-term correction.** The transfer is applied hour by hour to every reference hour of
   2015-2025 (11 complete years, including the concurrent 2025). Each calendar month therefore
   enters with its own long-term reference hours and its calendar weight: the monsoon months are
   not weighted by the record's coverage. 2015-2024 and 2016-2025 are sensitivities.
6. **Shear to 130 m.** From the mast's concurrent 100 and 120 m means, by sector (80 m
   direction) and day/night (06:00-17:59 local): SSW 0.038 / 0.040, SW 0.080 / 0.085,
   WSW 0.124 / 0.114 (night / day), other sectors the day/night all-sector values 0.101 / 0.097.
   The move from 120 to 130 m raises the mean by 0.74%.
7. **Mast to turbine (26.7 km).** By mast-cell direction sector, over 2015-2025: the ratio of
   the turbine cell's mean WS50M to the mast cell's (all-sector 1.0141; 0.925 to 1.429 by
   sector) and their circular-mean direction difference (all-sector -2.4 degrees), the
   direction difference interpolated between sector centres.
8. **Yield.** Gross AEP is the frequency-weighted sum of the 16 sector Weibull yields at 130 m
   through `analytics.wind.aep_tornado.gross_aep_farm_gwh`, with #1530's density factor and loss
   stack. Cross-checks: the omnidirectional Weibull through #1530's `single_turbine_yield`
   (integrators within 0.0007% of each other) and the hourly time series.

## Results

### MCP at 120 m (variance ratio)

| Sector | Hours | Fit | Slope | Intercept (m/s) | R^2 | Residual SD (m/s) |
|---|---:|---|---:|---:|---:|---:|
| SSW | 393 | sector | 1.5594 | -1.233 | 0.496 | 1.81 |
| SW | 1,911 | sector | 1.2053 | 0.367 | 0.599 | 1.61 |
| WSW | 2,085 | sector | 1.1281 | -0.037 | 0.490 | 1.96 |
| W | 260 | sector | 0.9532 | 0.182 | 0.360 | 2.37 |
| other 12 | 9-105 each (549 in all) | omni | 1.1398 | 0.310 | 0.004-0.392 | 1.69-2.73 |
| omni | 5,198 | - | 1.1398 | 0.310 | 0.610 | 1.98 |

### Long-term wind at the turbine, 130 m (2015-2025)

Mean 8.243 m/s; omnidirectional Weibull A 9.207 m/s, k 3.044 (Weibull mean 8.227 m/s);
annual means 7.96 (2018) to 8.51 (2025) m/s, CoV 1.86%.

| Sector | Frequency | Mean (m/s) | A (m/s) | k | Energy share (v^3) |
|---|---:|---:|---:|---:|---:|
| N | 3.79% | 7.10 | 7.94 | 2.85 | 2.50% |
| NNE | 7.86% | 7.72 | 8.51 | 3.79 | 5.84% |
| NE | 11.18% | 7.75 | 8.50 | 4.24 | 8.10% |
| ENE | 7.74% | 7.22 | 7.96 | 3.78 | 4.69% |
| E | 4.49% | 6.62 | 7.37 | 3.14 | 2.28% |
| ESE | 2.09% | 5.59 | 6.29 | 2.52 | 0.74% |
| SE | 1.36% | 5.00 | 5.67 | 2.11 | 0.41% |
| SSE | 1.22% | 5.38 | 6.11 | 1.93 | 0.49% |
| S | 2.94% | 7.49 | 8.45 | 2.50 | 2.47% |
| SSW | 12.44% | 8.85 | 9.84 | 3.38 | 14.69% |
| SW | 26.59% | 9.50 | 10.49 | 3.86 | 36.92% |
| WSW | 12.72% | 9.27 | 10.28 | 3.49 | 17.01% |
| W | 1.28% | 7.17 | 8.08 | 2.09 | 1.08% |
| WNW | 0.83% | 5.30 | 5.98 | 1.74 | 0.39% |
| NW | 1.04% | 5.67 | 6.39 | 1.72 | 0.59% |
| NNW | 2.44% | 7.07 | 7.95 | 2.39 | 1.79% |

SSW to WSW (the southwest monsoon) carry 51.8% of hours and 68.6% of the wind energy; NNE to
ENE (the northeast monsoon) 26.8% and 18.6%. Figure: `met_mast_wind_rose_130m.png`; table:
`met_mast_wind_rose_130m.csv`. Monthly means (local time) run from 4.99 m/s (April) to
10.81 m/s (June); the diurnal mean peaks near 22:00 local (8.84 m/s) and dips near 07:00
(7.64 m/s).

### Measured shear, turbulence and density (concurrent period only)

- Five-height concurrent means (31,201 rows): 7.748, 8.525, 8.556, 8.629, 8.793 m/s at 30, 50,
  80, 100, 120 m. Power-law exponent 0.080 (30-120 m fit), 0.066 (80-120 m), 0.1032 (100-120 m);
  day 0.101 and night 0.105 on 100-120 m.
- Turbulence intensity from the SD channels (10-minute SD / mean, speed at least 3 m/s). At
  120 m: mean TI 0.147 at 3-4 m/s, 0.066 at 9-11 m/s, 0.0710 at 15-16 m/s (representative,
  mean + 1.28 SD, 0.090). By sector the main monsoon sectors run 0.070-0.076 and the other
  sectors 0.09-0.18. This is not an IEC turbulence class: logger averaging, sensor and boom
  details and sector screening are undocumented.
- Air density at 130 m from the mast's pressure, temperature and humidity: 1.137 kg/m3 over
  March to November. It covers the hot months only, so #1530's 1.15 kg/m3 is kept; the
  mast's value lowers net AEP by 0.6% (sensitivity).

### Yield and the change from #1530

| Basis | Mean at 130 m | Net AEP | Net CF |
|---|---:|---:|---:|
| #1530, DutchBay ERA5 Weibull (A 8.036, k 2.665) | 7.143 m/s | 31.146 GWh | 0.374256 |
| ERA5 shape (k 2.665) with this transfer's mean | 8.243 m/s | 39.929 GWh | 0.479803 |
| This transfer, omnidirectional Weibull | 8.227 m/s | 40.456 GWh | 0.486135 |
| **This transfer, 16 sector Weibulls (P50)** | 8.243 m/s | **40.575 GWh** | **0.487560** |

Gross 43.994 GWh (CF 0.5287); losses 7.77%. Of the +9.43 GWh, the mean speed accounts for
+8.78, the steeper distribution (k 3.04 against 2.665) +0.53 and the sector split +0.12;
density and losses are unchanged. The speed level builds as: reference at the mast cell
6.791 m/s at 50 m; mast 120 m long-term 8.058; at 130 m 8.117 (shear x1.0074); turbine 8.243
(transfer x1.0155).

**Long-term correction.** The measured concurrent 120 m mean is 8.794 m/s; the long-term
120 m mean at the mast is 8.058, a factor of 0.916 (the reference's own long-term-to-concurrent
ratio is 0.912). By month, the long-term mean over the measured 2025 mean is 0.81 (April) to
1.09 (November), and 0.98-1.06 in June to October. The long-term hour shares equal the calendar
shares to 0.07 points, and the calendar-weighted monthly means reproduce the long-term mean
exactly, so the monsoon months are not double-weighted. December, January and February have no
concurrent data and are transferred with the omnidirectional fit. The long-term 130 m mean at
the turbine (8.243 m/s) is **below** the mast's own concurrent 120 m mean (8.794) and below the
package's outage-adjusted 130 m figure for the measured period (8.628), as it should be.

### Sensitivities (net AEP)

| Case | Mean (m/s) | Net AEP (GWh) | Net CF |
|---|---:|---:|---:|
| Primary | 8.243 | 40.575 | 0.487560 |
| 2015-2024 | 8.217 | 40.351 | 0.484866 |
| 2016-2025 | 8.257 | 40.699 | 0.489056 |
| 100 m transfer, sheared 100 to 130 m | 8.196 | 40.116 | 0.482043 |
| OLS instead of variance ratio | 8.492 | 43.835 | 0.526733 |
| One omnidirectional transfer | 8.226 | 40.554 | 0.487311 |
| Sparse sectors take their own concurrent bias | 8.051 | 38.876 | 0.467149 |
| No site transfer (mast at 130 m) | 8.117 | 39.530 | 0.475001 |
| Clock UTC+5.0 / +6.0 h | 8.245 / 8.241 | 40.608 / 40.532 | 0.487964 / 0.487044 |
| Mast density 1.137 kg/m3 | 8.243 | 40.317 | 0.484458 |

### Uncertainty and exceedance

Speed uncertainties (1 sigma) are converted to energy with the yield's own sensitivity,
d ln(AEP) / d ln(v) = 1.668, and combined by `wind_resource.bankable_aep.exceedance_levels`.

| Component | Speed | Energy | Basis |
|---|---:|---:|---|
| Measurement (undocumented sensors, calibration, booms) | 3.0% | 5.00% | assumed; above the 2-2.5% of a documented MEASNET cup |
| MCP correlation | 1.53% | | omni residual SD / sqrt(216 days) / mean |
| Concurrency and season (232 days) | 3.15% | | leave-one-month-out jackknife of the long-term mean |
| Long-term window | 0.61% | | half the window range, with IAV / sqrt(11) |
| Clock offset | 0.02% | | half the +5.0 / +6.0 h range |
| MCP method | | 4.02% | half the OLS-minus-variance-ratio AEP |
| Sparse (northeast-monsoon) sectors | | 4.19% | the bias-corrected sensitivity |
| Long-term, combined | | 8.29% | |
| Shear extrapolation 120 to 130 m | 0.20% | 0.33% | hour-weighted SD of the sector/day-night exponents |
| Transfer over 26.7 km | 4.0% | 6.67% | assumed; the reanalysis cannot resolve the coastal gradient |
| Resource, combined | | 11.77% | |
| Power curve | | 5.0% | repository default |
| Interannual variability | 1.86% | 3.10% | annual-mean CoV of the transferred series |

P50 40.57 GWh; 1-year sigma 13.16%: P75 36.97, **P90 (1 year) 33.73 GWh**; 20-year sigma
12.80%: **P90 (20 years) 33.92 GWh** (net CF 0.4054 and 0.4076).

### Shadow flicker, expected case

At the placeholder-lot receptors (`conf/blue_whale_wind_siting.yaml`), with the turbine on
DutchBay T2 (owner, 2026-11-07; re-run that day, and only these receptor figures changed),
hours per year: the
astronomical worst case; #1530's expected case (sunshine, operating probability 0.930, rotor
always facing the sun); and the realistic case here, with the rotor yawed into the long-term
wind (month by sector, five yaw angles per sector) and turning only when the hub speed lies in
the curve's producing range (94.1% of hours).

| Receptor | Distance (m) | Worst case | #1530 expected | Expected, yawed |
|---|---:|---:|---:|---:|
| corner_ne | 50 | 2,194.4 | 1,856.6 | 733.3 |
| mid_north | 106 | 1,425.9 | 1,260.8 | 445.1 |
| mid_west | 292 | 437.4 | 359.3 | 208.0 |
| corner_sw | 388 | 273.0 | 209.1 | 171.8 |
| corner_nw | 258 | 423.5 | 340.9 | 167.3 |
| mid_east, corner_se, mid_south | 146, 294, 309 | 0 | 0 | 0 |

Five of eight boundary receptors still exceed the 8 h/yr expected-case guidance (six at the
#1530 position). The receptors
are lot-boundary points, not dwellings (input B08).

## Assumptions

- The mast clock is UTC+05:30 (evidence above).
- The variance-ratio transfer fitted on March to November applies to December to February
  through the omnidirectional fit, because those months have no concurrent data.
- MERRA-2's cell-to-cell relationship represents the coastal gradient between the mast and the
  turbine. The two sites are on the same coastline, 26.7 km apart (owner direction above).
- Shear between 120 and 130 m equals that measured between 100 and 120 m, by sector and
  day/night; shear at the turbine equals shear at the mast.
- #1530's density (1.15 kg/m3), loss stack (7.77%), de-rate by clipping, and placeholder site.

## Limitations

- 232 days, monsoon-weighted, pre-filtered and undocumented (no sensor, calibration, boom,
  logger, site identity or flag dictionary): package evaluation section 9 lists what lifts the
  HOLD.
- 549 concurrent hours in the 12 sectors outside SSW to W; the northeast-monsoon sectors carry
  27% of long-term hours but are transferred by the omnidirectional fit.
- Hourly R^2 0.61 is moderate. Monthly in-sample bias of the transfer ranges from -5% (April)
  to +10% (July, March).
- MERRA-2 cells are 0.5 x 0.625 degrees and partly land; their diurnal timing differs from the
  mast's by one to two hours, so the long-term diurnal profile carries MERRA-2's timing.
- The sector-Weibull gross AEP is 3.6% below the hourly time-series integration (45.62 GWh);
  the Weibull basis is kept as the requested and more conservative one.
- The 120 m channel has a 15-day outage (QC-020); the 120 m fit uses only concurrent hours.
- Nothing here is a bankable energy yield assessment, an IEC site-suitability or turbulence
  class, or a validation of the turbine site.
