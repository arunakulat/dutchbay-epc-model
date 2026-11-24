"""Fail-closed source-safe R3 report and evidence-asset review.

Not a licence to publish: it checks the named files and obvious source leaks.
It cannot prove copyright consent, secret absence inside all image pixels or
that historic source interpretations are accurate.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

PKG = Path(__file__).resolve().parents[1]
ALLOWED = frozenset(
    {
        "DATA_HANDLING.md",
        "README.md",
        "evidence/consolidated_input_21.csv",
        "evidence/COVERAGE_RUBRIC_AND_BASELINE.md",
        "evidence/CP_feasibility_33_EIA_crosswalk.csv",
        "evidence/EIA_OCR_QC_summary.json",
        "evidence/module_assurance_matrix_25.csv",
        "evidence/R3_REMEDIATION_AND_RESIDUAL_HOLDS.md",
        "evidence/REPRODUCIBILITY_AND_QA.md",
        "grid_screen_config.yaml",
        "report/DBPL_build_receipt.json",
        "report/DBPL_Envision14_Wariyapola_SourceSafe_R3_P05.pdf",
        "report/layout_14counted_T2external.png",
        "report/reporting_activation.md",
        "report/windrose_16sector_screening.png",
        "results/finance_screening_hold.json",
        "results/grid_10_case_screening.json",
        "results/wake_7_case_screening.csv",
        "results/wind_robustness_screening.json",
        "results/windrose_16sector_screening.csv",
        "tools/path_guard.py",
        "tools/render_source_safe_dbpl.py",
        "tools/reproduce_grid_screening.py",
        "tools/reproduce_wind_screening.py",
        "tools/test_screening_safety.py",
        "tools/test_source_safe_verifier.py",
        "tools/validate_selective_eia_ocr.py",
        "tools/verify_public_package.py",
        "wind_screen_config.yaml",
    }
)

# Split patterns so this verifier does not trigger its own scan.
PRIVATE_MARKERS = (
    b"/" + b"Users/aruna",
    b"/" + b"Volumes/Data backup",
    b"617725" + "数据导出".encode(),
    b"BEGIN " + b"PRIVATE KEY",
    b"sk-ant-" + b"api",
)


def csv_rows(relative: str) -> list[dict[str, str]]:
    with (PKG / relative).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def inventory_and_privacy() -> dict:
    paths = list(PKG.rglob("*"))
    symlinks = [str(x.relative_to(PKG)) for x in paths if x.is_symlink()]
    if symlinks:
        raise ValueError(
            f"symbolic links disallowed in source-safe package: {symlinks}"
        )
    actual = {str(path.relative_to(PKG)) for path in paths if path.is_file()}
    if actual != ALLOWED:
        raise ValueError(
            f"unexpected or missing package assets (reject by default): "
            f"new={sorted(actual - ALLOWED)}, missing={sorted(ALLOWED - actual)}"
        )
    images = []
    for relative in sorted(actual):
        file = PKG / relative
        contents = file.read_bytes()
        if not contents:
            raise ValueError(f"Empty package asset: {relative}")
        if any(token in contents for token in PRIVATE_MARKERS):
            raise ValueError(f"Potential confidential path/key material: {relative}")
        suffix = file.suffix.lower()
        if suffix == ".pdf":
            continue
        if suffix == ".png":
            if contents[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"not an actual PNG: {relative}")
            images.append(relative)
        elif suffix in {".json", ".md", ".csv", ".yaml", ".py"}:
            try:
                contents.decode("utf-8")
            except UnicodeError as exc:
                raise ValueError(f"unexpected non-text bytes: {relative}") from exc
        else:
            raise ValueError(f"unapproved asset extension: {relative}")
        if file.stat().st_size > 2_000_000:
            raise ValueError(f"unexpected large artifact: {relative}")
    if len(images) != 2:
        raise ValueError("unexpected binary figure count")
    return {"allowlisted_files": len(actual), "derived_pngs": len(images)}


def verify() -> dict:
    inventory = inventory_and_privacy()
    modules = csv_rows("evidence/module_assurance_matrix_25.csv")
    cross = csv_rows("evidence/CP_feasibility_33_EIA_crosswalk.csv")
    inputs = csv_rows("evidence/consolidated_input_21.csv")
    rose = csv_rows("results/windrose_16sector_screening.csv")
    wake = csv_rows("results/wake_7_case_screening.csv")
    grid = json.loads((PKG / "results/grid_10_case_screening.json").read_text())
    finance = json.loads((PKG / "results/finance_screening_hold.json").read_text())
    stress = json.loads((PKG / "results/wind_robustness_screening.json").read_text())
    receipt = json.loads((PKG / "report/DBPL_build_receipt.json").read_text())

    if tuple(
        map(len, (modules, cross, inputs, rose, wake, grid["cases"], stress["cases"]))
    ) != (25, 33, 21, 16, 7, 10, 5):
        raise ValueError("unexpected scope/count in R3 register")
    cp = [row for row in cross if row["type"] == "condition_precedent"]
    feas = [row for row in cross if row["type"] == "feasibility_section"]
    if len(cp) != 13 or len(feas) != 20:
        raise ValueError("not 13 CP and 20 feasibility sections")
    if Counter(row["coverage"] for row in cp) != {
        "supporting": 2,
        "contextual": 7,
        "none": 4,
    }:
        raise ValueError("historical CP coverage drift")
    if Counter(row["coverage"] for row in feas) != {
        "substantial": 4,
        "partial": 11,
        "insufficient": 5,
    }:
        raise ValueError("historical feasibility coverage drift")
    if any("NOT ASSESSED" not in row["revised_project_status"] for row in feas):
        raise ValueError("historic EIA falsely attributed to revised project")
    if any(row["completion_status"].startswith("VERIFIED") for row in cross):
        raise ValueError("unsupported CP/feasibility completion")
    if any(not 0 < float(row["weibull_k"]) for row in rose):
        raise ValueError("invalid Weibull source")
    if abs(sum(float(row["frequency"]) for row in rose) - 1) > 0.0001:
        raise ValueError("rose frequencies incomplete")
    if finance["finance_KPIs_promoted"] is not False:
        raise ValueError("conditional energy improperly promoted")
    if not finance["pipeline_status"].startswith("FAILED_LOUD"):
        raise ValueError("AEP provenance guard removed")
    if "NOT_P90" not in finance:
        # Explicitly check the renamed nonbankable field rather than relying on prose.
        if "illustrative_uncertainty_ratio_transfer_gwh_NOT_P90" not in finance:
            raise ValueError("provisional P90 mislabeled as lender grade")
    if grid["status"] != "ILLUSTRATIVE_NON_BANKABLE":
        raise ValueError("utility SCR is not certified")
    if any("bankable" in row and row["bankable"] for row in grid["cases"]):
        raise ValueError("grid screen improperly flagged bankable")
    if "transformer_n_minus_one" not in grid:
        raise ValueError("N-1 missing transformer limitation")
    baseline = next(
        row
        for row in wake
        if row["name"] == "nasa_mcp_16sector_14plus_external_T2"
        and float(row["TI"]) == 0.10
    )
    if abs(float(baseline["net_screening_aep_gwh"]) - 462.9226999232198) > 1e-8:
        raise ValueError("source baseline mismatch")
    rotated = [row for row in stress["cases"] if "_rose_" in row["case"]]
    if (
        len(rotated) != 2
        or not 407 <= min(row["net_screening_gwh"] for row in rotated) <= 408
    ):
        raise ValueError("adverse rose stress missing")

    pdf = PKG / "report/DBPL_Envision14_Wariyapola_SourceSafe_R3_P05.pdf"
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != receipt["sha256"]:
        raise ValueError("DBPL PDF checksum mismatch")
    if not receipt.get("integrity_receipt_only_not_independent_source_certification"):
        raise ValueError("receipt falsely claims independent source proof")
    for rel, expected in receipt.get("source_inputs_sha256", {}).items():
        if (
            rel not in ALLOWED
            or hashlib.sha256((PKG / rel).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("report input SHA mismatch")
    if len(receipt.get("source_inputs_sha256", {})) < 8:
        raise ValueError("missing report source input digest manifest")
    with pymupdf.open(pdf) as report:
        if len(report) != receipt["pages"] or len(report) < 13:
            raise ValueError("unexpected report page count")
        if any(page.get_images(full=True) for page in report):
            raise ValueError("source images embedded in DBPL")
        if report.embfile_count() > 0:
            raise ValueError("embedded file inside PDF")
        for page in report:
            if (
                page.get_links()
                or list(page.annots() or ())
                or list(page.widgets() or ())
            ):
                raise ValueError(
                    "active PDF links, annotations or widgets not permitted"
                )
        if any(
            b"/JavaScript" in report.xref_object(i, compressed=False).encode()
            or b"/OpenAction" in report.xref_object(i, compressed=False).encode()
            or b"/Launch" in report.xref_object(i, compressed=False).encode()
            for i in range(1, report.xref_length())
        ):
            raise ValueError("active PDF JavaScript/open action prohibited")
        text = " ".join(page.get_text() for page in report)
        metadata = " ".join(str(v) for v in report.metadata.values())
        if any(
            token in text.encode() or token in metadata.encode()
            for token in PRIVATE_MARKERS
        ):
            raise ValueError(
                "private evidence/path marker inside PDF decoded text or metadata"
            )
        if re.search(
            r"(?:/Users/|/Volumes/|file://|BEGIN\s+PRIVATE\s+KEY)", text + metadata
        ):
            raise ValueError("absolute local path or private material inside PDF")
        for label in (
            "Wariyapola",
            "F-5 HOLD",
            "462.923",
            "13. Insurance",
            "20. Appendices",
            "render_source_safe_dbpl.py",
            "CHANGES_REQUESTED",
            "453.664",
            "377.175",
        ):
            if label.casefold() not in text.casefold():
                raise ValueError(f"missing R3 report qualification: {label}")
        if "Generated by run_full_pipeline_v14" in text:
            raise ValueError("false lender pipeline generation provenance")
        if any(
            not 594 < page.rect.width < 597 or not 840 < page.rect.height < 844
            for page in report
        ):
            raise ValueError("DBPL not on A4 paper")
    return {
        "status": "PASS_SAFE_INVENTORY_AND_R3_SCREENING",
        **inventory,
        "modules": len(modules),
        "historical_conditions_precedent": len(cp),
        "historical_feasibility_sections": len(feas),
        "input_dependencies": len(inputs),
        "wind_sector_count": len(rose),
        "wind_cases": len(wake),
        "adversarial_wind_cases": len(stress["cases"]),
        "grid_cases": len(grid["cases"]),
        "DBPL_pages": receipt["pages"],
        "DBPL_sha256": digest,
        "receipt_is_integrity_only": True,
        "F5_hold": True,
        "R3_review_complete": False,
        "external_rights_clearance": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
