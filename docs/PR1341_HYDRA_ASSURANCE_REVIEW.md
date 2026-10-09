# PR #1341 independent assurance/security disposition

**ACCEPT — exact frozen subject.** This is the separate assurance member of the required
RECRUIT-01 `R2_LOAD_BEARING` pair. It grants no merge, release, lender, Board,
professional, issue-closure or `HOLD` authority.

```yaml
schema: RECRUIT-01.module-3.structured-disposition.v1
reviewer_role: independent assurance/security reviewer
reviewer_identity: /root/pr1341_assurance_final_20261009
review_timestamp_utc: 2026-10-09
independence:
  distinct_from_writer: true
  distinct_from_coordinator: true
  distinct_from_domain_reviewer: true
  domain_conclusion_inspected: false
candidate_commit: 44fce646fce9749b7fe3fcb0cf106fd618180254
candidate_tree: ed02fbee5f5002c53ba4b7df0c8da3063b50931b
base_sha: 7dce2a67b44c36e73c877a2572fe43f159e8637a
merge_base_sha: 7dce2a67b44c36e73c877a2572fe43f159e8637a
subject_manifest:
  serialization: lexicographically sorted path<TAB>git-blob-SHA rows, LF terminated
  byte_length: 417
  sha256: a5e1045a261766caf1bcefaf9629a2d392acbe22fe538411d1a8a42ce3f60347
  result: MATCH
corpus_and_rule_identities:
  AGENTS.md_blob: 98ca2509de9e9b54cbc82d857ccd6d658b4ab9ba
  GWTF_csv_blob: 5102d0cdcdaa34c546a6351aed41f28a53f27cfa
  RECRUIT_01_module_blobs:
    module_1: 4b5cdfbf7500d9b5abb32400b013bc2d291112df
    module_2: 9c088a835171388da2da71885e119e8dc48db787
    module_3: b6616416d25859d9e356c3ca25e85fe2d0d8aefc
    module_4: b2f1963bc8a81fa45809024d3bfa1b8a2013fd2f
review_scope:
  - all six exact candidate blobs and complete remediation history
  - Hydra advisory ranges, lock/specifier policy and runtime compatibility
  - regression-guard responsiveness and every historical finding
  - scope isolation, hosted security evidence and issue #1110 HOLD
checks_executed_and_exact_results:
  - identity_and_manifest: PASS; exact objects and canonical 417-byte digest matched
  - governed_environment: PASS; Python 3.12.14 and 311 locked distributions
  - runtime_and_metadata: PASS; Hydra 1.3.7, OmegaConf 2.3.1 and ANTLR 4.9.3
  - pip_check: PASS; no broken requirements
  - focused_policy_plus_cli: PASS; 27 passed in 97.99s
  - mutation_responsiveness: PASS; all 24 hostile mutations rejected
  - hosted_security: PASS; exact-head Bandit and pip-audit check run 113889656846
  - independent_full_resolver: INCOMPLETE; interrupted while collecting metadata
  - independent_standalone_bandit: INCOMPLETE; stopped before completion
  - cleanliness: PASS; frozen head/tree and clean worktree retained
independent_oracles_or_counterexamples:
  rejected: [1.3.5, 1.3.6, 1.4.0.dev0-dev9]
  admitted: [1.3.7, 1.4.0.dev10]
  mutation_count: 24
  mutation_classes:
    - 12 affected exact-lock substitutions
    - 10 individually removed development-release exclusions
    - abstract specifier excluding locked 1.3.7
    - abstract specifier excluding fixed dev10
predecessor_finding_matrix:
  HIST-1.3.6-CVE-2026-106439: CLOSED
  HIST-STALE-BASE-REVIEW-COUNT: CLOSED
  HIST-RAW-MANIFEST-MISMATCH: CLOSED
  HIST-DEV4-DEV9-EXCLUSION-GAP: CLOSED
  HIST-DEV0-DEV3-EXCLUSION-GAP: CLOSED
  DOM-1341-001: CLOSED
  DOM-1341-002: CLOSED
findings_and_residual_limitations:
  - id: ASR-1341-001
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    detail: Dependency hardening is defense in depth and does not make arbitrary untrusted Hydra configuration sandbox-safe.
  - id: ASR-1341-002
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    detail: Independent resolver and standalone Bandit reruns were incomplete; exact-head hosted Security Scan, installed-lock validation, pip check and runtime/CLI execution passed.
  - id: ASR-1110-HOLD
    state: TRACKED_IN_NAMED_ISSUE
    detail: Issue #1110 remains OPEN and BOARD/LENDER CIRCULATION remains on HOLD.
hold_and_authority_effect: Accepts only the exact six-blob subject; no merge, release, closure, reliance or HOLD authority.
disposition: ACCEPT
safe_to_persist: true
mutation_attestation: No repository, index, ref, worktree, GitHub, environment or external state mutation.
```

The reviewer independently reproduced the full advisory union, exact-lock binding and both fixed
boundaries. Fresh exact-head hosted security evidence closes the network-backed local audit gap;
all broader reliance and release boundaries remain unchanged.
