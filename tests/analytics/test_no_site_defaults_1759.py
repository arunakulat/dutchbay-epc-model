"""Model code takes its site from configuration, never from a built-in default (#1759)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
import yaml

import run_full_pipeline_v14 as rfp
from analytics.gis import gis_export
from analytics.loader import aep_loader
from app.models.inputs import (
    BASE_SCENARIOS_CONFIG,
    WindFarmInputs,
    variant_scenario_paths,
)
from finance.irr_config import load_config
from wind_resource.resource_assurance import EVIDENCE_REQUEST_REGISTER

REPO_ROOT = Path(__file__).resolve().parents[2]

# The scenarios the web variants loaded before #1759 moved the map into configuration.
_PRE_1759_VARIANTS = {
    "lendercase": "scenarios/dutchbay_lendercase_2025Q4.yaml",
    "basecase": "scenarios/dutchbay_basecase_2025Q4.yaml",
    "equitycase": "scenarios/dutchbay_equitycase_2025Q4.yaml",
}


def test_wind_auto_orchestrate_refuses_a_scenario_without_a_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "cdsapi", types.ModuleType("cdsapi"))
    scenario = tmp_path / "no_location.yaml"
    scenario.write_text(yaml.safe_dump({"project": {"name": "x"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="location"):
        rfp._run_wind_producer(scenario, "P50", tmp_path / "out")


def test_irr_config_needs_a_path() -> None:
    with pytest.raises(ValueError, match="config_path"):
        load_config(None)


def test_gis_export_needs_its_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIS_EXPORT_CONFIG", raising=False)
    with pytest.raises(SystemExit, match="GIS_EXPORT_CONFIG"):
        gis_export.main()


def test_web_variants_load_the_same_scenarios_from_configuration() -> None:
    assert variant_scenario_paths() == _PRE_1759_VARIANTS
    for variant, rel in _PRE_1759_VARIANTS.items():
        inputs = WindFarmInputs.model_construct(scenario_variant=variant)
        assert inputs.base_scenario_path() == REPO_ROOT / rel
        assert (REPO_ROOT / rel).is_file()


def test_web_variants_fail_loud_when_one_is_missing(tmp_path: Path) -> None:
    target = tmp_path / BASE_SCENARIOS_CONFIG
    target.parent.mkdir(parents=True)
    target.write_text(
        yaml.safe_dump({"variants": {"lendercase": "scenarios/a.yaml"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="basecase, equitycase"):
        variant_scenario_paths(tmp_path)


def test_aep_sources_come_from_configuration() -> None:
    assert aep_loader.APPROVED_SOURCES_CONFIG == (
        REPO_ROOT / "conf" / "aep_approved_sources.yaml"
    )
    loaded = yaml.safe_load(
        aep_loader.APPROVED_SOURCES_CONFIG.read_text(encoding="utf-8")
    )
    assert aep_loader.APPROVED_SOURCES == loaded["sources"]
    assert dict(aep_loader.BUILTIN_APPROVED_SOURCES).keys() == loaded["sources"].keys()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ({"sources": {}}, "non-empty 'sources'"),
        ({"sources": {"X": {"type": "OEM"}}}, "sources.X needs type and description"),
    ],
)
def test_aep_sources_file_is_validated(
    tmp_path: Path, content: dict[str, object], message: str
) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        aep_loader._load_approved_sources(path)


def test_evidence_register_names_no_specific_mast() -> None:
    description = EVIDENCE_REQUEST_REGISTER["EV-REQ-01"].description
    assert "617725" not in description
    assert "met mast" in description
