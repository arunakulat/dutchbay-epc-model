"""Tests for the synthetic MCP measurement wiring (#961).

The single property these exist to protect: a wind estimate fitted on a GENERATED mast
series must not be able to reach canonical finance, a lender pack or a board pack. The
negative tests below are the point of the exercise — if the fence is ever weakened, they
fail rather than the defect shipping quietly.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.contracts_v14 import (
    CANONICAL_WIND_INTERFACE_FIELDS,
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    SyntheticMCPMeasurementRecord,
    require_canonical_wind_measurement,
)
from wind_resource.synthetic_mcp_measurement import (
    SYNTHETIC_MCP_SCHEMA,
    build_synthetic_mcp_measurement,
    campaign_adequacy_for,
    synthetic_series_for_audit,
)

_GOVERNED_CONFIG = Path("conf/synthetic_mcp_measurement.yaml")
_STAMP = "2026-08-22T00:00:00Z"


def _config() -> Dict[str, Any]:
    return dict(yaml.safe_load(_GOVERNED_CONFIG.read_text(encoding="utf-8")))


def _record() -> SyntheticMCPMeasurementRecord:
    return build_synthetic_mcp_measurement(_config(), generated_at_utc=_STAMP)


# --- the fence ---------------------------------------------------------------------------


def test_synthetic_mcp_result_cannot_enter_canonical_finance() -> None:
    """The reason this module exists. A synthetic estimate is refused at the door."""
    with pytest.raises(ValueError, match="cannot enter canonical finance"):
        require_canonical_wind_measurement(_record())


def test_record_refuses_to_be_relabelled_canonical() -> None:
    """dataclasses.replace re-runs __post_init__, so the record cannot be laundered."""
    record = _record()
    with pytest.raises(ValueError):
        dataclasses.replace(record, canonical_finance_eligible=True)
    with pytest.raises(ValueError):
        dataclasses.replace(record, finance_wiring_mode="canonical")


def test_mandatory_warning_cannot_be_softened_or_stripped() -> None:
    record = _record()
    assert record.required_warning == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    with pytest.raises(ValueError, match="exact mandatory synthetic"):
        dataclasses.replace(record, required_warning="synthetic - probably fine")
    with pytest.raises(ValueError, match="exact mandatory synthetic"):
        dataclasses.replace(record, required_warning="")


def test_record_cannot_claim_to_be_an_observed_measurement() -> None:
    record = _record()
    assert record.generated_input is True
    assert record.observed_measurement is False
    with pytest.raises(ValueError, match="observed measurement"):
        dataclasses.replace(record, observed_measurement=True)
    for flag in (
        "bankable",
        "lender_eligible",
        "board_eligible",
        "site_representative",
    ):
        with pytest.raises(ValueError):
            dataclasses.replace(record, **{flag: True})


def test_record_cannot_populate_the_canonical_wind_interface() -> None:
    """The copy-paste stopper.

    ``resource.wind.update(record.model_dump())`` must not be able to overwrite a real fit,
    so the record shares no field name with the canonical wind -> finance interface.
    """
    payload = _record().model_dump()
    assert not CANONICAL_WIND_INTERFACE_FIELDS.intersection(payload)
    # And the numbers it does carry are unmistakably namespaced.
    assert "synthetic_weibull_a" in payload
    assert "weibull_a" not in payload


def test_record_carries_the_segregated_output_class() -> None:
    record = _record()
    assert record.output_class == QSTS_SYNTHETIC_OUTPUT_CLASS
    assert record.input_kind == "synthetic_placeholder"
    assert record.finance_wiring_enabled is False
    assert record.canonical_finance_eligible is False


# --- determinism and provenance (MRM-01/02) ----------------------------------------------


def test_generation_is_deterministic() -> None:
    first = build_synthetic_mcp_measurement(_config(), generated_at_utc=_STAMP)
    second = build_synthetic_mcp_measurement(_config(), generated_at_utc=_STAMP)
    assert first.model_dump() == second.model_dump()


def test_series_is_deterministic_and_carries_the_planted_bias() -> None:
    mast_a, ref_a = synthetic_series_for_audit(_config())
    mast_b, ref_b = synthetic_series_for_audit(_config())
    assert (mast_a == mast_b).all()
    assert (ref_a == ref_b).all()
    # The bias is planted at slope 1.08, so the "mast" must read windier than the reference.
    # This is a property of the config, NOT a discovered fact about the site.
    assert mast_a.mean() > ref_a.mean()


def test_record_pins_the_sources_it_was_calibrated_against() -> None:
    record = _record()
    assert record.schema == SYNTHETIC_MCP_SCHEMA
    assert len(record.source_scenario_sha256) == 64
    assert len(record.source_era5_summary_sha256) == 64
    assert record.generated_at_utc == _STAMP


# --- CESSPIT: config explicit, no silent defaults ------------------------------------------


@pytest.mark.parametrize("dropped", ["generator", "mast_bias", "mcp", "source"])
def test_missing_config_block_raises_rather_than_defaulting(dropped: str) -> None:
    config = _config()
    config.pop(dropped)
    with pytest.raises(ValueError, match="must declare exactly"):
        build_synthetic_mcp_measurement(config, generated_at_utc=_STAMP)


def test_unexpected_config_key_is_refused() -> None:
    config = _config()
    config["surprise"] = True
    with pytest.raises(ValueError, match="unexpected"):
        build_synthetic_mcp_measurement(config, generated_at_utc=_STAMP)


def test_non_boolean_opt_out_is_refused() -> None:
    config = _config()
    config["mcp"]["allow_below_bankable"] = 1  # truthy, but not a bool
    with pytest.raises(ValueError, match="real bool"):
        build_synthetic_mcp_measurement(config, generated_at_utc=_STAMP)


def test_campaign_longer_than_reference_is_refused() -> None:
    config = _config()
    config["generator"]["campaign_hours"] = config["generator"]["reference_hours"] + 1
    with pytest.raises(ValueError, match="cannot exceed"):
        build_synthetic_mcp_measurement(config, generated_at_utc=_STAMP)


# --- campaign adequacy --------------------------------------------------------------------


def test_governed_config_runs_a_standards_length_campaign() -> None:
    """The shipped config uses 12 months, so the compliant branch is what CI exercises."""
    record = _record()
    assert record.mcp_n_concurrent == 8760
    assert record.campaign_adequacy == "iec_bankable"


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (8760, "iec_bankable"),
        (8759, "below_iec_bankable"),
        (2880, "below_iec_bankable"),
        (2879, "below_lender_disclosure_floor"),
    ],
)
def test_campaign_adequacy_boundaries(n: int, expected: str) -> None:
    assert campaign_adequacy_for(n) == expected


def test_a_short_synthetic_campaign_is_recorded_as_short() -> None:
    """Even inside the synthetic lane, a short campaign must not look compliant."""
    config = _config()
    config["generator"]["campaign_hours"] = 4000
    record = build_synthetic_mcp_measurement(config, generated_at_utc=_STAMP)
    assert record.campaign_adequacy == "below_iec_bankable"
