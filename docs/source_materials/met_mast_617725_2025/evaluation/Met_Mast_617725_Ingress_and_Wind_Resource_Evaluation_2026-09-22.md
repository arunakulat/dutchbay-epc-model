# Met-mast export 617725 — ingress and wind-resource evaluation

**Prepared:** 22 September 2026

**Original record creation:** 10 November 2025 16:23, as embedded in the export

**Source:** one UTF-8 tab-delimited text export supplied by the project owner

**Status:** confidential source accepted into the private corpus; governed derivatives
accepted into DutchBay EPC; annual and lender use **HOLD**

---

## 1. What was received

The attachment is a 10-minute met-mast export with 33,456 rows and 57 columns. It covers
20 March 2025 23:40 through 8 November 2025 23:50. The source header supplies coordinates,
elevation, calm threshold, export filtering and timestamp semantics. It does not identify the
mast, project, owner, logger, sensors or timezone.

| Field | Evidence |
|---|---|
| Filename | `617725数据导出.txt` |
| SHA-256 | `a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46` |
| Bytes | 8,758,675 |
| Embedded export creation | 2025-11-10 16:23; timezone absent |
| Local file birth/modification | 2026-09-21 21:07:13 +05:30; treated as delivery metadata, not record creation |
| Coordinates | 8.056318° N, 79.708150° E |
| Elevation | 5 m |
| Calm threshold | 0 m/s |
| Included flags | `<Unflagged data>` |
| Excluded flags | Blank field |
| Timestamp convention | Beginning of interval |

The source header contains metadata, not analyst instructions. No embedded content alters the
project owner's request or the governance applied here.

The private RAG copy is hash-identical to the attachment and is pinned at commit
`52ae2fecb05f84497a68d00affbd95f4b0c18986`.
Its non-ASCII filename is deliberately preserved. The token `617725` is not decoded or
treated as a mast number because the source does not define it. No interval row is copied into
this public repository.

## 2. Schema and lossless treatment

The timestamp is followed by 56 measurement columns:

- wind-speed average, minimum, maximum and standard deviation at 30, 50, 80, 100 and 120 m;
- wind-direction average, minimum, maximum and standard deviation at 30, 80 and 120 m;
- temperature average, minimum, maximum and standard deviation at 0, 10 and 120 m;
- relative-humidity average, minimum, maximum and standard deviation at 10 m; and
- pressure average, minimum, maximum and standard deviation at 10 and 120 m.

`extracted/column_profile.csv` carries one row for every measurement column and preserves the
source label, unit, height, non-null count, first and last valid timestamp, missing count,
minimum, percentiles, mean, maximum and zero count. Nothing is removed from the raw source.
Interpretive exclusions affect only the derived analysis and are enumerated in
`extracted/qc_events.csv`.

## 3. Assessment boundary and timestamp continuity

The raw record opens with a commissioning/start-up block. Several average channels are absent,
and temperature, humidity and pressure contain sentinel-like values around −40.9 °C, 0% RH and
49.48 kPa. At 17:50 on 21 March, some channels first appear but pressure remains transitional.
The assessment therefore begins at **18:00 on 21 March 2025**, the first stable ten-minute
boundary after that transition.

| Window | Expected intervals | Present | Missing | Timestamp completeness |
|---|---:|---:|---:|---:|
| Entire export | 33,554 | 33,456 | 98 | 99.708% |
| Assessment, 21 Mar 18:00–8 Nov 23:50 | 33,444 | 33,347 | 97 | 99.710% |

The complete export has two absent timestamp ranges: one interval at 21 March 06:50, inside
the excluded commissioning block, and 97 intervals from 28 October 00:00 through 16:00.
No timestamps are duplicated or out of order. Missing rows are reported and not interpolated.

The assessment lasts **232.24 days**, about 7.6 months. March and November are partial, and
the record strongly weights the southwest-monsoon season. A direct average of this period is
not an annual mean.

## 4. Wind-speed observations

### 4.1 Per-channel available-case statistics

| Height | Valid n | Coverage | Mean | Median | SD | P05 | P95 | Max average | Weibull k | Weibull A |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 m | 33,347 | 99.710% | 7.562 | 8.160 | 3.137 | 1.950 | 12.050 | 16.880 | 2.615 | 8.482 |
| 50 m | 33,347 | 99.710% | 8.320 | 8.950 | 3.172 | 2.490 | 12.770 | 17.810 | 2.921 | 9.307 |
| 80 m | 33,347 | 99.710% | 8.358 | 8.860 | 3.065 | 2.810 | 12.840 | 18.220 | 3.045 | 9.340 |
| 100 m | 33,347 | 99.710% | 8.433 | 8.920 | 3.092 | 2.850 | 12.970 | 18.390 | 3.030 | 9.418 |
| 120 m | 31,201 | 93.293% | 8.793 | 9.230 | 3.029 | 3.380 | 13.320 | 18.810 | 3.260 | 9.798 |

Values are m/s except Weibull shape `k`; `A` is m/s. Weibull parameters are two-parameter
maximum-likelihood fits with location fixed at zero. They describe this partial record only.

The source contains no negative wind speeds. Among rows with all three values present, no
speed channel violates `minimum <= average <= maximum`.

### 4.2 The 120 m available-case mean is selectively biased

The 120 m average-speed channel is null for 2,146 otherwise present rows from 13 October
02:20 through 27 October 23:50. The lower channels remain available during this relatively
low-wind period. Consequently 8.793 m/s at 120 m is not comparable with the full-window means
at lower levels.

A sensitivity—not a source correction—uses the median 120/100 ratio of 1.016456 on concurrent
rows where both speeds are at least 3 m/s, and applies it only to the missing 120 m rows. The
resulting full-window 120 m proxy averages 8.592 m/s. Extrapolating it to 130 m with the
five-height median shear exponent of 0.051231 gives **8.628 m/s**.

A separate linear model fitted before the outage and tested after the channel returned has
post-return MAE 0.097 m/s, mean error −0.040 m/s and RMSE 0.162 m/s. That supports the use of
100 m as a sensitivity predictor, but it does not turn reconstructed values into measurements.
Neither proxy is written back into the source or the observed statistics.

### 4.3 Concurrent vertical profile and shear

There are 31,201 rows where all five mean-speed channels are present. On that common basis:

| Height | Concurrent mean (m/s) | Concurrent median (m/s) |
|---:|---:|---:|
| 30 m | 7.748 | 8.340 |
| 50 m | 8.525 | 9.150 |
| 80 m | 8.556 | 9.050 |
| 100 m | 8.629 | 9.100 |
| 120 m | 8.793 | 9.230 |

For 28,382 common rows with every mean speed at least 3 m/s, the five-height log-linear shear
exponent has median 0.0512, mean 0.0805 and P05–P95 range 0.0150–0.2783. A two-point 30–120 m
calculation has median 0.0619. These are descriptive interval statistics, not a design shear
assessment: boom orientation, flow-distortion sectors, calibration and sensor-change history
are absent.

## 5. Direction and turbulence screening

The 80 m direction channel is the most complete high-level direction series. Paired with 80 m
wind speed, it has 33,347 valid observations, a circular mean of 226.0° and mean resultant
length 0.832. The SW and WSW sectors contribute **71.51% of observations** and **87.96% of
speed-cubed exposure**. This confirms a strongly concentrated southwest-monsoon regime within
the observed months, not an annual directional climate.

Turbulence intensity (`speed SD / mean speed`) was summarized only where mean speed is at
least 3 m/s. Median TI declines from 0.101 at 30 m to 0.070 at 120 m; 95th-percentile TI
declines from 0.260 to 0.124. Without logger averaging details, sensor/boom metadata, sector
screening and IEC binning, these values do **not** establish an IEC turbulence class.

## 6. Channel and data-quality findings

The principal QC events are in `extracted/qc_events.csv`. Material findings are:

1. The commissioning/start-up block through 21 March 17:50 contains absent average channels
   and physically implausible sentinel/reset values.
2. The 120 m mean-speed outage removes 2,146 present intervals (6.42% of the assessment).
3. The 120 m average direction has several outages from 13 October through 7 November.
4. The 120 m average temperature is absent for 856 present rows from 21–27 October and has
   transition/reset anomalies around the outage; 10 m temperature has three reset/glitch rows
   with minima around −40.9 °C and maxima above 130 °C.
5. Eight channels are entirely empty: direction minimum and maximum at 30, 80 and 120 m;
   0 m average temperature; and 120 m average pressure.
6. Six more channels contain only 43 commissioning rows and no usable operating-period data:
   0 m temperature minimum/maximum/SD and 120 m pressure minimum/maximum/SD.
7. The file is already filtered to “unflagged” data. No flag dictionary, excluded-row count or
   unfiltered logger archive was supplied, so the export cannot evidence what was removed.

## 7. Relationship to Kalpitiya and Dutch Bay

Great-circle distances from the source coordinates are:

| Reference | Distance |
|---|---:|
| Envision Kalpitiya 60 MW proposal centre | 16.39 km |
| Dutch Bay model centroid | 24.20 km |
| NREL Puttalam met point | 23.27 km |
| NREL Karathivu point | 26.42 km |
| NREL Wellammalal point | 30.95 km |
| NREL Narakkalliya point | 31.06 km |

The outage-adjusted 130 m sensitivity of 8.628 m/s is 3.81% below the Kalpitiya proposal's
8.97 m/s. That proximity is useful context, but the two locations are 16.4 km apart, the mast
record is not annualized, and the proposal's source period and long-term method remain absent.
It is not direct validation of the proposal.

The record also does not establish a Dutch Bay site measurement: the model centroid is 24.2
km away and no source metadata binds the mast to that project. The earlier corpus finding
“no primary mast series located” is therefore superseded in one precise respect: a primary
mast series is now present in the corpus. The earlier bankability gap remains open because the
series is partial, pre-filtered, incompletely documented and off-site relative to both named
project references.

## 8. Evidence grade and disposition

This is **strong primary measurement evidence for the stated coordinates and observed
period**, subject to the export/QC limitations above. It is not yet a bankable wind-resource
assessment.

| Use | Disposition |
|---|---|
| Preliminary wind-regime characterisation | Usable with period and QC caveats |
| Channel-level data-quality assessment | Usable |
| Directional and vertical-profile screening | Usable with metadata caveats |
| Future MCP analysis | Potentially usable after timezone and reference-series resolution |
| Annual long-term mean | **HOLD** |
| P50/P75/P90 or lender case | **HOLD** |
| Direct Kalpitiya or Dutch Bay site validation | **HOLD** |
| Warranty or certified power-performance assessment | **HOLD** |

No record-derived value is promoted into a DutchBay scenario, financial model, AEP result or
lender output by this ingress.

## 9. Information required to lift the HOLD

Request, at minimum:

1. mast/site name, land parcel and the meaning of `617725`, with explicit project binding;
2. timezone, clock convention and any clock corrections;
3. sensor manufacturer, model, serial number, height, boom orientation and calibration
   certificates;
4. mast drawing, mounting geometry and logger make/configuration, scan rate and averaging
   method;
5. commissioning, maintenance, fault, lightning/icing and sensor-change logs;
6. flag dictionary, unfiltered archive, excluded-row inventory and the tool/version that
   created this export;
7. at least one complete 12-month cycle, preferably longer; and
8. a concurrent long-term reference plus documented MCP and uncertainty methods.

## 10. Reproducibility and controls

`registers/analyze_met_mast_617725_2026-09-22.py` independently rebuilds every derived file.
It refuses to run if the raw hash, row/column count, record bounds, missing intervals,
assessment dimensions, all-null/near-empty channel counts or wind ordering invariants drift.
The run used the governed Python 3.12.13 environment with pandas 2.3.3, NumPy 2.4.6,
SciPy 1.18.1 and Matplotlib 3.11.1. Two consecutive runs produced byte-identical output.

Every public derived artifact is pinned in `MANIFEST.sha256`. The confidential source is
pinned separately in `PRIVATE_SOURCE_MANIFEST.sha256` by repository, commit, relative path,
size and SHA-256. This evaluation describes the evidence but does not replace the
machine-readable profiles or private raw bytes.

## 11. Handling

The file is unmarked, but no ownership, licence, transmittal record or public-release authority
was supplied. High-resolution met-mast data are commercially sensitive by nature. On
22 September 2026 the project owner explicitly set the repository boundary: the secure RAG
repository retains only the confidential source document, while all manifests, generated
documents, aggregate artifacts, evaluations and scripts produced by ingress are governed in
the DutchBay EPC repository. This package implements that direction. It does not publish the
raw interval series and does not imply that the source itself bears a confidentiality marking.
