# Frozen solar TMY inputs (SOLAR-6/12, #529)

Frozen hourly Typical Meteorological Year (TMY) files consumed by
`solar_resource.pv_producer` when a scenario sets `resource.solar.tmy_path`. Freezing (rather
than fetching live) keeps the finance stack pvlib/network-free and the P50 reproducible — the
same discipline as the frozen ERA5 wind export (#469). Re-freezing is a deliberate, dated,
authorized re-baseline.

## `kalpitiya_pvgis_tmy_8.27N_79.75E.csv`

| Field | Value |
|---|---|
| Source | PVGIS (EU JRC) TMY API via `pvlib.iotools.get_pvgis_tmy` |
| pvlib version | 0.15.2 |
| Coordinates | lat 8.27, lon 79.75 (DutchBay PV array centroid, Kalpitiya, Puttalam) |
| Fetched | 2026-06-30 |
| Radiation database | **PVGIS-ERA5** (reanalysis, 2005-2023; TMY months per the API's months-selected). Corrected 2026-11-01 (Blue Whale PR 7); this row said PVGIS-SARAH3, which does not cover the site (see below) |
| Rows | 8760 (hourly), UTC timestamps |
| Columns | `ghi`, `dni`, `dhi` (W/m²), `temp_air` (°C), `wind_speed` (m/s) |
| Annual GHI | ~1871 kWh/m² (cf. the prior declared clear-sky-scaling knob of 2000) |
| Mean ambient | ~27.0 °C (max ~33.5 °C) |

Drives the committed hybrid's re-baselined solar P50 CF **0.1685** (was 0.179; see CHANGELOG
#529). Only the five columns above are retained from the PVGIS response.

### Radiation database: PVGIS-ERA5, not SARAH3 (corrected 2026-11-01)

Until 2026-11-01 this README said the file was built on PVGIS-SARAH3. That was wrong. Blue
Whale PR 6 (#1540) found that PVGIS-SARAH3 does not cover this point: the PVGIS 5.3 API answers
`[raddatabase=PVGIS-SARAH3] Location out of the spatial coverage of the radiation database
selected. Please, selectanother database (PVGIS-ERA5).` The PVGIS 5.3 TMY at 8.27 N, 79.75 E is
built on PVGIS-ERA5 (2005-2023) and reproduces this file (first row, months selected, annual GHI
1,871.34 kWh/m2). The frozen file is therefore an ERA5 TMY. The evidence, with the API responses'
SHA-256, is in `conf/blue_whale_capex_solar_resource.yaml` (source `PVGIS-API-5.3`) and
`docs/blue_whale/CAPEX_AND_SOLAR_RESOURCE_METHODS.md` section 5.

The owner kept ERA5 as the basis on 2026-11-01 (#1353 comment 6563070978, decision 4, verbatim:
"Keep ERA5, fix README (Recommended)"). The data file, its hash and every capacity factor
derived from it are unchanged; only this description is corrected.

**Satellite irradiance as upside, not basis.** ERA5 is a reanalysis and sits below the
satellite-based products at this site (#1540, at the Blue Whale PV centroid 8.291526 N,
79.753204 E, 2.42 km from this point):

| Source | GHI (kWh/m2/yr) | Against this TMY | Specific yield (kWh/kWp/yr) | Against pvlib on this TMY |
|---|---:|---:|---:|---:|
| This TMY (PVGIS-ERA5), pvlib 0.16.1, 8 degrees, 14% losses | 1,871.3 | - | 1,536.3 | - |
| Global Solar Atlas (Solargis 2.2.68, data to 2025) | 2,047.7 | +9.4% | 1,632.5 (PVOUT, 9 degrees) | +6.3% |
| NASA POWER (SYN1DEG), 2015-2025 annual mean | 2,046.1 | +9.3% | - | - |

On satellite irradiance an array here would yield roughly 6-9% more than the committed basis.
That is reported as upside only. Re-basing onto satellite irradiance would be a KPI-moving
re-baseline under the refresh rule below and needs an owner decision.

The reproduction snippet below does not name a database. PVGIS then selects its default for the
point, which here is PVGIS-ERA5 because SARAH3 does not cover it.

### Reproduce / refresh

```python
from pvlib.iotools import get_pvgis_tmy

data, meta = get_pvgis_tmy(8.27, 79.75, map_variables=True)  # pvlib >= 0.15 returns 2 values
frozen = data[["ghi", "dni", "dhi", "temp_air", "wind_speed"]].round(3)
frozen.index.name = "time"
frozen.to_csv("inputs/solar_tmy/kalpitiya_pvgis_tmy_8.27N_79.75E.csv")
```

A refresh that changes the modelled P50 is a KPI-moving re-baseline: re-run the producer,
re-pin `generation.technologies.solar.capacity_factor` + the hybrid `expected_results` +
`aep_summary_dutchbay_hybrid.json`, bump VERSION, and surface the delta in the CHANGELOG.
