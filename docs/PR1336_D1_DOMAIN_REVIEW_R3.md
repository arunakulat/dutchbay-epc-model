# PR #1336 D1 domain review — round 3

- Reviewer: operational wind-plant assessment and renewable data-contract domain reviewer,
  `/root/pr1336_domain_review_refresh`
- Candidate: `f818a084d2ea0367aac18ca720577fb19327a826`
- Tree: `56a83dc1e06140e8f28c8f4d9e25d500172241e1`
- Base and merge base: `3b352034f74254af8b8baeb4d8cf9181ad252cb2`
- Subject-manifest SHA-256:
  `2136a8a0b47285b6238a6c722acceb1bebf67cc72d1fff6dc730f747243a702f`
- Disposition: `REJECT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

The reviewer reconstructed all eleven subject blobs and the manifest from Git objects, matched the
PR/local/base identities, read the full subject, governance and OpenOA v3.2 comparator corpus, and
remained blind to the concurrent assurance conclusion.

Independent checks passed 92 focused tests, strict mypy and `git diff --check`; replayed all five
purposes, 12 fixed-cadence pairs, four allowed and three disallowed calendar routes, and 15
split-product role sets; exercised 13 invalid timezone combinations and a real New York fold-0 /
fold-1 DST counterexample; and rejected malformed/duplicate/missing/non-derived lineage states.

## Reconciliation

`D1-DOM-001` through `D1-DOM-005`, assurance `A-01` and `A-02` were closed. Assurance `A-03`
remained deferred to #1332. `D1-DOM-006` recurred only through the cross-role digest identity below.

## `D1-DOM-006-R3` — `BLOCKS_CURRENT_CANDIDATE`

The flat derived-evidence record did not require its three artifact roles to be disjoint. All three
counterexamples were accepted:

```text
lineage_source_sha256 = (source_sha256,)
derivation_method_sha256 = source_sha256
derivation_method_sha256 = lineage_source_sha256[0]
```

The first is a content-addressed self-edge; the others collapse the method artifact into output or
upstream data. The bounded correction is to validate the output digest before lineage cross-checks
and reject all three collisions. Supporting intentional role identity would require a broader
artifact-occurrence graph and is outside D1.

## Residuals and authority

A 31-day ceiling cannot prove calendar cadence, and exact conversion depends on timezone-database
revision and implementation. Issue #1332 owns actual cadence, conversion execution, tzdb identity,
byte verification and derivation recomputation. These residuals do not lift issue #1110's HOLD.

This rejection blocked readiness and merge and granted no release, lender, Board, professional,
publication, issue-closure, canonical-finance, bankability or HOLD authority.
