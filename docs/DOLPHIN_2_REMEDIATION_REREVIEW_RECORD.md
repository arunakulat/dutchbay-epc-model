# Dolphin 2 remediation rereview record

**Record status:** independent veto, remediation and final exact-tree acceptance record
**Reviewed surface:** uncommitted `codex/feasibility-report-machine-contract` tree based on
`22d342ac32b7921de9b5cde0156f483fecf26294`
**Review roles:** renewable-project domain specialist and audit/assurance specialist
**Authority boundary:** these specialist AI reviews are not statutory assurance, external audit,
lender acceptance, verified human professional sign-off, achieved-grade authority or package
release authority.

## 1. Relationship to the first review

[`DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md) is the immutable
first-review record. It remains unchanged and continues to prove the original A-K/domain 1-11 veto
surface. This separate record preserves the second exact-tree rereview, the consolidated
remediation and the final specialist dispositions. Neither record lifts any audit,
lender, Board or release `HOLD`.

## 2. Exact second-pass predecessor fingerprints

The second rereview was performed before the L-S/N5-N8 remediation against files with these
SHA-256 fingerprints:

```text
acbb1d1b4b881a4bc1cda99da43677df282145756f4698cae809df8a19736bd1  analytics/contracts_v14.py
ce1240affc8a64ca6553415f14d49695af945b0e75d2ce0b0af375b07a57dc99  analytics/feasibility_report_contract/__init__.py
5220d1f637ba8599c0c560ea28c1733a9dd4451a0b42414e8cb523549b21a6ae  analytics/feasibility_report_contract/vocabulary.py
c3d0aebc8b231261e4b5f60b2904c6abe0d5ea7596befc970ddf54f9d9aac223  analytics/feasibility_report_contract/records.py
ac7fba36df90de405d4f35f4636f31249fe55532fb294a8afc53ef19c3483ff8  analytics/feasibility_report_contract/package.py
716f7944794efbc494679abda70741156f76a782add6dbac27c04080e079d382  changelog.d/feasibility-report-machine-contract.added.md
756fbe34f2dd67813dc0412e3257539537612cc90822f140f66b76c5bfaf52e0  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
9f7ff5e058005d94eb2b48238710e918f0bf86f92b8c9ea0378d74b2598abe76  docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
a793ad3f3955672ddb27b1fee6baae97995e99a489214e9e37056ec604f681a7  docs/SESSION_HANDOVER_2026-08-28_6.md
06b5a1147b9d9fc9da670d0d88ca67b79a5593b524415ee12378255d3f648a8d  tests/contracts/test_feasibility_report_machine_contract.py
```

The first-review record's historical pre-delivery fingerprint was
`756fbe34f2dd67813dc0412e3257539537612cc90822f140f66b76c5bfaf52e0`; the remediation did not
rewrite its evidence or findings. At the final staging boundary, `git diff --check` exposed exactly
three Markdown hard-break trailing-space markers in its metadata lines. Those three whitespace
markers were removed without changing any word, line ordering or review content, producing the
delivery fingerprint `69827eb77903f3efbc5b88bf3bd8dceef42219529839d9ca67de6b720f1395d1`.
Both hashes are retained here so the normalization is auditable rather than silent.

## 3. Second independent dispositions

**DOMAIN VETO.** The second domain pass required:

- **N5:** exactly one record for each of the six `ReconciliationFamily` values; empty, missing,
  duplicate and all-same family sets must fail, while every accepted record must be an honest
  operand-bound pass/failure or a reasoned N/A;
- **N6:** a typed jurisdiction-to-governed-subject mapping with an exact disposition pack, one
  jurisdiction per v1 jurisdiction pack and a real reciprocal section contribution;
- **N7:** one technology type per v1 technology pack and truthful multi-pack type coverage, proven
  by controlled two-jurisdiction and wind-plus-BESS fixtures without pretending D3 asset topology;
  and
- **N8:** an `ASSURED` pack owner, independent reviewer and assurance authority must have the human
  or institutional identity, organization, authority and producer-independence needed by their
  distinct roles.

**ASSURANCE VETO.** The second assurance pass admitted or could not prove refusal of these classes:

| ID | Blocking class |
|---|---|
| L | A performed human responsibility could be authorized by software/AI or by a person other than the exact performer despite no delegation model. |
| M | An `ASSURED` pack lacked sufficiently strict verified owner, distinct-person reviewer, distinct-organization reviewer and independent assurance-authority constraints. |
| N | A source whose effective date was after the evidence cutoff could support a current pack or claim. |
| O | Report-bound reviews or decisions could predate creation of the report identity, or lifecycle timestamps had no honest package snapshot bound. |
| P | Artifact/release authorizations were not completely ordered against artifact creation and the package snapshot. |
| Q | Pack review or assurance evidence could cite sources outside the exact pack without a typed compatibility edge. D2 v1 has no such edge. |
| R | A typed `HOLD` release could retain authority, decision or decision-date metadata that implied a positive authorization. |
| S | A pack-assurance subject could name a review superset rather than the exact qualifying independent review set. |

## 4. Consolidated implementer remediation

The uncommitted remediation now:

- makes every performed `Prepared`, `Checked`, `Reviewed` and `Approved` role name the exact
  verified organized human performer as its positive decision authority; software/AI and undeclared
  delegation are refused;
- requires an assured pack owner to be a verified human/institution with organization and authority
  basis; requires a distinct human reviewer from a distinct non-null organization; and requires the
  assurance authority to be identity- and organization-independent from the producer;
- rejects a current source whose effective date postdates the evidence cutoff and binds review and
  assurance evidence to relevant, usable evidence whose source is in the exact pack;
- adds required root `captured_at` snapshot semantics: report/run creation cannot postdate capture;
  contained artifacts, decisions, completed reviews and authorized release cannot postdate capture;
  report-bound reviews/decisions cannot predate report creation; completed-review decisions cannot
  predate completion; and artifact-bound decisions/reviews cannot predate the artifact. Pack reviews
  may legitimately predate report creation. Evidence cutoff remains a source/evidence currency
  boundary rather than a universal review timestamp;
- makes typed `HOLD` release incompatible with authority, decision and decision-date metadata and
  requires an assured decision's review IDs to equal the exact qualifying set;
- requires exactly six unique reconciliation families and honest N/A or real pass/failure operands;
- adds `JurisdictionSubjectBinding` plus typed governed-subject vocabulary and exact reciprocal
  disposition-pack contribution; and
- constrains each jurisdiction/technology pack to one axis value while accepting controlled
  two-jurisdiction and wind-plus-BESS type-level fixtures. Those fixtures prove only contract
  expressiveness, not a second real golden path or D3 project asset topology.

All repairs trace to DBAY-FRC-001 sections 3-6, 8.1-8.2, 9.1-9.4, 10.1-10.6 and 12.1-12.3, and to
the controlled D0 scope, responsibility, caveat, reconciliation, provenance and distribution
blocks. The repair does not implement grade aggregation, asset topology, orchestration, canonical
hashing, adapter migration, audit acceptance or release.

## 5. Implementer retest receipt

The exact final commands, results and remediated file fingerprints are recorded in
[`SESSION_HANDOVER_2026-08-28_6.md`](SESSION_HANDOVER_2026-08-28_6.md). Those are implementer
receipts only; conventional green checks cannot replace the two specialist dispositions below.

## 6. Third exact-tree veto and final remediation

The third independent review inspected the second-remediation tree with these controlling
predecessor fingerprints:

```text
c617d6cabaedb4fa4da351124c8071afbc71382ed3e413b4565fbd27f8bdee8a  analytics/contracts_v14.py
ce1240affc8a64ca6553415f14d49695af945b0e75d2ce0b0af375b07a57dc99  analytics/feasibility_report_contract/__init__.py
786557a839f353ba73cebd3d81902a944165c4ffdb0aa45fcb065e3db37f81c4  analytics/feasibility_report_contract/vocabulary.py
324b08e689147f0c3158a97fdae7d6ff9bd3d70805fb001b73f6490cd15b573e  analytics/feasibility_report_contract/records.py
c6406f20b20a5c52105cdb6b3fc1dd18b149608d26f69d89d696104c3c2c70e7  analytics/feasibility_report_contract/package.py
c3451807108f2c7508108ffa1550e4d2e0ea8b4024e49abc9cd2cbd3845705c7  changelog.d/feasibility-report-machine-contract.added.md
756fbe34f2dd67813dc0412e3257539537612cc90822f140f66b76c5bfaf52e0  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
a8d5275560124e74e89f2bc1b8d8cfa1da73cffa8dd45e0b925523bcb11c5587  docs/DOLPHIN_2_MACHINE_CONTRACT_CHARTER.md
092c66789da617835fd75ad40f707b315c8b8a31ad984bb4d6ee444415a64239  docs/DOLPHIN_2_REMEDIATION_REREVIEW_RECORD.md
274dd7de8ae2d6e163c07ed44f371cdd3354ae346d3dc60589f46ee46d544e48  docs/SESSION_HANDOVER_2026-08-28_6.md
a143879a398e8507b2efd80c1fe2c7409d14bcca82ab55f96df5a6c2e23d1c92  tests/contracts/test_feasibility_report_machine_contract.py
```

**DOMAIN VETO U1.** The prior `JurisdictionSubjectBinding` required a supported or assured
"resolving" pack and therefore could not honestly represent a scoped jurisdiction that is known to
be unsupported. The final repair renames the neutral edge to `disposition_pack_id`. A supported or
assured disposition retains the existing exact one-axis contribution rules. An unsupported
disposition instead requires the exact scoped one-axis `UNSUPPORTED` jurisdiction pack, reciprocal
affected sections, and exactly one matching `UnsupportedJurisdictionCapability` per affected
applicable section. Each such section is explicitly `not_run_unsupported_jurisdiction`, with typed
consequence and remedy. Wrong pack kind, wrong jurisdiction, Sri Lankan fallback, duplicate router
identity, duplicate governed-subject mapping and silent affected-section omission fail closed. The
positive Fictionland fixture remains held and ungraded.

**ASSURANCE VETO T1-T7.** The third assurance pass required complete lifecycle and distribution
authorization semantics:

- **T1-T3:** every performed report responsibility, for all four human roles, must satisfy
  `ReportIdentity.created_at <= performed_at <= supporting decision.decided_at <= captured_at`;
- **T4/T7:** every held or authorized artifact must satisfy
  `ReportIdentity.created_at <= artifact.created_at <= captured_at`;
- **T5:** pack assurance cannot predate any qualifying review's completion or its signed review
  decision;
- **T6:** authorized release must name exact typed `distribution_ids`; the selected current controls
  must be every control governing a released artifact, cover exactly the released artifact set and
  remain unexpired at `captured_at`; a held release carries no distribution authorization; and
- all lifecycle event timestamps, including `ValidationRecord.checked_at` and section production
  start/completion, are bounded by the package snapshot. Prospective semantic dates are not confused
  with lifecycle events: valuation dates, pack/review effective-until periods and expiry/review dates
  may describe a future basis or control horizon. Evidence cutoff remains the currency boundary for
  sources and evidence, current pack/source effective dates cannot follow that cutoff, and a release
  control's prospective expiry must not already have passed at capture.

This final implementer repair adds no applicability policy, asset topology, grade aggregation,
canonical hashing, delivery adapter or release authority. Live issue `#1110` and all audit/lender/
Board/release gates remain unchanged and held.

## 7. Final exact-tree dispositions

The final independent passes were bound to the following implementation and test fingerprints:

```text
3bf271c3008b6eb3c4b08a1f8ec2311c6e6ebc026a9965a65b1e5975b0535760  analytics/contracts_v14.py
786557a839f353ba73cebd3d81902a944165c4ffdb0aa45fcb065e3db37f81c4  analytics/feasibility_report_contract/vocabulary.py
d130d63d8d165ea5d74db0a87a8bc453d2e51c9306ade65a3618218cc104d2e0  analytics/feasibility_report_contract/records.py
f4fef3b85a061cff5bb8ecf74d21fc2782a73a009226ddee1fa3d8adfa233454  analytics/feasibility_report_contract/package.py
4fa17fcd294ef828eed6a0084f093b4e74db1945b06fd4f7864042d0e34f2e5f  tests/contracts/test_feasibility_report_machine_contract.py
69827eb77903f3efbc5b88bf3bd8dceef42219529839d9ca67de6b720f1395d1  docs/DOLPHIN_2_INDEPENDENT_REVIEW_RECORD.md
```

They also reviewed the then-current charter, this rereview record and successor handover at the
fingerprints recorded in `SESSION_HANDOVER_2026-08-28_6.md`. The acceptance text below is the
primary agent's faithful transcription of their returned dispositions; appending that receipt and
updating the successor changes only those documentation hashes, not the accepted implementation or
test fingerprints.

**Domain final exact-tree disposition: ACCEPTED.** The independent domain specialist recomputed the
frozen fingerprints before and after a 28-case replay of U1, N5-N8 and the original domain 1-11
counterexamples. The honest scoped Fictionland
`UNSUPPORTED` disposition remained accepted and held; omission, wrong-pack, wrong-state,
wrong-capability and Sri Lankan-fallback variants were rejected. Exact six-family reconciliation,
single-axis jurisdiction and technology packs, genuine type-level multi-pack fixtures and assured-
pack boundaries remained constructive. The broadened 231-test gate, the 171-test contracts gate
and static checks passed. This accepts the D2 representation boundary only; it does not establish a
real second-jurisdiction pack, achieved grade, project feasibility or release authority.

**Assurance final exact-tree disposition: ACCEPTED.** The independent assurance specialist
recomputed the frozen fingerprints before and after the complete bounded proof, re-entered the
governed Python 3.12.13/72-rule environment, passed the 143-test machine-contract A-S regression
surface and passed a separately selected 29-test T1-T7, U1, lifecycle and exact-distribution proof.
The 171-test contracts gate, 231-test broadened gate, Ruff check and format, Black, isort, mypy,
Draft 2020-12 schema/instance and `git diff --check` also passed. Performed-human, artifact,
validation, section-production, assurance-decision and distribution-control chronology now fail
closed at their exact boundaries.

These are specialist AI review dispositions, not statutory assurance, external audit, verified
human professional sign-off, lender acceptance, achieved-grade authority, pack approval or
package-release authority. They do not lift any live project, evidence, audit, Board, lender,
P01/P02/P03, F5-01/F5-02, resource/grid or package-release `HOLD`. Live issue `#1110` remained
open with 0 checked and 23 unchecked release gates at the final assurance query.
