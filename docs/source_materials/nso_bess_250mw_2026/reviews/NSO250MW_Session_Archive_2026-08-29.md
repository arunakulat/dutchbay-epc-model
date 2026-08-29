# NSO 250 MW BESS tender — session archive, 29 August 2026

Archival record for the working thread that ingressed the 27 August OEM supply tranche, read the
delivered dynamic models, and raised gaps A6 and A7. Closed on merge of
[#1181](https://github.com/arunakulat/dutchbay-epc-model/pull/1181) as `0e63f7a`.

This is a **workstream archive**, not a `PERSIST-01` successor. The
`docs/SESSION_HANDOVER_2026-08-2*.md` chain tracks the Dolphin / feasibility-contract workstream and
is unrelated to this one; nothing here changes its authority, and it should not be renumbered
against it.

- Tender: `TR/REP&PM/ICB/2026/001/C` — 250 MW / 1000 MWh standalone BESS from 10 MW / 40 MWh AC
  capacity projects, BOO, 15-year operational period
- **Closing date: 4 September 2026, 10.00 hrs.** The clarification window closed 25 August 2026
- OEM: Envision Energy / the supplying group entity

## 1. State at close

| | |
|---|---|
| `main` | `0e63f7a` |
| Corpus manifest | `MANIFEST.sha256` — 108 entries, all verifying |
| Supply manifest | `NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256` — 38 entries, all verifying |
| Gap register | 23 gaps: CRITICAL 7, HIGH 5, MEDIUM 7, LOW 2, INFORMATIONAL 2 |
| Critical path | A1, A2, A5, A6, A7 |
| Unverified findings | none |
| Register digest | `a334cba869ceb00b7bde2ecd0e8d9fad48c689fb33498f23d158d10880dc95e7` |

## 2. What is committed, and where

| Artifact | Path |
|---|---|
| Gap register (source of truth) | `../registers/build_gap_dossier_2026-08-27.py` |
| Internal dossier — names the bidder | `NSO250MW_Tender_Gap_Dossier_2026-08-27.pdf` |
| Advisory issue — bidder-neutral | `NSO250MW_Gap_Analysis_Advisory_Issue_2026-08-27.pdf` |
| Advisory issue renderer | `../registers/render_advisory_issue_2026-08-27.py` |
| Model reader (no PSCAD/PSS(R)E needed) | `../../../../scripts/analysis/extract_oem_dynamic_models.py` |
| Manifest hash refresher | `../../../../scripts/analysis/refresh_corpus_manifest.py` |
| Certificates (14) | `../oem/envision/compliance_evidence/certificates/` |
| Compiled model deliverables (11) | `../oem/envision/dynamic_models/` |

### Two issues of the same register

The register is rendered twice from one source, so the two documents cannot drift:

* the **internal** dossier names the bidding entity;
* the **advisory** issue is raised by *DutchBay / Icomunicamos Advisory Group*, for release to a
  bidder other than the one the register was raised for.

`render_advisory_issue_2026-08-27.py` imports the register unchanged and applies exactly three
changes — the raising label, the de-attribution of two statements that were true only of the
original recipient, and an added *Issue and reliance* section. It **fails loudly** if either
de-attributed passage moves, rather than silently emitting a document that misattributes a
clarification question. That guard has already fired once in anger.

Reproduced from the committed script on 29 August: 28 pages, identical page and character counts,
identical register digest, differing only in the render date in the running footer.

## 3. Findings that matter most before 4 September

**A7 — CRITICAL, critical path — the availability guarantee stops at year 2 of a 15-year
obligation.** The LTSA does offer Availability, RTE and Usable-capacity guarantees, but only
`Full Scope year 0-15` carries availability to year 15. Under the default `warranty 0-2` +
`year 3-15` split, availability is marked `-`, which the sheet's own legend defines as *not
included*, while RTE and usable capacity continue. Availability therefore lapses at year 2 while
gap A4's uncapped, unfloored 97 % exposure runs thirteen further years. Full Scope carries no
price, no guarantee level, no term, no response times, no LD indemnity and no signature; its BESS
tab is labelled `100225-Draft` and the workbook's other tab is a **wind turbine** service
catalogue.

**A6 — CRITICAL — the PCS cannot meet the Annex A overload ratings at site ambient.** 110 % for
10 minutes at 45 degrees C, 110 % continuous only at 40 degrees C, 120 % for 1 minute at
35 degrees C, against A.05.02(a)'s 110 % continuous and 120 % for at least 2 minutes. No
adjustability note attaches — these are thermal ratings. Clarification 64 sought exactly this
relief and was refused.

**B2 — the shipped model carries non-compliant frequency settings.** 47.5 Hz / 1800 s and
46.9 Hz / 0.04 s under-frequency; 51.5 / 1800 and 52.1 / 0.04 over-frequency, against Annex A
A.05.04's requirement for continuous operation across 47-52 Hz. Confirmed from three independent
sources. The vendor states the parameters are adjustable to the local grid code — but the model
submitted with the bid carries the non-compliant values.

## 4. Provenance notes worth carrying forward

* The PSCAD `.pscx` names its output `PCS_Model_GBR_240819` and its snapshot path references a UK
  3x45 project from August 2024 — the Sri Lanka EMT model is a rebadged GB project.
* The LTSA workbook's first tab is a wind-turbine service catalogue; the BESS tab is a draft
  appended to it.
* Compiled `.dll`/`.obj`/`.lib` yield metadata only. The control law is not recoverable and no
  attempt is made to recover it.

## 5. Publication position — a recorded reversal

The certification-body certificates and compiled binaries were previously manifest-only, and this
repository's own text said the binaries were *publish-never regardless of authorisation*. The
project owner directed, in writing and as project owner, that those restrictions be overridden
because the material forms part of the bid submitted to NSO, and that all of it — expressly
including personal data — be committed. **This repository is public**, so that is publication
rather than storage. The reversal is recorded in `../source_packages/README.md` rather than quietly
applied.

Personal data present, established by inspection rather than assumed: four individuals named in
professional capacity on the certificate faces, none with any contact detail — David Piecuch,
Thomas Wilson, Jiajun Zhang, Allen Hu.

## 6. Known limitations, stated rather than papered over

* **Two extract gaps.** `36_COVER_ENPCS2520_IEC_60068-2-30_78.pdf` produced no extract;
  `21_CERT_IEC_63056_2020_EN_62477-1_2022_RACK.pdf` extracted empty — an image-only scan that did
  not OCR. Both source PDFs are committed, so the gap is in the discovery aid, not the corpus.
* **Five sandbox-only test failures.** The watchdog tests in
  `tests/lint/test_cloud_audit_review_sandbox.py` introduced by #1165 fail in any container that
  cannot reap process groups (`transport probe process group could not be reaped`). They fail
  identically on pristine `main` and pass on GitHub runners, so CI will not warn anyone who hits
  this locally. Not a defect in this workstream; recorded because it will confuse the next person
  who runs the suite in Docker.
* **Neither manifest is covered by a test.** A stale or incomplete corpus manifest passes CI
  silently. Two such defects were found and repaired by hand in this thread; a test would have
  caught both.

## 7. Not archived here

The Envision technical proposal generator (`build_envision_proposal.py`, its Word renderer
`make_docx.js`, and the rendered v0.1-v0.3 drafts) was produced in this thread but is **not**
committed. It contains the bidder's own draft proposal text, which is a different disclosure
category from OEM documentation, and the tender had not closed at time of archival. It is
therefore lost with the working container unless separately preserved. Raise with the project
owner if the proposal needs to be reproducible.
