# PR1237 revision 2 independent CI-domain review

```yaml
reviewer_role: independent CI domain reviewer
reviewer_identity: /root/domain
risk_class: R2_LOAD_BEARING
review_type: fresh full-subject review after hosted failure
outcome: EVIDENCE_RETURNED
disposition: ACCEPT
candidate_commit: 5e2eead2b1abe72173da1b3d2db585bc23da899a
candidate_tree: 31226be79bf61b7583536f4d434bc48258888e4e
base_sha: 0fcb61b0760a96cd047e9cba6d11b36938631b09
merge_base_sha: 0fcb61b0760a96cd047e9cba6d11b36938631b09
subject_manifest_sha256: 91c3880a296010ccedd3afc8b971ea4d2d1c528403df115cf63c22d8aebc26a1
worktree: /Users/aruna/.codex/worktrees/f5c1/dutchbay-epc-model
branch: codex/pr1237-coverage-recovery
pr_url: https://github.com/arunakulat/dutchbay-epc-model/pull/1237
mutation_attestation: >
  Repository files, index, refs, branches, PRs, issues and other external
  state remained read-only. Independent probes and deliberate mutations used
  isolated temporary directories removed on exit. Only the explicitly
  authorized raw review scratch output was retained. No current revision-2
  assurance disposition was read or used to anchor this decision.
hold_and_authority_effect: >
  No release, deployment, lender, Board, publication, professional,
  issue-closure or HOLD authority changes. This accepts the named substantive
  object only. Both fresh reviews, durable receipt persistence, final-head
  rebind, exact-head hosted required CI and applicable Grid Study remain
  delivery requirements. Earlier acceptance/rebind does not transfer.
```

ACCEPT. The fixture now supplies an explicit child coverage basename, preserving the actual workflow's 95% enforcement and isolating nested coverage from the parent pytest shard. Independent execution reproduced the failed predecessor, exercised the repaired absent/inherited cases, killed the isolation-removal mutation, verified real parent database integrity, and reran independent workflow/summary controls. This is a new review of the entire six-file subject, not a carry-forward of the prior acceptance.

## Corpus and rule identities

Read the superseding revision2/domain_PROFILE.md and freeze; complete candidate and repair diffs; six-file subject manifest; reproduction.json, checks.json, isolation_mutation.json, predecessor_hosted_run.json and prepared revision2/pr_body.md. Re-examined the complete current policy module, actual workflow producer/consumer and summary semantics, changelog, historical domain/assurance records and corrected handover. Earlier historical findings and this reviewer's missed inherited-environment case were treated as defects to reproduce, not accepted conclusions to inherit.

Full canonical CSV, four RECRUIT modules, AGENTS, unabridged pinned framework definitions, programme profile/owner acknowledgement and September 7 bootstrap were read earlier in this same uninterrupted review session. Their current governing repository bytes were rehashed and verified unchanged; the current correction handover was read in full. Governance bootstrap was rerun successfully. Applicable controls remain R8/TEST-02, TEST-05, VERIFY-01, RECRUIT-01, GOV-01/02, R23/R25, WORKTREE-01, ENV-01, THREAD-01, PERSIST-01, DELIVERY-01 and MERGE-01.

| Governing object | Current SHA-256 |
|---|---|
| CSV | `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1` |
| AGENTS | `215dd99e206203b8b859cc0c2b97cf2e0150ea9863a91ccab80a72cabe0f4bcd` |
| RECRUIT module 1 | `32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e` |
| RECRUIT module 2 | `3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406` |
| RECRUIT module 3 | `2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7` |
| RECRUIT module 4 | `15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592` |

## Review scope and exact objects

Each manifest entry was independently compared with `git rev-parse HEAD:<path>`; the manifest digest was recomputed. Complete `git diff 0fcb61b HEAD` exactly matched candidate.diff and `git diff 72fc317 HEAD` exactly matched repair.diff.

| Path | Current Git blob |
|---|---|
| `.github/workflows/test-suite.yml` | `e59739e69779f4399f1c79b1e58fa11aaed73b33` |
| `changelog.d/1237-coverage-gate-shard-completeness.fixed.md` | `cf86803ebf6b68a30a0d5ce5bbbed777833f7543` |
| `docs/PR1237_COVERAGE_ASSURANCE_REVIEW_2026-09-08.md` | `5c1339b2ee28a5bb334fd967bd66b988057e802a` |
| `docs/PR1237_COVERAGE_DOMAIN_REVIEW_2026-09-08.md` | `ef79a03bd2e5c15f88855a227fb3fad9ea7d5971` |
| `docs/SESSION_HANDOVER_2026-09-08_PR1237.md` | `6d630ffb013667eeabb194fa688697bab25d5438` |
| `tests/lint/test_coverage_gate_policy.py` | `f53134e0077e9ebd8e85cfbbdfea81fee6ee398a` |

The production workflow retains its shared TOTAL_SHARDS, exact-count check before combine, positive-integer configuration guard, unchanged unconditional 95% floor, single-leg output wiring and fail-closed Test Summary. The repair changes the test child's environment and adds absent/inherited parameterization plus sentinel verification. Historical review documents retain their original objects and limitations; the appended handover correction explicitly supersedes their delivery acceptance after the hosted failure.

## Checks executed and exact results

- `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV`: Python 3.12.13.
- `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap`: PASS; active worktree imports, governed external prefix, no foreign checkout paths.
- `PYTHONDONTWRITEBYTECODE=1 DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py`: 74 active v3.0 rules.
- `COVERAGE_FILE=.coverage.3.12.1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest -p no:cacheprovider tests/lint/test_coverage_gate_policy.py tests/lint/test_stochastic_suite_policy.py tests/lint/test_grid_ci_policy.py -q --no-cov --tb=short`: **53 passed in 4.03s**.
- `git diff --check 0fcb61b HEAD`: exit 0. Final `git status --porcelain`: empty. Final `git rev-parse HEAD HEAD^{tree}` and `git merge-base HEAD origin/main`: exact candidate/tree/base above.
- `git ls-remote origin refs/heads/main`: unchanged protected base. This read-only remote check replaces ref-mutating fetch for this reviewer.
- `gh run view 34166367061 --json headSha,conclusion,status`: completed failure at 72fc317. Stored job metadata shows failed shards 1/2, successful Coverage Gate and Grid Study, failed Test Summary.
- `gh pr view 1237 --json headRefOid,state,mergedAt`: OPEN, unmerged, predecessor head 72fc317 at inspection. The new candidate is correctly treated as awaiting delivery, not already hosted-green.

## Independent oracles and counterexamples

Reproduction and mutations ran in an isolated skeleton containing the actual workflow plus either `git show 72fc317:tests/lint/test_coverage_gate_policy.py` or the current test bytes. Command pattern was the governed interpreter followed by `-m pytest -c /dev/null -p no:cacheprovider <scratch-test> -q --no-cov --tb=short`, with COVERAGE_FILE=.coverage.3.12.1 and active repository PYTHONPATH; predecessor/isolation cases additionally used `-k complete_inputs`.

| Fresh execution | Result |
|---|---|
| Predecessor fixture under inherited shard basename | **2 failed, 25 deselected in 0.43s**; both No data to combine |
| Repaired full module under same inherited basename | **29 passed in 2.26s**; absent and inherited fixture cases included |
| Delete only child `COVERAGE_FILE=str(workdir / ".coverage")` | **2 failed, 2 passed, 25 deselected in 1.09s**; inherited cases restore No data to combine |
| Mutate actual workflow count to `present=$TOTAL_SHARDS` | **5 failed, 24 passed in 3.12s** |
| Mutate actual floor from 95 to 90 | **6 failed, 23 passed in 2.60s** |

Separately devised direct oracles parsed the actual floor script using PyYAML, substituted the matrix version, constructed real 100-line CoverageData databases and invoked `bash -e <script>` in a resolved scratch directory. They did not call writer test helpers. An external valid parent SQLite coverage database contained independent measured lines and had SHA-256 `1525c15fab9839cc9a8ce265012d3837a5e92489e8b4b0d98cac2bc3c5eb8f5a`; every child execution preserved its exact bytes. Its path included spaces. Child COVERAGE_FILE was explicitly isolated.

| Direct workflow oracle | Exit and output |
|---|---|
| Three shards, configured three, 96% | 0; enforced=true |
| Six shards, 95% | 0; enforced=true |
| Six shards, 94% | 2; genuine threshold failure; enforced=true |
| Five shards, expected six | 1; no percentage; enforced=false |
| Seven shards, expected six | 1; no percentage; enforced=false |
| Empty TOTAL_SHARDS | 1; no percentage; enforced=false |

The same independently parsed actual summary passed the positive case and failed each hostile case with the expected diagnosis: Test failure, Test cancellation, unmeasured Coverage failure, post-floor Coverage/reporting failure, and applicable Grid Study skipped. `bash -n` passed on each direct floor script.

Enclosing pytest-cov/xdist integration also ran against the current copied test module with a scratch parent COVERAGE_FILE and `-n 2`. One smoke with `--cov=observed --cov-fail-under=0 --cov-report=` passed 29 tests in 2.36s; this alone only established collector compatibility. A stronger follow-up used `--cov=<scratch tests/lint directory> --cov-fail-under=0 --cov-report=` and passed **29 tests in 2.34s**. Reading the resulting parent CoverageData proved **233 executed lines of the actual policy module** survived in the parent database. The zero threshold here belongs only to this targeted scratch integration and is not a production floor change or a full-suite coverage claim.

## Predecessor finding matrix

| Finding | Applicable evidence and result |
|---|---|
| Hosted inherited COVERAGE_FILE fixture defect | Independently reproduced two predecessor failures; repaired cases pass; isolation deletion restores failure: CLOSED |
| Prior domain review missed the inherited parent environment | Acknowledge that my earlier local acceptance did not cover the hosted environment. Fresh inherited, parent-integrity and real collector evidence replaces that gap: CLOSED for this candidate; previous delivery acceptance remains superseded |
| Historical tautological workflow control | Current suite executes actual shell; fresh forced-count mutation fails five tests: CLOSED |
| Historical empty shard configuration fails open | Actual positive-integer guard; fresh empty configuration blocks before percentage: CLOSED |
| Historical cancelled-Test summary narrative | Earlier Test gate is retained and directly exercised; changelog and handover disclose distinction: CLOSED |
| Historical single-leg output pin absent | Parsed single-leg invariant retained; current full module passes: CLOSED |
| Historical workflow environment positional pin omitted | Current stochastic and grid policy consumers included in 53-test run: CLOSED |
| Historical comment-delimited/prose-only test parsing | Actual YAML step selection retained and executed; no summary comment delimiter: CLOSED |
| File count does not establish completion/content validity | Explicitly retained in changelog/handover and current tests; Test failure remains independently blocking: ACCEPTED_RESIDUAL_WITHIN_SCOPE |
| Historical review persistence / final-head acceptance | Current historical records preserved, correction explicit; fresh review and final rebind still required: DEFERRED to current PR1237 coordinator delivery stage |

## Findings and residual limitations

No finding blocks this frozen six-file candidate. The documentation candidly states that no merge occurred, names the hosted failing head/run, explains the fixture defect, and supersedes earlier acceptance for delivery. The prepared replacement PR body accurately describes that sequence and this repair. A pre-commit receipt-scope discrepancy was queried during review: the coordinator then recorded an additional exact three-file current-checkpoint invocation in checks.json, matching the PR-body command; the earlier two-file invocation included the corrected handover. These are coordinator execution receipts, not independently rerun lint claims.

Artifact count does not certify successful shard completion, semantic coverage-data validity or authenticity. Existing Test Summary remains the complementary gate. No live cancellation was induced. The full financial suite, all 491 lint tests, standalone formatter/type checks and new hosted candidate execution were not independently run by this reviewer; the focused 53-test run and independent controls above are the reviewer evidence. Broad writer counts are supplementary, not substitutes. Recovery-archive/process ownership controls were not re-audited beyond scoped records; original dirty state remains preserved.

This review authorizes no merge by itself. Persist both independent new dispositions, rebind any receipt-only final head after verifying all six reviewed subject blobs and accurate new metadata, run required hosted checks on the exact delivery head including applicable Grid Study, and verify protected merge identity. No prior green check or superseded rebind transfers to this candidate.
