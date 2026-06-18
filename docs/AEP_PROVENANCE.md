# AEP Provenance Chain (lender-grade, test-enforced)

DFI/lender due diligence requires that every AEP figure in a v14 output can be
traced to an **approved, certified source**. This document describes the
provenance pattern enforced by `analytics/loader/aep_loader.py` (Sprint 10 #18).

## The approved-source manifest

`APPROVED_SOURCES` in `analytics/loader/aep_loader.py` is the single registry of
permitted AEP sources. Each entry records the `type` (OEM / ECMWF / NREL), a
human description, the governing `iec_standard`, and (for OEM) the `certificate`.

Some entries are **placeholders** kept only for back-compat — currently the
retired, extrapolated 10 MW curve `OEM_ENVISION_EN171_10_PC`. Placeholders are
listed in `PLACEHOLDER_SOURCE_IDS` (or flagged by a `PLACEHOLDER` type/description)
and must never back a lender-grade AEP while a certified OEM curve exists.

## Declaring provenance in a scenario config

Every v14 scenario declares its AEP source under `resource.power_curve`:

```yaml
resource:
  power_curve:
    source_id: "OEM_ENVISION_EN171_65_PC"   # MUST be in APPROVED_SOURCES
    source_type: "OEM"
    iec_standard: "IEC 61400-12-1:2022"
    certificate_ref: "CGC-B-FNc-2024-184 (6.5 MW certified)"
  derived_from: ["ECMWF_ERA5_2020_2024_DUTCHBAY"]   # optional upstream IDs
```

## Enforcement API

```python
from analytics.loader.aep_loader import (
    validate_config_aep_provenance,   # P0 guard: call on a parsed config
    build_provenance_aep_block,       # construct the provenance.aep block
    assert_source_in_manifest,        # raise if source_id is not approved
    is_placeholder_source,            # detect a non-certified placeholder
)

# Raises KeyError (unknown source) or ValueError (missing / placeholder-when-OEM).
prov = validate_config_aep_provenance(parsed_config)
```

`validate_config_aep_provenance` returns the standardized **`provenance.aep`**
block that belongs in v14 outputs (JSON / CSV / summary):

```json
{
  "aep_source_id": "OEM_ENVISION_EN171_65_PC",
  "source_type": "OEM",
  "derived_from": ["ECMWF_ERA5_2020_2024_DUTCHBAY"],
  "iec_standard": "61400-12-1:2022",
  "certificate": "CGC-B-FNc-2024-184",
  "is_placeholder": false
}
```

`load_aep_from_summary()` automatically attaches this block at
`provenance.aep` for any manifest-approved summary it loads.

## Test enforcement

`tests/analytics/test_aep_provenance.py` is the test-enforced guard:

- the **real** lender config (`scenarios/dutchbay_lendercase_2025Q4.yaml`) must
  reference an approved, non-placeholder source — CI fails otherwise;
- unknown sources raise `KeyError`; missing sources raise `ValueError`;
- a placeholder source is refused while a certified OEM curve is available;
- loaded summaries carry the `provenance.aep` block.

When adding a new AEP source, add it to `APPROVED_SOURCES` first, then reference
its `source_id` from the scenario config.
