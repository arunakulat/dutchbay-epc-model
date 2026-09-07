# PR1237 revision 2 — independent assurance review

```yaml
reviewer_role: assurance
reviewer_identity: /root/assurance
risk_class: R2_LOAD_BEARING
outcome: EVIDENCE_RETURNED
candidate_commit: 5e2eead2b1abe72173da1b3d2db585bc23da899a
candidate_tree: 31226be79bf61b7583536f4d434bc48258888e4e
base_sha: 0fcb61b0760a96cd047e9cba6d11b36938631b09
merge_base_sha: 0fcb61b0760a96cd047e9cba6d11b36938631b09
subject_manifest_sha256: 91c3880a296010ccedd3afc8b971ea4d2d1c528403df115cf63c22d8aebc26a1
worktree: /Users/aruna/.codex/worktrees/f5c1/dutchbay-epc-model
branch: codex/pr1237-coverage-recovery
pr_url: https://github.com/arunakulat/dutchbay-epc-model/pull/1237
disposition: ACCEPT
review_kind: fresh six-file substantive review after hosted failure
mutation_attestation: >
  Repository files, index, refs, branches, worktrees, PRs and issues remained
  read-only. Test fixtures and deliberate mutations used automatically removed
  scratch directories. The only retained output is the authorized scratch review
  /tmp/pr1237-assurance-r2-review.md. No revision-2 domain conclusion was read.
hold_and_authority_effect: >
  No HOLD, release, deployment, professional, publication, lender, Board or
  issue-closure authority changes. Engineering acceptance is not permission to
  skip final-head rebind, exact-head required CI or protected merge verification.
```

ACCEPT. The child coverage CLI now explicitly uses its scratch data-file basename. I independently reproduced the predecessor failure, verified the repaired module under absent and inherited environments, observed the isolation-removal negative control fail, and ran the module under real parent pytest-cov collection with two workers. Fresh actual-workflow oracles and mutations also confirm the intended input-count guard and unchanged 95% floor.

This is a new substantive decision. My earlier acceptance and final-head rebind for 1112add/72fc317 are superseded. Those local controls missed a material inherited CI environment condition; their earlier green result cannot support delivery of the failed head. The hosted Test Summary correctly prevented merge.

## Corpus and rule identities

Required source ingress in this continuing review session covers the current complete canonical CSV, unabridged pinned CASPER/CESSPIT/CCCDIR definitions, AGENTS.md, all four RECRUIT modules, September 7 bootstrap and current PR1237 handover, programme PR1237_PROFILE.md and OWNER_ACK, the superseding revision2/assurance_PROFILE.md, original rejected review chain, both preserved first-recovery reviews, and all six current subject files. I reread the current test body and repair, corrected handover, revised PR body, reproduction.json, checks.json, isolation_mutation.json and predecessor_hosted_run.json. The complete candidate and repair diffs were independently reconciled to Git byte-for-byte. Historical reviews are evidence of earlier decisions, not automatic acceptance.

| Governing source | SHA-256 |
|---|---|
| canonical CSV | 0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1 |
| AGENTS.md | 215dd99e206203b8b859cc0c2b97cf2e0150ea9863a91ccab80a72cabe0f4bcd |
| RECRUIT module 1 | 32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e |
| RECRUIT module 2 | 3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406 |
| RECRUIT module 3 | 2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7 |
| RECRUIT module 4 | 15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592 |

Applicable controls include R8/TEST-02, VERIFY-01, RECRUIT-01, TEST-05 routing, ENV-01/THREAD-01, WORKTREE-01, PERSIST-01, GOV-01/02, R23/R25, DELIVERY-01 and MERGE-01. The persistent environment check passed with Python 3.12.13, the governed external prefix, active-worktree analytics imports and no foreign checkout paths; bootstrap loaded 74 active v3.0 rules. Project association had been verified through the Codex project inventory in this same task.

## Review scope and exact objects

The complete protected-base diff contains six files, 850 insertions and four deletions. Each on-disk file and committed object matches the new manifest:

| Path | Git blob |
|---|---|
| .github/workflows/test-suite.yml | e59739e69779f4399f1c79b1e58fa11aaed73b33 |
| changelog.d/1237-coverage-gate-shard-completeness.fixed.md | cf86803ebf6b68a30a0d5ce5bbbed777833f7543 |
| docs/PR1237_COVERAGE_ASSURANCE_REVIEW_2026-09-08.md | 5c1339b2ee28a5bb334fd967bd66b988057e802a |
| docs/PR1237_COVERAGE_DOMAIN_REVIEW_2026-09-08.md | ef79a03bd2e5c15f88855a227fb3fad9ea7d5971 |
| docs/SESSION_HANDOVER_2026-09-08_PR1237.md | 6d630ffb013667eeabb194fa688697bab25d5438 |
| tests/lint/test_coverage_gate_policy.py | f53134e0077e9ebd8e85cfbbdfea81fee6ee398a |

The production workflow still validates a positive shard count, counts before combining, initializes enforced=false, and applies the 95% floor after successful combination. Test Summary distinguishes incomplete measurement from floor/reporting failure and retains the preceding Test result gate. The one-leg matrix, literal shard list alignment, YAML-step selection, stochastic environment positioning and docs-only behavior remain intact.

The repair changes the fixture's child environment, adds absent/inherited parameterization and a parent sentinel assertion, and appends a candid hosted-failure correction. It does not weaken the production gate or alter finance runtime. The old reviews retain their exact historical objects and limits; the corrected handover explicitly supersedes their delivery acceptance and requires new review and CI. Its earlier checkpoint section is historical context, not a claim that this new head was already accepted.

## Checks executed and exact results

Commands ran with /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python and PYTHONDONTWRITEBYTECODE=1; the active checkout was first on PYTHONPATH. Scratch pytest ran against copied exact subject bytes, not modified repository files.

1. DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap: PASS, Python 3.12.13, correct imports/prefix.
2. DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py: 74 active v3.0 rules.
3. git ls-remote origin refs/heads/main: 0fcb61b0760a96cd047e9cba6d11b36938631b09. This read-only operation substitutes for bootstrap fetch, which would mutate shared refs.
4. gh run view 34166367061 --json headSha,conclusion,status: completed/failure, exact predecessor head 72fc317cf37380169b52b4ab9b50419b6a098693.
5. gh pr view 1237 --json headRefOid,state,mergedAt: OPEN at predecessor 72fc317, mergedAt=null. The new frozen candidate was not yet the live PR head at review.
6. git diff <base> HEAD versus revision2/candidate.diff and git diff 72fc317 HEAD versus revision2/repair.diff: exact byte equality. git hash-object and git rev-parse HEAD:<path> matched all six manifest blobs. Manifest SHA-256 matched the stated digest. git merge-base HEAD <base> returned that base.
7. Final git status --porcelain: empty; git rev-parse HEAD HEAD^{tree}: exact candidate/tree above; git diff --check 0fcb61b HEAD: exit 0.

The independent fixture harness used the exact invocation below in an isolated repository skeleton containing the actual workflow and either predecessor, current or deliberately mutated test bytes:

```text
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest   -c /dev/null -p no:cacheprovider tests/lint/test_coverage_gate_policy.py   -q --no-cov --tb=short
```

For predecessor and isolation-mutant probes it appended -k complete_inputs. Inherited runs set COVERAGE_FILE to an external scratch parent sentinel path containing spaces; absent runs removed the variable. The outer sentinel's SHA-256 was checked before and after each invocation.

| Execution | Result | Outer parent integrity |
|---|---|---|
| Exact predecessor test bytes with inherited data file | 2 failed, 25 deselected in 0.49s; both No data to combine | unchanged |
| Current complete policy module, variable absent | 29 passed in 2.29s | unchanged |
| Current complete policy module, variable inherited | 29 passed in 2.24s | unchanged |
| Current test bytes with only child COVERAGE_FILE binding removed | 2 failed, 2 passed, 25 deselected in 1.05s | unchanged |

The mutation restored the inherited-environment failure while the absence cases continued to pass. This demonstrates that the new parameterization observes the defect and that the repair, not unrelated test changes, closes it.

I separately invoked the exact current module under real parent coverage and two xdist workers:

```text
COVERAGE_FILE=<scratch>/.coverage.3.12.5 /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest   -c /dev/null -p no:cacheprovider tests/lint/test_coverage_gate_policy.py   -q -n 2 --cov=tests/lint --cov-report= --cov-fail-under=0
```

Result: 29 passed in 2.52s. CoverageData.read() successfully reopened the parent database; its measured_files contained exactly the test module and no nested subject.py. The zero threshold applies only to this focused scratch collector and makes no full-suite coverage claim. The production 95% threshold remains unchanged.

## Independent oracles and real-workflow mutations

Fresh independent governed-Python probes parsed the actual workflow with yaml.safe_load, selected its floor run body and substituted matrix.python-version=3.12. They built real CoverageData databases over a separately authored 40-line source, invoked bash -e -c <actual-script>, and verified a separate real parent database remained byte-identical. They did not call writer test helpers.

| Independent actual floor-script case | Result |
|---|---|
| 2/2 files, 38/40 lines = 95% | exit 0; enforced=true; parent DB unchanged |
| 2/2 files, 37/40 lines = 92.5% | exit 2; enforced=true; parent DB unchanged |
| 1/2 files, otherwise complete line data | exit 1 before percentage; no enforced=true |
| 3/2 files | exit 1 before percentage; no enforced=true |
| 2 files, TOTAL_SHARDS=bad | exit 1 before percentage; no enforced=true |

Fresh independent summary-script execution and bash -n checks passed five cases: all ordinary jobs successful (exit 0); Test failure despite successful Coverage (exit 1); incomplete Coverage measurement (exit 1 with NOT evidence diagnosis); enforced Coverage failure (exit 1 with 95% floor diagnosis); and required Grid Study skipped (exit 1). Thus successful coverage still cannot mask test or required-grid failures.

The unchanged current policy module was then run against three independently altered copies of the actual YAML using the same scratch pytest invocation above:

| Real workflow mutation | Observed policy failures |
|---|---|
| present=${#shard_files[@]} replaced with present=$TOTAL_SHARDS | 5 failed, 24 passed in 3.66s |
| coverage report --fail-under=95 replaced with --fail-under=90 | 6 failed, 23 passed in 2.58s |
| Summary enforced comparison changed from = true to != true | 3 failed, 26 passed in 2.19s |

All mutation invocations exited 1; scratch directories were removed after assertions. The separate isolation-removal mutant above also fired. These are freshly executed controls on this revision rather than transferred counts from the earlier acceptance.

## Predecessor finding matrix

| Finding | Applicability and fresh disposition evidence | Result |
|---|---|---|
| Original tautological predicate test | Current tests execute actual YAML; forced-count mutant yields five failures | CLOSED |
| Empty/invalid TOTAL_SHARDS falls through | Current validation and policy cases; independent bad configuration exits before percentage | CLOSED |
| Summary cancellation narrative overstated reachability | Current changelog and handover retain earlier Test gate limitation; fresh Test-failure execution blocks | CLOSED |
| Missing one-leg coverage output pin | Current parsed-matrix policy test passes and output semantics remain single-legged | CLOSED |
| Comment-delimited parsing/prose pins | Current helper selects exactly one parsed step; behavior and diagnosis-fragment tests pass | CLOSED |
| Environment positional pin overlooked | Workflow-level DUTCHBAY_TEST_MODE remains first; prior contextual consumer reviewed; no workflow bytes changed in repair | CLOSED |
| Artifact presence does not prove completion | Limitation is explicit; fresh successful-Coverage/failed-Test counterexample blocks | DEFERRED; ACCEPTED_RESIDUAL_WITHIN_SCOPE |
| Missing durable review/final attestation | Original records retained, hosted failure explicitly supersedes delivery acceptance; new review and final-head process pending | DEFERRED_TO_NAMED_DOLPHIN |
| Hosted inherited COVERAGE_FILE fixture defect | Exact predecessor reproduces both failures; repaired absent/inherited runs pass; isolation-removal mutant restores failure; real parent pytest-cov/xdist output validated | CLOSED |
| Earlier ACCEPT/rebind failed to cover hosted environment | Explicitly superseded; fresh six-file scope and independently executed environmental challenge | SUPERSEDED_BY_SUCCESSOR_FINDING; this review supplies the successor disposition |

## Findings and residual limitations

No blocking defect found in the six-file candidate.

ACCEPTED_RESIDUAL_WITHIN_SCOPE: the production guard proves artifact count, not successful execution of every intended test, shard identity attestation or semantic database completeness. The Test result gate remains necessary, and fresh execution confirms it blocks even when Coverage succeeds.

ACCEPTED_RESIDUAL_WITHIN_SCOPE: local tests cannot certify hosted runner behavior, artifact transfer, all optional-package combinations or the future exact-head CI result. The earlier missed fixture condition demonstrates why hosted CI remains an independent delivery requirement.

DEFERRED_TO_NAMED_DOLPHIN: coordinator 01a07de8-9e76-7861-bd7d-c678047bd10d owns PR1237 revision2 durable review persistence, replacement of live predecessor receipts, new final-head rebinds and exact-head hosted CI. Destination: programme pr1237/revision2 and repository successor review records. Acceptance gate: complete preserved reviews, byte-identical reviewed subjects through receipt-only additions, both final rebinds and required exact-head green including applicable Grid Study. No HOLD effect. These are expected post-review delivery steps, not waived obligations.

The proposed revision2/pr_body.md accurately describes the fixture defect, supersession, repair and remaining CI requirement. Its full-lint/style/type timings and recovery-copy inventory remain writer/coordinator evidence; I did not independently rerun or certify those counts. I did not fetch full hosted job logs, induce a live cancellation, rerun the financial suite/full repository lint, rehash the whole recovery archive, or dispatch hosted CI. The independent checks above address the bounded review scope; future hosted CI remains mandatory. No current revision-2 domain result informed this decision.

The complete review is returned for immediate persistence. No earlier acceptance is silently transferred, no source original is deleted, and no merge or authority change is claimed.
