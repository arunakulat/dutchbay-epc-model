"""Executable guards for GWTF TEST-04's report/API test architecture."""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest
import yaml
from conftest import REPORT_TEST_POLICY_PATH, _load_report_test_policy

REPO_ROOT = Path(__file__).resolve().parents[2]
RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
API_TESTS = REPO_ROOT / "tests" / "app" / "test_api.py"
E2E_TESTS = REPO_ROOT / "tests" / "integration" / "test_lender_report_e2e.py"


def _function(path: Path, name: str) -> ast.FunctionDef:
    """Return one top-level test function from a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{path.relative_to(REPO_ROOT)} has no function {name}")


def _function_source(path: Path, name: str) -> str:
    """Return the exact source segment for a top-level test function."""
    source = path.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, _function(path, name))
    assert segment is not None
    return segment


def _decorators(path: Path, name: str) -> set[str]:
    """Return normalized decorator expressions for a test function."""
    return {ast.unparse(value) for value in _function(path, name).decorator_list}


def test_test04_is_active_and_pins_the_assurance_boundary() -> None:
    """Keep TEST-04 explicit about retained assurance and prohibited claims."""
    with RULESET.open(encoding="utf-8", newline="") as handle:
        rules = {row["rule_id"]: row for row in csv.DictReader(handle)}

    rule = rules["TEST-04"]
    policy = " ".join((rule["title"], rule["description"], rule["enforcement"]))
    assert rule["status"] == "active"
    for required in (
        "deterministic",
        "representative live",
        "report_qualification",
        "supplemental-sensitivity",
        "PDF",
        "Python 3.12",
        "bankability",
        "release evidence",
    ):
        assert required.lower() in policy.lower()


def test_report_policy_is_strict_and_fail_closed(tmp_path: Path) -> None:
    """Validate the CESSPIT policy and reject undeclared execution switches."""
    policy = _load_report_test_policy()
    assert policy.api_transport_context == "deterministic_known_context"
    assert policy.renderer_context == "deterministic_known_context"
    assert policy.representative_live_e2e_required is True
    assert policy.claim_classification == "regression_and_coverage_only"
    assert policy.qualification_test_mode == "qualification"
    assert policy.qualification_marker == "report_qualification"
    assert set(policy.required_live_paths) == {
        "supplemental_sensitivity",
        "pdf_backend",
    }

    raw = yaml.safe_load(REPORT_TEST_POLICY_PATH.read_text(encoding="utf-8"))
    raw["ordinary_suite"]["silent_live_sweep"] = True
    bad = tmp_path / "bad_report_policy.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown=\['silent_live_sweep'\]"):
        _load_report_test_policy(bad)


def test_transport_tests_inject_known_contexts_at_the_orchestration_seam() -> None:
    """Response-only tests must not rerun finance or supplemental sensitivity."""
    names = (
        "test_run_case_report_html_renders",
        "test_run_case_report_pdf_503_without_weasyprint",
        "test_run_case_report_pdf_success_path",
    )
    for name in names:
        source = _function_source(API_TESTS, name)
        assert 'monkeypatch.setattr(api_main, "_build_report_context"' in source
        assert "pytest.mark.slow" not in _decorators(API_TESTS, name)

    missing = _function_source(
        API_TESTS, "test_run_case_report_pdf_503_without_weasyprint"
    )
    assert "ReportDependencyError" in missing
    assert 'monkeypatch.setattr(api_main, "render_report_pdf"' in missing


def test_live_supplemental_and_pdf_paths_remain_qualification_tests() -> None:
    """Do not obtain speed by deleting the two complete live report paths."""
    supplemental = "test_production_path_renders_sensitivity_sections"
    pdf_backend = "test_lender_report_pdf_renders_with_required_backend"
    for name in (supplemental, pdf_backend):
        assert "pytest.mark.report_qualification" in _decorators(E2E_TESTS, name)

    supplemental_source = _function_source(E2E_TESTS, supplemental)
    assert "api_main._build_report_context" in supplemental_source
    assert "Sensitivity Tornado" in supplemental_source
    assert "Global Sensitivity" in supplemental_source

    pdf_source = _function_source(E2E_TESTS, pdf_backend)
    assert "render_report_pdf" in pdf_source
    assert "importorskip" not in pdf_source
    assert 'b"%PDF-"' in pdf_source

    marked_files: set[Path] = set()
    for path in sorted((REPO_ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Attribute) and node.attr == "report_qualification"
            for node in ast.walk(tree)
        ):
            marked_files.add(path)
    assert marked_files == {E2E_TESTS}


def test_representative_http_e2e_keeps_live_finance_without_repeating_sweeps() -> None:
    """Keep one ordinary auth/HTTP/live-finance path with fixed supplemental seams."""
    source = _function_source(
        E2E_TESTS, "test_lender_report_renders_through_the_auth_gated_http_route"
    )
    for service in (
        "compute_report_tornado",
        "compute_report_global_sa",
        "compute_report_global_sa_pawn",
    ):
        assert f'"{service}"' in source
    assert source.count("monkeypatch.setattr") >= 4
    assert "TestClient(api_main.app)" in source
    assert 'client.post("/v1/cases/report.html"' in source
    assert 'monkeypatch.setattr(api_main, "_build_report_context"' not in source
    assert "pytest.mark.report_qualification" not in _decorators(
        E2E_TESTS, "test_lender_report_renders_through_the_auth_gated_http_route"
    )


def test_local_and_python312_ci_qualification_targets_are_explicit() -> None:
    """Pin the separate local, scheduled/manual, and release report gates."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/test-suite.yml").read_text(
        encoding="utf-8"
    )
    release = (REPO_ROOT / ".github/workflows/release-run.yml").read_text(
        encoding="utf-8"
    )

    assert "test-report-qualification:" in makefile
    assert "DUTCHBAY_TEST_MODE=qualification $(PYTEST)" in makefile
    assert "-n 2 tests/integration/test_lender_report_e2e.py" in makefile
    assert "-m report_qualification" in makefile
    assert "report-qualification:" in workflow
    assert "Report Qualification (Python 3.12, scheduled/manual)" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "-n 2 tests/integration/test_lender_report_e2e.py" in workflow
    assert "-m report_qualification" in workflow
    assert "Run report qualification tests" in release
    assert "DUTCHBAY_TEST_MODE: qualification" in release
    assert "-n 2 tests/integration/test_lender_report_e2e.py" in release
    assert "-m report_qualification" in release
