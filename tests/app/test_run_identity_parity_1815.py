"""One run carries one identity on every output surface (#1815, consumer matrix).

A single pipeline run of the lender case feeds the three consumer surfaces:

* the API response (``api.pipeline_api.run_pipeline``), its ``manifest`` block;
* the report context (``app.reports.report_model.build_report_context``), whose
  ``manifest`` the HTML report and the DBPL print render;
* the executive workbook (``analytics.executive_workbook``), its "Manifest" sheet.

Each must carry the run identity of ``analytics.run_identity.RUN_IDENTITY_FIELDS`` with
the same values. Hostile controls show the check fails when one surface is tampered with
or drops its identity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import openpyxl
import pytest

import api.pipeline_api as papi
from analytics.executive_workbook import (
    RUN_MANIFEST_SHEET,
    emit_executive_workbook_from_pipeline,
    read_workbook_run_manifest,
)
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_identity import RUN_IDENTITY_FIELDS, require_same_run_identity
from app.api.responses import CaseResult
from app.reports.report_model import build_report_context

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = "scenarios/dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(scope="module")
def run() -> Dict[str, Any]:
    return run_v14_pipeline(str(REPO_ROOT / LENDER))


@pytest.fixture(scope="module")
def surfaces(
    run: Dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> Dict[str, Any]:
    """Each surface built from the same run."""
    patch = pytest.MonkeyPatch()
    # The API route runs the engine itself; hand it this run so both bind to one stamp.
    patch.setattr(papi, "run_v14_pipeline", lambda **_kwargs: run)
    try:
        api = papi.run_pipeline(papi.RunPipelineRequest(config_path=LENDER))
    finally:
        patch.undo()
    report = build_report_context(
        CaseResult.from_pipeline_result(dict(run), scenario_variant="lender"),
        generated_at="2026-11-22T00:00:00Z",
        debt_result=run.get("debt_result"),
        annual_rows=run.get("annual_rows"),
        run_result=dict(run),
    )
    workbook = emit_executive_workbook_from_pipeline(
        run, tmp_path_factory.mktemp("wb") / "executive.xlsx"
    )
    return {"api": api, "report": report, "workbook": workbook}


def _manifests(surfaces: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "api": surfaces["api"].manifest.model_dump(),
        "report": surfaces["report"].manifest,
        "workbook": read_workbook_run_manifest(surfaces["workbook"]),
    }


def test_every_surface_carries_the_engine_stamped_identity(
    run: Dict[str, Any], surfaces: Dict[str, Any]
) -> None:
    shared = require_same_run_identity(_manifests(surfaces))
    engine = run["run_manifest"]
    assert shared == {key: engine.get(key) for key in RUN_IDENTITY_FIELDS}
    assert len(shared["config_sha256"]) == 64


def test_the_workbook_manifest_sheet_lists_each_identity_field(
    surfaces: Dict[str, Any],
) -> None:
    workbook = openpyxl.load_workbook(surfaces["workbook"], read_only=True)
    try:
        rows = list(workbook[RUN_MANIFEST_SHEET].iter_rows(values_only=True))
        assert workbook.sheetnames[0] == "Summary"  # the notice stays first
    finally:
        workbook.close()
    assert rows[0] == ("Field", "Value")
    assert tuple(row[0] for row in rows[1:]) == RUN_IDENTITY_FIELDS


def _tamper(path: Path, field: str, value: str) -> None:
    workbook = openpyxl.load_workbook(path)
    sheet = workbook[RUN_MANIFEST_SHEET]
    for row in sheet.iter_rows(min_row=2):
        if row[0].value == field:
            row[1].value = value
    workbook.save(path)


@pytest.mark.parametrize("field", ("config_sha256", "git_sha", "generated_at"))
def test_a_tampered_workbook_identity_is_refused(
    surfaces: Dict[str, Any], tmp_path: Path, field: str
) -> None:
    copy = tmp_path / "tampered.xlsx"
    copy.write_bytes(Path(surfaces["workbook"]).read_bytes())
    _tamper(copy, field, "0" * 64)
    manifests = _manifests(surfaces) | {"workbook": read_workbook_run_manifest(copy)}
    with pytest.raises(ValueError, match=f"{field}: api="):
        require_same_run_identity(manifests)


def test_a_workbook_without_the_manifest_sheet_is_refused(
    surfaces: Dict[str, Any], tmp_path: Path
) -> None:
    copy = tmp_path / "stripped.xlsx"
    workbook = openpyxl.load_workbook(surfaces["workbook"])
    del workbook[RUN_MANIFEST_SHEET]
    workbook.save(copy)
    assert read_workbook_run_manifest(copy) is None
    manifests = _manifests(surfaces) | {"workbook": read_workbook_run_manifest(copy)}
    with pytest.raises(ValueError, match="workbook: no run manifest"):
        require_same_run_identity(manifests)


@pytest.mark.parametrize(
    "field", ("config_sha256", "engine_version", "git_sha", "generated_at")
)
def test_a_report_missing_an_identity_field_is_refused(
    surfaces: Dict[str, Any], field: str
) -> None:
    report = dict(surfaces["report"].manifest)
    del report[field]
    with pytest.raises(ValueError, match=f"report: run manifest lacks {field}"):
        require_same_run_identity(_manifests(surfaces) | {"report": report})


def test_a_different_run_is_refused(surfaces: Dict[str, Any]) -> None:
    other = dict(surfaces["report"].manifest) | {"seed": 7}
    with pytest.raises(ValueError, match="seed: api=None, report=7, workbook=None"):
        require_same_run_identity(_manifests(surfaces) | {"report": other})


def test_one_surface_is_not_a_comparison() -> None:
    with pytest.raises(ValueError, match="at least two surfaces"):
        require_same_run_identity({"api": {}})
