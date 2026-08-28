"""NSO 250 MW BESS — tender evidence gap register, 27 August 2026.

Instance data for :mod:`app.reports.tender_gap_dossier_emit`. That emitter is vendor-neutral
machinery and hard-codes no tender, OEM, bidder or finding; THIS file is the register that
instantiates it, and it inherits the classification of the evidence it describes.

Every gap is anchored to a controlling clause in a document held in this corpus. A finding that
could not be confirmed from a corpus document carries ``verified=False`` and states its basis in
its own text, rather than being asserted or dropped — see gaps B2 and B3.

The register supersedes parts of the 31 July 2026 detailed gap statement and of the 21 August 2026
checklist ingress evaluation, on the authority of the controlling documents ingressed on
27 August 2026 (Addendum No. 01, Annex A, and the 76-item clarification register). The
"What changed since the 31 July gap statement" section below records each supersession.

Run from the repository root, with the ``[report]`` extra installed::

    PYTHONPATH=. python docs/source_materials/nso_bess_250mw_2026/registers/\
        build_gap_dossier_2026-08-27.py <output.pdf>

Rendering requires WeasyPrint (the ``[report]`` extra). Absent it, ``render_dbpl_pdf`` raises
``DbplDependencyError`` rather than emitting a degraded document.
"""

from __future__ import annotations

from app.reports.tender_gap_dossier_emit import (
    EvidenceLine,
    GapItem,
    SourceDocument,
    as_dbpl_document,
    build_dossier,
)

TENDER_REF = "TR/REP&PM/ICB/2026/001/C"
TENDER_TITLE = (
    "Establishment of 250 MW / 1000 MWh Standalone Battery Energy Storage System from "
    "10 MW / 40 MWh AC Capacity Projects on Build, Own and Operate (BOO) Basis with "
    "15 Year Operational Period"
)

SOURCES: tuple[SourceDocument, ...] = (
    SourceDocument(
        label="NSO RFP Volume I — Instructions to Project Proponents",
        role="controlling tender volume",
        sha256="fb61a4f827a0142e15c423cc2ea327a4035c596013b60f547065dff3976535a8",
        extraction="native",
        document_date="July 2026",
    ),
    SourceDocument(
        label="NSO RFP Volume II — proposal forms and compliance schedule",
        role="controlling tender volume",
        sha256="41644c2072137e7f13dc081c4965602335b8ab01378f4d47a6c90d13a61bdf0e",
        extraction="native",
        document_date="July 2026",
    ),
    SourceDocument(
        label="NSO RFP Volume III — Model Energy Storage Agreement",
        role="controlling tender volume",
        sha256="d3413e9d1a1b0d77b5da219e2d8a6c8d09899aa1de2f9c30aac5e9a7a9dfda3e",
        extraction="native",
        document_date="July 2026",
    ),
    SourceDocument(
        label="Addendum No. 01",
        role="controlling amendment — overrides the volumes it amends",
        sha256="2b99b1e507d8c1bfb235578250d4aa608700dd7c50c8374e2ddc320e390d7aa1",
        extraction="markitdown",
        document_date="7 August 2026",
        note="23 items. Complete embedded text layer; Attachments 1-4 are separate files "
        "and are NOT in this PDF or in the corpus.",
    ),
    SourceDocument(
        label="Annex A — Functional and Performance Requirement",
        role="controlling technical annex",
        sha256="be599073f5977a591022591ae9e28c376a3bd04528fa7a6501592617462fe5bb",
        extraction="markitdown",
        document_date="26 June 2026 (file creation)",
        note="27 pp. A.05.01(a) gives this annex precedence over the Grid Connection Code "
        "where they differ. Figures on 6 pages are not reproduced in the text extract.",
    ),
    SourceDocument(
        label="Clarifications for the RFP — 76 numbered items",
        role="controlling clarification register",
        sha256="73fbaca1a7e7c9e94766fdd04d93f9809764fd36d773bd1d363cbc56fda5e820",
        extraction="ocr",
        document_date="21 August 2026 (scan date)",
        note="IMAGE-ONLY SCAN — no text layer. MarkItDown returned an empty document and "
        "tesseract scrambled the two-column table, so all 15 content pages were read as page "
        "images. Quotations here come from that verified transcript, not from the OCR text.",
    ),
    SourceDocument(
        label="Envision design calculation, 10 MW / 40 MWh, V1.0",
        role="OEM evidence — superseded",
        sha256="7281d964654e606cdcd2c584ad93ef6b179d6e041dcd691613d9b3e62a04500a",
        extraction="native",
        document_date="29 July 2026",
        note="Superseded by a 5 August document that still carries version V1.0.",
    ),
    SourceDocument(
        label="Envision design calculation, 11 MW / 44 MWh, V1.0",
        role="OEM evidence — distinct candidate configuration",
        sha256="0cf77ec5d7615c611e0a5cbbf7ab8c3f8a6a722e5b31e42a25fad27f88841e86",
        extraction="native",
        document_date="5 August 2026",
        note="Does not state the tender number.",
    ),
    SourceDocument(
        label="Envision functional-requirements checklist",
        role="supplier declaration — not evidence",
        sha256="8236806c21f651fdf78591f9665cd68632e2f195e810f10d7d2f946325e0bd49",
        extraction="ooxml",
        document_date="21 July 2026 (metadata)",
        note="48 Yes / 7 No / 1 Partial across 56 rows. No tender identifier, signatory, "
        "revision or evidence-reference column.",
    ),
    SourceDocument(
        label="DutchBay detailed gap statement (prior issue)",
        role="derived analysis — superseded in part by this register",
        sha256="ce4a996893b55ac45479cd193908b37d797f0108e619b57709914d79a15f564a",
        extraction="markitdown",
        document_date="31 July 2026",
    ),
    SourceDocument(
        label="Bidder evidence dossier, checklist sections A-J",
        role="OEM evidence — held outside the repository, manifest only",
        sha256=None,
        extraction="manual",
        document_date="21 August 2026",
        note="72 files / 58 unique. Binaries are NOT committed (third-party copyright, "
        "compiled control code, personal data). Findings against this package are carried "
        "forward from the 21 August ingress evaluation, which read the originals.",
    ),
    SourceDocument(
        label="Envision Product Warranty Policy V1.0",
        role="OEM commercial terms — the warranty actually offered",
        sha256="2ac08c42431b9c1d8a60e066710de95724f9b4fcc7ec3c9409c6a5e527c8c9cf",
        extraction="markitdown",
        document_date="undated; version 1.0, marked Confidential",
        note="5 pp. Table 1 sets ONE warranty period for every listed item. Carries no "
        "document number and no signature block.",
    ),
    SourceDocument(
        label="Envision LTSA Solution — service scope matrix",
        role="OEM commercial offer — draft scope matrix, unpriced",
        sha256="53a51d5c3c9cf91763f01b35086bb1bf2e97ba4357a0265d7b26223547be4123",
        extraction="ooxml",
        document_date="undated; BESS tab labelled '100225-Draft'",
        note="Two tabs. The first, 'WTG-1228ver', is a WIND TURBINE service catalogue and "
        "is not about this project. The BESS tab is a scope matrix only: no prices, no "
        "guarantee levels, no term, no signature.",
    ),
)

EVIDENCE: tuple[EvidenceLine, ...] = (
    EvidenceLine(
        item="PSS(R)E RMS model, grid-forming",
        declared="Checklist item 48 — Received",
        received="Executable DLLs, Sri-Lanka dynamic record ENVSG_PPC_2520_260416_LKA.dyr "
        "(ENGFM01 + BNPPC_GFMV3), manual V1.4a",
        adequate=True,
        note="Satisfies half of Annex A A.05.23(d)(I). The manual itself states EMT is the "
        "better tool for fault ride-through.",
    ),
    EvidenceLine(
        item="PSCAD/EMTDC EMT model",
        declared="Checklist item 49 — Received",
        received="PCS2520x4_UPPC_x64_260605aBB.pscx — manual titled for the GFL PCS variant, "
        "model block labelled GFL-PCS, converter represented as a current source",
        adequate=False,
        note="Accepted for the A.05.23(d)(I) bid-stage minimum as an EMT model in PSCAD "
        "format, but cannot demonstrate voltage-source behaviour under fault.",
    ),
    EvidenceLine(
        item="Grid-forming capability letter",
        declared="Checklist item 37 — Received",
        received="Signed Envision letter asserting full grid-forming voltage-source operation "
        "under all operating conditions",
        adequate=False,
        note="Contradicted by the item 61 compliance list (dual-mode) and by the GFL EMT "
        "model. See gap A1.",
    ),
    EvidenceLine(
        item="Grid-forming modelling evidence",
        declared="Checklist item 38 — Received",
        received="A BESS plant BLACK-START technical solution, V1.0, marked 'for reference'",
        adequate=False,
        note="Not modelling evidence: no simulation results, no V/F characteristic, no fault "
        "response, no SCR sweep. Clarification 37 also confirms black start is NOT mandatory, "
        "so this document answers no tender requirement at all.",
    ),
    EvidenceLine(
        item="End-of-life recycling commitment",
        declared="Checklist item 57 — filed",
        received="A mechanical disassembly work instruction (tool list, cable disconnection, "
        "lifting procedure)",
        adequate=False,
        note="Zero occurrences of recycling, disposal, waste, take-back, second-life or Sri "
        "Lanka environmental regulation in the full extract.",
    ),
    EvidenceLine(
        item="Manufacturer's Authorization Letter",
        declared="Checklist item 58 — Received",
        received="Three EOI letters present; NO MAL in the package",
        adequate=False,
    ),
    EvidenceLine(
        item="Cell certification (UL 1973)",
        declared="Certified",
        received="UL 1973 component recognition (BBGA2), cell level, in the cell-manufacturing "
        "entity's name",
        adequate=False,
        note="The certificate states UL Recognized components are incomplete in certain "
        "constructional features. System-level UL 9540 is self-declared 'partially comply / "
        "future'.",
    ),
    EvidenceLine(
        item="Fire safety — UL 9540A",
        declared="Checklist item 45 — Received",
        received="Cell-level (2019) and module-level (2026) reports; Fire Protection System "
        "Specification V2.0 headed for ENS-D10",
        adequate=False,
        note="The module report's own conclusion requires a further test level. The offered "
        "configuration pairs ENS-D10G with ENS-D06G; D06G coverage is unevidenced.",
    ),
    EvidenceLine(
        item="Offered PCS track record",
        declared="22 PCS reference projects supplied",
        received="References list ENPCS 2750, 3450, 3300 and 2500. The offered ENPCS2520 "
        "appears in none of them. Client-contact column empty on every PCS and PPC row",
        adequate=False,
    ),
    EvidenceLine(
        item="Independent cell bankability study",
        declared="Checklist item 47 — Received",
        received="Genuine third-party test-house Technical Advisory Report, Issue D Final, "
        "28 January 2026, prepared for the battery affiliate",
        adequate=True,
        note="Adequate as an independent study — and it is the source of the 45 degrees C "
        "cycle-life exposure at gap A3.",
    ),
)

GAPS: tuple[GapItem, ...] = (
    # ── CRITICAL ────────────────────────────────────────────────────────────────────────
    GapItem(
        gap_id="A1",
        title="No artifact demonstrates grid-forming behaviour under fault at the required SCR",
        severity="CRITICAL",
        clause="Annex A A.05.17(i) and (j); Volume I §3(c); Annex A A.05.23(e)",
        requirement=(
            "Annex A A.05.17(i): 'The BESS shall support both grid-following and grid-forming "
            "control modes, enabling online switching between the two.' A.05.17(j): 'The "
            "grid-following mode shall operate stably under a minimum short-circuit ratio (SCR) "
            "of 1.2, while the grid-forming mode shall operate stably under a minimum SCR of "
            "1.0.' Volume I §3(c) additionally requires a voltage-sourced, voltage-controlled "
            "inverter that 'should NOT change the control mode to current-controlled "
            "(grid-following) during normal operation or under any network fault conditions'."
        ),
        supplied=(
            "Three inconsistent characterisations of the same converter: (1) item 37, a signed "
            "letter asserting full grid-forming operation at all times; (2) item 61, a grid "
            "compliance list describing GFM and GFL modes with 'seamless transition' at clauses "
            "3.17.4 and 3.17.4.4; (3) item 49, a PSCAD model that is the GFL variant, "
            "represented as a current source. A PSS(R)E grid-forming model with a Sri-Lanka "
            "dynamic record IS supplied, so the RMS grid-forming path is real."
        ),
        why_insufficient=(
            "A current-source EMT model cannot demonstrate voltage-source behaviour under fault, "
            "and the PSS(R)E GFM manual itself records that an EMT tool is the better "
            "recommendation for transient studies including fault ride-through. No supplied "
            "artifact therefore demonstrates grid-forming fault behaviour, and none addresses "
            "the SCR 1.0 grid-forming stability floor at A.05.17(j). IMPORTANT CORRECTION to "
            "the 31 July gap statement and to the 21 August review: the dual-mode capability "
            "itself is REQUIRED by A.05.17(i) and must NOT be withdrawn from the bid. A flat "
            "'no grid-following capability' declaration would now be non-compliant."
        ),
        question=(
            "1. Does a grid-forming PSCAD/EMTDC model of the ENPCS2520 exist? If the GFL model "
            "was supplied in error, please issue the GFM EMT model. If no GFM EMT model exists, "
            "please say so plainly — that answer is needed now, not at ESA signature. "
            "2. Please issue a single reconciled control-mode statement in these terms: the "
            "converter supports both modes with online switching as A.05.17(i) requires; it "
            "operates in grid-forming mode; it does not revert to current-controlled operation "
            "during normal operation or under network fault conditions as Volume I §3(c) "
            "requires; and grid-forming operation is stable to SCR 1.0 per A.05.17(j). "
            "3. Please re-point the 'seamless GFL/GFM transition' language at clauses 3.17.4 / "
            "3.17.4.4 so it is offered as the A.05.17(i) capability and NOT as the basis for "
            "converter robustness under fault."
        ),
        closure_test=(
            "A grid-forming EMT model in PSCAD 5.x that initialises and runs at an SCR of 1.0, "
            "producing V/P/Q traces through a deep fault, with the controller remaining in "
            "voltage-source mode throughout; plus the reconciled written control-mode statement."
        ),
        tier="critical path",
        consequence=(
            "Annex A A.05.23(e) makes the grid-forming demonstration in both PSS(R)E and PSCAD "
            "a condition of the post-award Dynamic Model Tests. Addendum 01 items 06 and 12 "
            "make those results due within one month of ESA execution (14 January 2027) and add "
            "failure to deliver them acceptably to the grounds for forfeiting the Performance "
            "Security."
        ),
    ),
    GapItem(
        gap_id="A2",
        title="The RTE guarantee sits exactly on the floor on a basis that has since been hardened four ways",
        severity="CRITICAL",
        clause="Volume I §2.8(iii); clarifications 5, 31, 40, 51 and 55(b)",
        requirement=(
            "A guaranteed minimum AC-to-AC round-trip efficiency of 85 %, assessed monthly, with "
            "liquidated damages at 150 % of the peak-time 33 kV General Purpose tariff on the "
            "excess losses. Clarification 5: a monthly shortfall 'shall not be carried forward "
            "or reconciled' against later months or the year end. Clarification 51: 'Auxiliary "
            "and HVAC loads that are directly associated with the operation of the BESS Facility "
            "... shall be accounted for in the RTE calculation.' Clarification 31: energy lost "
            "to frequency or voltage regulation in standby, unscheduled by the grid, is counted "
            "in RTE. Clarification 55(b): energy exchanged providing frequency response, "
            "synthetic inertia, oscillation damping and AGC is NOT excluded from the RTE "
            "calculation. Clarification 40, asked whether a 1 % test error could be treated as "
            "meeting the standard: 'No.'"
        ),
        supplied=(
            "The 5 August revision of the 10 MW design calculation moves year-15 RTE including "
            "auxiliaries from 84.9 % to exactly 85.0 %, by changing the DC container generation "
            "from ENS-D10E to ENS-D10G, relaxing the MV cable efficiency assumption from 99.5 % "
            "to 99.6 %, and adding a clause deeming RTE compliant within an assumed 0.5 % "
            "electricity-meter error. Auxiliaries are computed at 35 degrees C. The document "
            "still carries version V1.0 with no revision record."
        ),
        why_insufficient=(
            "Clarification 40 refuses the measurement-tolerance principle outright, so the "
            "0.5 % meter-tolerance clause has no contractual counterpart. Clarifications 31 and "
            "55(b) put two loss terms INSIDE the measured quantity that the design calculation "
            "does not model at all. Clarification 51 closes off the aux-exclusive basis (88.4 %) "
            "that the 30 July review had hoped might apply. Clarification 5 removes annual "
            "averaging. A guarantee sitting exactly on the floor, on a basis carrying two "
            "unmodelled loss terms, assessed monthly with no reconciliation and no tolerance, "
            "is a structurally short position rather than a thin margin."
        ),
        question=(
            "1. Please re-issue the guaranteed RTE schedule on the basis clarifications 51, 31 "
            "and 55(b) actually establish — auxiliary and HVAC inclusive, and including "
            "standby-regulation and ancillary-service energy — and WITHOUT the meter-tolerance "
            "clause, which clarification 40 has refused. "
            "2. Please state the auxiliary load and the resulting guaranteed RTE at 45 degrees C "
            "ambient, not 35 degrees C. "
            "3. If 85.0 % cannot be held on that basis in every year, please say so now and "
            "state the year and the margin, so the bid can be priced against it. "
            "4. Please re-issue the 5 August document with a proper revision number and a change "
            "record against the 29 July version."
        ),
        closure_test=(
            "A guaranteed monthly RTE schedule, by year, at 45 degrees C ambient, aux-inclusive, "
            "with the standby and ancillary-service terms itemised, showing positive margin "
            "above 85.0 % in every year with no tolerance clause relied upon."
        ),
        tier="critical path",
        consequence=(
            "Liquidated damages at 150 % of the peak-time 33 kV GP tariff on excess losses, "
            "assessed every month independently, with no annual reconciliation."
        ),
    ),
    GapItem(
        gap_id="A3",
        title="Cell cycle life at tropical temperature is not substantiated against the contracted throughput",
        severity="CRITICAL",
        clause="Volume I §3.1(k) and §3.1(m); Annex A A.05; clarification 55(b)",
        requirement=(
            "Volume I §3.1(k) requires demonstration of four hours at rated output at site "
            "ambient conditions at commissioning; the site envelope runs to +45 degrees C. The "
            "ESA contracts for 400 full equivalent cycles per year with a floor of 20 per month "
            "— about 6,000 cycles over the 15-year term as a MINIMUM obligation. Clarification "
            "55(b) confirms that energy exchanged providing frequency response, synthetic "
            "inertia, oscillation damping and AGC is not excluded from that 400-cycle allowance."
        ),
        supplied=(
            "The supplier's own independent test-house bankability study (Issue D Final, "
            "28 January 2026) records approximately 10,000 cycles to 70 % capacity retention at "
            "25 degrees C and 0.25P, but only approximately 4,000 cycles at 45 degrees C — a "
            "60 % reduction. The 20-year / 70 %-retention simulation the test house endorses is "
            "qualified to 25 degrees C, at most 50 % SOC and one cycle per day. Checklist items "
            "55 and 56 nonetheless declare 'No Augmentation needed during lifetime' and 'No "
            "replacement needed during lifetime', and both status cells are blank."
        ),
        why_insufficient=(
            "At the 45 degrees C figure in the supplier's own independently reviewed data the "
            "cell reaches the 70 % threshold roughly 2,000 cycles short of what the ESA "
            "contracts for. Stated fairly: the system is liquid-cooled, so cell temperature is "
            "not ambient temperature, and 45 degrees C ambient-soak is not a prediction of cell "
            "temperature in service. That is precisely the problem — the package contains no "
            "thermal model, no cell-temperature substantiation at 45 degrees C ambient, and no "
            "auxiliary-load figure above 35 degrees C. The cooling-energy gap and the cycle-life "
            "gap compound, because the same missing thermal case sets both."
        ),
        question=(
            "1. Please supply the thermal case at 45 degrees C ambient: coolant supply "
            "temperature, resulting steady-state CELL temperature at the 0.25P duty, and the "
            "cell-to-cell spread. "
            "2. Please state the chiller capacity and electrical draw at that condition — the "
            "industry convention is an L45/W18 rating point, i.e. rated cooling output at "
            "45 degrees C ambient with an 18 degrees C fluid supply. "
            "3. At the resulting cell temperature, please state cycles to 70 % retention and "
            "reconcile that against the roughly 6,022 EFC the 15-year duty requires. "
            "4. If the no-augmentation declaration cannot be substantiated at that cell "
            "temperature, please offer instead a capacity/throughput warranty with an "
            "augmentation undertaking triggered on measured capacity falling below the declared "
            "curve."
        ),
        closure_test=(
            "A thermal calculation showing cell temperature at 45 degrees C ambient under the "
            "contracted duty, tied to a cycle-life figure at that cell temperature that exceeds "
            "6,022 EFC with margin — or, failing that, a written augmentation undertaking with "
            "a defined measurement trigger and cost allocation."
        ),
        tier="cannot close in window",
        consequence=(
            "This is the deepest exposure in the package for a 15-year BOO structure, and it is "
            "evidenced by the supplier's own independent report rather than by inference."
        ),
    ),
    GapItem(
        gap_id="A4",
        title="Liquidated damages are uncapped over the term and the capacity charge has no monthly floor",
        severity="CRITICAL",
        clause="Volume III Appendix A Clause 2; clarifications 52 and 54; Volume I §7.1",
        requirement=(
            "Clarification 54: 'There is no aggregate cap on liquidated damages either per "
            "Contract Year or over the full 15-year Term.' The only cap is monthly. Further: "
            "'capacity charge deductions for failure to achieve the required 97 % availability "
            "are not liquidated damages and therefore do not fall within the monthly LD cap', "
            "and 'if the BESS fails to meet the 97 % availability requirement, the capacity "
            "charge payable for that month may be reduced, potentially down to LKR 0'."
        ),
        supplied=(
            "No reliability block diagram, failure-rate data, redundancy analysis, MTTR, "
            "planned-maintenance schedule or spares policy has been supplied to support a 97 % "
            "monthly availability position. Operator reference letters report 98.2 % "
            "availability with a consistent fault signature — 0 hours cell-fault downtime, "
            "36-43 hours DC-system, 68-70 hours PCS, 1 hour EMS."
        ),
        why_insufficient=(
            "This CORRECTS the 31 July gap statement, which recorded a 'total monthly LD cap of "
            "20 % of capacity charge' and treated that as the bound on performance exposure. The "
            "availability deduction sits OUTSIDE that cap and has no floor, so a bad month can "
            "pay zero while damages continue to accrue with no term aggregate. Clarification 52 "
            "adds that no termination compensation or buy-out formula is prescribed for NSO "
            "default, political force majeure attributable to the Government, or prolonged "
            "natural force majeure. Volume I §7.1 and clarification 30 confirm the ESA is final "
            "and unamendable after the Letter of Award, so none of this is negotiable later. "
            "Note also that PCS is the dominant availability risk in the operator record, and "
            "the offered PCS model appears in none of the references (gap B4)."
        ),
        question=(
            "1. Please provide a reliability block diagram, component failure rates, MTTR and "
            "spares holding sufficient to support 97 % monthly availability at the 95 % "
            "confidence level. "
            "2. Please confirm a back-to-back availability warranty with defined response times, "
            "remote diagnostics and OEM-caused liquidated-damages indemnity — noting that the "
            "Project Company's exposure here is uncapped over the term and unfloored in any "
            "month. "
            "3. Please state the spares list, location and replenishment lead time for the PCS "
            "specifically."
        ),
        closure_test=(
            "A signed availability warranty with a service-level schedule and an OEM indemnity "
            "that responds to the uncapped, unfloored structure clarification 54 describes."
        ),
        tier="document",
        consequence="Revenue can fall to zero in a month while damages accrue without a term cap.",
    ),
    GapItem(
        gap_id="A5",
        title="Grid Interconnection Confirmation Letter — a Major Deviation whose request window has closed",
        severity="CRITICAL",
        clause="Addendum 01 items 02, 07 and 08; Volume II Section 15; clarification 11",
        requirement=(
            "Addendum 01 item 02 adds the Grid Interconnection Confirmation Letter to the "
            "documents required with the proposal where Option 2 is selected under Volume II "
            "Section 11, and item 08 adds it to the Major Deviations list at Volume I clause "
            "6.3.1. Clarification 11 confirms it 'is mandatory and shall form part of the Bid'. "
            "Addendum 01 item 07 requires it to be requested from the relevant Provincial "
            "Director of EDL 'at least 21 days before the Closing date', and states that EDL "
            "'shall not be liable for any delays in issuance of the same'."
        ),
        supplied="Not evidenced in any material held in the corpus.",
        why_insufficient=(
            "21 days before the 4 September closing date is 14 August 2026. That request window "
            "has passed. If Option 2 is being taken and the letter has not been requested, this "
            "is a disqualification risk rather than a scoring one. This gap is addressed to the "
            "Bidder, not to the OEM, and is recorded here because it outranks every technical "
            "item in the register."
        ),
        question=(
            "Bidder action, not an OEM query: confirm immediately whether Option 1 or Option 2 "
            "is being taken for the Grid Point; if Option 2, confirm whether the letter was "
            "requested and whether it will arrive before 4 September; if Option 1, record that "
            "election explicitly in the bid so the absence of the letter is not read as an "
            "omission."
        ),
        closure_test=(
            "Either the executed Grid Interconnection Confirmation Letter in the bid, or a "
            "documented Option 1 election."
        ),
        tier="critical path",
        consequence="Major Deviation under Volume I clause 6.3.1 — the proposal may be rejected.",
    ),
    # ── HIGH ────────────────────────────────────────────────────────────────────────────
    GapItem(
        gap_id="B1",
        title="Annex A numeric performance parameters are not evidenced anywhere in the package",
        severity="HIGH",
        clause="Annex A A.05.02(a)(c)(d)(e), A.05.17(d) and (h)",
        requirement=(
            "A.05.02(a): PCS AC-side current continuous at 110 % of rated, sustaining 120 % for "
            "at least 2 minutes, preferably 150 % short-term. A.05.02(d): maximum inertia time "
            "constant 'no less than 20 seconds' with inertia response activation time at most "
            "5 ms, flexibly adjustable. A.05.02(e): primary frequency regulation response under "
            "0.2 s with active power adjustment deviation at most 2 %. A.05.17(d): autonomous "
            "suppression of 0.2-2.5 Hz oscillations with active power variation limited to "
            "10-30 % Pn. A.05.17(h): AGC regulation range -100 % to +100 % Pn with steady-state "
            "active deviation at most 2 % Pn, and AVC steady-state reactive deviation at most "
            "2 % Pn."
        ),
        supplied=(
            "The filled Volume 2 GTP declares droop 1-9 % and deadband 0.0-1.0 Hz in 0.05 Hz "
            "steps, which meet A.05.02(b). No other parameter in this list is evidenced. "
            "Clarifications 59 and 64 both asked for relief on the current ratings — including "
            "an explicit request to cut the 120 % duration from 2 minutes to 1 — and both were "
            "answered 'Please comply with A.05.02 of Annex A'."
        ),
        why_insufficient=(
            "These are hard numeric acceptance criteria in the controlling annex, and NSO has "
            "twice declined to relax the current ratings. The 110 % continuous requirement in "
            "particular implies roughly a 10 % PCS oversize on top of the reactive requirement, "
            "which is a sizing consequence and not merely a datasheet entry."
        ),
        question=(
            "Please confirm, for the offered ENPCS2520 and at the ambient at which each holds: "
            "(a) continuous current at 110 % of rated, 120 % for at least 2 minutes, and whether "
            "150 % short-term is supported and for how long; (b) inertia time constant and "
            "inertia response activation time, and the adjustment range; (c) primary frequency "
            "response time and active power adjustment deviation; (d) power-oscillation damping "
            "across 0.2-2.5 Hz and the active power variation band; (e) AGC and AVC regulation "
            "ranges and steady-state deviations."
        ),
        closure_test=(
            "A datasheet or type-test extract giving each figure against the Annex A clause, at "
            "a stated ambient temperature."
        ),
        tier="document",
    ),
    GapItem(
        gap_id="B2",
        title="The supplied Sri-Lanka protection envelope is narrower than Annex A requires at both ends",
        severity="HIGH",
        clause="Annex A A.05.04; clarification 29",
        requirement=(
            "Annex A A.05.04 sets steady-state operation across 47-52 Hz with extremes to "
            "45-55 Hz, and an under-frequency window extending to 45 Hz with a 10-second "
            "requirement in the band 47.0 > f >= 45.0. Clarification 29, asked which of the two "
            "frequency ranges in the tender governs, answers: 'The Project Proponents shall "
            "comply with the requirements specified in Clause A 05.04 of Annex A.'"
        ),
        supplied=(
            "The Sri-Lanka dynamic record ENVSG_PPC_2520_260416_LKA.dyr carries a 47.5 / 51.5 Hz "
            "continuous protection envelope with 46.9 / 52.1 Hz trip stages."
        ),
        why_insufficient=(
            "47.5 / 51.5 Hz is inside the 47-52 Hz steady-state band Annex A requires, so the "
            "plant as parameterised would trip within the range in which it is required to "
            "operate continuously — at both the under- and over-frequency ends."
        ),
        question=(
            "Please reconcile the .dyr protection envelope against Annex A A.05.04. Either "
            "confirm the settings are project-adjustable to at least 47-52 Hz continuous with "
            "the 45-55 Hz extremes and the 10-second requirement between 47.0 and 45.0 Hz, and "
            "state the adjustable range; or confirm the equipment limit if it cannot meet it."
        ),
        closure_test=(
            "A revised dynamic record, or a written settings range, demonstrating continuous "
            "operation across 47-52 Hz and ride-through to the A.05.04 extremes."
        ),
        tier="document",
        consequence=(
            "VERIFIED 27 August 2026 from primary source, and the non-compliance is wider than "
            "first recorded. The delivered .dyr sets CON(J+65) onward to 47.5 Hz / 1800 s and "
            "46.9 Hz / 0.04 s (three stages), and 51.5 Hz / 1800 s and 52.1 Hz / 0.04 s (three "
            "stages); the PSS(R)E UDM manual V1.4a confirms CON(J+65)-CON(J+100) are the "
            "frequency and voltage protection thresholds and that they TRIP the PCS. The "
            "ENPCS2520 specification Table 3 states the same behaviour in words: between 47 and "
            "47.5 Hz a CHARGING PCS must switch to discharging within 0.2 s or SEPARATE FROM THE "
            "GRID within 0.2 s, and a discharging PCS operates only 30 minutes (= the 1800 s in "
            "the .dyr); between 51.5 and 52 Hz the same applies in reverse. Annex A A.05.04 "
            "requires CONTINUOUS steady-state operation across 47-52 Hz. So the plant as "
            "delivered separates, or is time-limited to 30 minutes, inside the band where the "
            "tender requires continuous operation, and trips in 0.04 s below 46.9 Hz where "
            "A.05.04 requires 10 s ride-through to 45 Hz. MITIGATION, stated by the supplier's "
            "own specification: 'The PCS software parameters can be adjusted to the local grid "
            "code frequency protection requirements.' This is therefore a SETTINGS defect with a "
            "vendor-stated remedy, not a hardware limit — but the settings as shipped are "
            "non-compliant and the model submitted with the bid carries them."
        ),
    ),
    GapItem(
        gap_id="B3",
        title="Reactive capability at a declared 11 MW — CHECKED AND CLEARED",
        severity="INFORMATIONAL",
        clause="Annex A A.05.13; clarifications 2, 24 and 66",
        requirement=(
            "Clarification 24: 'The reactive power capability requirement shall be +/-0.3 times "
            "the rated active power of the BESS' — settling that it is a ratio, not the flat "
            "+/-3 Mvar referenced elsewhere. Clarification 2 confirms the Contracted Capacity "
            "will be the Declared Capacity offered in Section 1 of Volume II, expressly "
            "contemplating up to 11 MW. Clarification 66 confirms the declared capacity must be "
            "achieved and demonstrated at commissioning."
        ),
        supplied=(
            "The 10 MW / 40 MWh design calculation states +/-3.29 Mvar at the PCC with power "
            "factor +/-0.95."
        ),
        why_insufficient=(
            "NO LONGER A GAP. This item was raised on the arithmetic that +/-3.29 Mvar — the "
            "figure in the 10 MW design calculation — would fall marginally short of the "
            "+/-3.3 Mvar that clarification 24 implies at a declared 11 MW. It was marked "
            "UNVERIFIED because the 11 MW design calculation's own reactive figure had not been "
            "read. It has now been read: the 11 MW / 44 MWh design calculation states "
            "**Q required = +/-3.62 Mvar** at power factor +/-0.95. Against +/-3.3 Mvar that "
            "complies with roughly 10 % margin, and against the +/-3.0 Mvar required at a "
            "declared 10 MW it is comfortable. The concern does not hold and is withdrawn."
        ),
        question=(
            "No question to the OEM arises. Retained in the register as a closed item so the "
            "earlier concern is visibly resolved rather than silently dropped. For completeness "
            "Envision may still be asked for the four-quadrant P-Q chart across 0.9-1.1 pu, both "
            "charge and discharge, at minimum and maximum SOC, BoL and EoL, and at 45 degrees C."
        ),
        closure_test="Closed — +/-3.62 Mvar stated in the 11 MW design calculation exceeds the requirement.",
        tier="document",
        consequence=(
            "Removes the only constraint identified against declaring an 11 MW capacity, and so "
            "strengthens the oversizing option: 11 MW / 44 MWh hardware declared at 10 MW carries "
            "+/-3.62 Mvar against +/-3.0 Mvar required."
        ),
    ),
    GapItem(
        gap_id="A6",
        title="The PCS cannot meet the Annex A overload ratings at site ambient — from the supplier's own specification",
        severity="CRITICAL",
        clause="Annex A A.05.02(a); clarifications 59 and 64",
        requirement=(
            "Annex A A.05.02(a): the PCS AC-side current 'shall be capable of operating "
            "continuously at 110% of the rated current, sustain 120% of the rated current for "
            ">=2 minutes, and preferably support short-term overloads of 150%'. Clarification 59 "
            "asked whether 110 % continuous is a firm requirement and at what ambient; "
            "clarification 64 asked for the 120 % duration to be cut from two minutes to one. "
            "Both were answered 'Please comply with A.05.02 of Annex A'. No relief was given."
        ),
        supplied=(
            "The ENPCS2520 Technical Specification V1.0, supplied 27 August 2026 and not "
            "previously held, states the overload capacity as: 110 % for 10 minutes at "
            "45 degrees C; 110 % continuous at 40 degrees C; 120 % for 1 minute at 35 degrees C. "
            "Rated current 2109 A. No 150 % rating is stated anywhere in the document."
        ),
        why_insufficient=(
            "Read against the requirement, at the tender's own site envelope of +45 degrees C: "
            "(1) 110 % is available for TEN MINUTES, not continuously — continuous 110 % is "
            "offered only at 40 degrees C, five degrees below the site design condition; "
            "(2) 120 % is offered for ONE minute and only at 35 degrees C, against a requirement "
            "of at least TWO minutes — and the bidder asked for precisely that relief at "
            "clarification 64 and was refused; (3) the 'preferably 150 %' capability is not "
            "evidenced at any temperature. Unlike the frequency settings at gap B2, the "
            "specification attaches NO note that these figures are adjustable — they are thermal "
            "ratings of the hardware, not software settings. This is the first gap in the "
            "register established directly from the supplier's own product specification rather "
            "than from an absence of evidence, and it is a stated ground for technical rejection "
            "under a clause NSO has twice declined to relax."
        ),
        question=(
            "1. Please confirm the ENPCS2520 AC-side current capability specifically at "
            "+45 degrees C ambient: continuous rating, the duration available at 110 %, and the "
            "duration available at 120 %. "
            "2. Annex A requires 110 % continuous and 120 % for at least two minutes. The "
            "specification offers 110 % continuous only at 40 degrees C and 120 % for one minute "
            "at 35 degrees C. Please state plainly whether the ENPCS2520 can meet A.05.02(a) at "
            "site ambient, and if not, what can. "
            "3. If a de-rated deployment, forced-cooling option or a higher-rated converter is "
            "required to meet the clause, please identify it now — this is a sizing decision, "
            "not a datasheet correction, and it interacts with the export-limiter design. "
            "4. Please state the 150 % short-term capability and its duration, or confirm there "
            "is none."
        ),
        closure_test=(
            "A written statement of AC-side current capability at +45 degrees C showing 110 % "
            "continuous and 120 % for at least two minutes at that ambient, or an identified "
            "alternative configuration that does."
        ),
        tier="critical path",
        consequence=(
            "Volume I §3.1(p) and Annex A make failure against the technical requirements a "
            "stated ground for rejection of the technical proposal, and NSO refused relief on "
            "this exact clause twice."
        ),
    ),
    GapItem(
        gap_id="A7",
        title="The OEM availability guarantee stops at year 2 of a 15-year obligation, and the "
        "instrument that would extend it is an unpriced draft",
        severity="CRITICAL",
        clause="Volume III Appendix A Clause 2; clarifications 52 and 54; gap A4 question 2",
        requirement=(
            "Gap A4 records that availability deductions sit OUTSIDE the monthly LD cap, have "
            "no floor, and can take the capacity charge to LKR 0, with no aggregate cap over "
            "the 15-year Term. A4's second question asks for the answer to that exposure: a "
            "back-to-back availability warranty with defined response times, remote diagnostics "
            "and an OEM-caused liquidated-damages indemnity. Volume I clause 7.1 and "
            "clarification 30 confirm the ESA is final and unamendable after the Letter of "
            "Award, so the instrument has to exist before award, not after."
        ),
        supplied=(
            "Two documents supplied 27 August 2026 answer this and had not previously been "
            "held. (1) Product Warranty Policy V1.0: Table 1 sets a SINGLE period of 'two years "
            "from date of first time installation or commissioning; or delivery term and "
            "conditions in the supply contract; whichever occurs earlier' across every listed "
            "item — battery pack, BMS at all levels, HVAC, rack protection, fire detection and "
            "suppression, cables and consumables, battery container combiner panel, PCS, "
            "step-up transformer, RMU, electrical cabinets, and EMS/SCADA including the "
            "unit-level local controller. The client bears the cost of removing the defective "
            "product and re-installing the repaired one. Liability per product is capped at "
            "the product price and all consequential loss is excluded. (2) LTSA Solution: a "
            "service scope matrix whose 'Performance guarantee' block offers Availability, RTE "
            "and Usable capacity."
        ),
        why_insufficient=(
            "The LTSA does offer the guarantees — but read the columns. It sets out two "
            "structures: 'Full Scope year 0-15', and a split of 'warranty Period year 0-2' plus "
            "'year 3-15'. Under the split, the Availability guarantee is marked '-', which the "
            "sheet's own legend defines as 'Not applicable, or not included'. RTE and usable "
            "capacity continue to year 15; AVAILABILITY DOES NOT. So in the default structure "
            "the availability guarantee expires at year 2 and the Project Company carries the "
            "uncapped, unfloored 97 % availability exposure alone for thirteen further years — "
            "precisely the exposure A4 identifies. Only 'Full Scope' covers availability to "
            "year 15, and the sheet carries NO price for it, no guarantee level (no availability "
            "percentage, no RTE percentage, no capacity retention figure), no term, no response "
            "times, no LD indemnity and no signature. Its BESS tab is labelled '100225-Draft', "
            "and the workbook's other tab is a WIND TURBINE service catalogue, so the BESS "
            "sheet is a draft appended to a wind-service document. Nothing here is capable of "
            "being made back-to-back with the ESA. Separately, the two-year warranty is short "
            "against the tender's own frame: A2 puts the duty at roughly 6,000 equivalent full "
            "cycles over the term, so 13 of the 15 years of degradation, augmentation and "
            "component replacement fall outside any product warranty at all, and the client "
            "pays removal and re-installation even within the two years."
        ),
        question=(
            "1. Please state whether Envision will provide an availability guarantee running "
            "the full 15 years, and at what level — the LTSA marks availability as not included "
            "for years 3-15 outside Full Scope. "
            "2. Please price Full Scope 0-15 and state its guaranteed availability percentage, "
            "RTE percentage, usable-capacity retention, response times and the liquidated "
            "damages payable by Envision for missing them. "
            "3. Please confirm whether the two-year Table 1 warranty is Envision's final "
            "position for the PCS, transformer, RMU and EMS, and if an extension is available, "
            "for how long and at what price. "
            "4. Please state who bears removal and re-installation cost under an extended "
            "warranty, given Table 1 places it on the client. "
            "5. Please issue the LTSA as a signed, priced, project-specific document with the "
            "wind-turbine tab removed — the sheet supplied is marked Draft and is not capable "
            "of being made back-to-back with the ESA."
        ),
        closure_test=(
            "A signed, priced, project-specific LTSA running to year 15 with a stated "
            "availability guarantee, defined response times and OEM liquidated damages that "
            "respond to the uncapped and unfloored structure clarification 54 describes; plus a "
            "written warranty position for the balance of plant beyond two years."
        ),
        tier="critical path",
        consequence=(
            "This is the answer to gap A4's second question and it does not close it. Without a "
            "15-year availability instrument the Project Company absorbs an exposure that has no "
            "monthly floor and no term cap, and the ESA cannot be amended after award to fix it."
        ),
    ),
    GapItem(
        gap_id="B4",
        title="The offered PCS model has no track record in the submitted reference list",
        severity="HIGH",
        clause="Volume I clause 2.7.3; clarification 58",
        requirement=(
            "Manufacturer qualification requires 1 GWh of installed battery modules/cells, 1 GW "
            "of installed inverter products, and two projects using the same PPC product family. "
            "Clarification 58(a) and (b) settle that the threshold is CUMULATIVE GLOBAL "
            "INSTALLED volume and must be installed/commissioned volume, 'because the requirement "
            "says installed'. Clarification 58(e) settles that the qualification rests on the "
            "manufacturer's experience and 'need not be experience of the Project Proponent "
            "itself'."
        ),
        supplied=(
            "A supplier-experience workbook listing 22 PCS reference projects using ENPCS 2750, "
            "3450, 3300 and 2500, and 24 battery-side projects. The Envision letter discloses "
            "18.7 GW / 52.6 GWh contracted, 33.5 GWh shipped and 20.65 GWh at COD."
        ),
        why_insufficient=(
            "The model offered for Sri Lanka is the ENPCS2520, which appears nowhere in the "
            "reference list. The client-contact column the RFP form requests is empty for every "
            "PCS and PPC row, and the workbook is self-labelled '(part)'. Separately, "
            "clarification 58(b) means the qualifying figure is the 20.65 GWh at COD, not the "
            "52.6 GWh contracted or 33.5 GWh shipped — the bid should quote the right number. "
            "This matters more than a paperwork point because PCS is the dominant availability "
            "risk in the operator reference record (68-70 hours of PCS downtime against 0 hours "
            "of cell-fault downtime)."
        ),
        question=(
            "1. Please explain the ENPCS2520's relationship to the referenced ENPCS 2750 / 2500 "
            "family and identify any commissioned ENPCS2520 units, with project, location and "
            "commissioning date. "
            "2. Please complete the client-contact column for every PCS and PPC reference row. "
            "3. Please issue the reference workbook in complete form rather than '(part)'."
        ),
        closure_test=(
            "A manufacturer declaration on letterhead in the form clarification 58(c) accepts — "
            "product, installed quantity, project, location, commissioning date, manufacturer — "
            "covering the offered PCS model or a documented equivalence to the referenced family."
        ),
        tier="document",
    ),
    GapItem(
        gap_id="B5",
        title="Fire-safety chain stops at module level and does not cover the offered container",
        severity="HIGH",
        clause="Volume I §3.1(g); UL 9540A 2026 (sixth edition)",
        requirement=(
            "Volume I §3.1(g) requires fire prevention, detection, alarm, suppression, "
            "thermal-runaway mitigation, compartmentalisation, emergency isolation and safety "
            "procedures, with evidence submitted alongside the proposal."
        ),
        supplied=(
            "A cell-level UL 9540A (2019) report and a module-level UL 9540A (2026) report "
            "issued 25 June 2026, plus a Fire Protection System Specification V2.0 dated 21 May "
            "2026. Recorded module-level results: peak heat release rate 46.28 kW, peak smoke "
            "release rate 0.5457 m2/s, total smoke release 29.98 m2, total hydrocarbons 432.6 L, "
            "module weight loss 1.8 kg, no flaming observed."
        ),
        why_insufficient=(
            "The module report's own conclusion records that cell-to-cell thermal runaway and "
            "propagation occurred, that runaway was contained by the module design, and that "
            "cell vent gas was flammable at cell level — and then states that a further test "
            "level is required. Neither further test is in the package. Separately the Fire "
            "Protection System Specification is headed for ENS-D10 while the offered "
            "configuration pairs ENS-D10G with ENS-D06G, so fire-protection coverage of the "
            "D06G variant is unevidenced."
        ),
        question=(
            "1. Under the sixth edition of UL 9540A, published 13 March 2026, the unit-level "
            "test is no longer required for non-residential BESS and the installation-level "
            "large-scale fire test at Section 10 is the integrated fourth evaluation level. "
            "Please confirm which route applies to the offered product and supply a dated test "
            "commitment. "
            "2. Please confirm fire-protection coverage of the ENS-D06G container specifically, "
            "or issue a specification revision whose header scopes both offered container types."
        ),
        closure_test=(
            "Either an installation-level large-scale fire test report for the offered "
            "configuration, or a dated written commitment to it with a stated interim compliance "
            "basis; plus a fire-protection specification covering ENS-D06G."
        ),
        tier="cannot close in window",
    ),
    GapItem(
        gap_id="B6",
        title="Entity attribution and the missing Manufacturer's Authorization Letter",
        severity="HIGH",
        clause="Volume I clause 2.7.3; checklist item 58; clarification 58(d) and (e)",
        requirement=(
            "Checklist item 58 requires three signed EOI letters 'and MAL Also (on Company "
            "letterhead)'. Clarification 58(d): an OEM's standard EOI or letter format is "
            "acceptable provided it carries all RFP-required information and is signed by an "
            "authorised representative of the manufacturer."
        ),
        supplied=(
            "Three EOI letters (BESS; PCS and Transformers; SCADA/PPC and EMS), signed 31 July "
            "2026 by an affiliated supply entity on the battery affiliate's letterhead. The "
            "clause 2.7.3 track record is in Envision Energy's name. The cell certificates name "
            "the affiliate's cell-manufacturing entity. Item 59.2 is a group letter recording "
            "that the BESS business has moved to a group battery affiliate."
        ),
        why_insufficient=(
            "Clarification 58(e) substantially relieves this — the qualification rests on the "
            "manufacturer's experience and need not be the Proponent's. What it does not resolve "
            "is WHICH group entity holds it, when the track record, the supply commitment and "
            "the certificates sit in three different corporate names. And no MAL is in the "
            "package at all, though item 58 is marked Received."
        ),
        question=(
            "1. Please issue the Manufacturer's Authorization Letter on company letterhead. "
            "2. Please confirm in writing that Envision Energy's clause 2.7.3 track record is "
            "available to, and may be relied upon by, the affiliated supply entity that signed "
            "the EOI letters, and supply any parent guarantee or intra-group support letter "
            "needed to make that reliance effective."
        ),
        closure_test=(
            "A signed MAL, plus a written intra-group attribution confirmation naming the "
            "entities and the basis of reliance."
        ),
        tier="document",
    ),
    # ── MEDIUM ──────────────────────────────────────────────────────────────────────────
    GapItem(
        gap_id="C1",
        title="Fourteen standards remain uncertified, and the stated basis is stale in two places",
        severity="MEDIUM",
        clause="Volume I §3.1(b); clarification 62",
        requirement=(
            "Volume I §3.1(b) requires documentary proof of compliance for the listed battery, "
            "PCS, safety, quality and grid standards."
        ),
        supplied=(
            "Sixteen certificates and reports across checklist sections C and D. Still "
            "uncertified: IEC 62620, IEC 62902, IEC 62485-5, IEC 62933-1, IEC 62933-2-1, "
            "IEC 62933-5-2, UL 9540, IEEE 1547-2018, IEEE 2800-2022, UL 1741-SB and "
            "IEC TS 62786-3. IEEE 2800-2022 is declined outright as 'US region-specific ... not "
            "required for other markets'; UL 1741-SB is declined with EN 50549-2 and G99 offered "
            "instead. Two remarks read 'Will finish before 2026'."
        ),
        why_insufficient=(
            "The 'Will finish before 2026' remarks are stale — the date has passed — and a stale "
            "commitment reads worse than an honest revised one. The IEEE 2800 refusal is the "
            "substantive one: it is the transmission-level IBR interconnection standard whose "
            "grid-forming provisions are the natural reference for this tender's mandatory "
            "grid-forming requirement, and it is declined on market-scope grounds."
        ),
        question=(
            "1. Please re-date the two 'Will finish before 2026' commitments with realistic "
            "completion dates. "
            "2. Clarification 62 permits, where the exact package is newly introduced and "
            "certification is in progress, submission of currently valid certifications for the "
            "applicable cells, racks, major components or established product family TOGETHER "
            "WITH documentary evidence of the relationship and technical equivalence to the "
            "offered package. Please supply that equivalence evidence for each uncertified "
            "standard. "
            "3. For IEEE 2800-2022 and UL 1741-SB, please state the equivalence argument "
            "clause-by-clause against EN 50549-2 and G99 rather than asserting market scope. "
            "Note that no published equivalence mapping between these standards exists, so the "
            "argument has to be constructed and will be read closely."
        ),
        closure_test=(
            "For each uncertified standard: either a certificate for the offered package, or a "
            "clause-level equivalence statement with supporting certification for the "
            "established product family, in the form clarification 62 describes."
        ),
        tier="document",
    ),
    GapItem(
        gap_id="C2",
        title="Item 57 answers a different requirement than the one it is filed against",
        severity="MEDIUM",
        clause="Volume I §3.1(m); checklist item 57",
        requirement=(
            "End-of-life decommissioning and battery RECYCLING commitments, referenced to Sri "
            "Lanka environmental regulations."
        ),
        supplied=(
            "A BESS dismantling technical description — a mechanical disassembly work "
            "instruction covering special tools, cable disconnection, grounding removal, "
            "pipeline removal and lifting procedure."
        ),
        why_insufficient=(
            "A keyword sweep of the full extract returns zero occurrences of recycling, "
            "disposal, waste, take-back, second-life or Sri Lanka environmental regulation. The "
            "single 'environmental' hit refers to removal of the environmental-control pipeline, "
            "i.e. the cooling circuit. The item's status cell is blank in the tracking workbook, "
            "consistent with it never having been assessed."
        ),
        question=(
            "Please supply a genuine end-of-life decommissioning and recycling commitment: "
            "take-back or recycling route, the receiving facility and its jurisdiction, the "
            "treatment of the LFP cell chemistry, and an express reference to the Sri Lankan "
            "environmental regulations that apply. The disassembly manual is useful and should "
            "be retained, but filed against a different requirement."
        ),
        closure_test="A signed recycling and decommissioning commitment citing the applicable Sri Lankan regulation.",
        tier="document",
    ),
    GapItem(
        gap_id="C3",
        title="Item 38 is filed as grid-forming modelling evidence but answers no tender requirement",
        severity="MEDIUM",
        clause="Checklist item 38; clarification 37",
        requirement=(
            "Checklist item 38 requires supporting documentary and MODELLING evidence of "
            "grid-forming operation."
        ),
        supplied=(
            "A file named as a grid-forming technical solution whose own title page identifies "
            "it as a BESS plant BLACK-START technical solution V1.0, marked 'for reference'. Its "
            "content is a PPC/SCADA functional description — topology monitoring, "
            "anti-misoperation interlocks, GNSS-synchronised zero-voltage ramp-up, off-grid "
            "operation, SOC balancing, load management, resynchronisation."
        ),
        why_insufficient=(
            "It contains no simulation results, no V/F characteristic, no fault response and no "
            "SCR sweep, so it is not modelling evidence. And clarification 37, asked whether the "
            "black start function is mandatory in this project, answers 'No' — so the document "
            "does not answer item 38 and is not required by the tender in its own right either."
        ),
        question=(
            "Please replace item 38 with actual grid-forming modelling evidence — see gap A1. "
            "The black-start document may be withdrawn or retained as supporting information, "
            "but it should not stand against item 38."
        ),
        closure_test="Simulation output demonstrating grid-forming V/F behaviour, filed against item 38.",
        tier="document",
    ),
    GapItem(
        gap_id="C4",
        title="Filled Volume 2 GTP contains unforced data-entry errors in a scored schedule",
        severity="MEDIUM",
        clause="Volume II Section 6",
        requirement="The completed Guaranteed Technical Particulars schedule.",
        supplied=(
            "The completed Section 6 GTP, confirming the tender number. Substantive entries are "
            "sound: ENPCS2520 at 2.52 MW / 690 V / 50 Hz, liquid cooling, 416S1P x 6, 0.25C "
            "continuous, 100 % DoD, 7300 EFC at 100 % DoD / 9125 at 80 % / 14600 at 50 %, at "
            "most 3 %/month self-discharge, IP65, droop 1-9 %, deadband 0.0-1.0 Hz, PF +/-0.95."
        ),
        why_insufficient=(
            "A.5 'Model No.' is answered '8'; A.4 'Make' is answered 'BESS'; A.6 'Total Area "
            "Required (Acres)' is answered '350 m2' — wrong unit and implausible for the block. "
            "Block totals (A.15 12 MW, A.16 48 MWh, 8 modules, 8 inverters) reconcile to neither "
            "the 10 MW / 40 MWh nor the 11 MW / 44 MWh design calculation, and 8 x ENPCS2520 is "
            "20.16 MW against a declared 12 MW battery rating. B.40 'Grid Forming Capability' is "
            "answered with a bare 'Yes'. The GTP carries no round-trip-efficiency row, no "
            "capacity-warranty row, no degradation row and no augmentation row, so the "
            "commercially load-bearing guarantees live only in the design calculations."
        ),
        question=(
            "Please correct A.4, A.5 and A.6; reconcile the A.15/A.16 block totals to the "
            "offered configuration; expand B.40 to the reconciled control-mode statement at gap "
            "A1; and confirm whether the RTE, capacity-warranty, degradation and augmentation "
            "guarantees can be carried in the schedule rather than only in the design "
            "calculation."
        ),
        closure_test="A corrected, internally consistent GTP that reconciles to one offered configuration.",
        tier="document",
    ),
    GapItem(
        gap_id="C5",
        title="Grid-code compliance monitoring is now unambiguously the Developer's scope",
        severity="MEDIUM",
        clause="Addendum 01 item 03; clarifications 4(b), 21 and 63",
        requirement=(
            "Clarification 21: NSO will NOT specify the make and model of the grid-code "
            "compliance monitoring equipment ('No'); the DEVELOPER is responsible for its "
            "ongoing maintenance and calibration; and the data from it WILL be used for billing "
            "and verification ('Yes'). Clarification 4(b) sets the standard as IEC 61000-4-30 "
            "Class A. Clarification 63 requires a separate firewall at the BESS facility with a "
            "suitable management system."
        ),
        supplied=(
            "In the 21 August package, Section E of the GTP answered 'Meter is Bop scope' on all "
            "five grid-code compliance metering rows, and items 43 and 44 were likewise declined "
            "as BoP scope."
        ),
        why_insufficient=(
            "The 21 August evaluation recorded that no party in the package owned grid-code "
            "compliance monitoring. That is now resolved against the Developer, and the "
            "monitoring data is billing-relevant, so a BoP-scope answer is no longer available. "
            "An IEC 61000-4-30 Class A instrument and a separate managed firewall are now "
            "specified items to be priced and supplied."
        ),
        question=(
            "Please confirm whether the offered EMS/PPC package includes an IEC 61000-4-30 "
            "Class A power-quality instrument and the separate BESS-side firewall, or whether "
            "these remain outside OEM scope — and if outside, please say so explicitly so the "
            "Bidder can price them into BoP."
        ),
        closure_test=(
            "A written scope statement covering the Class A instrument, its calibration regime "
            "and the BESS-side firewall."
        ),
        tier="document",
    ),
    GapItem(
        gap_id="C6",
        title="SCADA gateway must serve four master servers without additional licences",
        severity="MEDIUM",
        clause="Addendum 01 item 09; clarification 27",
        requirement=(
            "The SCADA gateway 'shall support simultaneous communication and real-time data "
            "reporting to a minimum of four SCADA master servers, comprising two master servers "
            "at the National System Control Centre and two master servers at the Backup National "
            "System Control Centre', capable of reporting to any one, any combination, or all "
            "four 'without interrupting the existing communication links or requiring additional "
            "hardware, software, configuration changes, or licenses'. Clarification 27 confirms "
            "a gateway is still required even where the PPC itself supports IEC 104."
        ),
        supplied="Not evidenced. The package includes an EnOS PPC but no gateway specification against this requirement.",
        why_insufficient=(
            "This is a new requirement introduced by Addendum 01 and post-dates the OEM material "
            "in the corpus. The 'no additional licenses' wording is a commercial constraint as "
            "well as a technical one."
        ),
        question=(
            "Please confirm the offered SCADA gateway supports four simultaneous IEC 104 master "
            "connections in any combination, without additional hardware, software, "
            "configuration change or licence cost, and state the product and its concurrent "
            "session limit."
        ),
        closure_test="A gateway datasheet stating concurrent master-server support and the licensing position.",
        tier="document",
    ),
    GapItem(
        gap_id="C7",
        title="Tracking workbook cannot be relied on as a completeness measure",
        severity="MEDIUM",
        clause="Bidder document control",
        requirement="An accurate internal record of which checklist items are satisfied.",
        supplied=(
            "The supplier document checklist workbook, whose Summary tab uses COUNTIF over "
            "F2:F65 while the checklist data runs to row 69."
        ),
        why_insufficient=(
            "The Summary tab reports 38 Received against a true 41, because items 60, 61 and 62 "
            "fall outside the counted range. Separately, items 50-53 do not exist in the "
            "workbook at all — the numbering jumps from 49 (PSCAD model) straight to 54. Given "
            "the section they sit in, these are plausibly the SCR/phase-step and "
            "model-validation rows. Item 36 is also marked Not Received with no remark, although "
            "item 61 post-dates and largely answers it."
        ),
        question=(
            "Bidder action, not an OEM query: correct the Summary range to F2:F69, restore items "
            "50-53, set statuses for items 55-57, and update item 36 against item 61."
        ),
        closure_test="A workbook whose Summary reconciles to the checklist rows and contains no gaps in numbering.",
        tier="document",
    ),
    # ── LOW / INFORMATIONAL ─────────────────────────────────────────────────────────────
    GapItem(
        gap_id="D1",
        title="The clarification register contradicts itself on shared grid interconnection",
        severity="LOW",
        clause="Clarifications 20, 46 and 75",
        requirement=(
            "Clarification 20, on two projects at one GSS on a single land plot: 'Yes. A common "
            "grid interconnection line may be used, subject to compliance with the applicable "
            "technical requirements and obtaining the necessary approvals from the EDL.' "
            "Clarification 75, on the same question: 'Due to network constraints, only one BESS "
            "project can be connected to a single 33 kV feeder ... it is technically not "
            "feasible to accommodate both projects through the same feeder.'"
        ),
        supplied="Not applicable — this is a defect in the controlling document, not in the bid.",
        why_insufficient=(
            "The two answers point opposite ways on the same commercial question, and it "
            "determines whether a two-project bid at one GSS shares interconnection capital "
            "cost. They reconcile only if a common line can terminate in two separate feeder "
            "bays, which clarification 46's premise makes plausible but neither answer states. "
            "The clarification window closed on 25 August, so this can no longer be asked."
        ),
        question=(
            "Bidder action: cost any two-project bid at one GSS on the conservative reading — "
            "separate 33 kV feeders per clarification 75 — and state that assumption explicitly "
            "in the bid so it is visible to the evaluator rather than discovered later."
        ),
        closure_test="A stated, priced assumption in the bid recording which reading was taken and why.",
        tier="document",
    ),
    GapItem(
        gap_id="D2",
        title="Capacity Charge Rate unit is internally inconsistent within its own clarification",
        severity="LOW",
        clause="Clarification 65; Addendum 01 items 11 and 13",
        requirement=(
            "Clarification 65 answers the unit question with 'LKR/MW/month' and states 'Capacity "
            "Charge Rate proposed by the Project Proponent = Y LKR/MW/month', then gives "
            "'Applicable Capacity Charge Rate: 0.15xY + (0.85xYxP2/P1) LKR/MWh/month' — a "
            "different unit in the same answer, in the item whose whole purpose was to resolve "
            "unit ambiguity."
        ),
        supplied="Not applicable — a defect in the controlling document.",
        why_insufficient=(
            "The proposed rate and the applicable rate cannot be in different units and remain "
            "the same quantity. Addendum 01 item 11 also removes '(excluding VAT)' from clause "
            "2.8 and item 13 adds explicit SSCL and VAT-18 % rows to the Section 4 table, so the "
            "quoted figure's tax basis has changed as well."
        ),
        question=(
            "Bidder action: quote in LKR/MW/month, which is the unit the answer opens with and "
            "the unit of the proposed rate, and state that election on the form. Complete the "
            "new SSCL and VAT rows per Addendum item 13."
        ),
        closure_test="A Section 4 form completed in LKR/MW/month with the SSCL and VAT rows filled.",
        tier="document",
    ),
    GapItem(
        gap_id="D3",
        title="Two technical proposals are now permitted — the only remaining hedge",
        severity="INFORMATIONAL",
        clause="Addendum 01 item 23; clarification 73",
        requirement=(
            "Addendum 01 item 23 repeals the Volume I clause 2.7.1 note barring variant "
            "proposals and replaces it with: 'The Project Proponent may submit a maximum two "
            "(02) Technical Proposals under the Financial Proposal submitted for this RFP.' "
            "Clarification 73(a) confirms up to two alternative manufacturers or complete "
            "solutions, each 'a complete and technically integrated BESS solution', treated as "
            "'separate and complete solutions', with NO interchange of major equipment between "
            "them during detailed design, construction or implementation. Clarification 73(b), "
            "asked whether a nominated supplier may be changed after award: 'No.'"
        ),
        supplied="One configuration, with an unresolved question over which design calculation is the offered one.",
        why_insufficient=(
            "This is an opportunity rather than a deficiency, recorded here because it is the "
            "principal change to bid strategy and it expires at submission. It maps directly "
            "onto the two unresolved technical exposures — the grid-forming EMT gap at A1 and "
            "the PCS track-record gap at B4 — and it is the ONLY hedge available, because "
            "supplier substitution after award is refused. It also supersedes the 31 July gap "
            "statement's repeated instruction that the RFP permits only one technical solution."
        ),
        question=(
            "Bidder decision, informed by Envision's answer to A1: whether the second technical "
            "proposal should be the 11 MW / 44 MWh variant (more RTE headroom — see A2 and B3), "
            "a different PCS within the Envision range with an established track record (see "
            "B4), or a different OEM entirely."
        ),
        closure_test="Two complete, internally consistent technical proposals, with no shared or interchanged major equipment.",
        tier="document",
    ),
)

SECTIONS = {
    "What changed since the 31 July gap statement": (
        "This register supersedes the 31 July 2026 detailed gap statement in four respects, each "
        "because a controlling document has since been obtained rather than because the earlier "
        "analysis was careless.\n\n"
        "(1) GRID-FORMING. The 31 July statement required a 'no-GFL-reversion statement' and the "
        "21 August review went further, instructing deletion of the supplier's 'seamless GFL/GFM "
        "transition' language. Annex A A.05.17(i) REQUIRES support for both modes with online "
        "switching. Both instructions are withdrawn: acting on them would have removed evidence "
        "of compliance with a mandatory clause. The correct position is capability for both "
        "modes, operation in grid-forming, no reversion to current-controlled operation in "
        "normal or fault conditions, and grid-forming stability to SCR 1.0.\n\n"
        "(2) DYNAMIC MODELS. The 31 July statement read Volume I §3.1(p) correctly as models OR "
        "test results, and recommended supplying both models anyway. Annex A A.05.23(d) confirms "
        "that either/or, and Addendum 01 item 14 writes it into the Volume II compliance "
        "schedule. The bidder holds both models, so the stated rejection ground is clearable at "
        "bid stage; the SCR sweep moves to the post-award Dynamic Model Tests, due within one "
        "month of ESA execution with the Performance Security at risk.\n\n"
        "(3) COMMERCIAL EXPOSURE. The 31 July statement recorded a total monthly liquidated-"
        "damages cap of 20 % of the capacity charge. Clarification 54 establishes that there is "
        "no aggregate cap over the Contract Year or the Term, and that availability deductions "
        "sit OUTSIDE the monthly cap and can take the capacity charge to LKR 0. The exposure is "
        "materially larger than recorded.\n\n"
        "(4) BID STRATEGY. The 31 July statement repeatedly noted that the RFP permits only one "
        "technical solution. Addendum 01 item 23 now permits two."
    ),
    "Questions the 31 July statement recommended, and how the register answered them": (
        "The 31 July statement listed ten clarification questions for NSO. The issued register "
        "answers or partly answers seven of them:\n\n"
        "Q2, RTE metering boundary — ANSWERED by clarification 51: auxiliary and HVAC loads "
        "directly associated with BESS operation are inside the RTE calculation; general site "
        "loads such as CCTV, security and lighting are outside it.\n"
        "Q3, dynamic evidence route — ANSWERED by Annex A A.05.23(d) and clarification 35: "
        "PSS(R)E and PSCAD are compulsory; PowerFactory, the third tool named at A.05.23(b), is "
        "not.\n"
        "Q6, black start — ANSWERED by clarification 37: not mandatory.\n"
        "Q7, P-Q envelope — PARTLY, by clarifications 24 and 32.\n"
        "Q8, capacity test timing — PARTLY, by clarifications 25, 26 and 66.\n"
        "Q9, annex package — PARTLY: Annex A, Addendum 01 and the clarification register are now "
        "held. ANNEXES B, C AND D REMAIN OUTSTANDING and are referenced by clauses this register "
        "relies on.\n"
        "Q10, export limit — REFRAMED by clarification 2: the Contracted Capacity becomes the "
        "Declared Capacity, expressly up to 11 MW, so 11 MW is a declarable capacity rather than "
        "only a tolerance above 10 MW.\n\n"
        "Three were NOT answered and can no longer be asked, because the clarification window "
        "closed on 25 August 2026: Q1 (whether the Volume I 85 % monthly minimum or the Volume "
        "III FEC-banded schedule governs), Q4 (whether both phase-step polarities are required — "
        "Annex A A.05.23(d)(II) states +50 degrees, so the 31 July recommendation to test both "
        "polarities and record +50 as the explicit minimum stands), and Q5 (grid-forming fault "
        "current magnitude and acceptable current-limiting behaviour)."
    ),
    "Closure pathways — how these gaps can be closed": (
        "A1, GRID-FORMING AT SCR 1.0. The control approach matters here, not just the model. "
        "Power Synchronisation Control, which uses active power rather than a frequency "
        "measurement as the synchronising signal, is reported as the most stable grid-forming "
        "approach at very low short-circuit ratios below about 1.5, where PLL-based "
        "grid-following control approaches its critical SCR of 1.0. If the ENPCS2520 grid-"
        "forming firmware uses a virtual-synchronous-generator approach that reacts to frequency "
        "and ROCOF, its stability at SCR 1.0 should be demonstrated rather than assumed. For the "
        "validation package itself, IEEE 2800.2 is the companion guide covering model "
        "validation, verification and test procedures, and the published EMT model requirements "
        "of SPP, ERCOT and AEMO are usable templates for what an acceptable submission contains "
        "— they are the same deliverable NSO is asking for. Note that IEEE has issued an "
        "amendment, IEEE 2800a, specifically to reduce barriers for IBRs with grid-forming "
        "equipment; it is the right reference to cite if Envision argues grid-forming compliance "
        "outside the US market.\n\n"
        "A2 and A3, RTE AND CELL TEMPERATURE. These are one thermal problem with two contractual "
        "faces, and the closure route is the same calculation. Published practice is that a "
        "containerised system's HVAC load can move system RTE by 2-4 percentage points "
        "seasonally, and that cooling load at 40 degrees C ambient can consume 3-5 % of "
        "throughput — which is the order of the entire margin at issue in A2. The RTE test is "
        "run at rated power, where losses and auxiliary draw are both at maximum and auxiliary "
        "draw is dominated by battery cooling. The favourable side is that liquid cooling holds "
        "cell-to-cell spread below about 5 degrees C and, at a 0.5C duty, keeps module "
        "temperatures in a 20-30 degrees C band; the contracted duty here is 0.25P, gentler "
        "still. So the physics plausibly supports Envision's position — but only if the "
        "calculation is produced. The specifiable rating point is the L45/W18 convention: rated "
        "cooling output at 45 degrees C ambient with an 18 degrees C fluid supply. General "
        "industry data corroborates the bankability study independently: roughly every 10 "
        "degrees C of additional cell temperature doubles degradation rate, and sustained "
        "45 degrees C versus 25 degrees C operation is reported to cut cycle life by 50 % or "
        "more, which is the same order as the study's 10,000 to 4,000 figures.\n\n"
        "B5, FIRE. The sixth edition of UL 9540A, published 13 March 2026, restructured this. "
        "The unit-level test is no longer required for non-residential BESS, and the "
        "installation-level large-scale fire test at Section 10 is now fully integrated as the "
        "fourth evaluation level after cell, module and unit, aligned to NFPA 855 guidance and "
        "intended to demonstrate that fire will not propagate between ESS units. For a "
        "utility-scale installation the realistic route is therefore the Section 10 "
        "installation-level test. It is physical burn testing and cannot be completed before "
        "4 September, so the deliverable for this bid is a dated commitment plus an interim "
        "compliance basis — which is a materially stronger position than silence, given that the "
        "module-level report itself tells the evaluator a further test is required.\n\n"
        "C1, STANDARDS. Clarification 62 is the route: currently valid certifications for the "
        "applicable cells, racks, major components or established product family, plus "
        "documentary evidence of the relationship and technical equivalence to the offered "
        "package. This is an evidence route, not a waiver. One caution stated plainly: no "
        "published equivalence mapping between IEEE 2800-2022 or UL 1741-SB and EN 50549-2 or "
        "G99 was found, so that argument must be constructed clause by clause and should not be "
        "presented as though a recognised equivalence already exists."
    ),
    "References for the closure pathways": (
        "Grid-forming control and validation: 'Review of recent developments in grid codes: "
        "focus on compliance testing and grid-forming inverter-based resources', ScienceDirect, "
        "https://www.sciencedirect.com/science/article/pii/S1364032125011827 . SPP "
        "Electromagnetic Transient (EMT) Model Requirements, "
        "https://opsportal.spp.org/documents/studies/SPP%20EMT_Model_Requirements_R1.pdf . MISO "
        "draft GFM BESS performance requirements whitepaper, "
        "https://cdn.misoenergy.org/20240903%20IPWG%20Item%2004a%20DRAFT%20GFM%20BESS%20Performance%20Requirements%20Whitepaper%20REDLINE%20(PAC-2024-2)645386.pdf . "
        "IEEE 2800a, 'Reduce Barriers for IBRs with Grid-Forming Equipment', "
        "https://standards.ieee.org/ieee/2800a/12386/ . Elia INPOWEL EMT models for grid-forming "
        "assets, https://innovation.eliagroup.eu/en/projects/inpowel-emt-models-for-grid-forming-assets . "
        "NREL, 'Review of Technical Requirements for Inverter-Based Resources', "
        "https://docs.nrel.gov/docs/fy25osti/91792.pdf .\n\n"
        "UL 9540A sixth edition: Intertek, 'Advancing Fire Safety in Energy Storage: "
        "Understanding the 2026 Update to UL 9540A', "
        "https://www.intertek.com/blog/2026/03-23-understanding-the-2026-update-to-ul-9540a/ . "
        "Energy-Storage.News, 'UL9540A: shift to system-level testing defines new edition', "
        "https://www.energy-storage.news/ul9540a-shift-to-system-level-testing-defines-new-edition-of-key-bess-safety-standard/ . "
        "Mayfield Renewables, 'The 6th Edition of UL 9540A is Here', "
        "https://www.mayfield.energy/technical-articles/the-6th-edition-of-ul-9540a-is-here/ . "
        "UL Solutions, UL 9540A test method, https://www.ul.com/services/ul-9540a-test-method .\n\n"
        "Thermal and cycle life: Patsnap, 'LFP Battery Operating Temperature Guide', "
        "https://www.patsnap.com/resources/blog/articles/lfp-battery-longevity-optimal-temp-ranges/ . "
        "SunLith Energy, '0.5C vs 1C cycle life in liquid-cooled BESS (LFP data)', "
        "https://sunlithenergy.com/liquid-cooled-bess-0-5c-vs-1c-cycle-life/ . Bonnen Batteries, "
        "'Liquid cooling for BESS', "
        "https://www.bonnenbatteries.com/liquid-cooling-for-battery-energy-storage-systems-how-ci-bess-manages-heat/ .\n\n"
        "RTE and auxiliary load: Merus Power, 'Round-trip efficiency as a performance guarantee "
        "for BESS', "
        "https://meruspower.com/blog/round-trip-efficiency-as-a-performance-guarantee-for-battery-energy-storage-systems/ . "
        "Cooltechx, 'BESS liquid cooling capacity: why L45/W18 degrees C test conditions matter', "
        "https://www.cooltechx.com/bess-liquid-cooling-capacity-l45-w18/ .\n\n"
        "These references support the CLOSURE PATHWAYS only. No reference above is evidence about "
        "the offered Envision product, and none of them is a tender document. Every requirement "
        "in the register above is anchored to the NSO documents listed under Source provenance."
    ),
}


def build() -> object:
    """Assemble the dossier model."""
    return build_dossier(
        tender_ref=TENDER_REF,
        tender_title=TENDER_TITLE,
        oem_label="Envision Energy / the supplying group entity",
        # The emitter defaults to the neutral role label "Bidder". The project owner directed on
        # 27 August 2026 that the bidding entity be named, consistent with the corpus index and
        # the 30 July gap review, which already name it.
        bidder_label="Hayleys",
        gaps=GAPS,
        evidence=EVIDENCE,
        sources=SOURCES,
        sections=SECTIONS,
        submission_deadline="4 September 2026, 10.00 hrs (Addendum No. 01 item 01)",
        working_days_remaining=6,
    )


def main() -> None:
    """Render the dossier to PDF through the DutchBay Presentation Layer."""
    import sys
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    from app.reports.dbpl import render_dbpl_pdf

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "tender_gap_dossier.pdf")
    model = build()

    env = Environment(
        loader=FileSystemLoader("app/reports/dbpl/templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("dbpl_base.html.j2")

    # Two-pass: the first pass reports the real print-core provenance, which is then stamped
    # into the second. Reported from the result's own fields — never asserted.
    first = render_dbpl_pdf(template.render(doc=as_dbpl_document(model)))
    substituted = first.substituted_fonts
    embedded = first.house_fonts_embedded
    provenance = (
        f"Rendered by the DutchBay Presentation Layer (WeasyPrint), Python {model.python_version}.",  # type: ignore[attr-defined]
        f"PDF variant {first.pdf_variant}; house stylesheet applied: {first.stylesheet_applied}.",
        (
            "Font substitution: "
            + (", ".join(substituted) + " substituted" if substituted else "none")
            + "; house fonts embedded: "
            + (
                "UNVERIFIED (poppler unavailable)"
                if embedded is None
                else str(embedded)
            )
            + "."
        ),
        f"Gap register digest (SHA-256, first 32): {model.register_digest[:32]}.",  # type: ignore[attr-defined]
        f"Register content: {len(model.gaps)} gaps, {len(model.evidence)} evidence rows, "  # type: ignore[attr-defined]
        f"{len(model.sources)} source documents.",  # type: ignore[attr-defined]
    )
    final = render_dbpl_pdf(
        template.render(doc=as_dbpl_document(model, provenance_lines=provenance))
    )
    out.write_bytes(final.pdf)
    print(f"wrote {out} ({len(final.pdf):,} bytes)")
    print(f"register digest: {model.register_digest}")  # type: ignore[attr-defined]
    print(f"gaps: {len(model.gaps)}")  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
