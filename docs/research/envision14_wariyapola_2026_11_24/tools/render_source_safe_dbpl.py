"""Emit a source-safe DBPL-01 analytical working copy from already-public aggregates.

Intentionally excludes confidential OEM curve, raw met-mast measurements, original
EIA pages and original lender report. This output is NOT the full private report,
not independent review, and not a bankable source or finance model release.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path

import pymupdf

from app.reports.dbpl.print_core import render_dbpl_pdf
from app.reports.lender_report_emit import DbplFurniture, to_dbpl_print_html

PKG = Path(__file__).resolve().parents[1]


def read_csv(relative: str) -> list[dict[str, str]]:
    with (PKG / relative).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def E(value: object) -> str:
    return html.escape(str(value), quote=True)


def P(value: object) -> str:
    return "<p>" + E(value) + "</p>"


def H(value: str) -> str:
    return "<h2>" + E(value) + "</h2>"


def SUB(value: str) -> str:
    return "<h3>" + E(value) + "</h3>"


def table(headers: list[str], rows: list[tuple[object, ...]]) -> str:
    return (
        "<table><thead><tr>"
        + "".join("<th>" + E(x) + "</th>" for x in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join("<td>" + E(y) + "</td>" for y in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table>"
    )


def create() -> tuple[Path, int]:
    wind = read_csv("results/wake_7_case_screening.csv")
    grid = json.loads((PKG / "results/grid_10_case_screening.json").read_text())
    finance = json.loads((PKG / "results/finance_screening_hold.json").read_text())
    modules = read_csv("evidence/module_assurance_matrix_25.csv")
    cp_feas = read_csv("evidence/CP_feasibility_33_EIA_crosswalk.csv")
    required = read_csv("evidence/consolidated_input_21.csv")
    assert (
        len(wind),
        len(grid["cases"]),
        len(modules),
        len(cp_feas),
        len(required),
    ) == (
        7,
        10,
        25,
        33,
        21,
    )
    assert finance["finance_KPIs_promoted"] is False
    sections: list[str] = [
        H("Executive scope and independent work status"),
        P(
            "This is a source-safe public-repository reproduction of a private Dutch Bay "
            "working analysis, not a lender report or a regulator-reviewed design. "
            "It covers the 14 Envision EN206/10.5 turbines (T1 and T3-T15), the "
            "separately costed Blue Whale at T2 as an external wakemaker, preliminary "
            "resource and array wakes, the 220 kV proposed Wariyapola line, the 25 "
            "analytical-module gap list, and all 33 canonical EIA-to-feasibility items."
        ),
        table(
            ["Controlling input", "Proposed case", "Quality gate"],
            [
                (
                    "Turbine",
                    "Envision EN206/10.5; 206 m rotor; 130 m hub",
                    "9.5 MW capped mode not OEM-certified",
                ),
                (
                    "Farm / T2",
                    "14 counted turbines; T2 external Blue Whale",
                    "Actual turbine interactions and loads need approval",
                ),
                (
                    "Capacity",
                    "147 MW nameplate; 133 MW at 9.5 MW assumed cap",
                    "Not equivalent to certified MVA at PCC",
                ),
                (
                    "Resource",
                    "16-sector 2015-25 NASA/MERRA-2 + partial 2025 mast transfer",
                    "No site-certified bankable EYA",
                ),
                (
                    "EIA",
                    "Historical 15xEN220/10 layout; annex Wariyapola route",
                    "14xEN206 design change not approved",
                ),
                (
                    "Electricity",
                    "EIA 104.77 km twin-Zebra 220 kV double circuit",
                    "Source fault level and X are provisional",
                ),
                (
                    "Project COD",
                    "Legacy financial 2027 vs national line planned 2030",
                    "Critical-path decision open",
                ),
            ],
        ),
        H("1. Wind-sector resource and 14-Envision energy screening"),
        P(
            "The available mast record covers roughly 232 days of March-November 2025, "
            "not a full long-term on-site campaign. The public frozen Blue Whale MCP "
            "result used NASA POWER/MERRA-2 2015-2025 and a 16-sector 130 m wind rose. "
            "The source owner's original confidential 10.5 MW power/Ct curve is "
            "read only at reproduction time and capped to 9.5 MW. Such clipping may "
            "differ from a certified derated operation mode."
        ),
        table(
            ["Wind basis / case", "TI", "Counted", "Gross GWh", "Wake loss", "Net GWh"],
            [
                (
                    x["name"].replace("_", " "),
                    x["TI"],
                    x["counted"],
                    f'{float(x["gross_aep_gwh"]):.2f}',
                    f'{float(x["wake_loss_pct"]):.2f}%',
                    f'{float(x["net_screening_aep_gwh"]):.2f}',
                )
                for x in wind
            ],
        ),
        P(
            "Primary case (T2 active, TI 0.10): 616.043 GWh gross, 18.522% modelled "
            "array-wake loss and 462.923 GWh net screening energy after inherited "
            "non-wake losses. Legacy ERA5-fitted case gives 370.332 GWh, indicating "
            "substantial unresolved met-climate / wake basis uncertainty. "
            "Blue Whale T2 is excluded from owned generation, not from wakes."
        ),
        H("2. Finance AEP boundary and source-quality refusal"),
        table(
            ["Quantity", "Value", "Status"],
            [
                (
                    "Screening net energy",
                    "462.923 GWh",
                    "Physical screening, no lender P50",
                ),
                (
                    "Legacy conservative preconstruction haircut",
                    "2%",
                    "Policy reused provisionally",
                ),
                (
                    "Conditional billing screen",
                    f'{finance["conditional_billing_aep_gwh"]:.3f} GWh',
                    "Not bankable",
                ),
                (
                    "Transferred one-year P90-like",
                    f'{finance["unqualified_one_year_p90_like_gwh"]:.3f} GWh',
                    "Not accepted project P90",
                ),
                ("Financial case promoted?", "No", "AEP provenance refusal retained"),
                (
                    "Committed turbine/power curves altered?",
                    "No",
                    "Only external scenario built",
                ),
            ],
        ),
        P(
            "The original full finance pipeline correctly rejected the screening "
            "AEP export as not meeting source-provenance requirements. No IRR, DSCR, "
            "gearing, live tariff or lender model KPI is promoted by this study. "
            "Earlier P01 private lender reports remain on their older IEA baseline "
            "and should not be represented as revised Envision lendercases."
        ),
        H("3. Wariyapola 220 kV proposed interconnection and advisory SCR"),
        P(
            "The project-specific EIA Annex III I, PDF pages 138-142 and 160, "
            "describes an approximately 104.77 km Kalpitiya–Wariyapola double-circuit "
            "220 kV overhead line, twin Zebra conductors, two added 220 kV bays, "
            "and 2x90 MVA 33/220 kV collector transformers. The annex quotes "
            "0.0702 ohm/km AC resistance at 25 degrees C. Positive-sequence "
            "reactance 0.27 ohm/km/circuit and all upstream fault levels below "
            "are illustrative unverified assumptions."
        ),
        table(
            ["Assumed source MVA", "SCR both circuits", "SCR N-1", "Reliance"],
            [
                (
                    int(mva),
                    f'{next(c["scr"] for c in grid["cases"] if c["source_fault_level_mva_SCREENING_ASSUMPTION"] == mva and c["circuits"] == 2):.2f}',
                    f'{next(c["scr"] for c in grid["cases"] if c["source_fault_level_mva_SCREENING_ASSUMPTION"] == mva and c["circuits"] == 1):.2f}',
                    "Advisory only",
                )
                for mva in (500, 700, 900, 1100, 1500)
            ],
        ),
        P(
            "The project's 104.77 km EIA line must not silently be equated with "
            "the national Norochcholai–Wariyapola 220 kV project announced in "
            "November 2025. The NSO 2026 interim plan schedules the latter for "
            "2030, compared with the older Dutch Bay lendercase's 2027 COD. "
            "A certified NTNSP/NSO network study, utility fault envelope, PCC, "
            "line permits, wayleaves and commissioning dependency are outstanding."
        ),
        H("4. Conditions precedent — thirteen items"),
    ]
    for r in cp_feas[:13]:
        sections.append(
            SUB(
                f'{r["canonical_number"]}. {r["canonical_key"].replace("_", " ").title()}'
            )
            + table(
                [
                    "Coverage",
                    "Supporting EIA/annex pages",
                    "Qualifying evidence still owed",
                ],
                [
                    (
                        r["coverage"],
                        r["source_pdf_page_refs"],
                        r["unverified_or_missing_evidence"],
                    )
                ],
            )
        )
    sections.append(
        P(
            "Coverage is an EIA-content assessment, not satisfaction of financing CPs. "
            "Six CPs have useful supporting source material; four contextual only; "
            "three have no qualifying EIA evidence. None is certified complete."
        )
    )
    sections.append(H("5. Full 20-section feasibility coverage"))
    for r in cp_feas[13:]:
        sections.append(
            SUB(
                f'{r["canonical_number"]}. {r["canonical_key"].replace("_", " ").title()}'
            )
            + table(
                ["EIA coverage", "Pages", "Needed to complete"],
                [
                    (
                        r["coverage"],
                        r["source_pdf_page_refs"],
                        r["unverified_or_missing_evidence"],
                    )
                ],
            )
        )
    sections.extend(
        [
            P(
                "The EIA provides substantial coverage to five feasibility "
                "sections, partial to ten, and insufficient to five. "
                "That is not a 75%-complete lender feasibility deliverable."
            ),
            H("6. Analytical modules absent from the full report"),
            table(
                ["Module", "Missing / not-run presentation"],
                [
                    (
                        r["module"],
                        r["current_report"],
                    )
                    for r in modules
                ],
            ),
            H("7. Activation and evidence dependency register"),
            table(
                ["Item / next evidence", "Current maturity", "Responsible discipline"],
                [
                    (
                        r["input_or_decision"] + " — " + r["needed_for_promotion"],
                        r["maturity"],
                        r["suggested_owner"],
                    )
                    for r in required
                ],
            ),
            H("8. Release protection and source classifications"),
            P(
                "This public-branch derivative does NOT contain or reproduce the "
                "confidential released OEM power/Ct values, the raw 2025 met-mast "
                "interval observations, EIA full-text/annex images, or the original "
                "private 48/13/11-page DBPL reports. Access the original materials "
                "through the authorized private evidence repository, not public Git. "
                "No signed environmental approval, land right, grid connection, "
                "PPA, EPC, equity commitment or lender security is proved here."
            ),
            P(
                "GWTF/RECRUIT R3: domain and assurance reviewer attestations remain "
                "UNASSIGNED. The 9.5 MW derated operating characteristic, wake loads, "
                "site-specific P50/P90, utility SCR, 220 kV route and line delivery "
                "schedule need independent source control and acceptance. The F-5 "
                "Board, lender, covenant and publication HOLD remains unchanged. "
                "The source-safe calculations are valid only as clearly identified "
                "screening exercises."
            ),
        ]
    )
    safe = '<html lang="en"><head><meta charset="utf-8"></head><body>'
    safe += "<h1>Dutch Bay — Envision 14-turbine and Wariyapola 220kV assurance</h1>"
    safe += "".join(sections) + "</body></html>"
    assert not any(
        forbidden in safe
        for forbidden in ("/Volumes/", "/Users/", "617725数据", "power_curve_en206_")
    )

    status = (
        "RESTRICTED DERIVED EVIDENCE | R3 SCREENING | F-5 HOLD | "
        "NOT FOR BANKABLE LENDER / UTILITY / REGULATORY RELIANCE"
    )
    control = (
        ("Document ID", "DBAY-EN20614-SOURCE-SAFE-EVIDENCE-P03"),
        ("Version", "P03"),
        ("Date", "2026-11-24"),
        ("Work item", "#1939 / tracker #1353"),
        ("Classification", "Public-branch-safe derivative; SCREENING ONLY"),
        ("Status", "F-5 HOLD / R3 reviewers PENDING"),
        (
            "Source basis",
            "Full private evidence held separately; only derived data published",
        ),
    )
    furniture = DbplFurniture(
        document_id="DBAY-EN20614-SOURCE-SAFE-EVIDENCE-P03",
        version="P03",
        issue_date="2026-11-24",
        status="DRAFT",
        banner=status,
        title="Envision 14-Turbine / Wariyapola 220kV Working Evidence",
        caveat=(
            "R3 SCREENING ONLY — no source approval, no lender energy-yield "
            "promotion, no certified utility model, and no consent/finance closure. "
            "Original copyrighted/confidential source remains private."
        ),
        control=control,
        revisions=(
            {
                "rev": "P03",
                "date": "2026-11-24",
                "status": "DRAFT / F-5 HOLD",
                "prepared": "Evidence compilation",
                "checked": "PENDING",
                "reviewed": "PENDING",
                "approved": "PENDING",
            },
        ),
        table_source=(
            "Public source-safe aggregate evidence only: private OEM curve not "
            "reproduced; derived wind/short-circuit model results not independently "
            "certified; physical EIA PDF page numbers cited in crosswalk."
        ),
    )
    first = render_dbpl_pdf(to_dbpl_print_html(safe, furniture), deep_check=True)
    furniture_with_provenance = DbplFurniture(
        **{**furniture.__dict__, "provenance_lines": tuple(first.provenance_lines())}
    )
    final = render_dbpl_pdf(
        to_dbpl_print_html(safe, furniture_with_provenance), deep_check=True
    )
    target = PKG / "report/DBPL_Envision14_Wariyapola_SourceSafe_R3_P03.pdf"
    target.write_bytes(final.pdf)
    with pymupdf.open(target) as document:
        pages = len(document)
        full_text = " ".join(page.get_text() for page in document)
        assert all(
            x in full_text
            for x in ("453.664", "462.923", "Wariyapola", "F-5", "not a 75%")
        ), "Expected safety or figure text absent"
        assert all(
            round(page.rect.width, 1) == 595.3 and round(page.rect.height, 1) == 841.9
            for page in document
        )
        assert all(len(page.get_text().strip()) >= 30 for page in document)
        assert len(document) >= 8
    report = {
        "status": "R3_UNREVIEWED_F5_HOLD",
        "source_safe": True,
        "pages": pages,
        "module_count": len(modules),
        "CP_and_feasibility_count": len(cp_feas),
        "inputs_in_register": len(required),
        "sha256": hashlib.sha256(final.pdf).hexdigest(),
        "fonts_embedded": bool(final.house_fonts_embedded),
    }
    (PKG / "report/DBPL_build_receipt.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return target, pages


if __name__ == "__main__":
    p, pages = create()
    print("RENDERED_SOURCE_SAFE_DBPL", p.name, "pages", pages)
