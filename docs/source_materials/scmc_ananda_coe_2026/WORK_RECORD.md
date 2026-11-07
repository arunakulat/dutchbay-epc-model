# SCMC / STEAM Hub work record

Recorded 7 November 2026 for issue #1554. The evidence cutoff for the programme content is the
5 August 2026 corrected pack, plus the 5 September 2026 cross-centre feedback.

The commercial figures, individuals and source terms are deliberately left out. See
[`README.md`](README.md) for the boundary.

## Current state

- **Governing document:** `SCMC_Complete_Programme_Pack_Corrected_v2.0.pdf` (90 pages, 5 August 2026,
  SHA-256 `34a79a63cced3dc96467c02abb4f90c24883d770aa3539c3a972e2bf71211ee4`).
- **Superseded:** `SCMC_Complete_Programme_Pack.pdf` (105 pages, SHA-256
  `eb176793afa8820a22d95facf75216a8b4eaed4f6f767235fadda39f1efc7f10`). Do not cite it for a conclusion
  without checking v2.0, because v2.0 reverses some of its findings.
- **Programme shape:** 360-minute Discovery, 90-hour Foundation, and 120 to 180-hour Advanced.
- **Built in facilitator format:** Discovery only, as eight 45-minute modules.
- **Not built:** the Foundation phase in the same detailed facilitator format. Its syllabus exists in
  the pack. The agreed next step is to build it on the Mallorca CFGS production-workflow base, and
  this has not been started.
- **Funding result:** provisional. The v2.0 base case shows a small deficit, not a surplus.

## What v2.0 changed

| Topic | Earlier position | v2.0 position |
|---|---|---|
| Funding | Small surplus | Small provisional deficit, with stress cases recomputed |
| Connectivity | Satellite residential plan as the base case | School fibre first, institutional plan as a sensitivity, because the residential plan is ineligible |
| Capacity | Mixed arithmetic | One controlled ledger |
| NVQ | Credit conversion to Level 4 | Conversion removed. NVQ 4 and SLQF 2 are comparable, not equal. Written TVEC mapping is an approval gate |
| National records | None found | Claim withdrawn. Relevant records surfaced |
| Drone sequence | CAASL first, then Ministry of Defence | Ministry of Defence clearance first for the cited route |
| Studio height | Stated as a standard | Expert design advice, not a binding standard |
| Apple licensing | Discontinuation and a 20-seat discount assumed | Both removed. A written seven-seat quote is required |

## Work completed

| Date | Work | Output |
|---|---|---|
| 20 Jul 2026 | Ingested the 12-document pack and reconciled three incompatible centre designs | Ingestion and evaluation paper |
| 20 Jul 2026 | Investment proposal and endowment plan | Proposal PDF and finance model scripts |
| 23–24 Jul 2026 | Evaluated committee feedback and wrote two committee responses | Throughput and infrastructure letters |
| 24 Jul 2026 | Deep research, second pass, saved step by step | Findings F01–F12 and synthesis |
| 24 Jul 2026 | Research and programme report with a syllabus for all three phases | 27-page report |
| 4 Aug 2026 | Discovery handbook, written for a teacher new to the subject | 21-page handbook |
| 4 Aug 2026 | Technical requirements annexure | 23-page annexure |
| 5 Aug 2026 | Bound the complete pack, 105 pages | Superseded by v2.0 |
| 5 Aug 2026 | Design critique, reference audit and corrected release | v2.0, 90 pages, PDF/UA-1 |
| 5 Sep 2026 | Ingested the COE building consultant's AV and ELV package and advised on the interface | Cross-centre feedback and paste-ready replies |
| 5 Sep 2026 | Issued that feedback as a DBPL PDF. This exposed a renderer crash, since fixed in #1235 and recorded in #1553 | 6-page DBPL PDF |

## Decisions that shape the work

- **Scope boundary between centres:** the venues stage events and the Media Centre records them. The
  venue packages add three tie-ins: an audio feed, camera positions, and data drops at control
  positions. Recording equipment stays out of the venue packages.
- **Capital restraint is the sustainability strategy:** each capital item creates a lasting
  replacement obligation, so the proposal favours a smaller founding phase and a larger endowment.
- **Later phases are earned from surplus, not gifted.**
- **Networking:** size for spare capacity and confirm power over Ethernet before ordering. Re-cabling
  a finished room is the expensive part.

## Open items

| Item | Owner | Note |
|---|---|---|
| Merge the private corpus | Project owner | `arunakulat/DutchBay_RAG#41`, held while `MERGE-01` is suspended. A squash merge means updating the pinned commit in `README.md` |
| Confirm which pack the Board holds | Project owner | The 5 September feedback cites page 37 of the 105-page pack. In v2.0 the same items are on page 35 |
| AV expectations of the remaining centres | COE | Requested on 5 September, not received in this record |
| Written TVEC mapping | COE | Approval gate before any qualification claim |
| Eligible connectivity quote and measured traffic | COE | Needed to firm up the funding result |
| Joint network drop-schedule walkthrough | COE and consultant | Settles the switch size |
| Foundation phase build | Project owner to confirm | Do not start without confirmation |

## Sessions that contributed

| Host | Session | Dates | Role |
|---|---|---|---|
| Claude Code | "STEAM Hub Foundation Program" (`local_e25a0508-e17a-443d-93e3-e50ce2db652b`) | 20 Jul–7 Nov 2026 | Primary. All work above except the 5 August review and v2.0 |
| Codex | `019fd034-e0ad-7f52-b6a5-00776faea626` | 5 Aug 2026 | Design critique, reference audit and v2.0 |
| Codex | `019fc272-9ef3-7a91-841d-17910b5b9dd1` | 2 Aug 2026 | Opens with the same prompts as the primary session. No SCMC file writes detected |
| Codex | Sessions rooted in the `Plant Green Force` folder | From 4 Nov 2026 | PGF work, not SCMC. Filed in the private corpus. See `../planet_green_force_2026/README.md` |

**Search coverage.** Searched: Claude Code transcripts, Codex sessions and local Cowork session
files, by keyword, by user prompt and by file writes. No other Claude Code or Codex session has an
SCMC prompt or an SCMC file write, and no Cowork file matched. **Not searchable from this environment:** claude.ai web chats and ChatGPT. A
ChatGPT thread is the origin of Volumes I to III, so that work is only partly represented here.

## Lessons for the next contributor

- `markitdown` in the governed venv lacks DOCX support. Use a standard-library extractor for `.docx`.
- CAD-exported drawings need page rendering and visual reading, because their text layers can be
  garbled.
- Save research as you go. An interrupted workflow can return nothing while its agent transcripts
  still hold the findings on disk.
- Keep a version pointer in any summary. Summaries written before v2.0 still state its reversed
  conclusions.
