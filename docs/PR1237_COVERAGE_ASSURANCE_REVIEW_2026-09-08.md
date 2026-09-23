```yaml
reviewer_role: assurance
reviewer_identity: /root/assurance
risk_class: R2_LOAD_BEARING
outcome: EVIDENCE_RETURNED
candidate_commit: 1112adddcdb20a716e1faa91182b79528c7a0780
candidate_tree: 0612a3ccc4a002daeb7919548994a7e81e187382
base_sha: 0fcb61b0760a96cd047e9cba6d11b36938631b09
merge_base_sha: 0fcb61b0760a96cd047e9cba6d11b36938631b09
subject_manifest_sha256: 991e5e06a997c85be74b3e9f6154de449d389bb2f9631fe1e9549fdfbe4b643e
worktree: /Users/aruna/.codex/worktrees/f5c1/dutchbay-epc-model
branch: codex/pr1237-coverage-recovery
disposition: ACCEPT
mutation_attestation: >
  Repository files, index, refs, branches, PRs, issues and other external state
  remained read-only. Independently devised execution probes and four deliberate
  workflow mutations ran only in automatically removed temporary directories.
  Clean status and exact candidate commit/tree were verified after execution.
hold_and_authority_effect: >
  No HOLD is lifted. This is substantive engineering acceptance of the frozen
  candidate only. It confers no merge, release, deployment, lender, Board,
  publication or issue-closure authority. Final-head rebind and exact-head
  required CI remain coordinator delivery obligations.
```

**ACCEPT:** the frozen candidate repairs the incomplete-input diagnosis without weakening the 95% floor. Independent execution confirmed that configuration drives the count, incomplete and excess counts stop before coverage computation, combine failure retains `enforced=false`, and failure after the floor retains `enforced=true`. Four deliberate changes to the actual workflow each caused the candidate’s policy tests to fail.

`corpus_and_rule_identities`

Fresh ingress covered the complete current canonical CSV, all four RECRUIT-01 modules, repository `AGENTS.md`, the pinned unabridged framework definitions and their global index, latest `docs/SESSION_HANDOVER_2026-09-07.md` bootstrap, programme `PR1237_PROFILE.md` and `PR1237_OWNER_ACK.md`, this reviewer’s profile, freeze and subject manifest, complete candidate diff and test bodies, both historical reviews in `prior_reviews.json`, and the prepared replacement PR body.

The older pinned memory’s rule count, hashes and prose-based reviewer categorization were treated as dated pointers. Current CSV and semantic-risk modules govern this review.

| Governing object | SHA-256 |
|---|---|
| `go_with_the_flow_rules_v3_0_clean.csv` | `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1` |
| `01_capability_and_risk.md` | `32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e` |
| `02_writer_lease_and_recovery.md` | `3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406` |
| `03_independent_review_and_attestation.md` | `2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7` |
| `04_staged_delegation_and_ingress.md` | `15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592` |

Applicable requirements include R8/TEST-02, VERIFY-01, RECRUIT-01, GOV-01/02, R23/R25, WORKTREE-01, ENV-01, THREAD-01, PERSIST-01, DELIVERY-01 and MERGE-01. TEST-05 routing remains present and unchanged in substance.

`review_scope`

All three substantive subject blobs were independently verified against the manifest:

| Path | Git blob |
|---|---|
| `.github/workflows/test-suite.yml` | `e59739e69779f4399f1c79b1e58fa11aaed73b33` |
| `changelog.d/1237-coverage-gate-shard-completeness.fixed.md` | `cf86803ebf6b68a30a0d5ce5bbbed777833f7543` |
| `tests/lint/test_coverage_gate_policy.py` | `64eb89d40f9b6a19d3156169b91256669011f750` |

The complete base-to-candidate diff is three files, 489 insertions and four deletions. A byte comparison of `git diff <base> HEAD` with programme `candidate.diff` passed. Review included artifact upload/download naming, the inherited shard count, one-leg coverage matrix, step-to-job output wiring, real Coverage.py threshold tests, shell control flow, summary consumers, docs-only behavior, and the positional stochastic environment pin.

`checks_executed_and_exact_results`

- `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV` returned Python **3.12.13**.
- `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap` returned **PASS**, with the governed external prefix, imports from the active worktree, and no foreign checkout paths.
- `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` loaded **74 active v3.0 rules**.
- `git ls-remote origin refs/heads/main` returned **`0fcb61b0760a96cd047e9cba6d11b36938631b09`**. This replaced bootstrap `git fetch origin` for this read-only reviewer: fetching would mutate shared refs.
- `gh pr view 1237 --json headRefOid,baseRefOid,state,body` confirmed the existing PR was **OPEN**, still exposing original head `336aadb1…` and historical receipts at inspection. The frozen recovered candidate was correctly declared unpushed. Those historical receipts are not candidate evidence.
- `gh issue view 1110 --json state,title` confirmed **OPEN**. No issue control was changed.
- Parsed the actual YAML scripts with PyYAML, substituted only the known GitHub expressions, and executed them using **`bash -e -c <extracted-script>`** in scratch directories. Exact independent cases and results follow.
- Ran the unchanged candidate policy module in an isolated scratch repository layout using `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest -p no:cacheprovider -o addopts= tests/lint/test_coverage_gate_policy.py -q`, with `PYTHONDONTWRITEBYTECODE=1` and the active worktree first on `PYTHONPATH`: **27 passed in 1.85s**. These include real Coverage.py acceptance at 95% and rejection at 90%.
- Repeated that exact pytest invocation against four independently altered workflow copies. Results appear below.
- Executed the existing stochastic workflow environment regex `^env:\n  DUTCHBAY_TEST_MODE: full$` with multiline matching against the candidate: **PASS**. Read its actual consumer in `tests/lint/test_stochastic_suite_policy.py`.
- `bash -n -c <substituted-summary-script>` passed for all five independently selected summary scenarios.
- Final `git status --porcelain` was empty; `git rev-parse HEAD HEAD^{tree}` returned the exact frozen identities above; `git diff --check` returned **0**.

`independent_oracles_or_counterexamples`

These probes were independently constructed rather than importing the writer’s test helper.

| Actual floor-script probe | Result | Observed coverage calls and output |
|---|---:|---|
| Four artifacts, `TOTAL_SHARDS=4` | 0 | `combine`, `report --fail-under=95`, `xml`, `html`; final `enforced=true` |
| Three artifacts, `TOTAL_SHARDS=4` | 1 | No coverage invocation; `enforced=false` |
| Five artifacts, `TOTAL_SHARDS=4` | 1 | No coverage invocation; `enforced=false` |
| Six artifacts, `TOTAL_SHARDS=06` | 1 | Noncanonical configuration rejected; no coverage invocation; `enforced=false` |
| Six artifacts, combine stub exits 9 | 9 | Only `combine`; `enforced=false` |
| Six artifacts, XML stub exits 9 | 9 | `combine`, floor, `xml`; no HTML call; final `enforced=true` |

The four-shard positive case demonstrates that the executable shell follows configuration rather than a hidden six-shard constant. The post-floor failure probe demonstrates why the summary must include reporting failure in its diagnosis.

Independent summary execution additionally demonstrated:

| Scenario | Exit | Required observed diagnosis |
|---|---:|---|
| All required ordinary results successful | 0 | Accepted |
| Test matrix failed, coverage successful | 1 | `pytest matrix did not pass` |
| Coverage failed before floor, `enforced=false` | 1 | `NOT evidence` of a coverage regression |
| Coverage failed after floor, `enforced=true` | 1 | `subsequent coverage reporting` |
| Classification failure represented by skipped test job | 1 | `Test job did not complete` |

Deliberate mutations changed the real YAML workflow in scratch while retaining the candidate policy module unchanged:

| Mutation | Exact substitution | Policy result |
|---|---|---|
| Force complete count | `present=${#shard_files[@]}` → `present=$TOTAL_SHARDS` | **5 failed, 22 passed**, exit 1 |
| Weaken floor | `coverage report --fail-under=95` → `coverage report --fail-under=90` | **5 failed, 22 passed**, exit 1 |
| Remove incomplete-input termination | Replace that branch’s `exit 1` with `:` | **6 failed, 21 passed**, exit 1 |
| Bypass configuration validation | Positive-integer validation condition → `if false; then` | **4 failed, 23 passed**, exit 1 |

Temporary directories were removed by `TemporaryDirectory` after successful assertions. No persistent runtime log was created.

`predecessor_finding_matrix`

IDs below are assigned for this receipt because the historical reviews used headings rather than stable finding IDs.

| Finding ID | Applicability | Probe/evidence | Result |
|---|---|---|---|
| HIST-D1 / HIST-A1: predicate-only negative control falsely claimed workflow assurance | Applicable | Actual YAML execution; forced-count mutation now produces five failures | **CLOSED** |
| HIST-D2: summary coverage diagnosis unreachable after cancelled Test gate | Applicable | Earlier Test gate remains fail-closed; changelog explicitly states cancellation is reported there; independent summary probes validate later coverage cases | **CLOSED** as misleading narrative; ordering retained intentionally |
| HIST-D3: missing single-leg matrix pin | Applicable | `test_coverage_gate_matrix_is_single_legged` parses the configured matrix and pins `["3.12"]`; baseline passes | **CLOSED** |
| HIST-A2: empty `TOTAL_SHARDS` falls through | Applicable | Positive-integer validation; candidate tests cover missing, empty, invalid, zero, negative and fractional values; validation-bypass mutant fails | **CLOSED** |
| HIST-A3: workflow environment positional pin omitted from blast-radius analysis | Applicable | Read actual stochastic consumer; independently applied its multiline regex successfully | **CLOSED** |
| HIST-A4: prose delimiter silently widened summary slice | Applicable | `_step_run` selects exactly one parsed YAML step and asserts uniqueness; no comment delimiter remains | **CLOSED** |
| HIST-A4b: unnecessary full-sentence pins | Applicable | Current tests assert diagnosis fragments and executable behavior; expected output routing is intentionally pinned | **CLOSED** |
| HIST-A5: artifact presence does not prove test completion | Applicable | Changelog explicitly preserves limitation; independent failed-test/successful-coverage case exits 1 | **DEFERRED** as accepted residual within this bounded count-diagnosis scope |
| HIST-A6: no durable review records before merge | Applicable delivery obligation | This receipt returns substantive review for immediate coordinator persistence; final-head rebind still required | **DEFERRED** to current coordinator’s receipt/delivery phase; merge must wait |

`findings_and_residual_limitations`

No finding blocks the frozen substantive candidate.

- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** Counting files establishes input count, not successful completion, shard-content validity, or shard-identity attestation. Current literal upload filenames constrain the normal producer path, and Test Summary independently blocks failed/cancelled tests. The candidate candidly retains this limitation. No broader completed-shard certification is claimed.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** This is local execution of actual shell bodies with controlled inputs. It does not independently validate GitHub runner expression expansion, artifact service operation or publication of failed-step outputs. Exact-head hosted CI remains required.
- **DEFERRED_TO_NAMED_DOLPHIN:** Durable review persistence, replacement of historical PR receipts, final-head rebind and exact-head CI belong to the current PR1237 recovery/delivery coordinator. Owner: `01a07de8-9e76-7861-bd7d-c678047bd10d`. Destination: programme `pr1237` review records and final delivery metadata. Acceptance gate: unchanged reviewed blobs, truthful receipt-only delta, both final rebinds and successful required checks on the exact delivery head. HOLD effect: none.
- The full `tests/lint/` suite, financial suite, QSTS execution, hosted workflow dispatch, black/isort/mypy and the writer’s complete mutation harness were **not independently rerun by this reviewer**. The bounded assurance pass instead executed independent hostile controls and the complete candidate policy module. Prepared PR-body claims about broader writer checks remain writer receipts rather than newly independent results.
- I did not independently rehash the entire 2,525-file recovery archive or audit the original owner’s process inventory. Those are coordinator recovery controls outside the frozen three-file substantive review. I did read the authored stop acknowledgement and recovery scope.
- No domain reviewer result was consulted before this disposition.

The prepared replacement PR body accurately describes the reviewed behavior and retained limitations. Its statement that independent reviews are in progress is appropriate at preparation time and must be updated after persistence. Acceptance here binds only to the exact frozen objects named above.

<oai-mem-citation>
<citation_entries>
MEMORY.md:78-87|note=[Prior coverage control lessons used as hypotheses and independently reverified]
</citation_entries>
<rollout_ids>
</rollout_ids>
</oai-mem-citation>
