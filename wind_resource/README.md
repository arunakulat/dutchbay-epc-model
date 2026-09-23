# `wind_resource/`

ERA5 reanalysis → Weibull characterisation → wake → IEC uncertainty → the bankable AEP that
feeds the finance model.

**This page points; it does not repeat.** Every number that matters lives in exactly one
authoritative place, listed under [Where the numbers live](#where-the-numbers-live). A figure
copied to a second place is a figure that will drift — this file spent nine months asserting a
lender base case the project had already retired, which is what #1279 records.

## Two paths, and which one is the headline

| | Lender path | Diagnostic path |
|---|---|---|
| Entry point | `analytics.wind.aep_summary_builder.build_aep_summary_from_config` | `wind_resource.wind_pipeline.WindPipeline` |
| Resource input | a *declared* Weibull `(A, k)` from the scenario | an hourly hub-height *timeseries* |
| AEP method | analytic integration of the curve over the Weibull | integration over the raw series |
| Feeds finance | **yes** — this is the committed headline | **no**, by design |

`energy_calculator.py` says so in its own docstring, and `analytics/wind/losses_model.py` is
shared by both so the two can never disagree on the loss stack.

The third group is the **validate-only side branches**. `weibull_fit`, `arco_assessment`,
`crossval`, `long_term_trend`, `mcp`, `era5_grid.spatial_representativeness` and
`siting_metadata` all compute an independent view of the resource and report its *drift*
against the declared baseline. None of them mutates it. Adopting a new `(A, k)`, a new
reference period or a measured interannual sigma is always a deliberate, dated config edit,
never an automatic side effect — that rule is the reason the headline is auditable.

## Module map

`docs/MODULE_REFERENCE.md`, section *Wind Resource Pipeline (ERA5 to bankable AEP)*, describes
every module in this package and its role. It is kept complete by
`tests/docs/test_module_reference_covers_wind.py`, so a new module cannot land undescribed.

## Running it

The heavy geoscience dependencies are opt-in and call-time guarded (CASPER), so this package
imports cleanly without them and fails with an actionable message if you call a path that
needs one:

```bash
pip install -e '.[wind]'        # cdsapi, xarray, netcdf4, windpowerlib, turbine-models, py-wake
pip install -e '.[micrositing]' # adds topfarm (OpenMDAO), for layout_optimizer only
```

ERA5 retrieval needs your own Copernicus CDS key in `~/.cdsapirc` — register at
<https://cds.climate.copernicus.eu>. No credential is held in this repository (CASPER).

Hydra CLIs, `key=value` only — `argparse` is banned repo-wide (R3):

```bash
python scripts/run_wind_analysis_v14.py location=dutchbay   # conf/wind_analysis.yaml
```

The full pipeline consumes a *frozen* wind export rather than calling Copernicus itself; see
the header of `run_full_pipeline_v14.py`.

## Configuration

All of it is YAML under `config/` (CCCDIR — no hidden constants, and identity fields raise
rather than default):

| File | Holds |
|---|---|
| `locations.yaml` | site definitions (`dutchbay`, `mannar`, `hambantota`) |
| `power_curves.yaml` | the turbine curve store, keyed by slug — the slug a scenario names in `resource.power_curve.curve_key` |
| `era5_config.yaml` | CDS API settings, shear bounds, loss factors, P-levels |
| `era5_request_kalpitiya.yaml` | a worked single-point ARCO request |
| `gis_export_dutchbay.yaml` | grid-export settings for `era5_grid` |

A curve reaches the store only through `power_curve_sourcing.py`, which either fetches from
the open turbine library or validates a manually entered OEM spec-sheet curve. Neither path
fabricates curve data, and both stamp provenance.

## Where the numbers live

Do not copy these into a document, a docstring or this README. Cite the path instead.

| Want | Read |
|---|---|
| The committed bankable AEP, its losses, uncertainty budget and full method note | `scenarios/aep_summary_dutchbay_10mw.json` |
| The turbine, hub height, count, Weibull and loss stack of a case | that case's file in `scenarios/` |
| Which power curve a scenario uses and where the curve came from | `resource.power_curve` in the scenario, resolved against `analytics.loader.aep_loader.APPROVED_SOURCES` |
| How gross AEP, wake, losses and P50/P75/P90 are computed | `bankable_aep.py` and `analytics/wind/{aep_tornado,losses_model}.py` |
| The chain of custody from ERA5 to the finance model | `docs/WIND_AEP_CHAIN_OF_CUSTODY.md` |
| The wind interface contract | `docs/WIND_INTERFACE_SCHEMA.md` |

## Standards

IEC 61400-12-1 for the air-density wind-speed normalisation; IEC 61400-15-2 for the loss
taxonomy and the P50/P75/P90 uncertainty build-up (note that -15-2 is the energy-yield part and
was still in draft as of 2025 — it is not the published IEC 61400-15-1:2025, which covers site
suitability input conditions); Bastankhah & Porte-Agel 2014 for the Gaussian wake deficit via
PyWake, with the Niayifar & Porte-Agel 2016 turbulence-intensity closure; MEASNET and
IEC 61400-15 practice for MCP and long-term adjustment.

## Licence

Proprietary — see the repository `LICENSE`, which grants evaluation and audit, not deployment
or redistribution.
