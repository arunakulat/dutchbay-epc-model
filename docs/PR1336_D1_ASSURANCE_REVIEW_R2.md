# PR #1336 refreshed D1 assurance review — round 2

This record preserves the independent assurance disposition on the origin/main-refreshed candidate.
It is historical evidence only. The domain reviewer rejected the same candidate, so the union
disposition was `REJECT`; later subject-byte remediation invalidates this acceptance for successors.

- Reviewer role: independent Python contract, provenance, failure-mode and delivery assurance
  reviewer
- Reviewer identity: `/root/pr1336_assurance_review_refresh`
- Candidate commit: `a0ff5cff09514a6e0a6e1fa1cb7f88098017415f`
- Candidate tree: `ab206638119bafde69307947cecf769e0b4930a5`
- Base and merge base: `3b352034f74254af8b8baeb4d8cf9181ad252cb2`
- Subject-manifest SHA-256:
  `2522934fbc6f12b27dbbb4935d1c1e5c8a266c54e6185371dcbf0ab71afc9917`
- Disposition: `ACCEPT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

## Exact subject manifest

```text
analytics/contracts_v14.py	471a696a1e7b659b223ce745ec531abf689ca350
analytics/operational/__init__.py	1f0ca290e86e9594f4501193d0b3ecc4a562c686
analytics/operational/contracts.py	d8aa4f4ab4e4b805c85ee27448979a74081c0409
changelog.d/operational-evidence-contract.added.md	9c9c08f52bbaab411afc0313e5540e34dc4e6f7d
docs/ISSUE_1331_IMPLEMENTATION_RECORD.md	629ff508b1eef970d37088a7393ccd2c31ff3acb
docs/PR1336_D1_ASSURANCE_REVIEW_R1.md	e590765c1ade9f6e448ee390fccfa2da77c5f53d
docs/PR1336_D1_DOMAIN_REVIEW_R1.md	4adb04ffa723b6fc74c252d8d20b2c6ec683a26b
tests/contracts/test_contracts_v14_import_surface.py	4cdb6f4bb5f2c84d71d8d037db17dfd6dd07790f
tests/contracts/test_operational_evidence_contract.py	1d0d4a801aa120f88a8a4d87ab7af10350500586
```

The reviewer independently reconstructed the sorted manifest from Git objects and verified its
digest. The merge parents were the pre-refresh D1 head `34b3ad4f55e06e8b572a4c11d4bbdd3436e765c0`
and current base `3b352034f74254af8b8baeb4d8cf9181ad252cb2`. All nine subject blobs remained
byte-identical, and the incoming #1324 workflow/test changes were bidirectionally isolated from D1.

## Independent checks

The reviewer read all nine blobs and independently challenged mappings, cadence boundaries,
calendar routes, hostile vocabulary values, completeness, immutability, facades, import safety,
authority fences, receipts and D1/D2 separation. The independent oracle reported:

```text
independent_oracle=PASS purposes=5 hostile_values=48 cadence_pairs=15 facade_surfaces=3 immutable_maps=6
```

It rejected split-product role union, all authority-flag laundering attempts and 48 hostile values;
proved all fixed/calendar cadence boundaries; proved nested maps immutable and facade class identity;
and confirmed standard-library-only production imports. Supplementary focused tests passed 78 tests
in 1.49 seconds. CI was still running and was not used as the semantic oracle.

## Finding reconciliation

- `A-01`: `CLOSED`; closed-vocabulary values are type-guarded before membership.
- `A-02`: `CLOSED`; all aliases are exported through the three public facades.
- `A-03`: deferred to #1332; D1 declarations do not verify bytes or table content.
- `D1-DOM-001` through `D1-DOM-004`: `CLOSED` by the new declaration fields, cadence maps,
  one-product rule and predictable contract errors.
- `A2-01`: deferred to #1332. D1 named the timezone-treatment class but not the concrete IANA zone
  or DST policy. The reviewer accepted this as a future normalization-receipt obligation.
- `A2-02`: deferred to #1332. Dataset observation status was coarse and did not distinguish direct,
  operator-declared and analytically derived loss values. The reviewer accepted this as a future
  lineage-receipt obligation.
- `A2-03`: accepted residual. A 31-day ceiling declares a maximum but cannot prove real calendar
  cadence, completeness or absence of gaps.

No assurance finding independently blocked this candidate. The later domain review made `A2-01`
and `A2-02` blocking D1 representational requirements, and that stricter disposition controlled.

## Authority boundary

This review granted engineering assurance acceptance only. It granted no merge, release,
issue-closure, lender, Board, professional, publication, canonical-finance, bankability, deployment
or HOLD authority. Issue #1110 remained open with its Board/lender reliance HOLD fully active.
