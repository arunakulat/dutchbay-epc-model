# H06 domain review receipt — 2026-09-09

This is the delivery owner's compact transcription of an independent disposition.
The exact original body is preserved unchanged outside Git and identified below.
The reviewer must verify this transcription at the final delivery-head rebind.

```yaml
reviewer_role: independent_read_only_domain
reviewer_identity: 01a083f0-65d3-7081-a591-66385024773b
reviewer_agent: /root/h06_domain
model: gpt-6-astra
reasoning_effort: xhigh
configuration_evidence: actual session_meta and turn_context; independently checked by delivery owner
risk_class: R3_CONSEQUENTIAL
candidate_commit: 84beded0d4b460f3b668aeed58c52f244ecbbac2
candidate_tree: 5ecc3d38352d1366334d7d076d45315dbd026a91
base_sha: 3cc3d0ebba1d09c27c17556a2c40ee379904b969
merge_base_sha: 3cc3d0ebba1d09c27c17556a2c40ee379904b969
subject_manifest_sha256: 8c9d8882c34b1412aa3ffac3b9340594e0dd87149b34f5fe916798ab3a8ff7fb
original_body_sha256: 83682c7cab5f39bb47eb6268d61eb0a8a66042a3db1e41f8d45cfc84fc75abac
exact_tool_commands_sha256: d6d5afe7a074029004edf519eabfe18dba02ee85404c7e8d3e472f19408d4bd8
evidence_yield: EVIDENCE_RETURNED
disposition: ACCEPT_FROZEN_SUBJECT_WITH_STATED_LIMITATIONS
mutation_attestation: read-only; process-local substitutions and warning/error settings restored
```

## Corpus and scope

The reviewer read the full current GWTF CSV, pinned framework definitions, all four
RECRUIT-01 modules, applicable AGENTS and handover/bootstrap, H06 preparation and
original hygiene report, installed numerical implementation, source/test bodies,
manifest and writer evidence corrections. All 11 recorded ingress hashes matched.
GWTF SHA-256 is `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1`.
Independent bootstrap passed with Python 3.12.13 and 74 active v3.0 rules; imports
resolved from the active worktree without foreign-checkout or editable contamination.

Scope covers normalization-failure implication, financial equivalence, subnormal
inputs, property domain, bounds, residual validation, multiple roots, fallback
semantics, warning/error-state isolation, evidence accuracy and DOC-02 applicability.
No other reviewer's initial conclusion was accessed before this disposition.

## Independently executed checks and challenges

The exact commands are retained in `DOMAIN_TOOL_COMMANDS.json`; the complete
original disposition identifies execution details and every reviewed source blob.
The main probe was governed Python `-c` with program SHA-256
`a3b11914f331cbf3d15f676a48108024a24af21bf3c88f67551da65734b58dff`:

- 3,312 exact-rational binary64 boundary comparisons passed. All 2,208 positive
  predictions raised the real library's finite-matrix `LinAlgError`.
- 54 analytic quadratic cases used 380-digit Decimal roots, three investment
  magnitudes, three return factors, both subnormal tails, sign reversal and delayed
  flows. Old/new/restored outcomes matched; maximum absolute root error was
  `4.299471889623874e-11`. Candidate normalization warnings were absent.
- 12 additional root/scale cases and 13 edge/residual cases passed.
- Two distinct mutation challenges were killed, with restored positives. A hostile
  eigensolver seam for `[-16, 38, -21]` preserved the valid -12.5% library root;
  a whole-library overflow-as-error mutation lost it to `None`. Disabling the
  preflight restored the original normalization warning.

A separate governed Python `-c` replay, SHA-256
`eb6b8756ed3f3b28d87d58d2e5dd1cdc31499aab477362d7001cfe0ec2335872`, directly
executed all 54 existing `test_irr_coverage.py` test functions with restoration and a
filesystem-write audit guard. This was direct test-body execution, not pytest
collection or a fixture-session run. `git diff --check <base> HEAD` passed; final
Git state was clean and the remote main identity matched the stated base.

## Predecessor findings and scope disposition

| Concern | Evidence and disposition |
|---|---|
| Normalization overflow warning | CLOSED within the declared path by real-library failure and independent numeric oracle. |
| Broad library context could alter root selection | CLOSED by the narrower implementation and hostile root-selection challenge. Injected roots are explicitly seam evidence, not observed real-input output. |
| Stale property introduction | CLOSED; prose now matches existing residual validation. |
| Subnormal/domain narrowing | CLOSED; original generator/property bodies preserved and subnormal controls passed. |
| Preformat probe attribution | CLOSED by final-source v3 and append-only binding 003; earlier bytes and records remain preserved. |
| Mutation-count precision | CLOSED by receipt 004: the writer exercised two variants across five killed test executions. |
| Other hygiene categories | NOT_APPLICABLE; outside this source scope. |

The source implication supports no numerical-output change for the inspected
CPython binary64 / NumPy 2.4.6 / numpy-financial 1.0.0 path. A true predicate
identifies an infinity in the original companion matrix, whose finite check
necessarily fails before eigenvalue computation; both paths reach the same
fallback with identical cashflows and bounds. A false predicate retains the
original library, bounds and residual path. The reviewer therefore accepts no
VERSION/model CHANGELOG bump under DOC-02 for this exact candidate.

## Residual limitations and authority

`ACCEPTED_RESIDUAL_WITHIN_SCOPE`: reciprocal overflow remains observable; dependency
or solver changes require fresh assessment; historical fallback tolerances,
conditional property coverage, extreme-input outcomes and nonconvergence behavior
are preserved. This is not universal IRR correctness or convergence assurance.
No current-candidate blocker remains. Final-head rebind and required hosted CI
remain delivery work; this receipt alone is not merge evidence.

Writer results are attributed: final-source finance regression was 1,350 passed,
one existing optional-pvlib skip; final focused tests passed 111. This reviewer did
not run a local full suite, full finance-suite pytest campaign, coverage, native
Grid Study, qualification, dependency operation or deployment. No professional,
lender, Board, release, issue-closure or HOLD authority changed; #1110 stays OPEN.

Exact originals and commands are retained under
`/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H06/delivery/` with the hashes
above. The owner verified the embedded independent-program hashes against the
preserved tool commands. See `H06_HANDOVER_2026-09-09.md` for common delivery identity.
