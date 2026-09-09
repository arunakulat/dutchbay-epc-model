# H06 assurance review receipt — 2026-09-09

This is the delivery owner's compact transcription of an independent disposition.
The exact original body is preserved unchanged outside Git and identified below.
The reviewer must verify this transcription at the final delivery-head rebind.

```yaml
reviewer_role: independent_read_only_assurance
reviewer_identity: 01a083f0-ae72-7490-bafe-022063ced573
reviewer_agent: /root/h06_assurance
model: gpt-6-astra
reasoning_effort: xhigh
configuration_evidence: actual session_meta and turn_context; independently checked by delivery owner
risk_class: R3_CONSEQUENTIAL
candidate_commit: 84beded0d4b460f3b668aeed58c52f244ecbbac2
candidate_tree: 5ecc3d38352d1366334d7d076d45315dbd026a91
base_sha: 3cc3d0ebba1d09c27c17556a2c40ee379904b969
merge_base_sha: 3cc3d0ebba1d09c27c17556a2c40ee379904b969
subject_manifest_sha256: 8c9d8882c34b1412aa3ffac3b9340594e0dd87149b34f5fe916798ab3a8ff7fb
original_body_sha256: 13e271948aa28ba8593dad87f0d2c628e651a51c60bf5cf2afad53c7e9123277
exact_tool_commands_sha256: ec9cd6c50b6df5763ab75090d0e2368593d57e0c4a1fd6bea870e01dc39c6f3e
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

The exact commands are retained in `ASSURANCE_TOOL_COMMANDS.json`; the complete
original disposition identifies execution details and every reviewed source blob.
The independent governed-Python heredoc program has SHA-256
`5762799dc115c8d8c739d4b35c36215b86c109c894237cdcb02aa9ff2a66d41b`:

- 4,108 exact-rational binary64 boundary cases, seed `960609`, had zero false
  positives or negatives. All 527 positive predictions raised real installed
  `numpy_financial.irr` finite-matrix `LinAlgError`.
- 30 old/new/restored controls across NumPy `warn`, `raise` and `ignore` overflow
  policies matched exactly. These are controlled diagnostic contexts, not a
  production warning filter.
- The independent quadratic `[0, -100, 0, 121, -1e-310, 0, -0]` returned
  `0.09999999999962174`, within 1e-9 of the analytic 10% root.
- An injected incorrect in-band 40% result for `[-100,110]` was rejected by the
  existing residual guard and recovered the 10% fallback.
- Two distinct mutation variants were killed: always-true preflight lost a valid
  multiple root, and disabled preflight restored a normalization warning.
  Restored positives and original warning/error/function state all matched.
- Four original property/test function ASTs remained identical.

`git diff --check <base> <candidate>` passed. Independent object/corpus checks
matched commit/tree/base, all subject disk/Git blobs, manifest and ingress digests;
v2/v3 probe program bytes were identical. Final Git state was clean and the live
protected main identity matched the stated base.

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
