# PR1178 independent assurance disposition

**ACCEPT — exact repaired subject**, with delivery still subject to final-head rebind and all required exact-head hosted checks.

The corrected original-review transcription is confirmed at SHA-256 `83b2d301c64c57ffbf6b6892a3aeaf450b1dd0f580abe7f1ce57fe773027332c`. It implements my requested distinctions between independently executed dry-run evidence, published metadata and installation claims.

```yaml
reviewer_role: assurance
reviewer_identity: /root/assurance
candidate_commit: 06a4048b51cccd61d7447ec350f3d3a77822f1ba
candidate_tree: 56567180e07a1c3d3c716df8e447e55f897aa1f3
base_sha: dbd924a00dd4b29e23139da768a8f2603396dc17
merge_base_sha: dbd924a00dd4b29e23139da768a8f2603396dc17
subject_manifest_sha256: 60aa8ca1d6627507edea3b46ffa552ec4b5868cefa71bd8422388aeff142a57a
corpus_and_rule_identities:
  governance: Current AGENTS, complete 74-rule CSV, pinned unabridged frameworks, all four RECRUIT-01 modules
  rules_sha256: 0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1
  continuity: September 7 handover and applicable predecessor HOLD boundaries
  dependency_type_runtime: Requirements, constraints, pyproject, mypy configuration, workflow, candidate stub metadata/source, retained installed runtime
  final_profile: assurance_FINAL_PROFILE.md
  substantive_subject: All six files in repaired_subject_manifest.tsv
review_scope:
  - Complete six-file diff and substantive source/test/record bodies
  - Named pvalue extraction and numerical preservation
  - Regression oracle independence and hostile statistic substitution
  - Faithful target-stub local type evidence and evidence wording
  - Original blocker closure, current-base identity and unchanged authority boundaries
checks_executed_and_exact_results:
  - Independently recomputed repaired manifest SHA-256; matches frozen digest.
  - Independently checked every manifest path against HEAD git blob; all six match.
  - Independently ran new regression plus pre-existing wind analyzer tests; exit 0, 33 passed in 1.67s.
  - Independently injected KS statistic into pvalue in memory; all four new test cases raised AssertionError.
  - Independently validated and executed all 589 target-stub shadow mappings for full library/entrypoint mypy; exit 0, no issues in 269 source files.
  - git diff --check exits 0; git status --porcelain empty.
  - git rev-parse confirms exact repaired HEAD and tree.
  - Live PR head equals repaired candidate; mergeStateStatus BLOCKED at observation, so no CI-green or merge claim.
independent_oracles_or_counterexamples:
  - Runtime identity oracle from initial independent review proves named pvalue and second tuple element are the identical SciPy runtime object on three distinct datasets.
  - New regression oracle directly calculates both empirical-CDF deviations and Weibull CDF, then uses kstwo.sf; it does not call kstest for its expected result.
  - Independently executed hostile replacement pvalue=result.statistic fires in all four cases.
  - Full source diff proves unchanged kstest arguments, filtering, Weibull fitting, other output fields and numerical runtime pins.
predecessor_finding_matrix:
  - finding_id: A1178-01-original-type-errors
    applicability: applicable
    probe_evidence: Independently rerun candidate-stub full library mypy passes; both consumers now use typed public pvalue property.
    result: CLOSED
  - finding_id: A1178-02-stale-base
    applicability: applicable
    probe_evidence: Repaired frozen base and merge base both dbd924a; fresh substantive review performed.
    result: CLOSED
  - finding_id: PR1176-mpmath-SymPy-conflict
    applicability: not applicable
    probe_evidence: Neither pin changes.
    result: NOT_APPLICABLE
  - finding_id: PR1176-typing-NumPy-conflict
    applicability: not applicable
    probe_evidence: Retained pins; independent focused resolver dry-run from original review passes.
    result: NOT_APPLICABLE
  - finding_id: PR1174-consumer-ceiling-review
    applicability: applicable method
    probe_evidence: Actual primary metadata, stub source, retained runtime and resolver evidence reviewed.
    result: CLOSED
findings_and_residual_limitations:
  - id: assurance-final-01
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    finding: Local candidate typing uses source shadows rather than installing the new package; exact-head hosted installation and checks remain mandatory.
  - id: assurance-final-02
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    finding: Independent local full finance, QSTS, coverage and release qualification not run in this bounded review; no such achievement claimed.
  - id: assurance-final-03
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    finding: Unused mypy section warnings reproduced; no errors. Record separately discloses coordinator-observed NetCDF warning and pre-existing Ruff versus Black formatting difference.
hold_and_authority_effect: None; issue1110, empty production assembly authority, professional, publication, deployment, release, lender, Board and HOLD boundaries remain unchanged.
disposition: ACCEPT_EXACT_REPAIRED_SUBJECT
mutation_attestation: No repository, index, ref, branch, environment, PR, issue or evidence-file mutation; hostile fault was in process memory only and restored; no peer final disposition read before this receipt.
```

The two production edits only change how an existing `KstestResult` is read. They retain the existing call, consume its public `.pvalue` property and keep the same final `float` conversion. No cast, ignore, relaxed type rule or numerical change was introduced. The unchanged runtime and earlier identity oracle support the record's output-preservation claim.

My independently executed test invocation was the governed interpreter calling:

```python
pytest.main([
    "-p", "no:cacheprovider",
    "tests/wind/test_weibull_ks_pvalue.py",
    "tests/wind/test_wind_analyzer.py",
    "--no-cov", "-q",
])
```

It returned `0`, with **33 passed in 1.67s**. For the separate negative control, I loaded the new test function, temporarily replaced `scipy.stats.kstest` with a wrapper returning its genuine statistic as both `statistic` and `pvalue`, and invoked each combination of entrypoint `series`/`analyzer` and seed `7`/`21`. **All four failed their numerical assertion**, and the genuine function was restored in `finally`.

I also independently reran the complete library type invocation recorded in `repaired_library_types.json`, after validating the interpreter, cache controls, every shadow source/destination prefix and final checked paths. It passed with **269 source files**. This verifies the supplementary shadow-based type result; it is not a claim that the target wheel was installed locally.

The implementation record correctly separates its coordinator receipts from outstanding hosted evidence, states the observed warnings, declares checks not run and confers no extra authority. No substantive blocker remains in the reviewed six-file subject. Acceptance binds only to the stated commit/tree/base and manifest; changed subject bytes require fresh review.
