"""Tests for solar_resource.bifacial_guard (#743 — SOLAR-9 financed-chain discipline).

The financed solar CF chain is monofacial by design. The guard fires on the OVERWRITE finance
bridge (``solar_export_to_scenario_patch``) and refuses a bifacial rear-side uplift from
entering the billed capacity factor — while leaving the illustrative report's disclosed
cf_mono/cf_bifacial side-by-side untouched (that report bypasses the bridge).
"""

from __future__ import annotations

import pytest

from solar_resource.bifacial_guard import (
    BifacialInFinancedChainError,
    assert_monofacial_financed_cf,
    detect_bifacial_uplift,
)
from solar_resource.cashflow_adapter import solar_export_to_scenario_patch


def _export(**extra: object) -> dict:
    base = {
        "scenario": "P50",
        "technology": "solar",
        "annual_energy_gwh": 73.8,
        "capacity_factor": 0.1685,
        "dc_capacity_mw": 50.0,
        "specific_yield_kwh_per_kwp": 1476.0,
    }
    base.update(extra)
    return base


def _scenario(solar_extra: dict | None = None) -> dict:
    solar_block: dict = {
        "latitude": 8.27,
        "longitude": 79.75,
        "annual_ghi_kwh_m2": 2000.0,
        "dc_capacity_mw": 50.0,
    }
    if solar_extra:
        solar_block.update(solar_extra)
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


# --- detection primitive ----------------------------------------------------


@pytest.mark.parametrize(
    "block",
    [
        None,
        {},
        {"bifacial_gain": 1.0},  # unit multiplier = neutral
        {"bifacial_gain_pct": 0.0},  # 0% = neutral
        {"bifacial": False},  # falsey flag = neutral
        {"latitude": 8.27},  # unrelated keys
    ],
)
def test_neutral_or_absent_markers_are_no_ops(block: dict | None) -> None:
    assert detect_bifacial_uplift(block) is None


@pytest.mark.parametrize(
    "block,key",
    [
        ({"bifacial_gain": 1.07}, "bifacial_gain"),
        ({"bifacial_gain_pct": 7.0}, "bifacial_gain_pct"),
        ({"bifacial": True}, "bifacial"),
    ],
)
def test_active_markers_detected(block: dict, key: str) -> None:
    hit = detect_bifacial_uplift(block)
    assert hit is not None and hit[0] == key


def test_assert_no_op_when_clean() -> None:
    # Neither input carries a bifacial marker -> returns cleanly.
    assert_monofacial_financed_cf(_export(), _scenario()["resource"]["solar"])


# --- the guard on the finance bridge ----------------------------------------


def test_bridge_no_op_on_committed_shape_scenario() -> None:
    """A committed-shape scenario (no bifacial) passes the bridge unchanged."""
    patched = solar_export_to_scenario_patch(
        _export(), _scenario(), adapter_mode="validate_only"
    )
    assert patched["generation"]["technologies"]["solar"]["capacity_factor"] == 0.1685


def test_bridge_rejects_bifacial_in_resource_solar() -> None:
    with pytest.raises(BifacialInFinancedChainError, match="monofacial by design"):
        solar_export_to_scenario_patch(
            _export(),
            _scenario({"bifacial_gain": 1.07}),
            adapter_mode="validate_only",
        )


def test_bridge_rejects_bifacial_in_export() -> None:
    with pytest.raises(BifacialInFinancedChainError):
        solar_export_to_scenario_patch(
            _export(bifacial_gain_pct=7.0), _scenario(), adapter_mode="overwrite"
        )


def test_error_carries_actionable_detail() -> None:
    try:
        assert_monofacial_financed_cf(_export(bifacial=True), None)
    except BifacialInFinancedChainError as exc:
        assert exc.key == "bifacial"
        assert "generate_solar_assessment_report" in str(exc)
    else:  # pragma: no cover
        pytest.fail("expected BifacialInFinancedChainError")


def test_neutral_bifacial_gain_still_passes_the_bridge() -> None:
    """An explicit but neutral bifacial_gain=1.0 is not an uplift -> allowed (byte-identical)."""
    patched = solar_export_to_scenario_patch(
        _export(), _scenario({"bifacial_gain": 1.0}), adapter_mode="validate_only"
    )
    assert patched["generation"]["technologies"]["solar"]["capacity_factor"] == 0.1685


def test_illustrative_report_disclosure_pattern_is_not_a_bridge_input() -> None:
    """The illustrative report sets project.capacity_factor directly and never routes through
    this bridge, so a report-style cf_mono/cf_bifacial disclosure is NOT guarded here.
    """
    # A plain scenario whose project headline already carries a (report-style) bifacial CF but
    # no bifacial *marker* in resource.solar / the export must pass — the guard keys off the
    # explicit marker, not the numeric CF value, so it cannot false-positive on a disclosed CF.
    report_style = _scenario()
    report_style["project"]["capacity_factor"] = (
        0.1685 * 1.07
    )  # disclosed bifacial headline
    patched = solar_export_to_scenario_patch(
        _export(), report_style, adapter_mode="validate_only"
    )
    assert patched is not None
