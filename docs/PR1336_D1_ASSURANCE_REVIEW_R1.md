# PR #1336 D1 assurance review — round 1

This is the durable, read-only assurance review of the initial frozen D1 candidate. It is
historical evidence, not an acceptance of any successor. The independent domain review rejected
the same candidate, so the union disposition was `REJECT` and the candidate was not mergeable.

- Reviewer role: independent Python contract, provenance, failure-mode and delivery assurance
  reviewer
- Reviewer identity: `/root/pr1336_assurance_review`
- Candidate commit: `1c52e796a4c92887f0058c4391d90f9b55ddc298`
- Candidate tree: `be238e03a41f23c4d5e2cd80f593ca187a038b11`
- Base and merge base: `93823d55d60496a74936643c5038714b0df876f9`
- Subject-manifest SHA-256:
  `b41bc247069c7065f5f8e665d46793f8fa2f7c9019f20cebc54b126a10ca717e`
- Disposition: `ACCEPT`
- Mutation attestation: `READ_ONLY_NO_MUTATION`

## Corpus and rule identities

- `AGENTS.md` blob `98ca2509de9e9b54cbc82d857ccd6d658b4ab9ba`.
- Complete 74-row GWTF CSV blob `5102d0cdcdaa34c546a6351aed41f28a53f27cfa`.
- RECRUIT-01 modules 1–4 blobs `4b5cdfb`, `9c088a8`, `b661641`, and `b2f1963`.
- `FRAMEWORK-01` CASPER, `FRAMEWORK-02` CESSPIT, and `FRAMEWORK-03` CCCDIR.
- Issues #1330 and #1331; PR #1336 body, comments, receipts, and exact-head state.
- Corrected comparative record blob `a5cb8dddfce9c18f7e2072ee3ddd8044da23b76d`.
- Existing resource-contract and facade convention blobs `8645514`, `7176114`, and `76ef38f`.
- OpenOA v3.2 annotated tag `d580ee6bc14d20e384dbb861278428cb840818a5`,
  commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2`.

## Scope and checks

The reviewer read all seven substantive blobs and their production and test bodies; examined the
frozen dataclass graph, serialization, runtime validation, vocabularies, digest/time/coverage and
cross-kind checks, reliance fences, re-export topology, OpenOA v3.2 translation, documentation,
changelog, authority and D2 deferral boundaries; and independently verified the candidate identity,
tree, parent, merge base, sorted manifest, and every declared blob ID.

Independent checks established that:

- the new production module imports only the standard-library modules `__future__`, `dataclasses`,
  `datetime`, `re`, `types`, and `typing`;
- an independently built long-term-AEP envelope serialized through `json.dumps`;
- nested fields remained tuples and frozen dataclasses, while top-level and nested mappings rejected
  mutation;
- `dataclasses.replace()` could not elevate bankability or change dataset kind without satisfying
  the source-class invariant;
- runtime class identity was identical through `analytics.operational`,
  `analytics.contracts_v14`, and `analytics.contracts`; and
- all five purpose-to-kind and purpose-to-role minima matched the tagged OpenOA v3.2
  `ANALYSIS_REQUIREMENTS` translation.

The reviewer did not rerun writer-authored pytest. Exact-head CI was still running and was outside
this semantic disposition.

## Independent oracles and counterexamples

1. Reconstructed valid long-term-AEP evidence independently and proved JSON serialization plus
   facade identity.
2. Attempted finance laundering using `dataclasses.replace(bankable=True)`; construction rejected
   it with `OperationalEvidenceError`.
3. Attempted to launder revenue-meter evidence as reanalysis; construction rejected the resulting
   source-class mismatch.
4. Attempted top-level and nested mapping mutation; all attempts failed.
5. Supplied unhashable list values as role, unit, kind, and purpose; every construction failed before
   object creation.
6. Compared each required role set directly with the tagged OpenOA v3.2 source rather than relying
   on writer tests or prose.

## Findings and residual limitations

- `A-01 — ACCEPTED_RESIDUAL_WITHIN_SCOPE`: unhashable wrong-type vocabulary inputs raised Python
  `TypeError`, not `OperationalEvidenceError`. They failed closed, but field-specific contract errors
  were identified as a useful hardening improvement. The later domain review made this a blocker.
- `A-02 — ACCEPTED_RESIDUAL_WITHIN_SCOPE`: three typing-only aliases were public from
  `analytics.operational.contracts` but not re-exported from the convenience facades. Promised
  runtime classes, constants, and errors were re-exported correctly.
- `A-03 — DEFERRED_TO_NAMED_DOLPHIN`: D1 metadata declarations do not verify bytes, timestamp
  content, row counts, monotonicity, duplication, or coverage. Issue #1332 owns that controlled
  ingestion gate before analytical use.
- No assurance finding independently blocked the reviewed predecessor candidate.

The corrected Pydantic claim, raw-evidence finance fence, public import surface, and preservation of
issue #1110's HOLD were closed for D1. D2 byte/digest verification remained explicitly deferred to
#1332.

## Authority boundary

This review supplied engineering acceptance only. It granted no merge, release, lender, Board,
professional, publication, issue-closure, canonical-finance, bankability, or HOLD authority. Issue
#1110 remained open and its Board/lender reliance HOLD remained fully active.
