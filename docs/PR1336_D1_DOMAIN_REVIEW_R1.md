# PR #1336 D1 domain review — round 1

This is the durable, read-only domain review of the initial frozen D1 candidate. Its rejection is
the controlling predecessor disposition. Any successor that changes subject bytes requires a fresh
review; this record cannot be rebound as acceptance.

- Reviewer role: operational wind-plant assessment and renewable data-contract domain reviewer
- Reviewer identity: `/root/pr1336_domain_review`
- Candidate commit: `1c52e796a4c92887f0058c4391d90f9b55ddc298`
- Candidate tree: `be238e03a41f23c4d5e2cd80f593ca187a038b11`
- Base and merge base: `93823d55d60496a74936643c5038714b0df876f9`
- Subject-manifest SHA-256:
  `b41bc247069c7065f5f8e665d46793f8fa2f7c9019f20cebc54b126a10ca717e`
- Scope: PR #1336 / issue #1331 D1 operational-evidence contract; domain methodology,
  OpenOA-v3.2 translation, provenance/time/unit boundaries, D1/D2 separation, and authority fences
- Disposition: `REJECT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

## Corpus and rule identities

- `AGENTS.md`: SHA-256 `0969c6bce75908ad6fc1d6a9b00890c1875779a5e5e3a25be366c543de2f1778`.
- `go_with_the_flow_rules_v3_0_clean.csv`: SHA-256
  `5c8f1b163b3c65aa60fb93a333a0a11501ecb61ce414348fc85a0d2b3e4bed37`; parsed as 74
  active rules.
- RECRUIT-01 module SHA-256 values: module 1
  `32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e`; module 2
  `3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406`; module 3
  `2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7`; module 4
  `15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592`.
- Applied frameworks: `FRAMEWORK-01` CASPER, `FRAMEWORK-02` CESSPIT, and `FRAMEWORK-03`
  CCCDIR.
- Other controlling rules: `DATA-01`, `VERIFY-01`, `PERSIST-01`, `RECRUIT-01`,
  `DELIVERY-01`, `WORKTREE-01`, `GOV-02`, `R23`, `R25`, and `MERGE-01`.
- Live sources read: issues #1330, #1331, #1332, and #1110; PR #1336 body and comments.
- OpenOA comparator: tag v3.2, dereferenced commit
  `35e8a52c4cd8f43223f8181153d4e3f083f090d2`; tagged README SHA-256
  `767118f51658d0d36a595d2d09deb3959ad16eb7c9a6fe971fb1e73e78f254f7`;
  `openoa/schema/metadata.py` SHA-256
  `bf2f3d9fae20abc24b90efe6044855630c724ac7c710a07065b314ca80089620`;
  `openoa/plant.py` SHA-256
  `0686b8ad8e7ca732bdb00038ea084d3e98997038d0f809aa50e064ca900a790d`;
  `openoa/analysis/aep.py` SHA-256
  `19afc5ddbaec4cd5a1bfc367aaaa2780446ddf9d66cc3752b9020f62d41e9441`.

## Subject-object verification and checks

All seven working-tree files independently matched the frozen candidate blobs:

```text
analytics/contracts_v14.py                           cbd90d1a9a8d0c2decda0444fc3025fc319558cf
analytics/operational/__init__.py                    5d9529a34cc6bb528892d5708dd761898795b33f
analytics/operational/contracts.py                   d2fb6da03190a5bc2e944b419dbd343f76f3d040
changelog.d/operational-evidence-contract.added.md   5396c84762f6ec01c6edac3894420cc812bf2453
docs/ISSUE_1331_IMPLEMENTATION_RECORD.md             aa7251407bcf0f7698c8818201706b5758c71552
tests/contracts/test_contracts_v14_import_surface.py e1c8dce51d9556c25aa75269e7d8fed835a810da
tests/contracts/test_operational_evidence_contract.py ea2efc0271f3fe89d6b42738b2788e94401fcbf7
```

The worktree and index were clean, and local and GitHub refs matched the candidate and base. The
reviewer recomputed the sorted subject manifest, inspected the complete source/test bodies and
public re-export, read the tagged OpenOA README, `PlantData`, `ANALYSIS_REQUIREMENTS`, and
MonteCarloAEP source, and independently mapped all five purposes. Dataset and role mappings agreed
with the corresponding analyses; the additional timestamp roles were a reasonable strengthening;
and status data was correctly representable without being fabricated as a minimum.

Writer-authored pytest, mypy, pre-commit, and changelog checks were not rerun. Their receipts were
inspected, while an independent hostile oracle found the blockers below.

## Independent hostile oracle

```text
annual_wake_interval_accepted=
[('scada', 31536000), ('reanalysis', 31536000), ('asset', None)]

cross_product_role_union_accepted=
[('era5-wind', ['timestamp_utc', 'wind_speed_ms']),
 ('merra2-density', ['air_density_kgm3'])]

timezone_treatment_present=False
observation_status_present=False

unhashable_kind_exception=
TypeError unhashable type: 'list'
```

This proved that annual wake-loss inputs passed, unrelated products could jointly manufacture a
required role set, two issue-mandated provenance fields were absent, and malformed inputs escaped
the declared contract error surface.

## Findings ledger

### `D1-DOM-001` — `BLOCKS_CURRENT_CANDIDATE`

Issue #1331 requires every dataset to bind both timezone treatment and observation status. Neither
field existed. UTC coverage and a `timestamp_utc` role did not preserve whether source timestamps
were natively UTC, offset-aware, or converted with a named zone. `source_class` was broad
provenance, not observation/derivation status. The reviewer required closed, runtime-validated
declarations with hostile tests, while preserving D1 as metadata declaration and D2 as conversion
and verification.

### `D1-DOM-002` — `BLOCKS_CURRENT_CANDIDATE`

The candidate omitted the OpenOA purpose-and-kind frequency minima: MonteCarloAEP monthly or finer;
TurbineLongTermGrossEnergy daily or finer; ElectricalLosses SCADA daily or finer and meter monthly
or finer; WakeLosses hourly or finer. A positive interval alone admitted annual wake evidence. The
reviewer required purpose/kind sampling limits, explicit calendar-frequency treatment, and positive
and negative boundary tests.

### `D1-DOM-003` — `BLOCKS_CURRENT_CANDIDATE`

Required roles were unioned across all datasets of one kind. The test suite intentionally accepted
wind speed from one reanalysis product and density from another, despite there being no bundle
identity, join key, product identity, co-temporality rule, or derivation relationship. The reviewer
required at least one individually complete logical dataset per required kind, or an explicit
provenance-bound join contract.

### `D1-DOM-004` — `BLOCKS_CURRENT_CANDIDATE`

Malformed untyped values such as `kind=[]` raised raw `TypeError` during set membership. Comparable
exposure existed for other membership-based vocabularies. The reviewer required predictable
`OperationalEvidenceError` failures and hostile unhashable-value tests.

## Predecessor findings and residual limitations

- `KIMI-FALSE-BESS-GAP`: `CLOSED`; existing BESS finance, LCOS, project-economics, grid capability,
  and tests were verified, and D1 added no duplicate layer.
- `OPERATIONAL-LAYER-ABSENCE`: `RECURS`; D1 started the missing operational layer but did not yet
  meet its own acceptance.
- `AUDIT-1110-HOLD`: deferred to #1110; the issue remained open and D1 did not affect its HOLD.
- `D1-D2-BOUNDARY`: `RECURS`; byte verification, normalization, UTC conversion, duplicate/gap
  checks, and QA correctly belonged to #1332, but D1 lacked declarations D2 must consume.
- The remaining unit, immutability, digest-syntax, UTC-coverage, unique-ID, assessment-coverage, and
  hard authority-fence directions were otherwise sound. OpenOA was correctly treated as research
  software and a comparator rather than professional or bankability authority.

## Authority boundary

This rejection granted no merge, release, issue-closure, lender, Board, professional, publication,
finance, or HOLD authority. Issue #1110 remained open and its Board/lender reliance HOLD remained
fully active.
