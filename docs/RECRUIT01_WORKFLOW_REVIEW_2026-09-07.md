# RECRUIT-01 workflow review — 2026-09-07

This record preserves the independent initial rejection. It is not acceptance of a later candidate.
The coordinator transcribed the material findings and receipts; the reviewer must verify this
record at final rebind. Both reviewers reached initial dispositions without seeing the other.

```yaml
reviewer_role: workflow_domain
reviewer_identity: /root/workflow_review
candidate_commit: 7f10c067057abffa537ad0bca5f2509485527487
candidate_tree: 582590dcaadcd0b09e81278247f64f1afd6382c6
base_sha: 93aefbb7400287126060b1846b8cd83078fb6ac8
merge_base_sha: 93aefbb7400287126060b1846b8cd83078fb6ac8
subject_manifest_sha256: d5dca219f849d28c9bb6b3b13a21be85398d28adb8fc48b0a182dc5ecdcef4b2
candidate_csv_sha256: 0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1
disposition: REJECT
mutation_attestation: read-only; no writer lease or intentional state mutation
hold_and_authority_effect: none
```

## Scope and ingress

All 11 changed paths, complete CSV and AGENTS, four modules, both test files, implementation record,
September 7 handover, pinned unabridged framework definitions, and protected-base RECRUIT-01 with
the September 2 amendment. Independent manifest reconstruction matched the supplied digest.
The original abandoned reviews yielded no usable evidence; no old acceptance transfers.

## Blocking finding

The new `Path.read_text` wrapper at test line 267 forwards `*args: object` and `**kwargs: object`
where optional strings are required. Mypy independently returned two `arg-type` errors in one file,
checking both changed Python tests. Fix the typed signature without suppressions, retain negative
controls, rerun checks and obtain fresh substantive review of a new frozen candidate.

## Execution receipts

All commands ran in `/Users/aruna/Downloads/dutchbay-wt-recruit01-governance`; Python and mypy
came from `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/`, with checkout `PYTHONPATH`.
- `python -VV`: Python 3.12.13.
- `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap`:
  PASS, imports under reviewed checkout, no foreign checkout paths.
- `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py`:
  74 active v3.0 rules.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest -o addopts='' -n 0 --no-cov -p no:cacheprovider tests/lint/test_gwtf_canonical_source.py tests/lint/test_codex_project_guidance.py -q`:
  17 passed in 0.67s.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/mypy --cache-dir=/dev/null tests/lint/test_gwtf_canonical_source.py tests/lint/test_codex_project_guidance.py`:
  exit 1, two errors at line 267.

## Independent challenge and predecessor matrix

Source-level tabletop analysis is appropriate for this normative-prose deliverable; no automated
orchestration engine is claimed. The reviewer checked six hostile cases:
1. Interrupted writer resuming under old authority: refused by expiry/revocation and fresh lease.
2. Dead worker presumed terminated from timeout: refused without independent inactivity proof.
3. Receipt append smuggling policy changes or PR evidence edits: subject identity and content
   validation reject these; PR existence before rebind makes the positive path possible.
4. Base update with unchanged candidate files: all judged-file hashes, bidirectional imports,
   normative dependencies and full diff remain required.
5. Conflicting reviewer outcomes or one identity supplying both reviews: one veto blocks; distinct
   roles and initial independent conclusions remain required.
6. Failed workers reported as completed: absent evidence and zero completions remain NO_EVIDENCE.

Predecessor replay controls PRE-BASE-SEP02, PRE-ROLE-SEPARATION, PRE-INTERRUPTION, PRE-EXACT-OBJECT,
PRE-PERSIST-NOEVIDENCE and PRE-AUTHORITY were all CLOSED by the reviewed clauses. These labels name
controls replayed in this review, not invented historical finding identifiers.

WF-01 is BLOCKS_CURRENT_CANDIDATE (type failure). The stale AGENTS current-handover label is an
ACCEPTED_RESIDUAL_WITHIN_SCOPE: the controlling instruction is still to read the newest handover.

## Limitations

No finance, QSTS, deployment or final-head CI execution was claimed. Historical counts remain dated
receipts. Tests establish selected phrase loss detection, not actual lease compliance or full
semantic correctness. The ending candidate and clean worktree matched the starting freeze.
No release, lender, Board, professional, publication, deployment, issue or HOLD authority changed.


## Fresh substantive replacement disposition

```yaml
candidate_commit: c3705f032c5f407f37e7bd731e0e0abcb514a5fe
candidate_tree: 7c7bd50599353e7c2ff25a6d26dbacdfe9286f5e
base_sha: 93aefbb7400287126060b1846b8cd83078fb6ac8
merge_base_sha: 93aefbb7400287126060b1846b8cd83078fb6ac8
subject_manifest_sha256: d7a6bcd42a716a2bde9426dac09302333768210bf21f2626a32aab4bf98c72be
candidate_csv_sha256: 0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1
disposition: ACCEPT
mutation_attestation: read-only; ending commit/tree and clean state unchanged
hold_and_authority_effect: none
```

This is the same independent reviewer identified above, returning a fresh substantive disposition
without seeing the other reviewer's replacement conclusion. It is not inherited acceptance from
the rejected candidate. The reviewer verified this record's initial rejection as a faithful
condensed transcription, and independently reconstructed the eleven-subject manifest excluding
only these two named review-receipt paths. The typed signature, handover pointer and explicit
textual-guard limitation were inspected on the replacement.

Fresh command receipts use the same exact commands recorded above:
- Two-file mypy with `--cache-dir=/dev/null`: exit 0, no issues in 2 source files.
- Two-file focused pytest: 17 passed in 0.82s, including all four removal controls.
- `git diff --check`: exit 0. Identity/manifest probe matched all replacement fields.

The reviewer freshly replayed all six source-level tabletop challenges above; interruption,
timeout-only takeover, receipt/PR-evidence mutation, normative base dependency drift, conflicting
reviewers and failed-worker completion remain refused. Source-level reasoning is the independent
oracle for this normative-prose deliverable; tests are supplementary.

WF-01 and the stale-pointer residual are CLOSED. All six PRE control replays remain CLOSED.
The phrase-guard limitation is ACCEPTED_RESIDUAL_WITHIN_SCOPE: source review remains mandatory,
and no actual worker-compliance or machine-enforced lease system is claimed.

Earlier environment/bootstrap results are explicitly earlier receipts in the same review session,
not newly rerun results. No full finance, QSTS, deployment or GitHub final-head check is claimed.
This acceptance still requires a separate final-head rebind after the receipt commit, followed by
exact-head CI and protected merge verification.
