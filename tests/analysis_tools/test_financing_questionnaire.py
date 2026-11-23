"""Independent checks for public references and blank questionnaire output."""

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import openpyxl
import pytest
import yaml

from analysis_tools.financing_questionnaire import (
    ROOT,
    QuestionnaireError,
    build_questionnaire,
    export_questionnaire,
    scenario_path,
)

# Test fixtures only: the module itself names no scenario (#1783). These two declare every
# field the questionnaire reads; any other scenario that does is exported the same way.
WIND = "scenarios/blue_whale_wind_lot5b_2026.yaml"
SOLAR_BESS = "scenarios/blue_whale_solar_bess_lot5b_2026.yaml"
# A scenario of another site that lacks only the CAPEX price year.
OTHER_SITE = "scenarios/kalpitiya_lendercase_160m_fitted.yaml"


def config() -> dict[str, Any]:
    """Read the declarative exporter fields without Hydra controls."""
    data = yaml.safe_load((ROOT / "conf/financing_questionnaire.yaml").read_text())
    data.pop("defaults")
    data.pop("hydra")
    assert data["scenario"] == "???" and data["output_name"] == "???"
    data["scenario"] = WIND
    data["output_name"] = "questionnaire"
    return data


@pytest.mark.parametrize("scenario", [WIND, SOLAR_BESS])
def test_each_reference_matches_independent_yaml_and_preserves_source(
    scenario: str,
) -> None:
    """Compare every model cell to a separately parsed source and raw bytes."""
    cfg = config()
    cfg["scenario"] = scenario
    raw = (ROOT / scenario).read_bytes()
    oracle = yaml.safe_load(raw)
    result = build_questionnaire(cfg, raw)
    assert base64.b64decode(result["source"]["raw_yaml_base64"]) == raw
    assert result["source"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(cfg["fields"]) == 19
    for question, field in zip(result["questions"][:19], cfg["fields"], strict=True):
        value = oracle
        for part in field["path"].split("."):
            value = value[part]
        ref = question["model_reference"]
        assert ref["value"] == value
        assert ref["source_field_path"] == field["path"]
        assert ref["source_kind"] == "model_assumption"
        assert ref["source_model_path"] == scenario
        assert question["answer_status"] == "unknown"
        assert all(
            question[f"answer_{key}"] is None
            for key in ("value", "basis", "date", "citation")
        )


def test_perturbed_rate_dsra_fee_provenance() -> None:
    """Perturbed assumptions retain their roles and exact source identity."""
    cfg = config()
    raw = (ROOT / WIND).read_bytes()
    source = yaml.safe_load(raw)
    source["Financing_Terms"]["interest_rate_nominal"] = 0.1234567
    source["Financing_Terms"]["reserves"]["dsra_months"] = 9
    source["Financing_Terms"]["fees"]["upfront_pct"] = 0.0321
    altered = yaml.safe_dump(source).encode()
    rows = {r["id"]: r for r in build_questionnaire(cfg, altered)["questions"]}
    for key, value in [
        ("capacity_rate", 0.1234567),
        ("dsra_target", 9),
        ("upfront_fee", 0.0321),
    ]:
        assert rows[key]["model_reference"]["value"] == value
        assert (
            rows[key]["model_reference"]["source_sha256"]
            == hashlib.sha256(altered).hexdigest()
        )
    assert "not the repayment" in rows["capacity_rate"]["note"]
    assert "does not establish initial funding" in rows["dsra_target"]["note"]
    assert "does not establish CAPEX cash funding" in rows["upfront_fee"]["note"]


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "status",
        "confirmed",
        "path",
        "missing",
        "unhashable",
        "nan",
        "bool",
        "duplicate",
        "unset_scenario",
        "absolute_scenario",
        "escaping_scenario",
        "non_yaml_scenario",
    ],
)
def test_refusals(mutation: str) -> None:
    """Reject malformed inputs and attempts to preconfirm the model reference."""
    cfg = config()
    raw = (ROOT / WIND).read_bytes()
    if mutation == "unknown":
        cfg["extra"] = 1
    if mutation == "status":
        cfg["fields"][0]["answer_status"] = "invented"
    if mutation == "confirmed":
        cfg["fields"][0]["source_kind"] = "authenticated_transaction_term"
    if mutation == "path":
        cfg["fields"][0]["path"] = "project.name"
    if mutation == "missing":
        cfg["fields"].pop()
    if mutation == "unhashable":
        cfg["scenario"] = []
    if mutation == "unset_scenario":
        cfg["scenario"] = "???"
    if mutation == "absolute_scenario":
        cfg["scenario"] = "/" + WIND
    if mutation == "escaping_scenario":
        cfg["scenario"] = "scenarios/../conf/financing_questionnaire.yaml"
    if mutation == "non_yaml_scenario":
        cfg["scenario"] = "scenarios/notes.txt"
    if mutation in ("nan", "bool"):
        source = yaml.safe_load(raw)
        source["Financing_Terms"]["interest_rate_nominal"] = (
            float("nan") if mutation == "nan" else True
        )
        raw = yaml.safe_dump(source).encode()
    if mutation == "duplicate":
        raw += b"\nFinancing_Terms: {}\n"
    with pytest.raises(QuestionnaireError):
        build_questionnaire(cfg, raw)


def test_workbook_roundtrip_and_no_clobber(tmp_path: Path) -> None:
    """Keep numeric references, literal text, blank answers and visible limits."""
    cfg = config()
    cfg["fields"][0]["label"] = '=HYPERLINK("danger")'
    path = tmp_path / WIND
    path.parent.mkdir()
    path.write_bytes((ROOT / WIND).read_bytes())
    receipt = export_questionnaire(cfg, tmp_path)
    data = json.loads((tmp_path / receipt["json"]).read_text())
    ws = openpyxl.load_workbook(tmp_path / receipt["xlsx"], data_only=False).active
    book = openpyxl.load_workbook(tmp_path / receipt["xlsx"], data_only=False)
    assert book["Read me"].cell(2, 2).value == data["notice"]
    assert "does not import answers or authenticate terms" in data["notice"]
    assert ws.cell(2, 2).value == cfg["fields"][0]["label"]
    assert ws.cell(2, 2).data_type == "s"
    for index, question in enumerate(data["questions"], 2):
        assert ws.cell(index, 10).value == "unknown"
        assert all(ws.cell(index, column).value is None for column in range(11, 15))
        if question["model_reference"] and isinstance(
            question["model_reference"]["value"], (int, float)
        ):
            assert ws.cell(index, 4).data_type == "n"
    with pytest.raises(QuestionnaireError):
        export_questionnaire(cfg, tmp_path)


def test_second_write_failure_rolls_back_new_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed workbook write removes only the two newly created artifacts."""
    cfg = config()
    path = tmp_path / WIND
    path.parent.mkdir()
    path.write_bytes((ROOT / WIND).read_bytes())

    def fail_save(*args: Any, **kwargs: Any) -> None:
        raise OSError("simulated workbook failure")

    monkeypatch.setattr(openpyxl.Workbook, "save", fail_save)
    with pytest.raises(OSError):
        export_questionnaire(cfg, tmp_path)
    assert list((tmp_path / "outputs").iterdir()) == []


def test_outputs_symlink_rejected(tmp_path: Path) -> None:
    """Prevent writing through an outputs link to another directory."""
    cfg = config()
    path = tmp_path / WIND
    path.parent.mkdir()
    path.write_bytes((ROOT / WIND).read_bytes())
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "outputs").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(QuestionnaireError):
        export_questionnaire(cfg, tmp_path)
    assert list(elsewhere.iterdir()) == []


def test_any_scenario_declaring_the_fields_is_exported(tmp_path: Path) -> None:
    """#1783: a scenario of another site runs once it declares every field read.

    The negative control comes first: unchanged, that scenario lacks one field and is
    refused with the path it lacks, so nothing is filled in for it.
    """
    source = yaml.safe_load((ROOT / OTHER_SITE).read_bytes())
    (tmp_path / "scenarios").mkdir()
    target = tmp_path / "scenarios" / "another_site.yaml"
    target.write_bytes((ROOT / OTHER_SITE).read_bytes())
    cfg = config()
    cfg["scenario"] = "scenarios/another_site.yaml"
    with pytest.raises(QuestionnaireError, match="capex.price_basis.price_year"):
        export_questionnaire(cfg, tmp_path)
    source["capex"].setdefault("price_basis", {})["price_year"] = 2026
    target.write_text(yaml.safe_dump(source), encoding="utf-8")
    receipt = export_questionnaire(cfg, tmp_path)
    data = json.loads((tmp_path / receipt["json"]).read_text())
    assert data["scenario"] == "scenarios/another_site.yaml"
    assert data["source"]["path"] == "scenarios/another_site.yaml"
    rows = {r["id"]: r for r in data["questions"]}
    assert rows["capex_year"]["model_reference"]["value"] == 2026
    gearing = source["Financing_Terms"]["debt_ratio"]
    assert rows["gearing"]["model_reference"]["value"] == gearing


def test_scenario_must_be_a_file_inside_scenarios(tmp_path: Path) -> None:
    """Refuse a missing file and a link that leads out of scenarios/."""
    cfg = config()
    (tmp_path / "scenarios").mkdir()
    cfg["scenario"] = "scenarios/absent.yaml"
    with pytest.raises(QuestionnaireError, match="not found"):
        export_questionnaire(cfg, tmp_path)
    outside = tmp_path / "outside.yaml"
    outside.write_bytes((ROOT / WIND).read_bytes())
    (tmp_path / "scenarios" / "linked.yaml").symlink_to(outside)
    cfg["scenario"] = "scenarios/linked.yaml"
    with pytest.raises(QuestionnaireError, match="not found"):
        export_questionnaire(cfg, tmp_path)
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize(
    "value",
    [WIND, SOLAR_BESS, "scenarios/sub/dir/case.yml"],
)
def test_scenario_path_accepts_plain_paths(value: str) -> None:
    """The shape check accepts plain relative paths under scenarios/."""
    assert scenario_path(value) == value
