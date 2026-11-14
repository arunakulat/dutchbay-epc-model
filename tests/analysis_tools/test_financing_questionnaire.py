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
    SCENARIOS,
    QuestionnaireError,
    build_questionnaire,
    export_questionnaire,
)


def config() -> dict[str, Any]:
    """Read the declarative exporter fields without Hydra controls."""
    data = yaml.safe_load(
        (ROOT / "conf/blue_whale_financing_questionnaire.yaml").read_text()
    )
    data.pop("defaults")
    data.pop("hydra")
    return data


@pytest.mark.parametrize("project", ["wind", "solar_bess"])
def test_each_reference_matches_independent_yaml_and_preserves_source(
    project: str,
) -> None:
    """Compare every model cell to a separately parsed source and raw bytes."""
    cfg = config()
    cfg["project"] = project
    raw = (ROOT / SCENARIOS[project]).read_bytes()
    oracle = yaml.safe_load(raw)
    result = build_questionnaire(cfg, raw)
    assert base64.b64decode(result["source"]["raw_yaml_base64"]) == raw
    assert result["source"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(cfg["fields"]) == 18
    for question, field in zip(result["questions"][:18], cfg["fields"], strict=True):
        value = oracle
        for part in field["path"].split("."):
            value = value[part]
        ref = question["model_reference"]
        assert ref["value"] == value
        assert ref["source_field_path"] == field["path"]
        assert ref["source_kind"] == "model_assumption"
        assert question["answer_status"] == "unknown"
        assert all(
            question[f"answer_{key}"] is None
            for key in ("value", "basis", "date", "citation")
        )


def test_perturbed_rate_dsra_fee_provenance() -> None:
    """Perturbed assumptions retain their roles and exact source identity."""
    cfg = config()
    raw = (ROOT / SCENARIOS["wind"]).read_bytes()
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
    ],
)
def test_refusals(mutation: str) -> None:
    """Reject malformed inputs and attempts to preconfirm the model reference."""
    cfg = config()
    raw = (ROOT / SCENARIOS["wind"]).read_bytes()
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
        cfg["project"] = []
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
    path = tmp_path / SCENARIOS["wind"]
    path.parent.mkdir()
    path.write_bytes((ROOT / SCENARIOS["wind"]).read_bytes())
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
    path = tmp_path / SCENARIOS["wind"]
    path.parent.mkdir()
    path.write_bytes((ROOT / SCENARIOS["wind"]).read_bytes())

    def fail_save(*args: Any, **kwargs: Any) -> None:
        raise OSError("simulated workbook failure")

    monkeypatch.setattr(openpyxl.Workbook, "save", fail_save)
    with pytest.raises(OSError):
        export_questionnaire(cfg, tmp_path)
    assert list((tmp_path / "outputs").iterdir()) == []


def test_outputs_symlink_rejected(tmp_path: Path) -> None:
    """Prevent writing through an outputs link to another directory."""
    cfg = config()
    path = tmp_path / SCENARIOS["wind"]
    path.parent.mkdir()
    path.write_bytes((ROOT / SCENARIOS["wind"]).read_bytes())
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "outputs").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(QuestionnaireError):
        export_questionnaire(cfg, tmp_path)
    assert list(elsewhere.iterdir()) == []
