"""Tests for solar_resource.source_quality (#743 — graded provenance, bills off NOTHING).

The source-quality score is PURE METADATA: it grades the resource evidence behind a modelled
solar P50 and is emitted into the ``solar_resource`` provenance block, but it feeds no capacity
factor, no haircut, and no billed field. These tests prove the grading rubric and, critically,
that even a grade-A config leaves the financed economics untouched.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from solar_resource.cashflow_adapter import solar_export_to_scenario_patch
from solar_resource.source_quality import (
    AXIS_WEIGHTS,
    SolarSourceQuality,
    grade_solar_source_quality,
    solar_source_quality_from_config,
)


def test_axis_weights_sum_to_one() -> None:
    assert sum(AXIS_WEIGHTS.values()) == pytest.approx(1.0)


def test_default_grade_is_candid_low() -> None:
    """No config -> a candid low grade (D), never a silent investment-grade default."""
    q = solar_source_quality_from_config(None)
    assert q.grade == "D"
    assert q.measurement_type == "modelled"
    assert q.tmy_source == "unknown"
    assert 0.0 <= q.quality_score <= 0.3


def test_best_evidence_grades_a() -> None:
    q = grade_solar_source_quality(
        measurement_type="ground_measured",
        years_of_record=15,
        tmy_source="Solargis",
        ghi_dataset="on-site pyranometer 2010-2025",
    )
    assert q.grade == "A"
    assert q.quality_score == pytest.approx(1.0)
    assert q.ghi_dataset == "on-site pyranometer 2010-2025"


def test_satellite_pvgis_ten_years_grades_b() -> None:
    q = grade_solar_source_quality(
        measurement_type="satellite", years_of_record=10, tmy_source="PVGIS"
    )
    assert q.grade == "B"


def test_measurement_type_is_case_insensitive_and_dominant() -> None:
    hi = grade_solar_source_quality(measurement_type="GROUND_MEASURED")
    lo = grade_solar_source_quality(measurement_type="modelled")
    assert hi.quality_score > lo.quality_score
    assert hi.measurement_score == 1.0


def test_unknown_measurement_type_scores_zero_not_silent_default() -> None:
    q = grade_solar_source_quality(measurement_type="hearsay")
    assert q.measurement_score == 0.0  # candid, not a silent mid-grade


def test_unlisted_named_source_is_mildly_credited() -> None:
    q = grade_solar_source_quality(tmy_source="SomeVendorTMY")
    assert 0.0 < q.tmy_source_score < 0.85  # below the named-dataset scores


def test_negative_years_raises() -> None:
    with pytest.raises(ValueError, match="years_of_record"):
        grade_solar_source_quality(years_of_record=-1)


def test_unknown_config_key_raises() -> None:
    with pytest.raises(KeyError, match="unknown field"):
        solar_source_quality_from_config({"measurment_type": "satellite"})


def test_non_mapping_config_raises() -> None:
    with pytest.raises(TypeError):
        solar_source_quality_from_config(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_to_provenance_shape() -> None:
    q = grade_solar_source_quality(
        measurement_type="satellite_calibrated", years_of_record=5, tmy_source="NSRDB"
    )
    prov = q.to_provenance()
    assert set(prov) >= {
        "quality_score",
        "grade",
        "measurement_type",
        "years_of_record",
        "tmy_source",
        "measurement_score",
        "years_score",
        "tmy_source_score",
    }
    assert isinstance(prov["grade"], str)


# --- The load-bearing proof: the score bills off NOTHING --------------------


def _export() -> dict:
    return {
        "scenario": "P50",
        "technology": "solar",
        "annual_energy_gwh": 73.8,
        "capacity_factor": 0.1685,
        "dc_capacity_mw": 50.0,
        "specific_yield_kwh_per_kwp": 1476.0,
    }


def _scenario(source_quality: dict | None = None) -> dict:
    solar_block: dict = {
        "latitude": 8.27,
        "longitude": 79.75,
        "annual_ghi_kwh_m2": 2000.0,
        "dc_capacity_mw": 50.0,
    }
    if source_quality is not None:
        solar_block["source_quality"] = source_quality
    return {
        "project": {"capacity_mw": 209.6},
        "generation": {
            "technologies": {
                "solar": {
                    "type": "solar",
                    "capacity_mw": 50.0,
                    "capacity_factor": 0.1685,
                    "aep_gwh": 73.8,
                }
            }
        },
        "resource": {"solar": solar_block},
    }


def test_provenance_block_is_emitted_with_default_grade() -> None:
    patched = solar_export_to_scenario_patch(
        _export(), _scenario(), adapter_mode="validate_only"
    )
    sq = patched["solar_resource"]["source_quality"]
    assert sq["grade"] == "D"  # ungraded frozen export reads candidly


def test_graded_config_emits_high_grade_but_moves_no_economics() -> None:
    """A grade-A source_quality config changes the provenance ONLY, never the billed CF."""
    graded = _scenario(
        {
            "measurement_type": "ground_measured",
            "years_of_record": 12,
            "tmy_source": "Solargis",
        }
    )
    patched = solar_export_to_scenario_patch(
        _export(), graded, adapter_mode="validate_only"
    )
    assert patched["solar_resource"]["source_quality"]["grade"] == "A"
    # The financed solar CF is untouched by the grade (validate_only writes no economics).
    solar = patched["generation"]["technologies"]["solar"]
    assert solar["capacity_factor"] == 0.1685
    # And the blended headline is not written by validate_only either.
    assert "capacity_factor" not in patched["project"]


def test_grade_does_not_change_economics_across_overwrite_mode() -> None:
    """Even in OVERWRITE mode the grade never enters the per-tech economics."""
    lo = solar_export_to_scenario_patch(
        _export(), _scenario(), adapter_mode="overwrite"
    )
    hi = solar_export_to_scenario_patch(
        _export(),
        _scenario({"measurement_type": "ground_measured", "years_of_record": 20}),
        adapter_mode="overwrite",
    )
    # Different provenance grades...
    assert lo["solar_resource"]["source_quality"]["grade"] != (
        hi["solar_resource"]["source_quality"]["grade"]
    )
    # ...identical economics.
    assert (
        lo["generation"]["technologies"]["solar"]
        == hi["generation"]["technologies"]["solar"]
    )
    assert lo["project"]["capacity_factor"] == hi["project"]["capacity_factor"]


def test_dataclass_is_frozen() -> None:
    q = grade_solar_source_quality()
    assert isinstance(q, SolarSourceQuality)
    with pytest.raises(FrozenInstanceError):
        q.grade = "A"  # type: ignore[misc]
