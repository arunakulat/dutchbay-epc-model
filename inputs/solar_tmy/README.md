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
| Default PVGIS DB | PVGIS-SARAH3 (TMY year-span per the API's months-selected) |
| Rows | 8760 (hourly), UTC timestamps |
| Columns | `ghi`, `dni`, `dhi` (W/m²), `temp_air` (°C), `wind_speed` (m/s) |
| Annual GHI | ~1871 kWh/m² (cf. the prior declared clear-sky-scaling knob of 2000) |
| Mean ambient | ~27.0 °C (max ~33.5 °C) |

Drives the committed hybrid's re-baselined solar P50 CF **0.1685** (was 0.179; see CHANGELOG
#529). Only the five columns above are retained from the PVGIS response.

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
