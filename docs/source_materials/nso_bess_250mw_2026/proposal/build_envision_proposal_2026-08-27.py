"""Draft Envision technical proposal against NSO tender TR/REP&PM/ICB/2026/001/C.

Assembled ONLY from the DutchBay corpus. Every statement is one of two kinds, and the document
says which on every line:

  BLACK  — sourced. Traceable to a document held in docs/source_materials/nso_bess_250mw_2026/.
  RED    — DRAFTED GAP-FILL. Not found in any received Envision document. Written the way the
           tender requires it to read, so Envision can confirm, correct or replace it.

The red text is a drafting aid, NOT a representation about the offered product. Nothing in red
has been verified against Envision, and the document is not an Envision issue.

Rendered through the DutchBay Presentation Layer. Red is carried through a non-HTML sentinel
because the DBPL base template autoescapes every field.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.reports.dbpl import render_dbpl_pdf

# ── Red-text sentinel ────────────────────────────────────────────────────────────────────
# Guillemets survive Jinja autoescaping untouched, so they can be swapped for a span after
# rendering without risking HTML injection through any field.
_RO, _RC = "«GF»", "«/GF»"


def R(text: str) -> str:
    """Mark text as DRAFTED GAP-FILL (renders red)."""
    return f"{_RO}{text}{_RC}"


GAPFILL_CSS = """
.gf { color: #C00000; }
td .gf, p .gf, li .gf { font-weight: 500; }
"""

STATUS = "DRAFT FOR ENVISION COMPLETION - not an Envision document"

HEADLINE = (
    "DRAFT PROPOSAL PREPARED BY THE BIDDER'S ADVISOR - NOT AN ENVISION DOCUMENT AND NOT AN "
    "OFFER. This draft assembles, from the material Envision has supplied to date, the technical "
    "proposal that most closely fits the tender. Text in BLACK is sourced from a received "
    "Envision or NSO document. Text in RED is DRAFTED GAP-FILL: it was NOT found in any received "
    "Envision document and is written the way the tender requires it to read, so that Envision "
    "can confirm it, correct it, or replace it. No red statement has been verified with Envision "
    "and none may be relied upon or submitted until Envision has adopted it in writing."
)

DISCLAIMER = (
    "SOURCE DOCUMENTS GOVERN. Where this draft and a tender document, an Envision document or an "
    "issued addendum or clarification disagree, that document governs and this draft is wrong. "
    "Clause references are to NSO RFP Volumes I-III, Addendum No. 01 (7 August 2026), Annex A "
    "Functional and Performance Requirement, and the 76-item clarification register (21 August "
    "2026), all held in the corpus with SHA-256 recorded in MANIFEST.sha256."
)

SECTION_CAVEAT = (
    "BLACK = sourced from a received document | RED = drafted gap-fill, unverified, for Envision "
    "to confirm or replace"
)


def _control() -> list[tuple[str, str]]:
    return [
        ("Tender", "TR/REP&PM/ICB/2026/001/C"),
        (
            "Tender title",
            "Establishment of 250 MW / 1000 MWh Standalone Battery Energy Storage System from "
            "10 MW / 40 MWh AC Capacity Projects on Build, Own and Operate (BOO) Basis with "
            "15 Year Operational Period",
        ),
        (
            "Document",
            "Technical Proposal - Volume II Section 6 response and supporting schedules",
        ),
        (
            "Offered by",
            "Envision Energy / the supplying group entity (DRAFT - not yet adopted)",
        ),
        ("Project Proponent", "Hayleys"),
        (
            "Submission deadline",
            "4 September 2026, 10.00 hrs (Addendum No. 01 item 01)",
        ),
        (
            "Clarification window",
            "CLOSED 25 August 2026 - no further questions to NSO are possible",
        ),
        ("Declared Capacity offered", "10 MW / 40 MWh, export-limited (see section 2)"),
        ("Installed configuration", "11 MW / 44 MWh hardware - intentional oversizing"),
        (
            "Evidence base",
            "Updated 27 August 2026 after ingress of the OEM supply tranche (50 unique files), "
            "including the ENPCS2520 Technical Specification, the PSS(R)E and PSCAD model "
            "packages and the delivered dynamic record — none of which was held when this draft "
            "was first prepared",
        ),
        ("Status", STATUS),
        (
            "Completion required",
            R("Every red entry requires Envision confirmation before submission"),
        ),
    ]


# ═════════════════════════════════════════════════════════════════════════════════════════
# Sections
# ═════════════════════════════════════════════════════════════════════════════════════════


def _sections() -> list[dict]:
    s: list[dict] = []

    # ── 1. Offer summary ────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Offer summary and the single design decision behind it",
            "intro": (
                "Envision offers the 11 MW / 44 MWh equipment configuration, declared to NSO as a "
                "10 MW / 40 MWh Contracted Capacity and held to 10 MW by a tested export limiter. "
                "This is deliberate oversizing, and it is the single decision that resolves most "
                "of the tender's binding constraints at once."
            ),
            "table": {
                "columns": [
                    "Tender constraint",
                    "10 MW / 40 MWh build",
                    "11 MW / 44 MWh build, declared at 10 MW",
                ],
                "rows": [
                    {
                        "cells": [
                            "Usable energy at BoL against 40 MWh required",
                            "40.2 MWh - 0.5 % margin, smaller than the design calculation's own stated 1-2 % variability",
                            "43.9 MWh - approx. 9.75 % margin",
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Round-trip efficiency, year 15, auxiliary-inclusive (Volume I §2.8(iii), floor 85 %)",
                            "85.0 % - exactly on the floor, no margin",
                            "85.0 % declared; "
                            + R(
                                "re-rated at the lower relative loading of the oversized build, target 85.6 % - Envision to confirm"
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Reactive capability (clarification 24: +/-0.3 x rated active power)",
                            "+/-3.29 Mvar against +/-3.0 Mvar required - passes",
                            "+/-3.29 Mvar against +/-3.0 Mvar required at a declared 10 MW - passes with margin",
                        ]
                    },
                    {
                        "cells": [
                            "Four hours at rated output at site ambient (Volume I §3.1(k), envelope to +45 C)",
                            "Marginal - the 4.02 h figure is computed at 35 C",
                            R(
                                "Held at +45 C on the oversized energy base - Envision to confirm by thermal calculation, see section 5"
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Minimum Dispatchable Storage Capacity, year 15 (68 % of contracted)",
                            "30.8 MWh against 27.2 MWh required",
                            R(
                                "Approx. 33.6 MWh against 27.2 MWh required - Envision to confirm the degradation curve on the 44 MWh base"
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "400 full equivalent cycles per year, incl. ancillary-service energy (clarification 55(b))",
                            "Duty falls on a thinner energy base, so cell throughput per contracted MWh is higher",
                            R(
                                "Lower depth of discharge for the same delivered energy, extending cycle life - the principal answer to the 45 C exposure at section 5"
                            ),
                        ]
                    },
                ],
                "source": (
                    "Envision design calculations of 29 July 2026 (10 MW / 40 MWh, superseded 5 August) and "
                    "5 August 2026 (11 MW / 44 MWh); NSO RFP Volume I; Annex A; clarification register items 24 and 55."
                ),
            },
        }
    )

    s.append(
        {
            "heading": "Declared Capacity, export limiting and the second technical proposal",
            "intro": (
                "Clarification 2 confirms that the Contracted Capacity in Volume III Appendix 01 "
                "Clause 1 will be the Declared Capacity offered in Section 1 of Volume II, amended "
                "into the Contract at execution. Clarification 66 confirms the declared capacity "
                "must be achieved and demonstrated at commissioning."
            ),
            "points": [
                "Declared Capacity: 10 MW / 40 MWh. Every contractual obligation - availability, "
                "round-trip efficiency, dispatchable capacity, cycle allowance - is assessed against "
                "this figure.",
                "Installed equipment: 11 MW / 44 MWh, comprising 4 x ENPCS2520 on one AC skid "
                "(10.08 MW) plus the DC container set described in section 3.",
                R(
                    "Export limiter: the EnOS PPC limits net active power at the revenue metering "
                    "point to 10.0 MW continuous, with a hard ceiling of 11.0 MW (10 MW +10 %) at "
                    "the Termination Point. Setpoint resolution 0.1 MW, response time under 1 s to "
                    "a step, fail-safe action to 0 MW on loss of measurement or loss of PPC "
                    "heartbeat. Redundant measurement is taken from the revenue metering CT/VT set. "
                    "Envision to confirm the limiter hierarchy, response time and fail-safe state."
                ),
                R(
                    "Second technical proposal: Addendum No. 01 item 23 permits a maximum of two "
                    "Technical Proposals, and clarification 73(a) confirms up to two alternative "
                    "complete solutions with no interchange of major equipment between them. "
                    "Bidder decision pending Envision's answer on the grid-forming EMT model "
                    "(section 7): if a grid-forming PSCAD model of the ENPCS2520 does not exist, "
                    "the second proposal should carry a converter for which one does."
                ),
            ],
        }
    )

    # ── 3. Equipment schedule ───────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Equipment schedule and configuration",
            "intro": (
                "All part numbers, ratings and dimensions below are as recorded in the Envision "
                "design calculations, the filled Volume 2 Guaranteed Technical Particulars and the "
                "21 August evidence dossier."
            ),
            "table": {
                "columns": ["Item", "Designation", "Rating and particulars"],
                "rows": [
                    {"group": "Battery"},
                    {
                        "cells": [
                            "Cell",
                            "HC-L755A, LFP",
                            "3.2 V / 755 Ah / 2416 Wh. Approx. 10,000 cycles to 70 % retention at 25 C, 0.25P. "
                            "Storage recovery 99 % at 25 C and 97 % at 45 C after 135 days at 100 % SOC.",
                        ]
                    },
                    {
                        "cells": [
                            "Module",
                            "ENS-1P416S-L-10",
                            "Rack configuration 416S1P x 6.",
                        ]
                    },
                    {
                        "cells": [
                            "DC container (primary)",
                            "ENS-D06G-24120-10100-000",
                            "6,030 kWh per container; 6 racks in parallel; 24.121 MWh nameplate per AC twin-skid; "
                            "4 containers per twin-skid. DC range 1165-1500 V.",
                        ]
                    },
                    {
                        "cells": [
                            "DC container (secondary)",
                            "ENS-D10G-20100-10100-000",
                            "Supersedes ENS-D10E. 10 racks per DC container. DC range 1165-1500 V.",
                        ]
                    },
                    {
                        "cells": [
                            "Container envelope",
                            "-",
                            "6058 (L) x 2438 (W) x 3258 (H) mm, under 50,000 kg.",
                        ]
                    },
                    {"group": "Power conversion"},
                    {
                        "cells": [
                            "PCS",
                            "ENPCS2520",
                            "2.52 MVA, 690 V, 50 Hz, IP65, -25 to +45 C, at most 85 dB(A) at 1 m. "
                            "Droop settable 1-9 %; deadband 0.0-1.0 Hz in 0.05 Hz steps; power factor +/-0.95.",
                        ]
                    },
                    {
                        "cells": [
                            "AC skid",
                            "4 x ENPCS2520",
                            "10.08 MW aggregate.",
                        ]
                    },
                    {
                        "cells": [
                            "Step-up transformer",
                            "10,100 kVA",
                            "0.69 / 33 kV, three-winding, off-load tap changer, LI 170 kV / AC 70 kV, "
                            "oil-temperature indication, alarm and trip.",
                        ]
                    },
                    {
                        "cells": [
                            "MV switchgear",
                            "36 kV / 630 A RMU",
                            "33 kV rated, 170 kV LI / 70 kV power-frequency withstand, gas tank IP65, enclosure IP3X.",
                        ]
                    },
                    {
                        "cells": [
                            "MV station envelope",
                            "-",
                            "12192 x 2438 x 2896 mm, approx. 49,000 kg.",
                        ]
                    },
                    {"group": "Controls"},
                    {
                        "cells": [
                            "Plant controller",
                            "EnOS PPC",
                            "Per the filled Volume 2 GTP.",
                        ]
                    },
                    {
                        "cells": [
                            "SCADA / gateway",
                            "EnOS BESS SCADA (Univers) V2.4.4",
                            "Addendum No. 01 item 09 requires simultaneous real-time reporting to a minimum of "
                            "FOUR SCADA master servers — two at the NSCC and two at the Backup NSCC — in any "
                            "combination, without additional hardware, software, configuration change or licence. "
                            "The EnOS SCADA product manual allocates TCP ports 2401-2408 to the IEC 104 service, "
                            "i.e. EIGHT concurrent IEC 104 sessions, which covers the four required. "
                            + R(
                                "Envision to confirm in writing that four concurrent master connections carry no "
                                "additional licence cost, since the port allocation evidences capacity but the "
                                "manual does not address licensing. Clarification 27 confirms a gateway is "
                                "required even where the PPC itself supports IEC 104."
                            ),
                        ]
                    },
                ],
                "source": "Envision design calculations; filled Volume 2 GTP; 21 August evidence dossier; Addendum No. 01 item 09.",
            },
        }
    )

    # ── 4. Guaranteed performance ───────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Guaranteed performance schedule",
            "intro": (
                "Values are stated at the revenue metering point. Clarification 51 confirms that "
                "auxiliary and HVAC loads directly associated with BESS operation are inside the "
                "round-trip efficiency calculation, and that general site loads such as CCTV, "
                "security and lighting are outside it. Clarification 40 refused a measurement-error "
                "tolerance, so no tolerance is claimed below."
            ),
            "table": {
                "columns": ["Guaranteed parameter", "Basis", "Guaranteed value"],
                "rows": [
                    {
                        "cells": [
                            "Usable energy at BoL",
                            "At the metering point, 0.25P discharge",
                            "43.9 MWh installed; 40.0 MWh guaranteed at the Declared Capacity",
                        ]
                    },
                    {
                        "cells": [
                            "Discharge duration at rated output",
                            "Volume I §3.1(k), at site ambient",
                            R(
                                "4.0 hours at 10 MW at +45 C ambient - Envision to confirm on the thermal case at section 5"
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Round-trip efficiency, BoL",
                            "AC-to-AC, auxiliary-inclusive, monthly",
                            "86.9 %",
                        ]
                    },
                    {
                        "cells": [
                            "Round-trip efficiency, year 15",
                            "AC-to-AC, auxiliary-inclusive, monthly",
                            "85.0 % declared; "
                            + R(
                                "target 85.6 % on the oversized build, Envision to re-rate"
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "State of health, year 15",
                            "Against the 68 % MDSC floor",
                            "76.7 % on the 10 MW curve; "
                            + R(
                                "Envision to issue the equivalent curve on the 44 MWh base"
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Reactive capability at the PCC",
                            "Clarification 24: +/-0.3 x rated active power",
                            "+/-3.62 Mvar at power factor +/-0.95 (11 MW / 44 MWh design calculation), against +/-3.0 Mvar "
                            "required at a declared 10 MW and +/-3.3 Mvar at a declared 11 MW. Complies on either basis.",
                        ]
                    },
                    {
                        "cells": [
                            "Availability",
                            "ESA, monthly",
                            R(
                                "97.0 % monthly, guaranteed back-to-back. Envision to supply the reliability "
                                "block diagram, component failure rates, MTTR and spares holding that support "
                                "it - see section 11."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Cycle allowance",
                            "400 full equivalent cycles per year, floor 20 per month",
                            "Cell rated 7300 EFC at 100 % DoD, 9125 at 80 %, 14600 at 50 % (filled GTP)",
                        ]
                    },
                    {
                        "cells": [
                            "Self-discharge",
                            "Filled Volume 2 GTP",
                            "At most 3 % per month",
                        ]
                    },
                    {
                        "cells": [
                            "Auxiliary load",
                            "At BoL, 4-hour discharge",
                            "0.17 MW at 35 C in the design calculation. Envision's auxiliary-consumption note supplied "
                            "27 August states 160 kW during charge/discharge and 58 kW in standby. "
                            + R(
                                "Neither figure states the ambient temperature it holds at, and none is given for +45 C. "
                                "The standby figure now matters directly: clarification 31 places standby-regulation energy "
                                "inside the RTE calculation, so 58 kW of standby draw is inside the guarantee. Envision to "
                                "state both figures at +45 C."
                            ),
                        ],
                        "emphasis": True,
                    },
                ],
                "notes": [
                    "Clarification 5: a monthly RTE shortfall shall not be carried forward or reconciled against "
                    "later months or the year end. Every month stands alone.",
                    "Clarification 31: energy lost to frequency or voltage regulation in standby, unscheduled by "
                    "the grid, is counted in the RTE calculation.",
                    "Clarification 55(b): energy exchanged providing frequency response, synthetic inertia, "
                    "oscillation damping and AGC is not excluded from the RTE calculation or from the 400-cycle "
                    "allowance.",
                ],
                "source": "Envision design calculation 5 August 2026; filled Volume 2 GTP; clarification register items 5, 24, 31, 40, 51, 55.",
            },
        }
    )

    # ── 5. Loss stack and the 45 C case ─────────────────────────────────────────────────
    s.append(
        {
            "heading": "Loss stack and the +45 C guaranteed case",
            "intro": (
                "The loss stack below is as stated in the 5 August design calculation for the 11 MW "
                "case. The +45 C column is the tender's binding condition and is the single largest "
                "open item in this proposal: the received calculation computes auxiliaries at 35 C, "
                "while the site envelope runs to +45 C and Volume I §3.1(k) requires four hours at "
                "rated output at site ambient."
            ),
            "table": {
                "columns": [
                    "Loss element",
                    "As calculated (35 C basis)",
                    "At +45 C site ambient",
                ],
                "rows": [
                    {
                        "cells": [
                            "Calendar degradation, FAT to SAT",
                            "97 %",
                            R("No change expected - Envision to confirm"),
                        ]
                    },
                    {"cells": ["Usable DC ratio", "98 %", R("Envision to confirm")]},
                    {"cells": ["LV DC cable", "99.9 %", R("Envision to confirm")]},
                    {
                        "cells": [
                            "PCS conversion",
                            "98.5 %",
                            R(
                                "Derate expected above 40 C - Envision to state the curve"
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "LV/MV transformer",
                            "99.2 %",
                            R("Envision to confirm at 45 C oil rise"),
                        ]
                    },
                    {"cells": ["MV cable", "99.6 %", R("Envision to confirm")]},
                    {
                        "cells": [
                            "MV/HV transformer and HV cable",
                            "100 % (assumed, BoP scope)",
                            "100 % (assumed, BoP scope)",
                        ]
                    },
                    {
                        "cells": [
                            "Auxiliary and HVAC",
                            "0.17 MW over 4 h at BoL",
                            R(
                                "Envision to state - the RTE guarantee cannot be closed without it"
                            ),
                        ],
                        "emphasis": True,
                    },
                ],
                "source": "Envision design calculation, 11 MW / 44 MWh, V1.0, 5 August 2026.",
            },
        }
    )

    s.append(
        {
            "heading": "Thermal substantiation at +45 C - the case Envision must supply",
            "intro": (
                "The system is liquid-cooled, so cell temperature is not ambient temperature. That "
                "is the whole of Envision's answer to the cycle-life question, and it is currently "
                "unstated. The following is the shape of the case the tender requires."
            ),
            "points": [
                "The supplier's own independent test-house bankability study (Issue D Final, "
                "28 January 2026) records approximately 10,000 cycles to 70 % capacity retention at "
                "25 C and 0.25P, but only approximately 4,000 at 45 C. The 20-year / 70 %-retention "
                "simulation it endorses is qualified to 25 C, at most 50 % SOC and one cycle per day.",
                "The contracted duty is approximately 400 full equivalent cycles per year over 15 "
                "years, i.e. roughly 6,000 cycles as a minimum obligation - about 2,000 more than "
                "the 45 C figure supports.",
                R(
                    "Proposed substantiation. At +45 C ambient the liquid-cooling system maintains a "
                    "coolant supply temperature of 18 C, holding steady-state cell temperature at or "
                    "below 30 C at the contracted 0.25P duty, with cell-to-cell spread within 5 C. "
                    "Cycle life at that cell temperature is therefore materially closer to the 25 C "
                    "figure than to the 45 C figure, and exceeds the approximately 6,022 EFC the "
                    "15-year duty requires. Envision to supply the thermal calculation that "
                    "establishes this."
                ),
                R(
                    "Chiller rating point. The industry convention for this duty is an L45/W18 "
                    "rating - rated cooling output at 45 C ambient with an 18 C fluid supply. "
                    "Envision to state the installed chiller capacity at L45/W18 and the electrical "
                    "draw at that condition, which is the auxiliary figure the RTE guarantee needs."
                ),
                R(
                    "Contractual backstop. Where the thermal case cannot be closed before "
                    "submission, Envision offers a capacity and throughput warranty with an "
                    "augmentation undertaking triggered on measured capacity falling below the "
                    "declared curve, at Envision's cost. This converts the exposure into a bankable "
                    "term and is the correct answer even with more time. Envision to confirm."
                ),
            ],
        }
    )

    # ── 7. Grid-forming ─────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Grid-forming control - declaration and compliance",
            "intro": (
                "This section is drafted to reconcile two Employer documents that pull in different "
                "directions. Annex A A.05.17(i) REQUIRES the BESS to support both grid-following and "
                "grid-forming control modes with online switching between them. Volume I §3(c) "
                "requires a voltage-sourced, voltage-controlled inverter that must not change to "
                "current-controlled operation during normal operation or under any network fault "
                "condition. Clarification 12 confirms grid-forming capability is both mandatory and "
                "practical for these projects."
            ),
            "points": [
                "Declaration, from the ENPCS2520 specification section 6: the PCS 'can run in both "
                "grid following and grid forming mode with seamless transition', and in grid-forming "
                "mode 'works as a VIRTUAL SYNCHRONOUS GENERATOR LIKE A VOLTAGE SOURCE', supporting "
                "active power control, reactive power control, virtual inertia, primary frequency "
                "control and voltage droop control. The specification also records that the PCS "
                "'has a current control in its inner loop to make sure the equipment operates "
                "safely'. That inner current loop is an equipment-protection limit inside a "
                "voltage-source control, not a change of control mode, and the proposal states it "
                "expressly so it cannot later be characterised as grid-following operation.",
                "Key grid-forming functions declared (specification Table 7): Frequency Governor and "
                "Virtual Inertia for frequency support and stabilisation; Automatic Voltage Regulator "
                "for voltage support; Unit Control for current limitation during faults and inrush; "
                "Islanding Control; and Synthetic Impedance for 'Grid Strengthen when SCR < 2'.",
                R(
                    "Operating declaration for the bid. The plant is delivered, commissioned and "
                    "operated in GRID-FORMING mode as its normal and continuous operating state, and "
                    "does not change to current-controlled operation during normal operation or under "
                    "any network fault condition, as Volume I §3(c) requires. Mode transition is "
                    "available only as a commissioning and maintenance function under NSO's written "
                    "instruction, and is not an automatic fault response. Envision to adopt this "
                    "wording — the capability is evidenced; the operating commitment is not yet."
                ),
                "Short-circuit ratio. Annex A A.05.17(j) requires grid-forming stable to SCR 1.0 and "
                "grid-following to SCR 1.2. The specification's Synthetic Impedance function is "
                "scoped to 'Grid Strengthen when SCR < 2', and Envision's own text is candid about "
                "the limits: 'most [grid-forming inverters] are implemented based on the power "
                "synchronization mechanism of synchronous machines. Consequently, classical stability "
                "issues such as power angle stability persist… This scenario poses challenges for the "
                "stable operation of a large-scale aggregation of PCSs operating in VSG (Virtual "
                "Synchronous Generator) mode.' The stated mitigation is virtual-impedance emulation "
                "with grid-impedance detection, improving as more PCSs are deployed on the same "
                "impedance-matching technology. "
                + R(
                    "Envision to confirm stable grid-forming operation specifically at SCR 1.0 — the "
                    "'SCR < 2' scoping does not by itself establish it — and to evidence it by EMT "
                    "simulation per section 8. This is the single most important open technical "
                    "question in the proposal."
                ),
                "Reconciliation of existing documents. The item 61 Grid Compliance List describes "
                "GFM and GFL modes with seamless transition at clauses 3.17.4 and 3.17.4.4. That "
                "dual-mode capability is REQUIRED by A.05.17(i) and is retained. What is re-pointed "
                "is its framing: it is offered as the A.05.17(i) capability, and NOT as the basis "
                "for converter robustness under fault, which is delivered by grid-forming operation "
                "per Volume I §3(c).",
                R(
                    "Document control. The item 61 Grid Compliance List currently carries the "
                    "placeholder document number PMD - XXXXXXXX, revision A, and is unsigned, while "
                    "the checklist requires it signed on company letterhead. Envision to issue a "
                    "signed, numbered revision."
                ),
                R(
                    "Superseded filing. Checklist item 38 requires grid-forming MODELLING evidence. "
                    "The document currently filed against it is a black-start technical solution "
                    "marked 'for reference'. Clarification 37 confirms black start is not mandatory "
                    "for this project, so that document answers no tender requirement. It is "
                    "withdrawn from item 38 and replaced by the model package at section 8."
                ),
            ],
        }
    )

    s.append(
        {
            "heading": "Annex A A.05 numeric performance parameters",
            "intro": (
                "Annex A sets hard numeric acceptance criteria. Clarifications 59 and 64 both "
                "requested relief on the current ratings - including an explicit request to reduce "
                "the 120 % duration from two minutes to one - and both were answered 'Please comply "
                "with A.05.02 of Annex A'. No relief is available."
            ),
            "table": {
                "columns": ["Annex A clause", "Requirement", "Offered"],
                "rows": [
                    {
                        "cells": [
                            "A.05.02(a)",
                            "PCS AC-side current 110 % continuous, 120 % for at least 2 min, preferably 150 % short-term",
                            "NOT MET AS SPECIFIED. The ENPCS2520 Technical Specification V1.0 states: 110 % for 10 minutes at 45 C; 110 % continuous at 40 C; 120 % for 1 minute at 35 C. No 150 % rating is stated. "
                            + R(
                                "At the +45 C site envelope the converter therefore offers 110 % for ten minutes, not continuously, and 120 % for one minute at 35 C against a requirement of at least two minutes. Unlike the frequency settings below, no adjustability note attaches — these are thermal ratings. Clarification 64 requested exactly this relief and NSO refused. Envision must state what configuration DOES meet A.05.02(a) at site ambient; this is a sizing decision, not a datasheet correction."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "A.05.02(b)",
                            "Droop settable 1-9 %; default 4 % where NSO specifies none",
                            "Droop settable 1-9 % (filled GTP) - COMPLIES. Default set to 4 %.",
                        ]
                    },
                    {
                        "cells": [
                            "A.05.02(c)-(d)",
                            "Synthetic inertia through grid-forming control; inertia time constant no less than 20 s; activation at most 5 ms; flexibly adjustable",
                            "The specification's Table 5 gives PCS reaction time <= 5 ms, which meets the <= 5 ms inertia-response activation the clause requires, and virtual inertia is a declared grid-forming function (Table 7). "
                            + R(
                                "The INERTIA TIME CONSTANT itself is not stated anywhere in the specification. Annex A requires no less than 20 s. The delivered .dyr carries a value of 20.0 at CON position 13 of the ENGFM01 record, which is consistent with a 20 s constant, but the model guide does not define that position and it must NOT be quoted as the inertia constant until Envision confirms it. Envision to state the inertia time constant, its adjustment range, and confirm the activation time in grid-forming mode."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "A.05.02(e)",
                            "Primary frequency regulation response under 0.2 s; active power adjustment deviation at most 2 %",
                            "MET. Specification Table 5 (dynamic response): reaction time <= 5 ms, response time <= 30 ms, settling time <= 50 ms — comfortably inside the < 0.2 s the clause requires. "
                            + R(
                                "Table 5 is stated for GRID FOLLOWING mode; Envision to confirm the same or better figures in grid-forming mode, and to state the active power adjustment deviation, which the specification does not give."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "A.05.04",
                            "Steady-state 47-52 Hz; extremes 45-55 Hz; 10 s ride-through in the band 47.0 > f >= 45.0",
                            "NOT MET AS DELIVERED — verified from three sources. The supplied dynamic record sets 47.5 Hz / 1800 s and 46.9 Hz / 0.04 s under-frequency, and 51.5 Hz / 1800 s and 52.1 Hz / 0.04 s over-frequency; the PSS(R)E UDM manual V1.4a confirms these CONs trip the PCS; and the ENPCS2520 specification Table 3 states the same in words — between 47 and 47.5 Hz a CHARGING PCS separates from the grid within 0.2 s, and a discharging one operates only 30 minutes (the 1800 s in the record). "
                            + R(
                                "Annex A A.05.04 requires CONTINUOUS operation across 47-52 Hz, and 10 s ride-through between 47.0 and 45.0 Hz where the record trips in 0.04 s. REMEDY, stated by Envision's own specification: 'The PCS software parameters can be adjusted to the local grid code frequency protection requirements.' Envision to re-issue the protection settings to A.05.04 and re-supply the dynamic record carrying them — the model submitted with the bid currently carries the non-compliant settings."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "A.05.17(d)",
                            "Autonomous damping of 0.2-2.5 Hz oscillations; active power variation limited to 10-30 % Pn",
                            R(
                                "Autonomous power-oscillation damping across 0.2-2.5 Hz, active power variation limited to 10-30 % Pn, enabled by default. Envision to confirm."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "A.05.17(h)",
                            "AGC range -100 % to +100 % Pn, steady-state active deviation at most 2 % Pn; AVC steady-state reactive deviation at most 2 % Pn",
                            R(
                                "AGC -100 % to +100 % Pn with steady-state deviation at most 2 % Pn; AVC steady-state reactive deviation at most 2 % Pn. Envision to confirm."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "A.05.17(j)",
                            "GFL stable at SCR >= 1.2; GFM stable at SCR >= 1.0",
                            "Synthetic Impedance is declared for 'Grid Strengthen when SCR < 2' (specification Table 7). "
                            + R(
                                "'SCR < 2' does not establish stability AT SCR 1.0. Envision to confirm the 1.0 figure explicitly and evidence it by EMT simulation — see section 7."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "A.05.18",
                            "Fault-current contribution bounded by the breaker capability NSO specifies; withstand per A.04",
                            "The specification states fault-current injection at 1.2 times rated current, and up to 1.3 times allowing for margin of error in actual operation. Rated current is 2109 A, so the per-PCS contribution is approximately 2.53-2.74 kA. "
                            + R(
                                "Envision to state the DURATION of that injection and confirm withstand for the 550 ms breaker-failure clearing time, neither of which the specification gives, and to confirm the aggregate four-PCS contribution sits within the 25 kA POC limit."
                            ),
                        ]
                    },
                ],
                "source": "Annex A Functional and Performance Requirement; filled Volume 2 GTP; clarification register items 29, 59, 64.",
            },
        }
    )

    # ── 9. Models ───────────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Dynamic simulation models",
            "intro": (
                "Annex A A.05.23(d) states the bid-stage minimum as an ALTERNATIVE: either initial "
                "non-site-specific models in both PSS(R)E and PSCAD/EMTDC formats with the tender, "
                "OR test results demonstrating V/P/Q response through deep and shallow faults and a "
                "+50-degree phase-angle step at SCR 1, 3, 5 and 10 with X/R 5. Failure to meet at "
                "least one may result in rejection of the technical proposal. Addendum No. 01 item "
                "14 writes the same either/or into the Volume II Section 5 Compliance Schedule as "
                "new item 12. Envision holds both models, so route (I) is satisfied at bid stage."
            ),
            "table": {
                "columns": ["Deliverable", "Status", "Particulars"],
                "rows": [
                    {
                        "cells": [
                            "PSS(R)E RMS model",
                            "HELD - submitted",
                            "ENVSG01_20260327_PSSE_V35.dll (grid-forming PCS), ENPPC_260415_PSSE_V35.dll (PPC), and "
                            "the Sri-Lanka dynamic record ENVSG_PPC_2520_260416_LKA.dyr instantiating ENGFM01 "
                            "(2520 kW base) and BNPPC_GFMV3. Manual V1.4a, 11 August 2026. Runs in PSS(R)E 35.x "
                            "as A.05.23(c) requires.",
                        ]
                    },
                    {
                        "cells": [
                            "PSCAD/EMTDC EMT model",
                            "HELD - but grid-FOLLOWING variant",
                            "PCS2520x4_UPPC_x64_260605aBB.pscx (4 x ENPCS2520 at 690 V / 50 Hz on one 10.1 MVA skid), "
                            "PCSControllerInterface.dll, five .obj and one .lib interface objects. Requires PSCAD V5.0 "
                            "with Intel Fortran XE 15+, 1-200 us timestep, 50 us recommended - meets A.05.23(c).",
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Grid-forming EMT model",
                            R("REQUIRED - not held"),
                            R(
                                "The EMT model supplied is titled for the GFL PCS variant, its model block is "
                                "labelled GFL-PCS, and the converter is represented as a CURRENT SOURCE. A "
                                "current-source model cannot demonstrate voltage-source behaviour under fault, and "
                                "the PSS(R)E grid-forming manual itself records that EMT is the better tool for "
                                "fault ride-through. Envision to confirm whether a grid-forming PSCAD model of the "
                                "ENPCS2520 exists and to issue it. If none exists, that answer is needed "
                                "immediately."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "SCR sweep and phase step",
                            R("Post-award deliverable"),
                            R(
                                "V/P/Q traces through deep and shallow faults and a +50-degree phase-angle step at "
                                "SCR 1, 3, 5 and 10 with X/R 5, plus the A.05.17(j) grid-forming case at SCR 1.0. "
                                "Not required at bid stage where both models are submitted. Due within one month of "
                                "ESA execution - 14 January 2027 - under Addendum No. 01 item 12."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "PowerFactory models",
                            "NOT required",
                            "A.05.23(b) names a third tool, but clarification 35 confirms: 'It is compulsory to "
                            "provide PSSE and PSCAD models.' PowerFactory is therefore outside the compulsory set.",
                        ]
                    },
                ],
                "notes": [
                    "Addendum No. 01 item 06 adds failure to submit the Dynamic Model Test results, in a form and "
                    "level of detail acceptable to NSO, within one month of ESA execution to the grounds on which "
                    "the Performance Security may be forfeited. The grid-forming EMT gap is therefore a "
                    "security-backed post-award obligation on a one-month clock, not merely an evidence gap.",
                    "Document hygiene noted for correction: the PSCAD manual describes the compiled DLL using "
                    "wind-turbine source-code wording, and section 4 of the PSS(R)E manual renders as a Word "
                    "undefined-bookmark error in the released PDF.",
                ],
                "source": "Annex A A.05.23; Addendum No. 01 items 06, 12 and 14; clarification 35; 21 August evidence dossier.",
            },
        }
    )

    # ── 10. Fire ────────────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Fire safety and thermal runaway",
            "table": {
                "columns": ["Element", "Status", "Particulars"],
                "rows": [
                    {
                        "cells": [
                            "UL 9540A cell level",
                            "HELD",
                            "Cell-level report to UL 9540A-2019.",
                        ]
                    },
                    {
                        "cells": [
                            "UL 9540A module level",
                            "HELD",
                            "Module-level report to UL 9540A-2026, 54 pp, issued 25 June 2026. Recorded results: peak "
                            "heat release rate 46.28 kW; peak smoke release rate 0.5457 m2/s; total smoke release "
                            "29.98 m2; total hydrocarbons 432.6 L; module weight loss 1.8 kg; no flaming observed. "
                            "Cell-to-cell thermal runaway and propagation occurred and was contained by the module "
                            "design; cell vent gas was determined flammable at cell level.",
                        ]
                    },
                    {
                        "cells": [
                            "Next test level",
                            R("REQUIRED - not held"),
                            R(
                                "The module report's own conclusion states that a further test level is required. "
                                "Under the sixth edition of UL 9540A, published 13 March 2026, the unit-level test is "
                                "no longer required for non-residential BESS, and the installation-level large-scale "
                                "fire test at Section 10 is the integrated fourth evaluation level, aligned to NFPA "
                                "855 and intended to demonstrate that fire does not propagate between ESS units. "
                                "Envision offers a dated commitment to the Section 10 installation-level test, with "
                                "the module-level result as the interim compliance basis. Physical burn testing "
                                "cannot complete before 4 September. Envision to confirm the route and the date."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Fire Protection System Specification",
                            "HELD - scope mismatch",
                            "V2.0, 21 May 2026. The header scopes ENS-D10, while the offered configuration uses "
                            "ENS-D06G and ENS-D10G containers.",
                        ]
                    },
                    {
                        "cells": [
                            "D06G coverage",
                            R("REQUIRED"),
                            R(
                                "Envision to re-issue the specification with a header scoping both offered container types, or to confirm coverage of ENS-D06G in writing."
                            ),
                        ]
                    },
                ],
                "source": "21 August evidence dossier, checklist item 45; UL 9540A sixth edition (13 March 2026).",
            },
        }
    )

    # ── 11. Standards ───────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Standards and certification register",
            "intro": (
                "Sixteen certificates and reports are held across checklist sections C and D - five "
                "DC-side and eleven AC-side. Clarification 62 opens the route for the remainder: "
                "where the exact proposed package is newly introduced and certification is still in "
                "progress, the bidder may submit currently valid certifications for the applicable "
                "cells, racks, major components or established product family, TOGETHER WITH "
                "documentary evidence of the relationship and technical equivalence to the offered "
                "package. That is an evidence route, not a waiver."
            ),
            "table": {
                "columns": ["Standard", "Declared position", "Action"],
                "rows": [
                    {
                        "cells": [
                            "IEC 62619 (CB scheme)",
                            "Certified, cell level",
                            "Held. Certificate is in the cell-manufacturing entity's name.",
                        ]
                    },
                    {
                        "cells": [
                            "UL 1973",
                            "Component recognition, cell level (BBGA2)",
                            R(
                                "The certificate states that UL Recognized components are incomplete in certain constructional features. It is not system certification and must not be presented as such. Envision to supply the equivalence evidence bridging cell-level recognition to the offered system under clarification 62."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "UL 9540 (system level)",
                            "Partially comply / future",
                            R(
                                "Envision to state a realistic certification date and the interim equivalence basis."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "IEC 62620, IEC 62933-5-2",
                            "Not certified - 'Will finish before 2026'",
                            R(
                                "STALE: the date has passed. Envision to re-date with realistic completion dates - a stale commitment reads worse than an honest revised one."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "IEC 62902",
                            "Not comply - ISO 7010 labelling offered instead",
                            R("Envision to state the equivalence argument."),
                        ]
                    },
                    {
                        "cells": [
                            "IEC 62485-5",
                            "Not comply - IEC 62619 / 61000-6-2/-6-4 / 62620 offered",
                            R("Envision to state the equivalence argument."),
                        ]
                    },
                    {
                        "cells": [
                            "IEC 62933-1",
                            "Comply, no certificate - 'do not plan to certificate'",
                            R(
                                "Envision to supply a signed declaration of compliance in lieu."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "IEC 62933-2-1",
                            "Not comply - framework standard",
                            R("Envision to state the equivalence argument."),
                        ]
                    },
                    {
                        "cells": [
                            "IEEE 1547-2018",
                            "Partially - only US-version products tested",
                            R(
                                "Envision to state which provisions are met by the offered product."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "IEEE 2800-2022",
                            "Declined - 'US region-specific, not required for other markets'",
                            R(
                                "This is the substantive refusal. IEEE 2800 is the transmission-level IBR "
                                "interconnection standard whose grid-forming provisions are the natural reference for "
                                "this tender's mandatory grid-forming requirement, and declining it on market-scope "
                                "grounds will be read closely. Envision to state the equivalence argument clause by "
                                "clause against EN 50549-2 and G99. NOTE: no published equivalence mapping between "
                                "these standards exists, so the argument must be constructed, not cited. IEEE has "
                                "issued amendment IEEE 2800a specifically to reduce barriers for inverter-based "
                                "resources with grid-forming equipment; it is the right reference to engage."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "UL 1741-SB",
                            "Declined - US-only; EN 50549-2 / G99 offered",
                            R(
                                "Envision to state the clause-level equivalence argument."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "IEC TS 62786-3",
                            "Not applicable - string-PCS standard; centralised PCS offered",
                            "Position is sustainable as stated.",
                        ]
                    },
                    {
                        "cells": [
                            "Sri Lanka Grid Connection Code (July 2024)",
                            "Checklist item 36 marked Not Received, no remark",
                            "STALE STATUS: item 61, the Grid Compliance List of 11 August 2026, post-dates the checklist and largely answers it. Bidder to update the workbook.",
                        ]
                    },
                ],
                "source": "21 August evidence dossier, checklist sections C and D; clarification 62.",
            },
        }
    )

    # ── 12. Operations ──────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Capacity maintenance, availability and end of life",
            "points": [
                R(
                    "Capacity Maintenance Plan (Volume I §3.1(m)). Envision to issue a plan, not a "
                    "curve. It must state beginning-of-life energy at the Termination Point against "
                    "the contracted rating; the augmentation schedule in MWh and timing, or an "
                    "express and substantiated statement that none is required; module and rack "
                    "replacement intervals; the augmentation and outage interface with NSO; and "
                    "end-of-life decommissioning and recycling commitments."
                ),
                R(
                    "Augmentation. Checklist items 55 and 56 declare that no augmentation and no "
                    "replacement are needed during the lifetime, and both status cells are blank. "
                    "That declaration is supportable only near 25 C cell temperature. Envision to "
                    "substantiate it against the thermal case at section 5, or to replace it with a "
                    "trigger-based augmentation undertaking with reserved space, compatible future "
                    "cell supply, outage durations and spares."
                ),
                R(
                    "Availability. Envision to supply a reliability block diagram, component failure "
                    "rates, redundancy, MTTR, planned-maintenance schedule and spares holding "
                    "sufficient to support 97 % monthly availability. This carries unusual weight: "
                    "clarification 54 confirms there is no aggregate cap on liquidated damages per "
                    "Contract Year or over the 15-year Term, and that capacity-charge deductions for "
                    "missing 97 % availability are NOT liquidated damages and fall outside the "
                    "monthly cap - so the capacity charge for a month may be reduced to LKR 0. The "
                    "operator reference record shows PCS as the dominant availability risk: 68-70 "
                    "hours of PCS downtime against 0 hours of cell-fault downtime."
                ),
                R(
                    "End of life. The document currently filed at checklist item 57 is a mechanical "
                    "disassembly work instruction; a keyword sweep of it returns zero occurrences of "
                    "recycling, disposal, waste, take-back, second-life or Sri Lanka environmental "
                    "regulation. Envision to supply a genuine commitment: the take-back or recycling "
                    "route, the receiving facility and its jurisdiction, treatment of the LFP "
                    "chemistry, and express reference to the applicable Sri Lankan environmental "
                    "regulations."
                ),
                "Service life and warranty (Volume I §3.1(l)) — THE LARGEST COMMERCIAL GAP IN THE "
                "PACKAGE, and it is established by Envision's own Product Warranty Policy V1.0, "
                "supplied 27 August. Its Table 1 sets ONE warranty period across the whole scope — "
                "battery pack, BMS at pack/rack/bank level, HVAC, rack protection, fire detection "
                "and suppression, cables and consumables, battery container combiner panel, the PCS, "
                "the step-up transformer, the RMU, electrical cabinets, and the EMS/SCADA: "
                "'2 years from date of first time installation or commissioning; or delivery term "
                "and conditions in the supply contract; whichever occurs earlier.' Within that "
                "period Envision repairs or replaces at its option, and 'the client shall bear the "
                "costs of removing the non-conforming or defective product(s) and (re) installation'. "
                "The policy contains no capacity warranty, no throughput warranty and no "
                "availability warranty.",
                R(
                    "Against a FIFTEEN-YEAR build-own-operate term this leaves thirteen years of "
                    "equipment risk unwarranted — on a contract where clarification 54 establishes no "
                    "aggregate cap on liquidated damages and a capacity charge that can fall to LKR 0 "
                    "in any month missing 97 % availability. The 20-year non-battery design-life "
                    "letter already in the package is a design-life STATEMENT, self-certified, and "
                    "the checklist itself records 'No certification to prove this but we provided a "
                    "statement'; a design-life statement is not a warranty. Envision to state what "
                    "warranty term, capacity warranty and availability warranty it will offer for a "
                    "15-year BOO project, because a 2-year product warranty cannot support this "
                    "tender's risk allocation. This should be settled before submission, not after "
                    "award: Volume I §7.1 and clarification 30 make the ESA unamendable once the "
                    "Letter of Award issues."
                ),
            ],
        }
    )

    # ── 13. Qualification ───────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Qualification and corporate",
            "table": {
                "columns": ["Requirement", "Position", "Action"],
                "rows": [
                    {
                        "cells": [
                            "Manufacturer track record (Volume I clause 2.7.3)",
                            "Envision Energy letter: 18.7 GW / 52.6 GWh contracted; 33.5 GWh shipped; 20.65 GWh at COD",
                            R(
                                "Clarification 58(a)-(b) settles that the threshold is CUMULATIVE GLOBAL INSTALLED / COMMISSIONED volume, 'because the requirement says installed'. The qualifying figure is therefore the 20.65 GWh at COD - not the 52.6 GWh contracted or 33.5 GWh shipped. The bid should quote 20.65 GWh."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Whose experience qualifies",
                            "Track record in Envision Energy's name; EOI signed by an affiliated supply entity; cell certificates in the cell-manufacturing entity's name",
                            "Clarification 58(e): 'The qualification should be satisfied based on the manufacturer/component supplier's experience, and therefore need not be experience of the Project Proponent itself.' "
                            + R(
                                "Residual: which group entity holds it. Envision to confirm in writing that Envision Energy's track record is available to and may be relied upon by the entity that signed the EOI letters, with any parent guarantee needed to make that reliance effective."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Manufacturer's Authorization Letter",
                            "Checklist item 58 marked Received; three EOI letters present; NO MAL in the package",
                            R("Envision to issue the MAL on company letterhead."),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Offered PCS track record",
                            "22 PCS reference projects listed, using ENPCS 2750, 3450, 3300 and 2500. The offered ENPCS2520 appears in none",
                            R(
                                "Envision to explain the ENPCS2520's relationship to the referenced family and identify any commissioned ENPCS2520 units with project, location and commissioning date. Clarification 58(c) accepts a manufacturer declaration on letterhead carrying product, installed quantity, project, location, commissioning date and manufacturer."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Reference contact details",
                            "Client contact column empty for every PCS and PPC row; workbook self-labelled '(part)'",
                            R(
                                "Envision to complete the contact column and issue the workbook in full."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Operating references",
                            "Four operator letters. Two named-grid projects report 98.2 % availability to 1 March 2024, with 0 h cell-fault, 36-43 h DC-system, 68-70 h PCS and 1 h EMS downtime",
                            "None of the four demonstrates grid-forming operation. "
                            + R(
                                "Envision to identify any grid-forming reference installation."
                            ),
                        ]
                    },
                ],
                "source": "21 August evidence dossier; clarification register item 58.",
            },
        }
    )

    # ── 14. Commercial ──────────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Commercial framework required from Envision",
            "intro": (
                "The Project Company's exposure under this ESA is unusually open, and the ESA cannot "
                "be amended after the Letter of Award (Volume I §7.1, confirmed by clarification 30). "
                "Whatever back-to-back support Envision provides must be agreed before submission."
            ),
            "table": {
                "columns": [
                    "ESA exposure",
                    "Established by",
                    "Back-to-back support required",
                ],
                "rows": [
                    {
                        "cells": [
                            "No aggregate cap on liquidated damages, per Contract Year or over the 15-year Term",
                            "Clarification 54",
                            R(
                                "Envision to confirm an aggregate liability position adequate for performance-caused losses, without excluding model or control failures."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "Capacity charge may be reduced to LKR 0 in a month missing 97 % availability, outside the monthly LD cap",
                            "Clarification 54",
                            R(
                                "Back-to-back availability warranty with response times, spares, remote diagnostics and OEM-caused LD indemnity."
                            ),
                        ],
                        "emphasis": True,
                    },
                    {
                        "cells": [
                            "RTE liquidated damages at 150 % of the peak-time 33 kV GP tariff on excess losses, assessed monthly with no reconciliation",
                            "Volume I §2.8(iii); clarifications 5 and 40",
                            R(
                                "RTE guarantee at the contractual meter, correction plan, test protocol and back-to-back loss compensation. No measurement tolerance is available."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "No termination compensation or buy-out for NSO default, political force majeure or prolonged natural force majeure",
                            "Clarification 52",
                            R(
                                "Envision to confirm supply and warranty continuity terms that survive a termination in which the Project Company recovers nothing."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Flat LKR capacity charge for 15 years with a single 85 % USD adjustment at ESA signing; P2 fixed and not moved to LC settlement",
                            "Clarification 16",
                            R(
                                "Price validity through award and ESA signature, defined FX basis, capped LTSA and spares escalation, transparent local/foreign split."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "No CCR adjustment or penalty-free withdrawal for tax or regulatory change after the Closing Date",
                            "Clarification 19",
                            R(
                                "Envision to hold pricing on that basis or state the assumptions it is conditioned on."
                            ),
                        ]
                    },
                    {
                        "cells": [
                            "Supplier substitution after award refused",
                            "Clarification 73(b)",
                            R(
                                "Envision to confirm supply-chain security for the exact nominated equipment for the full delivery window."
                            ),
                        ]
                    },
                ],
                "source": "NSO RFP Volumes I and III; clarification register items 5, 16, 19, 30, 40, 52, 54, 73.",
            },
        }
    )

    # ── 15. Bidder-side actions ─────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Bidder-side actions - not Envision's scope",
            "intro": (
                "Recorded here so nothing is lost between the two workstreams. These are the Project "
                "Proponent's, not Envision's."
            ),
            "points": [
                R(
                    "GRID INTERCONNECTION CONFIRMATION LETTER - most urgent. Addendum No. 01 items 02 "
                    "and 08 make it mandatory where Option 2 is selected under Volume II Section 11, "
                    "and a MAJOR DEVIATION under Volume I clause 6.3.1 if absent. Item 07 required it "
                    "to be requested from the Provincial Director of EDL at least 21 days before "
                    "closing - i.e. by 14 August 2026 - and EDL is not liable for delays. Confirm "
                    "immediately which Option is taken and whether the letter was requested."
                ),
                R(
                    "PCA3 registration. Addendum No. 01 item 10 adds failure to submit the "
                    "Certification of Registration under the Public Contract Act No. 3 of 1987 to the "
                    "grounds for disqualification."
                ),
                R(
                    "Submission arithmetic. A separate RFP purchase per proposal (clarification 46); "
                    "each proposal a complete and separate submission (clarification 70); LKR 600 "
                    "million financial resources per project, cumulative - LKR 1,200 million for two "
                    "(clarification 69); Proposal Security addressed to the CEO of NSO (clarification "
                    "41) and valid to 3 March 2027 (Addendum item 03)."
                ),
                R(
                    "Joint-venture structure. Clarification 60: any technical or manufacturing "
                    "partner that is a FORMAL JV member must meet 25 % of the LKR 600 million "
                    "regardless of its role. To avoid that, it must be structured as a manufacturer, "
                    "supplier, technical partner or subcontractor, not a JV member. FIN-1 to FIN-4 "
                    "are completed by each formal member."
                ),
                R(
                    "Shared interconnection. Clarifications 20 and 75 contradict each other - 20 "
                    "permits a common grid interconnection line for two projects at one GSS, 75 says "
                    "only one BESS project can connect to a single 33 kV feeder. The window to ask "
                    "closed on 25 August. Cost any two-project bid on the conservative reading "
                    "(separate feeders) and state the assumption in the bid."
                ),
                R(
                    "Capacity Charge Rate unit. Clarification 65 answers 'LKR/MW/month' and states "
                    "the proposed rate as Y LKR/MW/month, then writes the applicable-rate formula "
                    "0.15xY + (0.85xYxP2/P1) in LKR/MWh/month - a different unit in the same answer. "
                    "Quote in LKR/MW/month and complete the SSCL and VAT-18 % rows added by Addendum "
                    "item 13."
                ),
                R(
                    "Tracking workbook. Correct the Summary COUNTIF range from F2:F65 to F2:F69 (it "
                    "reports 38 Received against a true 41), restore missing items 50-53, set "
                    "statuses for items 55-57, and update item 36 against item 61."
                ),
            ],
        }
    )

    # ── 16. Basis register ──────────────────────────────────────────────────────────────
    s.append(
        {
            "heading": "Basis of statement - what is sourced and what is drafted",
            "intro": (
                "This section exists so that no reader has to infer the status of any statement in "
                "this draft from its tone."
            ),
            "table": {
                "columns": ["Colour", "Meaning", "How it may be used"],
                "rows": [
                    {
                        "cells": [
                            "Black",
                            "Sourced. Traceable to a document held in the corpus with its SHA-256 recorded in "
                            "MANIFEST.sha256 - an NSO tender volume, Addendum No. 01, Annex A, the clarification "
                            "register, an Envision design calculation, the filled Volume 2 GTP, or the 21 August "
                            "evidence dossier.",
                            "May be relied upon subject to the source-governs caveat on every page.",
                        ]
                    },
                    {
                        "cells": [
                            R("Red"),
                            R(
                                "DRAFTED GAP-FILL. Not found in any received Envision document. Written the way the "
                                "tender requires it to read, so Envision can confirm, correct or replace it."
                            ),
                            R(
                                "MUST NOT be submitted, quoted to NSO, or relied upon until Envision has adopted it "
                                "in writing. Red values are drafting placeholders that reflect what the tender "
                                "demands - they are NOT representations about the offered product and were not "
                                "supplied by Envision."
                            ),
                        ],
                        "emphasis": True,
                    },
                ],
            },
        }
    )

    s.append(
        {
            "heading": "Source register",
            "table": {
                "columns": ["Source", "Role", "SHA-256 (first 12)"],
                "rows": [
                    {
                        "cells": [
                            "NSO RFP Volume I",
                            "Controlling tender volume",
                            "fb61a4f827a0",
                        ]
                    },
                    {
                        "cells": [
                            "NSO RFP Volume II",
                            "Controlling tender volume",
                            "41644c207213",
                        ]
                    },
                    {
                        "cells": [
                            "NSO RFP Volume III (Model ESA)",
                            "Controlling tender volume",
                            "d3413e9d1a1b",
                        ]
                    },
                    {
                        "cells": [
                            "Addendum No. 01, 7 August 2026",
                            "Controlling amendment - overrides what it amends",
                            "2b99b1e507d8",
                        ]
                    },
                    {
                        "cells": [
                            "Annex A Functional and Performance Requirement",
                            "Controlling technical annex",
                            "be599073f597",
                        ]
                    },
                    {
                        "cells": [
                            "Clarification register, 76 items, 21 August 2026",
                            "Controlling clarifications (image-only scan; read from page images)",
                            "73fbaca1a7e7",
                        ]
                    },
                    {
                        "cells": [
                            "Envision design calculation 10 MW / 40 MWh, 29 July 2026",
                            "OEM evidence - superseded 5 August",
                            "7281d964654e",
                        ]
                    },
                    {
                        "cells": [
                            "Envision design calculation 11 MW / 44 MWh, 5 August 2026",
                            "OEM evidence - the offered configuration",
                            "0cf77ec5d761",
                        ]
                    },
                    {
                        "cells": [
                            "Envision functional-requirements checklist",
                            "Supplier declaration - not evidence",
                            "8236806c21f6",
                        ]
                    },
                    {
                        "cells": [
                            "Bidder evidence dossier, 21 August 2026",
                            "OEM evidence - held outside the repository, manifest only",
                            "not committed",
                        ]
                    },
                ],
                "source": "docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256",
            },
        }
    )

    return s


def build_doc(provenance: tuple[str, ...] = ()) -> dict:
    return {
        "title": "Technical Proposal - NSO 250 MW / 1000 MWh Standalone BESS",
        "banner": "DRAFT FOR ENVISION COMPLETION | RED = DRAFTED GAP-FILL, UNVERIFIED | TR/REP&PM/ICB/2026/001/C",
        "document_id": "DBAY-EPROP-DRAFT",
        "version": "v0.1 DRAFT",
        "issue_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": STATUS,
        "headline_caveat": HEADLINE,
        "disclaimer": DISCLAIMER,
        "section_caveat": SECTION_CAVEAT,
        "control": _control(),
        "control_section_number": 0,
        "first_section_number": 1,
        "sections": _sections(),
        "provenance_lines": provenance,
    }


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "envision_proposal_draft.pdf")
    # Second argument exports the same document model make_docx.js consumes, so the Word and PDF
    # issues are built from ONE source. Without this the Word chain has no producer and the two
    # formats can drift silently — which is exactly what happened while this lived outside the
    # repository. The red gap-fill sentinel is carried through verbatim; make_docx.js maps it to
    # the red run colour, and dropping it there would present drafted text as sourced.
    json_out = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    env = Environment(
        loader=FileSystemLoader("app/reports/dbpl/templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("dbpl_base.html.j2")

    def render(doc: dict) -> str:
        html = template.render(doc=doc)
        # The sentinel is non-HTML, so it survives autoescaping and can be swapped safely.
        return html.replace(_RO, '<span class="gf">').replace(_RC, "</span>")

    first = render_dbpl_pdf(render(build_doc()), extra_css=GAPFILL_CSS)
    substituted = first.substituted_fonts
    embedded = first.house_fonts_embedded
    provenance = (
        f"Rendered by the DutchBay Presentation Layer (WeasyPrint), Python {platform.python_version()}.",
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
        "Assembled only from the DutchBay NSO corpus. Red text is drafted gap-fill, not supplied "
        "by Envision, and is not a representation about the offered product.",
    )
    final_doc = build_doc(provenance)
    final = render_dbpl_pdf(render(final_doc), extra_css=GAPFILL_CSS)
    out.write_bytes(final.pdf)
    print(f"wrote {out} ({len(final.pdf):,} bytes)")

    if json_out is not None:
        # Exported WITHOUT the render provenance above: those lines describe how the PDF was
        # rasterised (PDF variant, font substitution) and are meaningless in a Word file, where
        # they would read as claims about a document they do not describe.
        word_doc = build_doc()
        json_out.write_text(
            json.dumps(word_doc, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        gapfills = json.dumps(word_doc, ensure_ascii=False).count(_RO)
        print(f"wrote {json_out} ({gapfills} gap-fill spans)")


if __name__ == "__main__":
    main()
