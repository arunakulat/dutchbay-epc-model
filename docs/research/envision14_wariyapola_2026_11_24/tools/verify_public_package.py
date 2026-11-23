"""Source-safe static/DBPL QA and screen audit.
No secrets or private data required to run this verifier.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pymupdf

PKG = Path(__file__).resolve().parents[1]


def csv_rows(relative: str) -> list[dict]:
    with (PKG / relative).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def verify() -> dict:
    modules = csv_rows("evidence/module_assurance_matrix_25.csv")
    cp_feas = csv_rows("evidence/CP_feasibility_33_EIA_crosswalk.csv")
    inputs = csv_rows("evidence/consolidated_input_21.csv")
    rose = csv_rows("results/windrose_16sector_screening.csv")
    wake = csv_rows("results/wake_7_case_screening.csv")
    grid = json.loads((PKG / "results/grid_10_case_screening.json").read_text())
    finance = json.loads((PKG / "results/finance_screening_hold.json").read_text())
    pdf_receipt = json.loads((PKG / "report/DBPL_build_receipt.json").read_text())

    assert (len(modules), len(cp_feas), len(inputs), len(rose), len(wake)) == (
        25,
        33,
        21,
        16,
        7,
    )
    assert len(grid["cases"]) == 10
    assert {r["type"] for r in cp_feas} == {
        "condition_precedent",
        "feasibility_section",
    }
    cp = [x for x in cp_feas if x["type"] == "condition_precedent"]
    feas = [x for x in cp_feas if x["type"] == "feasibility_section"]
    assert len(cp) == 13 and len(feas) == 20
    assert Counter(x["coverage"] for x in cp) == {
        "supporting": 6,
        "contextual": 4,
        "none": 3,
    }
    assert Counter(x["coverage"] for x in feas) == {
        "substantial": 5,
        "partial": 10,
        "insufficient": 5,
    }
    assert abs(sum(float(r["frequency"]) for r in rose) - 1) < 0.0001
    base = next(
        r
        for r in wake
        if r["name"] == "nasa_mcp_16sector_14plus_external_T2"
        and float(r["TI"]) == 0.10
    )
    assert abs(float(base["net_screening_aep_gwh"]) - 462.9226999232198) < 1e-8
    assert abs(float(base["wake_loss_pct"]) - 18.522357329555582) < 1e-8
    assert finance["finance_KPIs_promoted"] is False
    assert finance["pipeline_status"].startswith("FAILED_LOUD")
    assert all("bankable" not in x or x["bankable"] is False for x in grid["cases"])
    assert grid["status"] == "ILLUSTRATIVE_NON_BANKABLE"
    pdf = PKG / "report/DBPL_Envision14_Wariyapola_SourceSafe_R3_P03.pdf"
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert digest == pdf_receipt["sha256"]
    with pymupdf.open(pdf) as d:
        assert len(d) == pdf_receipt["pages"] == 13
        assert all(len(p.get_images()) == 0 for p in d), "source page image leak"
        text = " ".join(p.get_text() for p in d)
        for phrase in [
            "Wariyapola",
            "F-5 HOLD",
            "462.923",
            "13. Insurance",
            "20. Appendices",
        ]:
            assert phrase.lower() in text.lower(), phrase
        assert all("/Volumes/" not in p.get_text() for p in d)
    # Scan source-safe text files, not the original private PDF/raw dataset.
    bad = ["/" + "Users/aruna", "/" + "Volumes/Data backup", "617725" + "数据导出"]
    leak = []
    for p in PKG.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".csv", ".yaml", ".json", ".py"}:
            s = p.read_text(encoding="utf-8")
            leak.extend(str(p.relative_to(PKG)) for needle in bad if needle in s)
    assert not leak, leak
    return {
        "status": "PASS",
        "analytical_modules": len(modules),
        "conditions_precedent": len(cp),
        "feasibility_sections": len(feas),
        "data_inputs": len(inputs),
        "wind_rose_sectors": len(rose),
        "wake_cases": len(wake),
        "grid_cases": len(grid["cases"]),
        "DBPL_pages": pdf_receipt["pages"],
        "DBPL_sha256": digest,
        "raw_EIA_or_OEM_images_embedded": False,
        "financial_reliance": False,
        "R3_review_complete": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
