# Controlled Registers

Registers in this directory use stable identifiers, explicit enumerations, reciprocal evidence links, and deterministic builders. Blank status fields are not permitted in circulation candidates. A structurally valid working register is not Board/lender release approval.

## Active working successors

- `primary_source_register.v2.csv` and `.json`: 42 claim-level records with many-to-many finding links, hashed artefacts, source gaps, and explicit claim boundaries.
- `findings_register.v2.json`: 111 findings with atomic audited-commit code anchors, typed dependencies, completed reproduction links, confidence, canon impact, owner, limitations, and additive remediation evidence. P3-MCFX-03/P2-MC-SENS-02 record PR #1030 as merged/green while retaining independent review of the governed post-merge run; P2-MC-SENS-01 records PR #1031 as merged/green while retaining independent successor semantic QA; P3-EQ-04 records PR #1032 as merged/green while retaining independent review of the manifest-bound FX disclosure. P5-HDL-003 and P5-FIN-002 now cite completed governed reproduction `P5-REPRO-A15-001`: current deterministic canon unchanged, noncanonical project-IRR scale sensitivity confirmed, independent successor review still blocking, and no date-aware `xirr` defect asserted. Six audit-control rows record corrigendum v1.0.1 implementation complete while remaining `requires_correction` behind document-QA and final-synthesis gates.
- `architecture_pointer_adjudications.json`: the sole active 25-row overlay over the immutable architecture map.
- `architecture_pointer_dispositions.csv` and `.json`: generated full-population register for all 72 `RS-*` pointers, including examination coverage and typed validation dependencies.
- `architecture_examination_plan.v1.json`: immutable pre-execution plan for the 51
  `not_examined` and five `deferred` pointers. It freezes the historical claim, pinned
  current-main file-level scout seam, owner, dependency and planned negative control;
  the schema cannot carry a completed result.
- `history/architecture_pointer_dispositions.pre-architecture-examination-plan.20260824.0b9c6803.json`:
  byte-preserved 72-pointer source state used to create v1 (SHA-256
  `0b9c68039c24a4f23b2c6299b4189db6b6cabaffddf0cec628de5afc70ea96d8`).
  The v1 builder reads this frozen input, not the mutable active overlay.
- `architecture_examination_ledger.v1.json` and `.csv`: deterministic descendants of
  the 56-row plan and the 72-pointer register. Every v1 row is
  `pending_examination`/`not_assessed`, has no reviewer identity or result hash, and
  blocks Board/lender release. Completed examinations must use an additive result
  overlay or a new plan version; v1 must not be rewritten.
- `history/github_issue_1110.remediation_and_release_gates.20260824.9f7348f7.md`:
  byte-preserved source snapshot of the OPEN issue #1110 body at GitHub
  `updated_at=2026-08-24T11:29:43Z`. Its exact 5,371-byte body has SHA-256
  `9f7348f7a5c56f8aff45a5074e323d96abda418567f8cfd0eefb16f43855e0b9` and
  contains 23 unchecked checkboxes. The live issue remains authoritative for later
  state; this snapshot makes v1 portable and reproducible without a live GitHub call.
- `programme_gate_plan.v1.json`: immutable pre-execution execution plan for all 23
  issue #1110 gates. It adds 11 dependency-ordered stages, owner/reviewer-role
  separation, known prerequisite artifacts, evidence requirements, completion
  criteria, negative controls and limitations. It cannot carry a result, reviewer
  identity, completion state or closure authorization.
- `programme_gate_ledger.v1.json` and `.csv`: deterministic descendants of the
  frozen issue snapshot and programme plan. All 23 rows remain `pending`, source
  checkboxes remain `unchecked`, completion hashes and reviewer identities are null,
  `closure_authorized=false`, and every row blocks Board/lender release. P06
  (authenticated F5-02 evidence) and L03 (the evidence-dependent decision) are
  separate gates; L01 is the separate F5-01 rollback surface. Only a later additive
  completion overlay may record results.
- `../reproductions/reproduction_register.json`: completed, required-not-run, and unavailable reproduction controls. Only completed, output-hashed records may appear in `reproduction_refs`; planned or unavailable work belongs in typed validation dependencies.

The 22-row primary-source files, 107-row findings draft, historical source manifest, pre-normalization architecture overlay, pre-PR-#1030/pre-PR-#1031/pre-corrigendum-v1.0.1/pre-PR-#1032/pre-A15 111-row findings states, pre-A15 reproduction/architecture states, the local PR-#1037 candidate evidence, and corrigendum v1.0.0 are preserved as predecessors. They are not active successor inputs. Historical register states live under `history/`, are byte-preserved, and are explicitly superseded. The additive PR #1037 merged evidence validates the narrow empty-`debt` parity correction but deliberately leaves the underlying P2-F5-01 finding open.

## Controlled disposition vocabulary

Architecture and audit claims use only:

- `confirmed`
- `partially_confirmed`
- `refuted`
- `not_a_defect`
- `deferred`
- `not_examined`

Evidence support uses only:

- `supports`
- `partially_supports`
- `contradicts`
- `context_only`
- `unavailable`

Source class uses only:

- `standard`
- `official_guidance`
- `official_project_document`
- `academic_primary`
- `official_software_documentation`
- `official_source_code`
- `official_catalogue_record`
- `transaction_document`
- `repository_evidence`
- `analyst_judgment`

## Release boundary

Run `../scripts/validate_controlled_registers_v2.py` for structural, lineage, deterministic, and ingressed-remediation controls. Its result remains `release_status=HOLD`: corrigendum v1.0.1 is issued; PRs #1030/#1031/#1032 are merged/green; A15 is a completed governed same-agent reproduction with a separately blocking independent-review gate; and F5-01 parity correction PR #1037 is merged/green with post-merge pins. The canon-moving F5-01 caller binding/reconciliation, seven other P5 impact programmes, unavailable transaction evidence, remaining implementation dolphins, successor semantic QA, and synthesis regeneration remain open. F5-02 is not part of PR #1037.

The final synthesis may summarize the active controlled successors but must not introduce an unregistered material claim. F5-01 and F5-02 remain separate findings, specifications, changes, tests, reconciliations, commits, and pull requests.
