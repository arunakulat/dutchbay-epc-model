# Controlled Registers

Registers in this directory use stable identifiers, explicit enumerations, reciprocal evidence links, and deterministic builders. Blank status fields are not permitted in circulation candidates. A structurally valid working register is not Board/lender release approval.

## Active working successors

- `primary_source_register.v2.csv` and `.json`: 42 claim-level records with many-to-many finding links, hashed artefacts, source gaps, and explicit claim boundaries.
- `findings_register.v2.json`: 111 findings with atomic audited-commit code anchors, typed dependencies, completed reproduction links, confidence, canon impact, owner, limitations, and additive remediation evidence. P3-MCFX-03/P2-MC-SENS-02 record PR #1030 as merged/green while retaining independent review of the governed post-merge run; P2-MC-SENS-01 records PR #1031 as merged/green while retaining independent successor semantic QA; P3-EQ-04 records PR #1032 as merged/green while retaining independent review of the manifest-bound FX disclosure. P5-HDL-003 and P5-FIN-002 now cite completed governed reproduction `P5-REPRO-A15-001`: current deterministic canon unchanged, noncanonical project-IRR scale sensitivity confirmed, independent successor review still blocking, and no date-aware `xirr` defect asserted. Six audit-control rows record corrigendum v1.0.1 implementation complete while remaining `requires_correction` behind document-QA and final-synthesis gates.
- `architecture_pointer_adjudications.json`: the sole active 25-row overlay over the immutable architecture map.
- `architecture_pointer_dispositions.csv` and `.json`: generated full-population register for all 72 `RS-*` pointers, including examination coverage and typed validation dependencies.
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
