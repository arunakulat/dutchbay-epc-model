# DutchBay #1110 Non-Canonical QA and Controlled Re-ingress Checklist v1

Status: **WORK PROGRAMME — RELEASE HOLD**
Prepared: 2026-08-24 (Asia/Colombo)
Tracker: GitHub issue #1110
Applies to: controlled-successor evidence, reproductions, current-main reconciliation, and F5-02 transaction evidence
Does not authorize: a canonical re-baseline, lender/Board circulation, investment approval, tariff claims, or financial close

## 1. How to use this checklist

1. Create one controlled work package per checklist item. Do not combine implementation, reproduction, and independent adjudication into an unreviewable change.
2. Freeze the target commit, source files, inputs, runtime, command, and expected evidence boundary before execution.
3. Preserve originals and historical registers. Add a versioned successor record; never rewrite a finder/refuter or old result to look current.
4. Record execution status separately from claim disposition. A runner can pass while the underlying claim remains unsupported, partially supported, or refuted.
5. Use deterministic JSON with sorted keys, no NaN, no absolute temporary paths, no wall-clock durations, and no retained high-volume logs.
6. A same-author or same-stream review is useful QA but is not formal independent authorization. Formal independent review requires a separate reviewer who did not author the runner, expectations, or result.
7. F5-01 and F5-02 remain completely separate. Never net their financial effects or use one to close the other.
8. Keep `release_status: HOLD` until every release gate in #1110 is explicitly checked and a controlled `RELEASED` decision is recorded.

Each work package must retain this minimum receipt:

- [ ] control/work-package ID and version;
- [ ] target repository commit and tree;
- [ ] immutable input paths and SHA-256 values;
- [ ] exact command/argv and governed runtime;
- [ ] concise assertion and negative-control results;
- [ ] output path and SHA-256;
- [ ] limitations and unsupported conclusions;
- [ ] author verification level;
- [ ] independent reviewer identity, conflict disclosure, rerun result, and disposition;
- [ ] register/manifest changes and post-change validator result.

## 2. Roles and separation of duties

| Role | May author | May independently authorize the same package? |
|---|---|---:|
| Control author | config, runner, tests, candidate result | No |
| Evidence custodian | source ingress, hashes, chain of custody | No, unless uninvolved in expectations and execution |
| Adversarial reviewer | pre-merge code and claim review | No formal closure if part of the same delivery stream |
| Independent reproducer | fresh checkout rerun and negative controls | Yes, if no authorship and conflicts are disclosed |
| Semantic adjudicator | source-to-claim review and disposition | Yes, if independent from authorship |
| Model owner | accepts or rejects a canonical change | Only after evidence and independent review |
| Release authority | records HOLD or RELEASED | Only after every named release gate is complete |

## 3. QA-01 — independent semantic QA of the manifest-bound FX disclosure

Objective: determine what the historical FX report actually proves, correct unsupported provenance language, and preserve the distinction between implementation behavior and transaction/source authority.

Inputs:

- manifest-bound FX candidate/result and its resolved-config hash;
- retained BIS exchange-rate series and any retained CBSL spot evidence;
- report source, rendered artifact if available, and evidence-register entries;
- audited commit and current-main comparison commit.

Procedure:

- [ ] Verify every file and manifest SHA-256 before reading content.
- [ ] Recompute the retained BIS geometric depreciation value independently without importing DutchBay finance/FX code.
- [ ] Confirm the report values `333.79` and `5.89%` are traceable to the bound resolved configuration, not merely repeated literals.
- [ ] Verify fail-closed behavior by changing the expected config hash in a disposable copy and requiring rejection.
- [ ] Inspect the controlled primary-source register for an FX row and the finding/source references for the disclosure.
- [ ] Verify whether the original Open Exchange Rates response, dated CBSL spot evidence, and rendered HTML were actually retained.
- [ ] Check the report sentence claiming an “FX evidence-register row” against the register. If the row is absent, classify the sentence as unsupported and correct it additively.
- [ ] Separate three dispositions: arithmetic/integrity, implementation behavior, and primary-source provenance.

Pass boundary:

- [ ] Historical config-hash binding and arithmetic are independently reproduced.
- [ ] Every disclosure has an evidence-register row or is explicitly labelled as an unresolved provenance gap.
- [ ] No reviewer upgrades BIS/context evidence into transaction-specific lender evidence.

Do not conclude:

- that the selected FX path is lender-approved or transaction-specific;
- that missing source rows are cured by a matching number;
- that a same-stream rerun is independent closure.

## 4. QA-02 — independent QA of the governed 10,000-trial Monte Carlo evidence

Objective: verify historical arithmetic and integrity while stating exactly why the run does not authorize a current lender conclusion or release.

Procedure:

- [ ] Verify result, manifest, config, and source hashes.
- [ ] Recalculate with a standalone standard-library or independently implemented reader:
  - strict historical pass count and rate;
  - tolerance-aware pass count and rate;
  - every retained output-array summary statistic;
  - the reported Wilson interval as arithmetic only.
- [ ] Confirm the retained historical results reproduce `9,868 / 10,000 = 98.68%` strict and `8,244 / 10,000 = 82.44%` tolerance-aware.
- [ ] Confirm the reported Wilson arithmetic is `[0.8168185613879781, 0.8317323004691268]`.
- [ ] Inspect whether sampled-input rows were retained. Record `raw_results: null` or equivalent as a blocking reproducibility gap if the input matrix is absent.
- [ ] Confirm seed, sampler design, dependence structure, and number of independent designs.
- [ ] Determine whether the interval’s i.i.d. coverage assumptions are justified for correlated Latin-hypercube samples. Do not describe an arithmetic Wilson calculation as a design-valid confidence interval without that proof.
- [ ] Record that the run predates F5-01, resizes debt (`fixed_debt_stress=false`), uses placeholder construction/draw schedules, and emits repeated intermediate equity warnings where applicable.
- [ ] Run a fresh current-main comparison only as a new versioned reproduction with explicit seed/design; never overwrite the historical result.

Pass boundary:

- [ ] Historical output arithmetic and hashes are independently verified.
- [ ] Missing sampled inputs, one-design dependence, predecessor canon, debt-resizing posture, and placeholders remain explicit limitations.

Do not conclude:

- current lender bankability;
- convergence from one seed/design;
- statistically valid confidence coverage merely because Wilson arithmetic is correct;
- release readiness.

## 5. QA-03 — P4 scenario schema and YAML safe-load controls

Control IDs:

- `P4-CFG-1-SCHEMA-GUARD`
- `P4-CFG-2-YAML-SAFE-LOAD`

Procedure:

- [ ] Create a config-first policy listing all 39 tracked scenario YAML/JSON artifacts explicitly, including role, parse contract, schema contract, expected error, and audited SHA-256.
- [ ] Run against exact audited commit `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8` in a detached checkout.
- [ ] Fail if imports resolve outside the target checkout.
- [ ] Require the Git tree population to match the 39-entry policy exactly.
- [ ] Require every declared v14 scenario to parse to one mapping and pass `validate_config_for_v14(..., ["cashflow", "debt"])`.
- [ ] Treat `zz_bad.yaml` and `bad_missing_tax.yaml` as expected-invalid controls with exact error classes/messages.
- [ ] Classify `example_fx_structured_blocks.yaml` accurately: valid four-document YAML stream; invalid under the repository single-document scenario contract; `safe_load()` raises `ComposerError`; `safe_load_all()` returns one mapping followed by three null/comment-only documents.
- [ ] Detect and fence every test that catches `yaml.YAMLError` and continues.
- [ ] Run population/hash/import/error-class negative controls.
- [ ] Emit separate canonical JSON outputs for CFG-1 and CFG-2 plus a comparison-only current-main result.
- [ ] Obtain independent rerun and semantic review before completing the linked dependency.

Pass boundary: both controls are output-hashed `completed`; current-main comparison is explicitly non-authoritative; HOLD remains.

## 6. QA-04 — P4 historical CI-gate reproduction

Control ID: `P4-F1-CI-GATE-RUNS`

Procedure:

- [ ] Keep this separate from QA-03 because the target is GitHub Actions/toolchain enforcement, not scenario semantics.
- [ ] Bind historical GitHub run `31925512287` and exact head `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`.
- [ ] Verify the Code Quality, Security Scan, and Test Summary job IDs/conclusions from GitHub-hosted evidence.
- [ ] Parse the audited workflow and prove lint/security commands are fail-loud, have no `continue-on-error` or `|| true`, and feed Test Summary.
- [ ] Run audited direct commands under GitHub-hosted Python 3.11; do not create a local non-governed Python 3.11 environment.
- [ ] Execute all-files pre-commit in a disposable audited checkout. Classify only the declared `check-yaml` failure at the line-114 multi-document stream as known; any other failure or mutation is a control failure.
- [ ] Record local-hook/CI asymmetry: mypy and Bandit are CI controls but absent from local pre-commit.
- [ ] Run workflow-mutation negative controls and an independent GitHub-hosted rerun against the exact result hash.

Pass boundary: historical CI claims are supported, local-hook asymmetry remains explicit, and architecture pointer RS-F4 is no stronger than partially confirmed.

## 7. QA-05 — additive current-main F5-01 reconciliation

Objective: reconcile the completed F5-01 implementation with current main without rewriting historical audit registers or combining F5-02.

Procedure:

- [ ] Preserve the historical finder/refuter, candidate, and merged F5-01 artifacts unchanged.
- [ ] Record the merged implementation chain: #1035, #1036, #1037, #1038, #1040, and #1057 with exact commit SHAs.
- [ ] Freeze current main and independently reproduce the current lender vector and prudential NPV/rate.
- [ ] Reconcile each implementation claim to current source, focused tests, protected CI, and current computed outputs.
- [ ] Record separately: code complete, current-main computed behavior, historical audit disposition, independent semantic review, and remaining release dependencies.
- [ ] Add a dated successor reconciliation and link it from the controlled register builder; do not edit only generated JSON/CSV descendants.
- [ ] State explicitly that F5-02 remains open and transaction-evidence blocked; do not net its historical proxy against F5-01.
- [ ] Regenerate publication descendants and manifest only after the private/source-of-truth builder is updated.

Current values to independently reproduce, not blindly copy:

- project IRR `-0.001166233356501311`;
- equity IRR `-0.07853839579881439`;
- project NPV `-91810995.06051566`;
- min DSCR and min-period DSCR `1.3`;
- total CFADS `166083177.3168602`;
- prudential NPV `-96435848.53558263`;
- prudential rate `0.11285835226329409`.

Pass boundary: current-main results, source lineage, and independent review reconcile; historical evidence stays immutable; RELEASE remains HOLD.

## 8. QA-06 — controlled current-main delta ledger from #1111 onward

Procedure for every merged PR from #1111 to the current cutoff:

- [ ] Record PR number/title, merge commit, parent/base commit, merged timestamp, changed paths, issue links, and changelog fragment.
- [ ] Classify the change as financial behavior, test/oracle, governance, evidence/provenance, deployment/operations, presentation, or documentation.
- [ ] Record whether canonical KPIs can move and cite the independent oracle or byte-identity receipt.
- [ ] Record all protected checks, including dynamically registered aggregate checks and governed skips.
- [ ] Record merge-tree/patch-equivalence and cleanup receipts where available.
- [ ] Link the change to affected findings, architecture pointers, reproductions, release gates, and handovers.
- [ ] Mark unknown evidence explicitly; do not infer a check or review from a green merge alone.
- [ ] Close the ledger at a named commit and SHA-256 the canonical JSON/CSV output.

Pass boundary: every merge in the interval appears exactly once; the ledger total reconciles to GitHub and Git history; no release claim is introduced.

## 9. QA-07 — method-only reproductions for required-not-run controls

Run these as separate, versioned controls after freezing source/expectations and assigning independent reviewers:

| Control ID | Method focus | Required caution |
|---|---|---|
| `P5-REPRO-C1-001` | sampling and random-design behavior | Multiple explicit seeds/designs; retain sampled inputs |
| `P5-REPRO-C2-001` | dependence/correlation behavior | Do not infer calibrated dependence without external evidence |
| `P5-REPRO-C8-001` | sensitivity method behavior | Reconcile estimator convention and sample-space transform |
| `P5-REPRO-RISK-001` | risk/exceedance arithmetic | Lock quantile, tail, and breach conventions independently |
| `P5-REPRO-A14-001` | debt sculpt allocation | Method-only until facility/intercreditor evidence arrives |
| `P5-REPRO-D4-001` | resource/AEP method behavior | No bankable resource conclusion without independent resource evidence |
| `P5-REPRO-LLCR-001` | LLCR window/discounting | Bind dates, cash-flow window, curve, DSRA/bridge treatment |
| `P5-REPRO-WIND-001` | wind-distribution behavior | Compare pooled and seasonal/monthly structure; retain limitations |

For every method control:

- [ ] use the exact audited target and source hash;
- [ ] declare units, formulas, conventions, tolerances, seeds, and negative controls before execution;
- [ ] distinguish method execution PASS from whether the audited claim is supported;
- [ ] emit deterministic output and obtain a separate independent rerun;
- [ ] keep transaction/resource/calibration conclusions conditional where source evidence is absent.

## 10. QA-08 — reconstruct the five historically unavailable scratch controls

The five old IDs remain permanently `unavailable`; do not overwrite or relabel them as recovered:

- `P2-SCRATCH-R1_F1_CHECK`
- `P2-SCRATCH-R1_F1_CHECK2`
- `P2-SCRATCH-R1_F1_CHECK3`
- `P2-SCRATCH-R2_CHECK`
- `P2-SCRATCH-R2_FEE`

Create new versioned controls that supersede the evidence gap, not the historical rows:

- `P2-REPRO-F1-01-SCALE-V1`
- `P2-REPRO-F1-05-CAPEX-TIMING-V1`
- `P2-REPRO-F1-CANON-TIMELINE-V1`
- `P2-REPRO-F2-DEBT-SEAMS-V1`
- `P2-REPRO-F2-FEE-BASIS-V1`

Procedure:

- [ ] Pin audited commit `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8` and retained source hashes.
- [ ] Use a config-first Hydra/JSON-first runner with one deterministic artifact per control.
- [ ] Fail closed on wrong checkout/import path, source hash, inputs, or expected units.
- [ ] Record `supersedes_evidence_gap` pointing to the unavailable legacy ID.
- [ ] Use retained finder/refuter inputs where present, including P2 F1/F2 JSON and retained CFADS.
- [ ] Include at least one mutation/negative control per reconstructed claim.
- [ ] Mark implementation-author evidence as governed same-agent validation, not independent reproduction.
- [ ] Commission a separate reviewer to rerun the fixed spec and adjudicate each result.

Pass boundary: five new output-hashed controls exist and independently rerun; five old rows remain unavailable; HOLD remains until all linked dependencies and release gates are complete.

## 11. QA-09 — F5-02 lender YAML return and controlled re-ingress

Input template: `DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml`.

Repository-owned internal decision template: `DUTCHBAY_F5_02_INTERNAL_DECISION_RECORD_TEMPLATE_v1.yaml`. Repository-owned private-ingress manifest template: `DUTCHBAY_F5_02_PRIVATE_INGRESS_MANIFEST_TEMPLATE_v1.yaml`. Do **not** send either internal file to the lender team and do not let a respondent select the canonical treatment, evidence eligibility, or release state.

Controlling requirements source: `F5-02 Transaction-Evidence, Legal-Currency and Repayment Requirements Register`, evidence cutoff 2026-08-18, SHA-256 `7f3199867ae6aaae2e7365b0cb15fe7ca81b3348060e9ac443622fbc231a9416`. Its tabulated register contains 53 distinct requirement IDs; an older narrative reference to a “55-item” list is a stale count, not authority to invent two fields.

Outbound procedure:

- [ ] Send an immutable copy of the blank template with document ID/version and SHA-256.
- [ ] Keep only the blank template, validator, and a redacted receipt in the public repository. Never commit a completed return, source document, lender identity, data-room path, account reference, pricing, security term, or legal/tax opinion.
- [ ] Before dispatch, assign a private access-controlled return location and evidence custodian outside this public repository; communicate that location through the approved confidential channel.
- [ ] Ask the lender/agent, borrower, legal counsel, tax adviser, and authorized dealer to complete only fields within their authority.
- [ ] Require every `confirmed` and `not_applicable` field to cite evidence ID, exact clause, and exact page.
- [ ] Do not permit `not_applicable` for borrower identity, lender/agent/trustee identity, facility/tranche mapping, commitment currency, principal-accounting currency, interest-payment currency, or principal-repayment currency.
- [ ] Require each facility/tranche to have a separate complete item.
- [ ] Permit `unknown`, `provisional`, and `conflicted`; prohibit guessed completion.

Inbound procedure:

- [ ] Preserve the exact returned file as immutable source evidence in the assigned private access-controlled store before editing or normalization; never copy it into this repository or a public issue/PR.
- [ ] Record received timestamp, sender, channel, filename, size, and SHA-256.
- [ ] Preflight the YAML with the validator's duplicate-key, alias, unsafe-tag, and multi-document rejecting safe loader. Do not normalize the bytes before hashing.
- [ ] Run the repository validator from the current governed checkout with the confidential path outside Hydra composition and the mandated shared Python 3.12 environment: `PYTHONPATH="$PWD" DUTCHBAY_F5_02_RETURN_PATH=/private/absolute/path/returned.yaml DUTCHBAY_F5_02_CUSTODIAN_ROLE=evidence_custodian DUTCHBAY_F5_02_RECEIPT_TIMESTAMP=YYYY-MM-DDTHH:MM:SS+HH:MM /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python scripts/validate_f5_02_lender_return.py mode=structural`. The privacy-safe Hydra config disables job/config/log artifacts. The CLI accepts exactly one explicit validation-mode override and emits only the permitted five-field public receipt on success or one stable error code on rejection; detailed validation facts remain private.
- [ ] Validate schema/version, all 53 requirement IDs per the project/facility scope, exact response shapes, real quoted Gregorian dates, currency codes against the frozen SIX ISO-4217 Maintenance Agency List One cutoff, decimal-string rate/amount fields, base-unit scale, facility/entity uniqueness, evidence/citation referential integrity, sign-offs, conflicts, and protected HOLD controls.
- [ ] Reject a confirmed/not-applicable field lacking clause/page evidence.
- [ ] Reconcile every cited evidence item to a retained authenticated file and SHA-256.
- [ ] Remove the untouched conflict placeholder when there are no conflicts. Any populated conflict row requires a unique ID; a resolved conflict requires resolution text plus eligible resolution evidence and citations.
- [ ] Commission separate legal/tax/authorized-dealer review for the fields in their scope.
- [ ] Independently create the private custodian manifest from `DUTCHBAY_F5_02_PRIVATE_INGRESS_MANIFEST_TEMPLATE_v1.yaml`. Bind the exact raw lender-return SHA-256 and every evidence ID to an existing retained absolute path, exact byte count, raw-file SHA-256, exact title, parties, version/effective/amendment status, governing-law relevance, acquisition date, confidentiality, source/authentication fields, independent review disposition, limitations, and supersession links. Store the completed manifest outside every public worktree.
- [ ] Run closure-candidate validation only after the previous step: `PYTHONPATH="$PWD" DUTCHBAY_F5_02_RETURN_PATH=/private/absolute/path/returned.yaml DUTCHBAY_F5_02_INGRESS_MANIFEST_PATH=/private/absolute/path/ingress-manifest.yaml DUTCHBAY_F5_02_CUSTODIAN_ROLE=evidence_custodian DUTCHBAY_F5_02_RECEIPT_TIMESTAMP=YYYY-MM-DDTHH:MM:SS+HH:MM /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python scripts/validate_f5_02_lender_return.py mode=closure_candidate`. Every requirement must be confirmed or validly not applicable, every conflict resolved, all confirmations/sign-offs complete, the return must state a valid evidence cutoff, and all evidence must be byte- and metadata-bound by the separate manifest. A passing closure-candidate validation remains non-authorizing and does not lift HOLD.
- [ ] Retain publicly only a redacted receipt containing document ID, custodian role, receipt timestamp, confidentiality classification, and SHA-256—never returned values.
- [ ] Commission independent model semantic review; record reviewer independence/conflicts, fixed specification and hash, exact rerun, counterexamples, disposition, unresolved rebuttals, signature, and date in the internal decision record.
- [ ] Select Option A, Option B, or a hybrid only in the separate internal decision record with clause-level evidence, legal/tax/authorized-dealer conclusions, model-owner approval, and release-authority decision.
- [ ] Keep the internal decision record at `canonical_binding_status: blocked` and `board_lender_release_status: HOLD` until every governed approval is independently supported.

## 12. QA-10 — architecture-pointer examination programme

The 51 historical `not_examined` pointers and five deferred pointers have been scout-mapped to current code seams, but none is counted as examined by this checklist. Before execution, create a separate 56-row controlled ledger with one immutable row per pointer: historical source anchor, current code seam, owner, dependencies, fixed claim, planned negative control, independent reviewer, result hash, disposition, confidence, unresolved gaps, and HOLD effect. Execute them in these dependency-aware batches; each pointer receives its own disposition even where evidence work is shared:

1. current-audit reconciliation: RS-F3;
2. governance fences: RS-F1, RS-F5, RS-F6, RS-F7, RS-F11;
3. grid/configuration: RS-F2, RS-F10;
4. scenario-family semantics: RS-F8;
5. gateway/integrity parity: RS-B1, RS-B2, RS-B3, RS-E1, RS-E2;
6. contracts/imports/deprecation: RS-A13, RS-B4, RS-B5, RS-B6, RS-B9, RS-C12;
7. finance safety/disclosure: RS-A11, RS-A12, RS-B7, RS-B8, RS-D11;
8. Monte Carlo arithmetic/report semantics: RS-C3 through RS-C7;
9. sample-space/degradation semantics: RS-C9 through RS-C11;
10. stochastic reproductions: RS-C1, RS-C2, RS-C8;
11. wind coherence: RS-D5, RS-D6, RS-D7, RS-D8, RS-D10;
12. resource reproductions: RS-D2, RS-D4, RS-D12;
13. async/API: RS-E3 through RS-E9;
14. operations/security/presentation: RS-E10 through RS-E13;
15. transaction-dependent debt allocation: RS-A14.

For each pointer:

- [ ] preserve the historical risk claim and source anchor;
- [ ] record current-main code seam and whether the historical wording is stale;
- [ ] collect independent evidence and negative controls;
- [ ] classify `confirmed`, `partially_confirmed`, `refuted`, `remediated`, `not_a_defect`, or `blocked_external` with confidence;
- [ ] link completed reproductions only after output hash and independent review exist;
- [ ] add, never rewrite, the current-main adjudication overlay;
- [ ] regenerate JSON/CSV descendants and publication manifest through the canonical builder;
- [ ] retain HOLD unless every separate release gate is complete.

## 13. Final register and release procedure

- [ ] Update the source-of-truth/private deterministic register builder first.
- [ ] Regenerate findings, architecture dispositions, reproduction register, README counts, and controlled publication descendants.
- [ ] Rebuild `PUBLICATION_MANIFEST.sha256` and verify every entry.
- [ ] Run the repository-safe controlled-pack validator from a clean current-main worktree.
- [ ] Run the external/private validator where available and record missing-source limitations exactly.
- [ ] Create a separate 23-row controlled gate ledger by copying each controlling #1110 gate verbatim at a named issue-revision cutoff; record status, owner, dependencies, evidence hashes, independent reviewer, and explicit HOLD effect.
- [ ] Verify all 23 #1110 issue gates one by one against that ledger; do not infer completion from counts, batches, merged PRs, or a green aggregate validator.
- [ ] Verify every Critical/High finding has evidence or a declared blocking dependency.
- [ ] Obtain independent semantic sign-off for FX, MC, P4, reconstructed controls, architecture dispositions, F5-01 reconciliation, and F5-02 evidence binding.
- [ ] Regenerate the final synthesis and rendered lender/Board artifacts only after all prerequisites pass.
- [ ] Record either `HOLD` with exact remaining blockers or `RELEASED` with authority, date, commit, manifests, hashes, and limitations.

Until the last step records `RELEASED`, the only valid release disposition is **HOLD**.
