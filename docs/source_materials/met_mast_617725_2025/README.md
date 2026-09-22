# Met-mast export 617725 — 20 March to 8 November 2025

A 10-minute met-mast export supplied by the project owner and ingressed on 22 September
2026. The source itself says it was created on **10 November 2025 at 16:23**. That embedded
creation time, not the local download timestamp, is the record's chronological date.

The source is the first primary met-mast time series found in the Dutch Bay / Kalpitiya
corpus. It materially improves the evidence base, but it is a partial, pre-filtered export
whose site identity, timezone, instrumentation and operating history are not documented.
It is therefore held as primary evidence with a **HOLD** on annual or lender-grade use.

The interval-level source is confidential and remains only in the private
`arunakulat/DutchBay_RAG` repository. This public DutchBay EPC package is the governed home
for every extraction, aggregate, figure, evaluation, manifest, validation receipt and
reproducibility script produced from it.

## Source identity

| Item | Source value or status |
|---|---|
| Raw filename | `617725数据导出.txt` |
| SHA-256 | `a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46` |
| Size | 8,758,675 bytes |
| Private source location | `arunakulat/DutchBay_RAG`, commit `52ae2fecb05f84497a68d00affbd95f4b0c18986`, `corpus/met_mast_617725_2025/raw/617725数据导出.txt` |
| Embedded creation time | 2025-11-10 16:23; timezone not stated |
| Measurement period | 2025-03-20 23:40 to 2025-11-08 23:50; timezone not stated |
| Coordinates | 8.056318° N, 79.708150° E |
| Elevation | 5 m |
| Interval | 10 minutes; timestamps mark the beginning of each interval |
| Export filter | `Included flags: <Unflagged data>`; excluded-flags field blank |
| Project/site identity | Not stated |
| Meaning of `617725` | Not stated; it is not assumed to be a mast identifier |

The first 12 lines of the attachment are source metadata. They contain no request or
instruction to the analyst. The project owner's request governs this ingress.

## Contents

| Directory | Holds |
|---|---|
| `extracted/` | Lossless metadata and column profiles, QC events, descriptive statistics, sector and monthly tables, structured summary, and a QC overview figure |
| `evaluation/` | The source-grounded ingress and wind-resource evaluation |
| `registers/` | The deterministic analysis generator and its embedded validation assertions |
| Package root | The derived-artifact manifest and the hash-only private-source manifest |

All 57 source columns are represented and profiled: the timestamp plus 56 measurement
channels for wind speed, wind direction, temperature, relative humidity and pressure. Empty
and near-empty channels are recorded rather than silently dropped. The interval rows
themselves are not published here.

## Key result

The clean assessment window is 21 March 2025 18:00 through 8 November 2025 23:50:
33,347 present rows out of 33,444 expected (99.710% timestamp completeness). It covers only
232.24 days and heavily weights the southwest-monsoon months. It cannot establish an annual
mean or a long-term wind climate.

| Height | Valid mean-speed rows | Coverage of expected intervals | Observed mean (m/s) | Weibull MLE k | Weibull MLE A (m/s) |
|---:|---:|---:|---:|---:|---:|
| 30 m | 33,347 | 99.710% | 7.562 | 2.615 | 8.482 |
| 50 m | 33,347 | 99.710% | 8.320 | 2.921 | 9.307 |
| 80 m | 33,347 | 99.710% | 8.358 | 3.045 | 9.340 |
| 100 m | 33,347 | 99.710% | 8.433 | 3.030 | 9.418 |
| 120 m | 31,201 | 93.293% | 8.793 | 3.260 | 9.798 |

The 120 m observed mean is **available-case**, not like-for-like: its speed channel is absent
from 13–27 October, a relatively low-wind part of this partial record. A transparent
sensitivity fills only those missing 120 m values from the concurrent 100 m channel using
the median high-wind 120/100 ratio and extrapolates the resulting full-window mean to 130 m.
It gives 8.628 m/s, versus the Kalpitiya proposal's 8.97 m/s. That is a diagnostic comparison,
not a replacement series or direct site validation: the mast is 16.4 km from the proposal
centre and 24.2 km from the Dutch Bay model centroid.

## Evidence disposition

**Usable now:** preliminary wind-regime characterisation, channel-level QC, directional and
vertical-profile screening, and preparation for a future measure-correlate-predict study.

**Not usable alone:** annual long-term wind speed, bankable P50/P75/P90, direct validation of
either project site, warranty assessment, or certified power-performance work.

No value from this record has been promoted into a model scenario or lender output. The full
reasoning and information request are in
`evaluation/Met_Mast_617725_Ingress_and_Wind_Resource_Evaluation_2026-09-22.md`.

## Reproducing

From this package, using the DutchBay governed Python 3.12 environment:

```bash
DUTCHBAY_MET_MAST_617725_SOURCE=/path/to/private/617725数据导出.txt \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python \
  registers/analyze_met_mast_617725_2026-09-22.py
```

The run used Python 3.12.13, pandas 2.3.3, NumPy 2.4.6, SciPy 1.18.1 and Matplotlib
3.11.1. The script asserts the source hash, dimensions, timestamp bounds, missing-interval
count, assessment dimensions and core QC invariants before writing derived files. Repeated
runs produce byte-identical outputs.

## Integrity

`MANIFEST.sha256` records every public derived file except itself. Verify it from this
directory with:

```bash
shasum -a 256 -c MANIFEST.sha256
```

`PRIVATE_SOURCE_MANIFEST.sha256` records the confidential source's immutable identity and
private-repository path. It is a cross-repository receipt, not a claim that the source exists
in this public checkout.

## Handling

The source carries no explicit confidentiality label, copyright notice or publication grant.
The project owner directed on 22 September 2026 that the secure RAG repository retain only
the confidential source document and that every datum derived through governed ingress return
to the DutchBay EPC repository. Accordingly, the raw interval series remains private while
the aggregates and evaluation in this package are public project evidence. Do not publish or
forward the raw or interval-level data without separate authority.
