# GIS → EPC Wind Interface Schema (`resource.wind`)

The wind/AEP handoff from the GIS resource assessment to the EPC finance model
goes through a single **normalized block**, `resource.wind`. Cashflow and metrics
depend on this stable contract — not on raw CSVs — so the resource pipeline can
evolve without breaking the finance model (Sprint 10 #22).

## The block

```yaml
resource:
  wind:
    ws150_mean_ms: 7.85       # Mean hub-height (150 m) wind speed (m/s)
    ws150_std_ms: 3.69        # Std dev of hub-height wind speed (Weibull-derived A=8.32,k=2.1)
    capacity_factor: 0.307    # Net capacity factor (0–1), matches the AEP summary
    aep_gwh: 402.6            # Net AEP (GWh), matches the AEP summary
    source_id: "OEM_ENVISION_EN171_65_PC"   # MUST be in the approved manifest (#18)
    source_type: "OEM"        # OEM / ECMWF / NREL
```

(Live example: `scenarios/dutchbay_lendercase_2025Q4.yaml`.)

## Fields & validation

| Field | Rule |
|---|---|
| `ws150_mean_ms` | number, `0 < x < 30` |
| `ws150_std_ms` | number, `>= 0` |
| `capacity_factor` | number, `0 < x <= 1` |
| `aep_gwh` | number, `> 0` |
| `source_id` | string, present in `APPROVED_SOURCES` (`aep_loader`) |
| `source_type` | one of `OEM`, `ECMWF`, `NREL` |

The specs live in `analytics/wind/wind_interface_schema.py` and reuse the #18
manifest guard (`validate_source_manifest`) for `source_id`.

## Enforcing it

```python
from analytics.schema_guard import validate_config_for_v14

# Raises ConfigValidationError listing any missing/invalid resource.wind fields.
validate_config_for_v14(parsed_config, "scenario.yaml", ["wind"])
```

`tests/analytics/test_wind_interface_schema.py` enforces that the real lender
config satisfies the schema (CI fails otherwise) and that broken blocks are
rejected.

## Adding a new source

Register it in `APPROVED_SOURCES` (`analytics/loader/aep_loader.py`) first, then
reference its `source_id` from `resource.wind` — see
[AEP_PROVENANCE.md](AEP_PROVENANCE.md).
