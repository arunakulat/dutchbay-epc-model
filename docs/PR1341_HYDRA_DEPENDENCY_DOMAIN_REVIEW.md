# PR #1341 independent dependency/package-domain disposition

**ACCEPT — exact frozen subject.** This is one member of the required RECRUIT-01
`R2_LOAD_BEARING` review pair. It grants no merge, release, lender, Board, professional,
issue-closure or `HOLD` authority.

```yaml
schema: RECRUIT-01.module-3.structured-disposition.v1
reviewer_role: independent Python dependency/package-domain reviewer
reviewer_identity: /root/pr1341_domain_final_20261009
review_session: PR-1341-ISSUE-1339-post-fix-domain-review
review_timestamp_utc: 2026-10-09T15:29:45Z
independence:
  distinct_from_writer: true
  distinct_from_coordinator: true
  distinct_from_assurance_reviewer: true
  assurance_conclusion_inspected_or_sought: false
  review_mode: read-only
candidate_commit: 44fce646fce9749b7fe3fcb0cf106fd618180254
candidate_tree: ed02fbee5f5002c53ba4b7df0c8da3063b50931b
base_sha: 7dce2a67b44c36e73c877a2572fe43f159e8637a
merge_base_sha: 7dce2a67b44c36e73c877a2572fe43f159e8637a
subject_manifest:
  serialization: lexicographically sorted path<TAB>git-blob-SHA rows, LF terminated
  byte_count: 417
  sha256: a5e1045a261766caf1bcefaf9629a2d392acbe22fe538411d1a8a42ce3f60347
  result: MATCH
corpus_and_rule_identities:
  AGENTS.md_blob: 98ca2509de9e9b54cbc82d857ccd6d658b4ab9ba
  GWTF_csv_blob: 5102d0cdcdaa34c546a6351aed41f28a53f27cfa
  GWTF_csv_sha256: 5c8f1b163b3c65aa60fb93a333a0a11501ecb61ce414348fc85a0d2b3e4bed37
  RECRUIT_01_module_blobs:
    module_1: 4b5cdfbf7500d9b5abb32400b013bc2d291112df
    module_2: 9c088a835171388da2da71885e119e8dc48db787
    module_3: b6616416d25859d9e356c3ca25e85fe2d0d8aefc
    module_4: b2f1963bc8a81fa45809024d3bfa1b8a2013fd2f
review_scope:
  - all six exact subject objects and complete base-to-head history
  - Python packaging, PEP 440 and pip resolution
  - Hydra, OmegaConf and ANTLR compatibility
  - primary advisory interpretation and regression-guard adequacy
  - scope, authority and issue #1110 HOLD isolation
checks_executed_and_exact_results:
  - identity: PASS; exact head, tree, base, merge base and six changed paths matched
  - manifest: PASS; independently reconstructed 417-byte canonical digest matched
  - primary_advisories: PASS; CVE-2026-106439 affects stable >=1.3.4,<1.3.7 and dev4-dev9; CVE-2026-106441 affects stable <1.3.6 and dev0-dev8; CVE-2026-106442 affects stable >=1.3.4,<1.3.6 and dev0-dev8
  - tested_predecessor_candidates: 1.3.5, 1.3.6 and the combined dev0-dev9 development interval are rejected
  - dependency_policy_tests: PASS; 26 passed in 8.69s
  - governed_environment: PASS; Python 3.12.14 and all 311 locked distributions
  - runtime_metadata: PASS; Hydra 1.3.7, OmegaConf 2.3.1 and ANTLR 4.9.3 compatible
  - hydra_cli: PASS; canonical no-artifact sensitivity CLI returned status success
  - hosted_security: PASS; exact-head check run 113889656846
  - local_full_resolver: INCOMPLETE; interrupted without a conflict or success claim
  - local_pip_audit: NOT_CLAIMED; interrupted network-backed attempt
  - whitespace_and_cleanliness: PASS; no diff errors and worktree remained clean
independent_oracles_or_counterexamples:
  exact_lock_predicate: version >= 1.3.7 and abstract specifier contains version with prereleases enabled
  rejected: [1.3.5, 1.3.6, 1.4.0.dev0-dev9]
  admitted: [1.3.7, 1.4.0.dev10]
  mutations:
    - pin exact lock to 1.4.0.dev0: guard fails
    - remove the dev7 exclusion: guard fails
    - add an overbroad <1.4.0 ceiling: dev10 positive assertion fails
predecessor_finding_matrix:
  PRED-INITIAL-1.3.6-STILL-VULNERABLE: CLOSED
  PRED-RAW-MANIFEST-MISMATCH: CLOSED
  PRED-STALE-BASE-WORDING: CLOSED
  PRED-ONE-REVIEW-WORDING: CLOSED
  PRED-DEV4-DEV9-GAP: CLOSED
  PRED-DEV0-DEV3-SUCCESSOR-GAP: CLOSED
  DOM-1341-001: CLOSED
  DOM-1341-002: CLOSED
  LOCAL-PIP-AUDIT-INTERRUPTION: CLOSED_BY_EXACT_HEAD_HOSTED_SECURITY_SCAN
findings_and_residual_limitations:
  - id: DOM-1341-LOCAL-RESOLVER
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    detail: The fresh local full-install dry-run was interrupted without a result.
    why_nonblocking: Dependency inputs are unchanged from the prior successful resolver; the governed environment and CLI pass; exact-head hosted security passed.
  - id: ISSUE-1110-HOLD
    state: TRACKED_IN_NAMED_ISSUE
    detail: Issue #1110 remains OPEN and BOARD/LENDER CIRCULATION remains on HOLD.
hold_and_authority_effect: No authority or HOLD changes; this is one required R2 disposition only.
disposition: ACCEPT
safe_to_persist: true
mutation_attestation: No repository, index, ref, worktree, GitHub, environment or external state mutation.
```

The reviewer independently confirmed that the repaired guard passes the exact lock through the
same fail-closed predicate used for every affected candidate. It also pins both fixed boundaries,
so neither an affected exact prerelease nor an overbroad future exclusion can silently pass.
