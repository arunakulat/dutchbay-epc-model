# RECRUIT-01 assurance review — 2026-09-07

This record preserves the independent initial rejection. It is not acceptance of a later candidate.
The coordinator transcribed the material findings and receipts; the reviewer must verify this
record at final rebind. Both reviewers reached initial dispositions without seeing the other.

```yaml
reviewer_role: independent_contract_assurance
reviewer_identity: /root/assurance_review
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
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest -o addopts='' -n 0 --no-cov -p no:cacheprovider tests/lint/test_gwtf_canonical_source.py tests/lint/test_codex_project_guidance.py tests/lint/test_pr_receipts_policy.py -q`:
  33 passed in 0.69s.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/mypy --cache-dir=/dev/null --follow-imports=skip tests/lint/test_gwtf_canonical_source.py tests/lint/test_codex_project_guidance.py`:
  exit 1, two errors at line 267.
- `git diff --check`: exit 0.

## Independent hostile controls and predecessor matrix

A read-only Python stdin probe used `runpy.run_path` and `unittest.mock.patch.object(Path,
"read_text")` to alter module 3 reads only in memory. Unmodified guard passed; removing
BLOB-HASH IDENTITY raised AssertionError. Replacing the lapse sentence with a statement retaining
acceptance, while keeping the words "Disposition LAPSES" elsewhere, passed the guard. Therefore
textual presence cannot establish semantic consistency; no semantic enforcement claim is accepted.

ASSURANCE-01: BLOCKS_CURRENT_CANDIDATE, typed forwarding errors above.
ASSURANCE-02: ACCEPTED_RESIDUAL_WITHIN_SCOPE, keyword-guard limitation; record it and retain source
review as semantic gate. ASSURANCE-03: ACCEPTED_RESIDUAL_WITHIN_SCOPE, stale handover example;
update the pointer during repair. Neither residual changes any HOLD.

Predecessor controls for the September 2 carve-out, candidate-owned drift, documentation in the
subject, mutable external evidence, receipt recursion, writer collision, and absent-review evidence
were CLOSED by source challenge. Unrelated financial and source-corpus findings are NOT_APPLICABLE
and remain outside this review. Base updates require normative-dependency isolation for prose.

## Limitations

No finance, QSTS, deployment or final-head CI execution was claimed. Historical counts remain dated
receipts. Tests establish selected phrase loss detection, not actual lease compliance or full
semantic correctness. The ending candidate and clean worktree matched the starting freeze.
No release, lender, Board, professional, publication, deployment, issue or HOLD authority changed.
