# DutchBay controlled-register semantic closure check

**Document ID:** `DB-AUD-REMED-REG-SEM-CLOSE-2026-08-16-01`
**Cutoff:** `2026-08-16T11:11:36+05:30`
**Repository basis:** `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Review basis:** Primary-agent closure check against the independently prepared B1-B14 patch map; this is not a substitute for a new independent refuter pass.
**Controlled-register result:** **PASS**
**Programme release:** **HOLD**

## Scope and result

This check compares the active v2 source, reproduction, findings, and architecture controls against every required transformation in `qa/CONTROLLED_REGISTERS_EXACT_PATCH_MAP.md` (SHA-256 `979d2e42076f7ae3a7e09805e9258b47ae6437b7d17324b93297db6e20655787`). It verifies claim boundaries and control semantics in addition to schema, count, path, and hash validity.

The active successors now implement all B1-B14 register migrations. During this pass, B1 rejected the residual use of raw scratch scripts and `required_not_run` work IDs as architecture `reproduction_refs`. Those scripts are now documentary `evidence_refs`; ten planned architecture runs are typed, blocking validation dependencies linked reciprocally to the reproduction registry; and RS-A1 no longer claims `independent_reproduction` without a retained, hashed output.

The same pass made PSR-0005's missing DutchBay transaction evidence explicit as `transaction_evidence_status=unavailable`, added semantic validation of both IEC 61400-15-2 negative queries and the IEC 61400-15-1 positive control, and updated the controlled-register README from a stale planned-state description.

## B1-B14 closure matrix

| Control | Status | Closure evidence |
|---|---|---|
| B1 reproduction status boundary | PASS | 32 registry rows: 15 completed, 12 required-not-run, five unavailable. Findings cite only completed hash-resolving outputs. Architecture has zero unregistered/bare reproduction refs and ten typed pending validation dependencies. |
| B2 P3 refuter ingress and atomicity | PASS | 13 MC/FX/equity claim IDs retained; P3-MCFX-07/08 and P3-EQ-04/05 are separate; no EVAL-10 duplicate; refuter hash pinned. |
| B3 source-class and many-to-many schema | PASS | 42 v2 PSR rows; `finding_ids` arrays round-trip identically between CSV and JSON; all IDs resolve reciprocally; controlled source classes include `official_catalogue_record`. |
| B4 frozen evidence or narrow exception | PASS | 92 hashed artefact links; PSR-0009 is the sole typed analyst-synthesis exception over six hashed supporting records; PSR-0011 preserves the exact audited-commit scenario-tree command and snapshot. |
| B5 MEASNET/transaction boundary | PASS | PSR-0005 remains `context_only`, explicitly records transaction evidence as unavailable, and does not convert MEASNET deviation treatment into a DutchBay condition precedent. |
| B6 IEC catalogue control | PASS | Query log plus both zero-result responses and the 15-1 positive control resolve and hash; request bodies differ on `validOnly`; parsed totals are 0/0/0, 0/0/0, and one positive 15-1 record. |
| B7 P5 claim-level sources | PASS | All 18 P5 rows use exact PSR mappings or an explicit source/transaction gap; headline rows are document reconciliation; no generic PSR evidence link or fake cross-finding dependency remains. |
| B8 P2 population recomputation | PASS | Six finder/refuter pairs produce 29 unique candidates, 14/11/1/3 dispositions, 25 live and four closed; every controlled P2 disposition maps to the parsed verdict. |
| B9 global closure semantics | PASS | Only P2-F1-04, P2-F1-05, P2-F3-03, and P2-F4-03 are closed; none carries a blocking implementation, validation, or transaction-evidence dependency. P4-DC-5 remains deferred. |
| B10 authoritative architecture overlay | PASS | One active overlay, 25 explicit items, byte-preserved superseded predecessor, deterministic 72-row CSV/JSON rebuild. |
| B11 atomic anchors and dependencies | PASS | 299 audited-commit/path/line anchors and 175 typed finding dependencies resolve; architecture adds ten typed validation dependencies. |
| B12 P2 authorization wording | PASS | P2-F1-01 and P2-F2-04 exact post-refuter title, canon-impact, and root-cause boundaries are pinned. |
| B13 mixed severity provenance | PASS | P2-F4-04 preserves `Low/Medium`, controls it to `low`, and retains explicit policy and rationale. |
| B14 examination coverage | PASS | All 72 pointers are registered; only 21 have substantive dispositions; 51 (70.8%) remain not examined; RS-B9, RS-D12, RS-E13, and RS-F10 remain explicitly not examined. |

## Controlled snapshot

- `registers/primary_source_register.v2.json`: SHA-256 `4c8cc05648abd31f5123c80de09a65b60f60bb57cb12e8ed6fad309498a6df96`
- `registers/primary_source_register.v2.csv`: SHA-256 `eb40b182debefb45a0492d5eb0052f035b972204f99336a5302ba2d5d3e2ab8d`
- `reproductions/reproduction_register.json`: SHA-256 `7f57bffc5ccab50f01e0f747376a404fab525125264f2b997b6814bc41fdb3f5`
- `registers/architecture_pointer_adjudications.json`: SHA-256 `bcf6332eeaea8e2151fd1ea830ab5ddaba8aae457395a8773310bcfa876d7e40`
- `registers/architecture_pointer_dispositions.json`: SHA-256 `0c746f34cd2aaa1018328bd2e0f60b1aee522153a3ef4f91cb9109a14027f946`
- `registers/architecture_pointer_dispositions.csv`: SHA-256 `df265b29fce55f5f9bb4aa84d5dfbe37af1207535a7ecd60c5b551546a57419e`
- `registers/findings_register.v2.json`: SHA-256 `da6048d0d4505d6b72e6664c3c62db9a5426bdc71d786448b0b25ff8b34bcf66`
- `scripts/validate_controlled_registers_v2.py`: SHA-256 `bebf0130849868cc7643008b25df978949e5886b19604c95fe44cbdc6ccf1610`

## Why release remains HOLD

This closure applies only to the B1-B14 controlled-register migrations. It does not claim that the underlying project is remediated or that every architecture pointer was examined.

Release remains blocked by:

- 12 required-not-run reproductions;
- unavailable DutchBay facility/intercreditor, lender, independent-engineer, resource-assessment, and other transaction evidence where expressly recorded;
- 51 of 72 architecture pointers not examined, including four explicit overlay rows;
- P4's retained single-pass limitation and the deferred P4-DC-5 owner/refuter decision;
- open implementation, validation, and monitoring dependencies across the 111 findings;
- separate F5-01 and F5-02 code/canon programmes;
- protected PR, CI, merge, and post-merge verification for every code dolphin; and
- regeneration and review of the corrigendum and Board/lender synthesis only after the preceding gates close.

No original audit file, historical overlay, historical manifest, repository model code, canon baseline, or Board/lender synthesis was changed by this register-closure check.
