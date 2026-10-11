# PR #1336 refreshed D1 domain review — round 2

This record preserves the independent domain disposition on the origin/main-refreshed candidate.
Its `REJECT` controlled the review union and blocked readiness and merge.

- Reviewer role: operational wind-plant assessment and renewable data-contract domain reviewer
- Reviewer identity: `/root/pr1336_domain_review_refresh`
- Candidate commit: `a0ff5cff09514a6e0a6e1fa1cb7f88098017415f`
- Candidate tree: `ab206638119bafde69307947cecf769e0b4930a5`
- Base and merge base: `3b352034f74254af8b8baeb4d8cf9181ad252cb2`
- Subject-manifest SHA-256:
  `2522934fbc6f12b27dbbb4935d1c1e5c8a266c54e6185371dcbf0ab71afc9917`
- Disposition: `REJECT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

## Object and refresh verification

The reviewer independently reconstructed the same nine-blob manifest recorded in
`PR1336_D1_ASSURANCE_REVIEW_R2.md`, verified its digest, and proved the refresh merge parents,
merge base and subject-byte identity. The incoming #1324 workflow, changelog and grid-policy test
were bidirectionally isolated from D1.

Focused tests passed 78 tests in 1.62 seconds, strict mypy was clean, and `git diff --check` passed.
An independent production-only oracle accepted all five exact purpose minima; exercised all 12
non-asset fixed-seconds boundaries, four permitted calendar routes and three purpose-disallowed
calendar routes; rejected all 15 split-product role sets; rejected eight hostile unhashable values
with `OperationalEvidenceError`; and rejected `bankable=True` laundering. Tagged OpenOA v3.2
requirements matched the purpose/kind/role/cadence translation.

## Predecessor reconciliation

- `D1-DOM-001` through `D1-DOM-004`: `CLOSED` mechanically. New semantic sufficiency findings
  `D1-DOM-005` and `D1-DOM-006` applied.
- Assurance `A-01` and `A-02`: `CLOSED`.
- Assurance `A-03`: deferred to #1332 and did not independently block D1.
- Issue #1110 remained open and controlling.
- The D1/D2 execution boundary was otherwise correctly preserved: no I/O, parser, estimator,
  report or finance path was introduced.

## `D1-DOM-005` — `BLOCKS_CURRENT_CANDIDATE`

A `named_zone_to_utc` declaration did not identify the named zone or the DST
ambiguity/nonexistent-time policy. The same naive source could therefore be declared under
materially different conversions without changing any contract field. D2 could not reproduce or
challenge the intended conversion from the D1 object.

Required correction: bind the source timezone or an immutable conversion-policy identity,
conditionally validate it against `timezone_treatment`, and retain D2 as the execution and
verification layer. Named-zone conversion must carry an IANA zone and declared ambiguous- and
nonexistent-local-time policies. Asset, source-UTC and offset-aware cases must reject inapplicable
combinations.

## `D1-DOM-006` — `BLOCKS_CURRENT_CANDIDATE`

`observation_status` was a deterministic restatement of kind/source class and could not represent
derived operational evidence. OpenOA describes curtailment inputs as loss estimates, but the
candidate forced every curtailment dataset to claim `observed` and rejected `derived_estimate`.

Required correction: make epistemic status independently meaningful. At minimum, admit and
validate derived/estimated curtailment evidence, preserve its lineage, and never force transformed
or estimated values to claim direct observation. The contract must support per-column status or
explicitly prohibit mixed-status logical datasets.

## Residuals and deferrals

- `D1-DOM-R01`: accepted residual. A 31-day fixed-seconds ceiling cannot prove calendar-consistent
  monthly series; #1332 owns observed cadence, gaps, duplicates and drift.
- `D1-DOM-D02`: byte hashing, normalization, actual-cadence and table-content QA remain correctly
  assigned to #1332. Future receipts must include deterministic source/derived digests, UTC/DST
  conversion, non-finite/gap/duplicate/interval-drift checks and declared-versus-observed cadence.

The OpenOA mapping, UTC coverage, immutability, SHA syntax, unique IDs, complete-product rule,
unit-bearing roles, public facade and hard-false reliance flags were otherwise sound.

## Authority boundary

This rejection blocked readiness and merge and granted no release, lender, Board, professional,
publication, issue-closure, canonical-finance, bankability or HOLD authority. Issues #1331 and #1110
remained open, and #1110's Board/lender reliance HOLD remained fully active.
