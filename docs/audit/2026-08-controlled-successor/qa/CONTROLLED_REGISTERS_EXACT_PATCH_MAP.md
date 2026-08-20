# DutchBay Audit Remediation — Exact Controlled-Registers Patch Map

**Document ID:** `DB-AUD-REMED-QA-PATCH-MAP-2026-08-12`
**Review posture:** Independent control/refuter pass; controlled registers and repository remain unedited by this reviewer.
**Repository basis:** `arunakulat/dutchbay-epc-model@7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Control basis:** `qa/CONTROLLED_REGISTERS_QA_CHECKPOINT.md`, SHA-256 `e0484670a765dcdb20eb7992a1d009feb55112d80608efced636f7f6be50ab2e`
**New refuter basis:** `refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md`, SHA-256 `2e150dc6b1f949418236256057b3e291f80d7c466873d436a15db37523631685`
**Disposition:** **HOLD / NEEDS REVISION.** Apply the dolphins below in order, regenerate derived artefacts after their controlling inputs change, and rerun semantic QA before Board/lender synthesis.

## 1. What the saved P3 refuter resolves — and what remains

The persisted P3 refuter resolves the **evidentiary part** of checkpoint blockers B2 and B9 for the assigned MC/FX/equity-reporting claims:

- the alleged canonical 100,000-trial finance-MC run is refuted;
- MCFX-01, MCFX-02, MCFX-05, MCFX-06, EQ-01, and EQ-03 are partially confirmed with narrowed scope;
- MCFX-03, MCFX-04, and EQ-02 are confirmed with corrected scope; and
- two additional reporting defects and one separate wind-adapter defect were independently reproduced.

That evidence is **not yet ingressed**. The controlled findings register still contains the nine pre-refuter P3 rows and no atomic rows for the false 100,000-trial assertion, list-schema adapter failure, unsupported CBSL/IMF report wording, or contradictory verdict path. Therefore B2 is no longer “refuter not run”; it is now “completed refuter not incorporated.” P3-MCFX-06 and P3-EQ-01 are no longer defensible as `not_a_defect` / `closed`, but P4-DC-5 remains an independent residual closure blocker.

The current live checkpoint sentence at `CHECKPOINT_2026-08-12T103431+0530.md:75` correctly retains `3/10` only as a judgmental credit conclusion, withdraws the false `2/10` arithmetic-average label, and states the simple mean as `4.5/10`. No score-direction patch remains for that live file.

## 2. Ordered patch sequence

Apply these as separate dolphins. A later dolphin must not be used to conceal a failure in an earlier one.

1. B1 — create the reproduction registry and classify every existing reference.
2. B2 — ingress the completed P3 refuter, split compound findings, and recompute findings metadata.
3. B3–B6 — normalize the primary-source schema, claim boundaries, hashes, and IEC multi-artefact query evidence.
4. B7 — replace generic P5 source claims with claim-level mappings or honest source gaps.
5. B8 — make EVAL-09 independently recomputable from all finder/refuter files.
6. B9 — apply global closure/dependency semantics, including P4-DC-5.
7. B10 — retire the stale architecture overlay and establish one authoritative generator input.
8. B11 — atomize code anchors and dependencies.
9. B12–B13 — repair the two remaining P2 display claims and preserve severity provenance.
10. B14 — encode and disclose architecture examination coverage.
11. Strengthen the permanent validator in the same order as the data/schema migrations.
12. Generate a new versioned evidence manifest, rerun the validator and semantic QA, then regenerate the Board/lender synthesis.

## 3. Exact blocker-by-blocker patch map

### B1 — Separate completed reproductions from planned, unavailable, and documentary evidence

**Controlling files**

- add `reproductions/reproduction_register.json` (CSV projection optional);
- update `registers/findings_register.draft.json`;
- update `registers/architecture_pointer_adjudications.json` and regenerate both disposition outputs;
- update `registers/README.md`; and
- update `scripts/validate_controlled_registers.py`.

**Required reproduction schema**

Each reproduction record must contain:

```json
{
  "reproduction_id": "P3-REPRO-FX-001",
  "status": "completed",
  "repository_commit": "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8",
  "interpreter_or_tool": "...",
  "command": "...",
  "seed": 42,
  "input_refs": [],
  "output_path": "...",
  "output_sha256": "...",
  "finding_ids": [],
  "pointer_ids": [],
  "result": "...",
  "limitations": "...",
  "verification_level": "independent_reproduction"
}
```

Controlled `status` vocabulary: `completed`, `required_not_run`, `unavailable`, `superseded`, `not_applicable`.

**Finding-reference transformations**

- P2 unavailable scratch references must become registry rows with `status=unavailable`, while the durable finder/refuter JSON remains in `evidence_refs`:
  - P2-F1-01, P2-F1-03, P2-F1-05;
  - P2-F2-01 through P2-F2-07.
- Normalize the bare completed covenant filenames to stable completed IDs:
  - P3-COV-02, P3-COV-03, P3-COV-04, P3-COV-05, P3-COV-07;
  - files: `canonical_covenant_reproduction.json`, `canonical_covenant_fee_and_reserve_reproduction.json`, and `covenant_config_consumer_trace.json`.
- All `P5-REPRO-*` values currently present on P5-HDL-003, P5-MC-001/002/003, P5-SA-001/002, P5-RISK-001, P5-WIND-001/002/003, and P5-FIN-001/002/004 must be registry rows with `status=required_not_run`, not completed `reproduction_refs`.
- Add completed machine-readable P3 records for the refuter commands/results:
  - `P3-REPRO-MC-ROUTING-001` — caller/config routing and absence of a 100,000-trial finance pack;
  - `P3-REPRO-FX-001` — seed-42, 256-trial uniform/calibrated comparison;
  - `P3-REPRO-BREACH-001` — 64/128/256 bare versus tolerant breach counts;
  - `P3-REPRO-CVAR-001` — deterministic 20/100/101 VaR/CVaR comparison;
  - `P3-REPRO-WIND-AEP-001` — canonical list-schema adapter failure;
  - `P3-REPRO-CONV-001` — 20/30-trial convergence metadata boundary;
  - `P3-REPRO-REPORT-001` — canonical report/verdict and rendered wording;
  - `P3-REPRO-VERDICT-001` — synthetic positive-equity-NPV/negative-equity-IRR verdict probe; and
  - `P3-REPRO-BRIDGE-001` — reconciled project-to-equity IRR bridge.

**Architecture-reference transformations**

- Planned P5 work IDs on RS-A4, RS-A14, RS-A15, RS-C1, RS-C2, RS-C8, and RS-D4 resolve through the reproduction registry and remain `required_not_run` until outputs exist.
- `wind-refuter:*` labels on RS-D1, RS-D3, and RS-D9 are documentary refuter anchors, not executable reproductions. Move them to typed `evidence_refs` pointing to exact sections of `refuters/01_WIND_STANDARDS_REFUTER.md`, or create completed reproduction records only where an actual command/output is preserved.
- P4 work labels on RS-F4 and RS-F9 (`P4-F1-CI-GATE-RUNS`, `P4-CFG-1-SCHEMA-GUARD`, `P4-CFG-2-YAML-SAFE-LOAD`) must be `required_not_run` validation dependencies unless their exact outputs are archived and hashed.

**Validator invariant**

- Every `reproduction_ref` must resolve to a registry row whose status is `completed` and whose output exists and matches its SHA-256.
- `required_not_run` and `unavailable` IDs are permitted only in typed dependencies, never as proof of completed verification.
- A finding/pointer using `verification_level=independent_reproduction` must have at least one completed reproduction linked to that same ID.
- Bare filenames, `unarchived_refuter_scratch:*`, `wind-refuter:*`, and unknown work IDs fail validation.

**Proof / positive control**

- zero unresolved reproduction references;
- all completed output hashes match;
- P2 scratch unavailability remains explicit rather than silently dropped; and
- no planned P5 programme is counted as executed evidence.

### B2 — Ingress the completed P3 refuter and split atomic defects

**Controlling files**

- `registers/findings_register.draft.json`;
- `registers/primary_source_register.csv` and `.json` for MCFX-02 source links;
- `reproductions/reproduction_register.json`; and
- `scripts/validate_controlled_registers.py`.

For all nine existing rows, add `refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md` with the claim-specific line span to `evidence_refs`, replace compound string anchors under B11, link completed P3 reproductions under B1, set `confidence=high`, and use these exact controlled outcomes:

| Finding | Severity | Disposition | Status | Verification | Required corrected-claim boundary | Required dependency wording |
|---|---|---|---|---|---|---|
| P3-MCFX-01 | `high` (from `critical`) | `partially_confirmed` | `open` | `independent_reproduction` | Canon uses uniform `[300,367]`; no committed `fx_calibrated`; the available feature is a one-year two-regime spot mixture plus constant drift, not a 20-year regime/path model; the 256-trial widening/skew is illustrative, not production validation. | “Calibration validation; approved horizon, tail and truncation policy; governed MC configuration; independent run review; lender-facing disclosure.” |
| P3-MCFX-02 | `high` | `partially_confirmed` (from `deferred`) | `deferred` | `source_and_code_refuter` | Six live joint drivers and the listed omissions are confirmed; no universal rule requires every material risk to be one MC dimension; disclose whether each risk is MC, deterministic stress, event-tree, contractual, or qualitative treatment. | “Approved risk taxonomy; source-backed distributions/correlations; live tranche-rate paths; construction-delay timing model; offtaker default/recovery mechanism; validation tests.” |
| P3-MCFX-03 | `high` | `confirmed` | `open` | `independent_reproduction` | Bare `< floor` counting is wrong; seed-42 overstatement is 12.5 pp at 64/128 and 12.890625 pp at 256; no 100,000-trial impact was evidenced; other percentile intervals are not invalidated. | “Route through the shared tolerance-aware covenant primitive; exact point/CI regressions; regenerate governed run metadata.” |
| P3-MCFX-04 | `medium` | `confirmed` (from `partially_confirmed`) | `open` | `independent_reproduction` | Two VaR/ES definitions disagree on deterministic arrays; lean CASPER blocks omit CVaR, but async and capital-risk surfaces expose a definition; do not claim universal surface absence. | “Approved ES convention; golden vectors including ties/floors/mass points; serializer decision; versioned contract review.” |
| P3-MCFX-05 | `medium` | `partially_confirmed` | `open` | `source_and_code_refuter` | Keep this row solely about the unattributed/ambiguous 10% Weibull knob: it is not the live finance-MC driver and no executed canonical A/k-band impact can be inferred. Move adapter failure to P3-MCFX-08. | “Source-approved EYA uncertainty budget; separate wind/finance simulation schemas; actual governed wind-AEP run manifest before use.” |
| P3-MCFX-06 | `low` | `partially_confirmed` (from `not_a_defect`) | `requires_correction` (from `closed`) | `independent_reproduction` | Successful runs attach keys and populate per metric at at least 30 finite trials; diagnostics quantify approximate error but do not certify sufficiency; the breach subblock is wrong; “above typical” is unsupported. | “User-approved precision gates by statistic/use case; corrected breach counting; acceptance tests on actual governed runs.” |
| P3-EQ-01 | `medium` (from `low`) | `partially_confirmed` (from `not_a_defect`) | `requires_correction` (from `closed`) | `independent_reproduction` | Limit positive assurance to the reproduced canonical HTML/PDF, full-finance API, workbook and IC surfaces; they are correctly value-destructive. Repository-wide absence claims are false. Move the two atomic defects to EQ-04/EQ-05. | “Inventory decision versus analytical surfaces; bound all positive assurance to named reproduced outputs.” |
| P3-EQ-02 | `low` | `confirmed` (from `partially_confirmed`) | `open` | `independent_code_refuter` (add vocabulary) | At least three production info logs omit equity IRR; returned objects retain it; this is observability inconsistency, not a finance-output defect. | “One canonical KPI-summary formatter and regression tests for all three log sites.” |
| P3-EQ-03 | `medium` | `partially_confirmed` | `open` | `independent_reproduction` | The report already has a reconciled current-state IRR bridge; the dated ten-step history remains comment-only; “roughly half” is not a controlled causal attribution. | “Structured rebaseline register; retained pre/post hashes; approved one-factor-plus-interaction or alternative attribution method; report projection.” |

**Add four atomic rows**

1. `P3-MCFX-07`
   - title: `Claimed canonical 100,000-trial finance-MC run is not evidenced`
   - source phase: `P3_MC_FX`
   - severity/disposition/status/confidence: `high` / `refuted` / `requires_correction` / `high`
   - verification: `source_and_code_refuter`
   - corrected claim: use the exact boundary at refuter lines 61–63: the 100,000 value belongs to the legacy wind-AEP path; finance callers request 1,000–20,000 by current defaults/policy; no executed 100,000-trial finance pack exists; sufficiency requires declared tolerances and an actual run manifest.
   - canon impact: `level=none`, `direction=none`; deterministic KPIs unchanged, but the audit’s stochastic-evidence characterization is invalid.
   - dependency: “Governed finance-MC run configuration; declared mean/percentile/breach/ES precision tolerances; actual effective-`n_trials` manifest; retained risk pack.”

2. `P3-MCFX-08`
   - title: `Wind-AEP adapter cannot consume the canonical list-form MC parameter schema`
   - source phase: `P3_MC_FX`
   - severity/disposition/status/confidence: `high` / `confirmed` / `open` / `high`
   - verification: `independent_reproduction`
   - corrected claim: the wind adapter expects a mapping while the canonical finance config correctly uses a list; the adapter fails before wind-AEP simulation with `AttributeError: 'list' object has no attribute 'get'`; no 100,000-scenario wind sidecar is evidenced.
   - canon impact: `level=confirmed`, `direction=none_deterministic`; deterministic finance KPIs unchanged, current optional wind-AEP execution is broken.
   - dependency: “Split wind-AEP and finance-MC schemas; add a canonical-config adapter regression; emit a governed wind-AEP run manifest.”

3. `P3-EQ-04`
   - title: `Canonical report falsely attributes FX stress to CBSL/IMF projections`
   - source phase: `P3_EQUITY_DISCLOSURE`
   - severity/disposition/status/confidence: `high` / `confirmed` / `requires_correction` / `high`
   - verification: `independent_reproduction`
   - corrected claim: the actual canonical report contains the CBSL/IMF sentence, while the run uses BIS-derived deterministic depreciation plus an authored uniform MC spot band and no IMF projection input was found.
   - canon impact: `level=confirmed`, `direction=none_numeric`; current lender narrative is false/misattributed although the KPI vector is unchanged.
   - dependency: “Generate methodology wording from the governed run manifest; replace the static default; add a report test proving source/method consistency.”

4. `P3-EQ-05`
   - title: `Positive equity NPV can yield a Bankable headline despite negative equity IRR`
   - source phase: `P3_EQUITY_DISCLOSURE`
   - severity/disposition/status/confidence: `medium` / `confirmed` / `open` / `high`
   - verification: `independent_reproduction`
   - corrected claim: a type-valid synthetic positive-equity-NPV/negative-equity-IRR payload produces a Bankable headline with a negative-IRR note; this proves a latent consistency defect, not a defect in the current canonical output.
   - canon impact: `level=potential`, `direction=latent_reporting`; current canonical headline remains correctly value-destructive.
   - dependency: “Approve an IRR/NPV consistency policy; fail or downgrade contradictory return signals; add contradictory-payload regressions.”

**Post-B2/B9 target findings totals**

These are the exact counts after the four atomic additions and the recommended P4-DC-5 deferral in B9:

- record count: **111**;
- phase: EVAL 9, P2 29, P3 covenants 8, P3 equity/disclosure 5, P3 MC/FX 8, P3 wind 7, P4 27, P5 18;
- disposition: confirmed 32, partially confirmed 51, refuted 10, not a defect 3, deferred 15;
- status: open 70, requires correction 21, deferred 16, closed 4;
- severity: critical 4, high 36, medium 40, low 30, none 1.

**Validator invariant / positive control**

- pin the expected IDs and recompute all metadata from rows rather than accepting authored counts;
- require P3-MCFX-07/08 and P3-EQ-04/05;
- reject the old disposition/status combinations for MCFX-06 and EQ-01;
- require the P3 refuter hash and claim-level evidence anchors; and
- require the reproduction records listed above before permitting `independent_reproduction`.

### B3 — Normalize source classes and make claim-to-finding links many-to-many

**Controlling files:** both PSR files, `registers/README.md`, `scripts/build_primary_source_register.py`, and the validator.

**Schema migration**

- bump the PSR schema;
- replace singular `finding_id` with `finding_ids` (JSON array in CSV, array in JSON) for every row;
- declare and enforce this `source_class` vocabulary: `standard`, `official_guidance`, `official_project_document`, `academic_primary`, `official_software_documentation`, `official_source_code`, `official_catalogue_record`, `transaction_document`, `repository_evidence`, `analyst_judgment`.

**Exact row changes**

- PSR-0012: `source_class` from `transaction_evidence_status` to `repository_evidence`; retain `evidence_role=transaction_evidence_status` and the limitation that it is a mutable internal status snapshot, not lender evidence.
- PSR-0015: `source_class` from `catalogue_status` to `official_catalogue_record`; retain `evidence_role=catalogue_status`; replace unresolved `P5C-IEC-STATUS` with `finding_ids=["P3-G3","P5-WIND-001","P5-WIND-002"]`.
- Every other row: transform the existing non-empty singular ID into a one-element array without changing its claim or disposition.

**Validator invariant / positive control**

- every source class and evidence role must be in its declared vocabulary;
- every value in `finding_ids` must resolve to the current findings register;
- CSV and JSON arrays must round-trip identically; and
- no unresolved `P5C-IEC-STATUS` token remains.

### B4 — Require frozen claim evidence or an explicit, narrow exception

**Exact row changes**

- PSR-0009:
  - change `source_class` to `analyst_judgment`;
  - add `supporting_record_ids=["PSR-0006","PSR-0007","PSR-0008","PSR-0016","PSR-0017","PSR-0018"]`;
  - add `archive_exception_reason="Analyst synthesis over the listed independently archived official records; no separate source document exists."`;
  - retain `evidence_status=contradicts` and the boundary that no universal DutchBay covenant band is established.
- PSR-0011:
  - archive the exact output of `git ls-tree -r --name-only 7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8 -- scenarios` under `sources/original/`;
  - record its command, commit, filename, SHA-256, and access timestamp;
  - retain the 29 top-level YAML / 5 top-level JSON / 39 nested YAML-or-JSON distinction and the non-runnable-artefact limitation.

**Validator invariant**

- each PSR row must have at least one hashed evidence artefact, except `source_class=analyst_judgment` with non-empty `supporting_record_ids` and an approved `archive_exception_reason`;
- every supporting record resolves and itself passes hash validation;
- the source manifest must equal the complete controlled `sources/original` plus `sources/converted` set, not merely contain valid listed entries.

**Positive control:** PSR-0009 remains explicitly analyst synthesis; PSR-0011 becomes reproducible at the audited commit; no missing hash is mistaken for primary evidence.

### B5 — Correct the MEASNET measurement-versus-condition-precedent boundary

**Affected row:** PSR-0005.

**Exact changes**

- set `evidence_status=context_only`;
- preserve the transaction-CP claim text as the proposition being tested, but state in `paraphrased_support` that MEASNET supports only the measurement-procedure/deviation basis;
- add `transaction_evidence_status=unavailable`;
- use this limitation: “MEASNET does not prescribe DutchBay loan conditions, make a deviation legally unwaivable, or establish a financing condition precedent. That classification requires lender, independent-engineer, or executed transaction evidence.”

PSR-0001 through PSR-0003 continue to support the 12-month/on-site/deviation facts. Do not convert PSR-0005 into support for the CP claim.

**Validator invariant:** a row cannot use `supports` or `partially_supports` when its limitations expressly say the cited source does not establish the claim’s normative/transaction proposition.

**Positive control:** the standard fact and transaction-credit judgment remain separate; P3-G1 may recommend a pre-financing action as analyst judgment, but cannot attribute it to MEASNET as an unwaivable rule.

### B6 — Link the complete IEC catalogue query, including its positive control

**Affected row/file:** PSR-0015 and `sources/IEC_CATALOGUE_QUERY_LOG.json`.

Add an `evidence_artifacts` array to PSR-0015 containing all four controlled items:

- query log: SHA-256 `6a7b24b58e952f684267ed21b46470951b11a28cdcf281850175ded70ab602dc`;
- `IEC_catalogue_61400-15-2_valid.json`: `9e324b99e9607a87569551356e1825ca631d5200337a12cad7bd882e93f92058`;
- `IEC_catalogue_61400-15-2_all.json`: the same `9e324b99e9607a87569551356e1825ca631d5200337a12cad7bd882e93f92058` (byte-identical response to a distinct recorded request); and
- `IEC_catalogue_61400-15-1_positive_control.json`: `16312898bb0ed8027bcb8835790922387530d9ff98e6321cf92525a1fcd6a728`.

Each element must record role, request label/body reference, path, and hash. The conclusion remains limited to absence from the public catalogue at the cutoff; it does not disprove an unpublished committee draft.

**Validator invariant / positive control:** all artefacts resolve and hash; the two negative request bodies differ on `validOnly`; both zero-result counts are parsed; the same API/request shape returns the published 15-1 record as a positive control.

### B7 — Replace generic P5 source claims with exact claim-level support or an honest gap

**Affected rows:** all 18 P5 findings and their generic `primary_source_register.csv` evidence reference.

The generic PSR-file reference must be replaced by exact `#PSR-nnnn` links. Create and archive additional source records only from exact papers/docs actually obtained, with version/page/section/access/hash. Do not retain `source_and_code_refuter` merely because a bibliography name appears in the immutable audit.

| P5 finding(s) | Required evidence mapping / verification treatment |
|---|---|
| P5-HDL-001/002/003 | These are cross-document synthesis conclusions. Use `document_reconciliation` or add `independent_refuter_synthesis`; do not imply direct primary-source proof. HDL-003’s impact programme remains `required_not_run`. |
| P5-MC-001 | Archive/map Iman–Conover and McKay–Beckman–Conover primary material if available. Until then use `independent_code_refuter` plus explicit `source_gap`; do not call it primary-source verified. |
| P5-MC-002 | Map exact SciPy Sobol implementation/docs at the locked version and the specific Owen source used for the comparative claim. Otherwise narrow to locked-library code conformance. |
| P5-MC-003 | Add an exact primary dependence/tail source and distinguish mathematical zero-tail-dependence from transaction appropriateness; the latter remains deferred owner judgment. |
| P5-SA-001/002 | Map SALib 1.5.2 source/docs plus the exact Saltelli/Morris/Pianosi primary sources actually used. Sample sufficiency remains deferred until registered reproductions complete. |
| P5-RISK-001 | Map Rockafellar–Uryasev or another explicit expected-shortfall primary definition, exact section/page; keep deterministic reproduction separate. |
| P5-RISK-002 | Obtain an official lender/energy-yield percentile convention source or use `independent_code_refuter` and state the external convention gap. |
| P5-WIND-001/002/003 | Map Lee & Fields, MEASNET PSR-0001/0002/0003, IEC public-scope PSR-0004, and catalogue-status PSR-0015 only to the claims they actually support. Do not cite a final IEC 61400-15-2 standard. |
| P5-FIN-001 | Record `transaction_evidence_status=unavailable`; facility/intercreditor terms are not replaced by generic guidance. |
| P5-FIN-002 | Map official SciPy bisection documentation/source plus the P2 numeric reproduction; do not use generic DFI material. |
| P5-FIN-003 | Map PSR-0019 exactly; retain the limitation that the high-level DSCR identity is not transaction-complete. |
| P5-FIN-004 | Map PSR-0020 and PSR-0021 exactly; retain transaction-specific loan-life/bridge/rate/date/DSRA limitations. |
| P5-COV-001 | Use `document_reconciliation` / scope-map evidence, not `source_and_code_refuter`; the proof is the ten-pointer population and dispositions. |

**Validator invariant**

- every `external_source_refuter` or `source_and_code_refuter` P5 row must link at least one exact PSR record whose `finding_ids` includes that finding;
- generic PSR file references without a fragment fail;
- `deferred` transaction judgments require a typed transaction-evidence dependency, not a claim of direct source verification.

**Positive control:** existing exact mappings remain: PSR-0019 → P5-FIN-003; PSR-0020/0021 → P5-FIN-004; PSR-0015 → the bounded P5-WIND publication-status claims. Headline P5 withdrawals remain valid without pretending that a primary paper directly proves a synthesis score is false.

### B8 — Make EVAL-09 independently recomputable

**Affected file:** `reproductions/p2_population_reconciliation.json`.

Add `finder_files` with the six exact paths and hashes:

- `raw/P2_f1_irr.json` — `c479672d667980ce00caea0dd570e149a31f59fe65cf49736809026888522e4b`;
- `raw/P2_f2_debt.json` — `c7940a0dab2eb2796a2a2e7450059d9ba40987637266a194b642ef88578db435`;
- `raw/P2_f3_waterfall.json` — `3f549929ffe99e04a5d8bd49b3b615b8fefa608db4e9316d8a652e4005198e8e`;
- `raw/P2_f4_tax.json` — `27fdded6cd35dfdbba8d9ac923d2f7d7b11cf117ff1e5a11a2e33a446e645604`;
- `raw/P2_f5_fx.json` — `1a573d200603e0d8b2f44a974f08cbd5c697607bb2500a7c2f9ccc9661bbd897`;
- `raw/P2_f6_mc_sensitivity_casper.json` — `7af1dcf26d395b9fe4e30da7f0f2dad7d42892971e214d4d29898d00579c8fb6`.

Persist the per-pair candidate IDs and derived `id_to_verdict` mapping. Exact pair populations are:

- F1: F1-01..F1-05 (5);
- F2: F2-01..F2-07 (7);
- F3: F3-01..F3-06 (6);
- F4: F4-01..F4-05 (5);
- F5: F5-01..F5-04 (4);
- MC-SENS: MC-SENS-01..02 (2).

**Validator invariant**

- hash and parse all six finder and six verdict files;
- require exact ID-set equality within each finder/refuter pair and global uniqueness;
- derive, rather than trust, 29 candidates and the 14/11/1/3 verdict split;
- require the 25 live and four closed sets to partition the same 29 IDs;
- hash-check and parse `02_finance_correctness_findings.md`; and
- compare each controlled `P2-*` disposition to the parsed verdict mapping.

**Positive control:** EVAL-09 remains `confirmed`; exact totals remain 29, with 25 live and four closed. This patch strengthens lineage and does not alter those arithmetic conclusions.

### B9 — Apply closure and dependency consistency globally

**P3 rows resolved by the new refuter:** P3-MCFX-06 and P3-EQ-01 must take the B2 states; neither remains closed.

**Residual row:** P4-DC-5.

Apply this conservative exact state until an independent code-owner/refuter record exists:

- severity: `medium`;
- disposition: `deferred` (from `not_a_defect`);
- status: `deferred` (from `closed`);
- confidence: `medium`;
- verification: `single_pass_code_inspection`;
- title: `Staged, deliberately unwired layout/GIS modules require an explicit activation-or-preservation decision`;
- corrected claim: “The files appear deliberately staged and unwired, but no independent refuter or approved activation/removal decision has closed the maintenance and governance risk.”;
- canon impact: `level=none`, `direction=none`; no current canonical consumer was established;
- validation dependency wording: “Independent code-owner review or targeted reproduction before activation or removal; preserve the files; no implementation or deletion is authorized by this finding.”

If later owner evidence proves deliberate staging is the accepted end-state, only then may it become `not_a_defect` / `closed` with `No implementation action; preserve staged modules` and no unresolved blocking validation dependency.

**Validator invariant**

- enforce closure rules for every phase, not P2 only;
- `status=closed` permits only `disposition in {refuted,not_a_defect}` and zero blocking implementation, validation, or transaction-evidence dependencies;
- monitoring/future-activation conditions must be typed and non-blocking;
- `requires_correction`, `open`, and `deferred` are never simultaneously represented as closed.

**Positive control:** after B2 and B9, the only closed findings are P2-F1-04, P2-F1-05, P2-F3-03, and P2-F4-03; each already says `No implementation action` and carries no present blocking dependency.

### B10 — Establish one authoritative architecture overlay

**Affected files:** `architecture_pointer_adjudications.draft.json`, `architecture_pointer_adjudications.json`, control index, builder, validator.

**Exact safe treatment**

- move the obsolete draft byte-for-byte to `registers/history/architecture_pointer_adjudications.pre-normalization.20260812.a6c3d56d.json`;
- preserve SHA-256 `a6c3d56dd6c891b2061f13f3dec2038996c15ef49beda5b451e46cc9ef7514b7`;
- add a sidecar/control-index entry with `status=superseded`, `superseded_by=registers/architecture_pointer_adjudications.json`, and the historical hash; do not silently overwrite or delete it;
- designate only `registers/architecture_pointer_adjudications.json` as active;
- regenerate the CSV/JSON dispositions only from the immutable architecture map plus that active overlay.

**Validator invariant**

- exactly one active overlay is allowed;
- `.draft`, `.superseded`, and `history/` artefacts cannot be accepted as generator inputs;
- deterministically rebuild into a temporary directory and require byte/row equality with both committed generated outputs;
- require CSV/JSON row identity and canonical overlay equality for every explicit item.

**Positive control:** 72 unique pointers remain; all 25 explicit overlay items match; the repaired P2/P3 IDs and repository paths remain; the P5 crosswalk remains 1 confirmed / 5 deferred / 4 not examined.

### B11 — Atomize code anchors and dependencies

**Affected findings with compound code-anchor strings (50 IDs)**

P2-F1-01/02/03/04/05; P2-F2-01/02/03/04/05/06/07; P2-F3-02/03/04/05/06; P2-F4-01/02/03/04/05; P2-F5-01/02/03/04; P2-MC-SENS-01/02; P4-CFG-2/3; P4-COMPLEX-01/02/03; P4-COV-01/02/03/04/06/07; P4-DC-3/4/5; P4-DUP-01; P4-MAKEFILE-COMMENT; P4-MYPY-EXCLUSIONS; P4-SCRIPTS-RUFF; P4-SEC-1; P4-TQ-1/2/3.

Convert every anchor, including all P3 rows changed/added in B2, to one object per path/range:

```json
{
  "repository_commit": "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8",
  "path": "finance/irr.py",
  "start_line": 427,
  "end_line": 495,
  "symbol": "approx_project_irr",
  "note": "stopping rule and loop"
}
```

Replace the mixed `remediation_dependency` string list with typed dependency objects:

```json
{
  "dependency_id": "DEP-P3-MCFX-03-01",
  "kind": "implementation",
  "target": "analytics/core/covenant_breach.py",
  "owner_role": "risk-metrics owner",
  "status": "required_not_started",
  "blocking": true,
  "requirement": "Route the diagnostic through the shared tolerance-aware covenant primitive."
}
```

Controlled kinds: `implementation`, `validation`, `transaction_evidence`, `monitoring`, `cross_finding`. Controlled statuses must distinguish at least `required_not_started`, `in_progress`, `completed`, `unavailable`, `not_applicable`.

**Validator invariant**

- every repository anchor uses the audited commit, a repository-relative existing path, positive integer lines, `start_line <= end_line`, and `end_line` within the file;
- no semicolon/multiple-path prose remains in an anchor;
- every dependency has a unique ID, controlled kind/status, owner, blocking flag, and resolvable target where applicable;
- cross-finding and reproduction targets resolve.

**Positive control:** all existing 302 absolute evidence-path occurrences continue to resolve; anchor migration changes structure, not the underlying finding verdicts.

### B12 — Repair two remaining P2 display/authorization conflicts

**P2-F1-01**

- replace title with: `Latent scale-sensitive IRR convergence failure above the canonical size/horizon; no canonical-scale failure reproduced`;
- retain severity `medium`, disposition `partially_confirmed`, status `open`, and the existing narrowed corrected claim;
- keep canon impact `none` for the canonical vector;
- dependency may authorize a scale-invariant stopping rule / larger iteration cap, but must not describe a current canonical failure.

**P2-F2-04**

- replace title with: `Stale LLCR window-disclosure magnitude caused by the F2-02 bridge convention`;
- retain severity `low`, disposition `partially_confirmed`, status `open`;
- replace dependency with: “Correct the stale disclosure now. Any LLCR numerical change occurs only through the separately approved P2-F2-02 root-cause dolphin; do not re-cut the numerator independently.”;
- set canon impact for this finding to `level=none`, `direction=none`, detail: “Correcting the stale note changes no KPI. A numerical LLCR change belongs solely to a separately approved P2-F2-02 implementation.”

**Validator invariant / positive control:** pin both post-refuter titles and the F2-04 dependency/impact boundary; reject language authorizing standalone LLCR realignment. P2 verdict counts remain unchanged.

### B13 — Preserve mixed source severity without changing the controlled verdict

**Affected row:** P2-F4-04.

Add:

```json
"source_severity_label": "Low/Medium",
"severity_normalization": {
  "controlled_value": "low",
  "policy": "For a mixed adjacent source label, select the lower controlled bucket unless the refuter explicitly promotes it.",
  "rationale": "The statutory applicability/formula remains unverified; no canonical impact was established."
}
```

Retain `severity=low`, `disposition=partially_confirmed`, and `status=open`.

**Validator invariant:** every source label not exactly in the controlled vocabulary requires the original label, controlled value, documented policy, and rationale. The normalized value must agree with `severity`.

**Positive control:** source fidelity is preserved without inflating severity or altering the P2 14/11/1/3 verdict arithmetic.

### B14 — Encode honest architecture examination coverage

Do not change the current 72-pointer dispositions merely to improve coverage optics.

Add derived coverage metadata:

```json
{
  "registered_count": 72,
  "explicit_overlay_count": 25,
  "substantive_disposition_count": 21,
  "not_examined_count": 51,
  "not_examined_pct": 70.83333333333333
}
```

Required circulation wording:

> All 72 architecture pointers are registered. Twenty-one have a substantive disposition; 51 of 72 (70.8%) remain not examined. Four of the 25 explicit overlay records—RS-B9, RS-D12, RS-E13, and RS-F10—remain `not_examined`. Registration and reconciliation do not mean examination, confirmation, or closure.

**Validator invariant**

- recompute all five values from the population and active overlay;
- require 2 confirmed, 13 partially confirmed, 1 not a defect, 5 deferred, 51 not examined, and 0 refuted at this cutoff unless a later independently evidenced adjudication changes a row;
- reject synthesis metadata or wording claiming all 72 were examined/verified.

**Positive control:** the exact population remains A15 + B9 + C12 + D12 + E13 + F11; the P5 crosswalk and four named unexamined rows remain explicit.

## 4. Permanent-validator implementation order

After each data dolphin above, add the corresponding invariant; do not defer all controls to one final whale. The final validator must perform, in order:

1. PSR CSV/JSON identity, `source_class`/role/status vocabularies, many-to-many finding-ID resolution, claim-boundary consistency, hashed artefacts/approved exceptions, and exact manifest-set equality.
2. Reproduction-registry schema/status validation, completed-output hash resolution, and verification-level consistency.
3. P2 finder/refuter parsing, exact ID equality, verdict derivation, source-report hash/content reconciliation, and controlled-row mapping.
4. Architecture immutable-source parsing, one-active-overlay rule, deterministic regeneration, CSV/JSON parity, overlay parity, evidence/ID resolution, and coverage derivation.
5. Findings required fields, computed counts, evidence path/fragment validation, atomic code-anchor commit/path/line bounds, typed dependency resolution, and global closure rules.
6. Controlled severity-provenance rules and the exact P2 title/authorization pins.
7. P3 refuter ingress pins, required new atomic IDs, and target 111-row count distribution.
8. F5-01/F5-02 separation: separate finding IDs, dependencies, specifications, reproductions, commits/PRs, and no rhetorical netting.
9. Top-level evidence manifest covering immutable inputs, sources, PSR, refuters, reproductions, overlays, generated outputs, findings, validator version/output, and semantic-QA result.

The emitted result should be named `structural_pass` unless and until an independent semantic QA gate also passes. A structural pass is not release approval.

## 5. Current snapshot and positive controls that must survive

Current controlled artefacts remain byte-identical to the frozen QA snapshot:

| Artefact | Current SHA-256 |
|---|---|
| `sources/SOURCE_ARCHIVE_MANIFEST.sha256` | `568c54095213821a683fd385fe5f7dabfb8d026ddfa9b4d750c386ed145aed93` |
| `sources/IEC_CATALOGUE_QUERY_LOG.json` | `6a7b24b58e952f684267ed21b46470951b11a28cdcf281850175ded70ab602dc` |
| `registers/primary_source_register.csv` | `3b3003a5dd263227594a380231d40d0ad87d1a5b9ba19fc34dd97e7726040f31` |
| `registers/primary_source_register.json` | `6302ce76aa7e8bcd1274a8031a951a273d6c13c2166dd869b4b8ad2f096b78f9` |
| `reproductions/p2_population_reconciliation.json` | `2269d2ef2517761e6871ca262c511b18f6c3d638d12498e326a40708bfd165d0` |
| `registers/architecture_pointer_adjudications.json` | `7f0a24b1d1b6e37dc646ade4a2b6426102744bcc62876f3bacb2b53674175de4` |
| stale draft overlay | `a6c3d56dd6c891b2061f13f3dec2038996c15ef49beda5b451e46cc9ef7514b7` |
| architecture CSV | `89cd5f8d1550f62697579b883733445b1c1731ad037cfc21637ba2c3be72b45f` |
| architecture JSON | `3856dd45ffb31d12a0bdd1da5aa5ff70dca180f732c22f0d044bd1f29aff12d5` |
| `registers/findings_register.draft.json` | `b64c8e4430ea9febd58226c4a8a039fb2001fbce5979e433631c53216c3864f8` |
| `scripts/validate_controlled_registers.py` | `8a5550a7580f051297957d7275d22c18b23fc56b3e2f6b588b0c2169a577ff21` |
| P3 refuter | `2e150dc6b1f949418236256057b3e291f80d7c466873d436a15db37523631685` |
| frozen QA checkpoint | `e0484670a765dcdb20eb7992a1d009feb55112d80608efced636f7f6be50ab2e` |

The current structural validator still passes its six implemented gates: 23 archived sources, 22 PSR rows, 29 P2 candidates, 72 architecture pointers, the 1/5/4 P5 pointer crosswalk, and 107 findings. Preserve these positive controls while extending the schema.

The following accepted repairs must not regress:

- PSR CSV/JSON row identity;
- archived PSR-0010 and PSR-0022 evidence;
- normalized P2 and P3 architecture finding IDs;
- removal of the non-finding P4-F1 link;
- corrected repository paths;
- lossless 72-row architecture CSV/JSON parity;
- repaired closed P2 dependency wording;
- P2 severity corrections and F2-07 magnitude/canon impact;
- P5-FIN-002’s non-inverted title; and
- complete separation of F5-01 and F5-02.

## 6. Live checkpoint-manifest control

`CHECKPOINT_MANIFEST.sha256` is a historical 10:34 snapshot and must not be represented as validating the resumed live workspace. A full current check gives **63 entries: 60 match, 3 differ, 0 missing**:

- `00_CONTROL_INDEX.md`: expected `e1843660471d14e54091cecaa97658e81423ececd12be6df8a597678525a2efb`; current `9366d054def5e908c6e238a8a5748e7ffd497d4f81b3cec022d0acf57220b8d8`;
- `CHECKPOINT_2026-08-12T103431+0530.md`: expected `07f61b0b636b5190dd1e95c637486ce721e3db8d717446efdb2f6b9902dd6b9c`; current `c2e6fef5fa8b04d4fb7e857b54849fa2c978f243475e7c857fd98100b89f7be5`; and
- `WORKLOG.md`: expected `fd52e7436b9a333ba278ebc4119f05ec1b5d475c5c59784dd9e0bcaeb4b689d4`; current `9bf4198c091b95fba7888c1bcd929a1c02b114f54c32ddaf5a9390a59e47a8bf`.

This drift is expected from resumed, append-only/control-document work. Preserve the historical manifest unchanged and issue a new versioned current-state manifest after the register-ingress dolphins; do not silently replace the historical hashes.

## 7. Release proof required after patching

The HOLD may be reconsidered only after all of the following are simultaneously true:

1. strengthened validator returns `structural_pass` on the new schema and recomputed metadata;
2. zero unresolved source, finding, reproduction, dependency, evidence-path, or code-anchor references remain;
3. the P3 refuter is fully ingressed, including four atomic rows and the 111-row target counts;
4. the P2 29-candidate population is independently recomputed from all twelve files;
5. one authoritative architecture overlay deterministically regenerates identical 72-row CSV/JSON outputs;
6. source claims are bounded to exact evidence and P5 source gaps remain explicit;
7. global closure invariants pass, leaving only the four supported P2 closures at this stage;
8. architecture coverage is disclosed as 51/72 not examined;
9. a new current-state evidence manifest verifies every release input/output; and
10. an independent semantic QA rerun returns PASS.

Only then should the Board/lender synthesis be regenerated. No item in this map authorizes activation of `fx_calibrated`, invention of risk distributions, a standalone LLCR recut, removal of staged code, or combining F5-01 and F5-02.
