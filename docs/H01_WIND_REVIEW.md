# H01 wind review — original transported disposition

Reviewer session: `01a08237-8a83-7c20-bc07-121891ba0c3e`. Original body SHA-256: `4a9910d847c7728d64f5bdb605ad74867287c750efd795a13f51600a3ca7e529`.
Original body length: 21338 UTF-8 bytes. The bytes between the following
markers preserve the delivered reviewer body, including its trailing newlines.

<!-- H01_ORIGINAL_BODY_BEGIN -->
**ACCEPTED for the frozen H01 substantive candidate.** I found no issue that blocks this wind-test integrity repair. The original assertions remain intact; independent hostile inputs now fail rather than skip; genuine package absence still skips; and the new guard rejects a deliberate restoration of the failure-masking behavior.

```yaml
reviewer_role: H01 independent WIND/TEST-DOMAIN reviewer
reviewer_identity:
  agent_path: /root/h01_wind_review
  session_id: 01a08237-8a83-7c20-bc07-121891ba0c3e
  model: gpt-6-astra
  reasoning_effort: xhigh
  independent_from_writer: true
  independent_from_assurance_reviewer: true
  assurance_initial_disposition_seen: false
candidate_commit: acd64af762643dd3e85dd64566711f68f8f33faf
candidate_tree: 4630738c62859e5fd390dcb8a68847db72739641
base_sha: 5ec33d32834c18e8c14dff06617ff92fec365828
merge_base_sha: 5ec33d32834c18e8c14dff06617ff92fec365828
subject_manifest_sha256: 8a40ecc0fe9bd348b22ffb827bcf44a86ab0485d02af1e7bf71cfd73e56af158
review_scope:
  risk: R2_LOAD_BEARING
  worktree: /Users/aruna/.codex/worktrees/440e/dutchbay-epc-model
  branch: codex/h01-wind-test-integrity
  subject_files:
    - changelog.d/hygiene-wind-failures.fixed.md
    - docs/H01_IMPLEMENTATION.md
    - tests/wind/test_power_curve_sourcing.py
    - tests/wind/test_power_curve_sourcing_skip_integrity.py
  examined:
    - Original-test assertion preservation and exception boundaries
    - Optional-package discovery versus broken installed-package imports
    - Real sourcing-loader execution under independent hostile inputs
    - Rated-capacity, power-curve validity, provenance and thrust assertions
    - Positive controls before and after hostile probes
    - Guard behavior under an actual-source broad-catch mutation
    - Local-data default claim
    - Implementation record and changelog scope and limitations
  excluded:
    - Production changes
    - Dependency or persistent-environment changes
    - Test-policy changes
    - Native-grid repair or five-run acceptance
    - Financial-behavior acceptance
    - Merge, issue-closure, publication, release or HOLD authority
disposition: ACCEPTED
evidence_yield: NO_FINDING_WITH_EVIDENCE
mutation_attestation:
  source_index_ref_branch_worktree_changes: none
  pr_issue_or_other_external_state_changes: none
  environment_or_dependency_changes: none
  permitted_activity: Focused pytest, in-memory probes, ordinary temporary test fixtures
  ending_worktree_state: clean
  ending_candidate_identity: unchanged
hold_and_authority_effect:
  issue_1110: OPEN; BOARD/LENDER CIRCULATION HOLD unchanged
  issue_1229: OPEN; no native-crash cure or closure claimed
  engineering_acceptance_only: true
  final_head_rebind: required after the PR and receipt-only final head exist
  hosted_exact_head_required_ci: remains mandatory
```

`corpus_and_rule_identities`

I read the current canonical GWTF CSV, the pinned unabridged framework definitions, actual `AGENTS.md`, all four RECRUIT-01 modules, the September 7 bootstrap handover and the two applicable September 8 successors. I also read the delivery profile, worktree brief, leases 001–004, baseline and freeze receipts, predecessor diagnosis, all four subject files, the complete production sourcing module, both pre-existing sourcing test files, `pyproject.toml`, and the stochastic/report/grid policies. Relevant collection and environment sections of `tests/conftest.py` and CI-policy references were inspected.

The framework meanings applied were the canonical definitions: CASPER—Clear API Surfaces with Predictable Error Responses; CESSPIT—Config Explicit, Schema Strict, Pre-flight Integrity Tests; CCCDIR—Contracts Centralized, Compliance Documented, Import Relationships explicit.

| Source | SHA-256 |
|---|---|
| Current canonical GWTF CSV | `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1` |
| Pinned framework definitions | `c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af` |
| H01 `DELIVERY_PROFILE.md` | `3db3dbec513fccb31170c9f25f26e31d9399d7454b1e9374c79bf4b8062a60ae` |
| H01 `delivery/WORKTREE_BRIEF.md` | `fa968912b37d7b727ad303a871ff1b442b2312ad5c521c1a9fdc13c0248bcfec` |
| H01 `delivery/baseline.json` | `ac84e130fcfd73d7b941ab7597901b25195325c99f1fadcfc738cef3bdd7a73d` |
| H01 `delivery/freeze001.json` | `d3c58326c28b1c68b1d87a2e9dd1dd87f3d2e447b2d5b9ceee5dbcf7ff337b96` |
| Predecessor `assurance_diagnosis.md` | `3f7f81f2dce0bf8b57410281736eeb9e47ea0a18868775c32ac5bf423e4cc53a` |

The governed interpreter reported Python **3.12.13**. The environment check returned `PASS`, the active checkout supplied imports, no foreign checkout paths were reported, and the rules bootstrap loaded **74 active v3.0 rules**. Project association was established through the actual coordinator dispatch; the captured task-configuration record also identifies this reviewer as `gpt-6-astra`/`xhigh`, distinct from the writer and assurance reviewer.

Two live `git ls-remote origin refs/heads/main` checks returned the frozen base. The open-PR query showed no H01 PR at review ingress. Issues #1110 and #1229 were independently read as OPEN. I did not fetch because this reviewer’s explicit authority prohibits ref mutation; `ls-remote` supplied the live protected-head check.

`checks_executed_and_exact_results`

Commands ran from `/Users/aruna/.codex/worktrees/440e/dutchbay-epc-model`.

| Check | Exact command or exact-command evidence | Result |
|---|---|---|
| Interpreter | `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV` | Python 3.12.13 |
| Environment | `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv PYTHONDONTWRITEBYTECODE=1 ./check_venv.sh --no-bootstrap` | PASS; active-checkout import binding |
| Rules | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` | 74 active v3.0 rules; exit 0 |
| Focused sourcing suite | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest -o addopts='' -p no:cacheprovider --no-cov tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_coverage.py tests/wind/test_power_curve_sourcing_skip_integrity.py -q --tb=short` | **46 passed, 1 warning in 1.80 seconds**, exit 0 |
| Ruff | `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff check --no-cache tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | All checks passed |
| Ruff formatting | `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff format --check --no-cache tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | 2 files already formatted |
| Scoped types | `PYTHONDONTWRITEBYTECODE=1 /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/mypy --follow-imports=silent --cache-dir=/dev/null tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | Success: no issues found in 2 source files |
| Whitespace | `git diff --check` | Exit 0; repeated at final preflight |
| Scope | `git diff 5ec33d32834c18e8c14dff06617ff92fec365828 HEAD --stat` | Exactly four subject files; 360 insertions, 43 deletions |
| Identity | `git status --short --branch`, `git worktree list`, `git rev-parse HEAD HEAD^{tree}`, `git merge-base HEAD 5ec33d32834c18e8c14dff06617ff92fec365828` | Frozen identities matched; clean |
| Protected head | `git ls-remote origin refs/heads/main` | Frozen base matched at ingress and final inventory |
| Live PRs | `gh pr list --state open --limit 100 --json number,title,headRefName,headRefOid,baseRefName` | No H01 PR at ingress |
| HOLD state | `gh issue view 1110 --json number,state,title,body` and `gh issue view 1229 --json number,state,title` | Both OPEN; applicable HOLD retained |

The three substantive reviewer probes used this exact interpreter prefix:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python - <<'PY'
```

Their complete here-document command bodies and original results are preserved in this reviewer’s durable session:

`/Users/aruna/.codex/sessions/2026/09/08/rollout-2026-09-08T23-41-13-01a08237-8a83-7c20-bc07-121891ba0c3e.jsonl`

Use the following result-chunk identifiers to locate the corresponding exact invocation; preserve the scripts as reproduction evidence alongside this disposition:

| Probe | Exact invocation locator | Result |
|---|---|---|
| Independent real-data matrix, original assertion AST comparison, actual-source AST mutation | `8f0054` | **45 observations matched expected outcomes**; 48 original assertion ASTs preserved; mutant killed; exit 0 |
| Corrected historical source replay against the collected guard | `90ac03` | **12 failed, 6 passed, 0 skipped in 1.54 seconds**; nested pytest exit 1 as expected; outer verification exit 0 |
| Local-data execution and corrected negative-power control | `fd5d7a` | Packaged local CSV read, zero network-mode calls; invalid power failed; restored fetch passed; exit 0 |

The initial historical replay, locator `b0d8b8`, was a **reviewer harness failure**. It patched `tests.wind.test_power_curve_sourcing`, while pytest collected `wind.test_power_curve_sourcing`. It therefore returned 18 passing guard tests and failed the outer expected-count assertion, exit 1. The corrected probe patches `item.module.sourcing_tests` in a `trylast` collection hook and records the actual collected module name. Its 12-failure result supersedes that initial attempt.

The first large probe also emitted a pandas chained-assignment warning from the reviewer’s negative-power injection. The subsequent probe uses a copied DataFrame and a single `.loc[...] = ...` assignment, verifies the injected value, observes the expected original-test `AssertionError`, and passes the restored control. That warning was in the reviewer harness, not introduced candidate code.

Black, isort and pre-commit were **not independently rerun**: the writer’s receipts were inspected, and this review independently executed Ruff, formatting and scoped mypy. Full-suite, local coverage, financial regression, QSTS, qualifications and native five-run acceptance were **not run**, consistent with the bounded profile and native owner’s priority. Hosted CI is a subsequent delivery gate, not supplied by this review.

`independent_oracles_or_counterexamples`

The principal independent oracle used the installed third-party packages and actual original test functions. It did not replace the sourcing functions with stubs that directly raised the desired errors.

- **Assertion preservation:** Parsed the base and candidate source with Python AST and compared every original function’s assertion ASTs. All **48 assertions across 17 original functions** were preserved. The source diff also retains the original numerical tolerances, provenance strings, Ct presence/absence checks, Ct length/range checks, and curve-validation calls.
- **Real-data controls:** The original list, OEDB fetch, reference-thrust and reference-list/fetch functions all passed before hostile probes, after them, and after the mutation—**12 passing real-data control observations**.
- **Wind-data failures:** Empty manufacturer results, wrong nominal watts, reversed wind-speed ordering, negative source power, wrong returned source provenance, missing required CSV columns, missing IEA Ct, out-of-range IEA Ct, unexpected NREL Ct and wrong 15 MW reference rating all produced the expected `AssertionError` or `ValueError`. An internal reference-listing `ImportError` propagated.
- **Genuine discovery absence:** Removed each target package’s top-level cache entry and excluded site-packages from the process-local search path. `find_spec()` returned `None`; all four original test paths intentionally raised pytest’s skip exception.
- **Broken installed imports:** After proving normal discovery succeeded, intercepted the actual import boundary with transitive `ModuleNotFoundError`, internal `ModuleNotFoundError`, ordinary `ImportError`, and native-library-style `OSError`, across all four original paths. **All 16 cases failed; none skipped.** Existing production wrappers convert some import errors to actionable `ImportError`; the tests now allow those failures to propagate.
- **Meaningful guard mutation:** Compiled the actual candidate OEDB test function in memory with a broad `except Exception: pytest.skip(...)` around its body, then supplied an empty listing. The new guard raised **`pytest.fail.Exception` containing “unexpected skip”**. It did not pass or become a skipped guard.
- **Predecessor replay:** Executed the protected-base test source in pytest’s actual collected subject module. The new guard failed the original empty-list, wrong-rating, thrust-parser, internal-listing and eight broken-import cases: **12 failed / 6 passed / 0 skipped**.
- **Local-data claim:** Inspected installed `windpowerlib` **0.2.2** source and executed the original listing test with the online loader replaced by a failure sentinel. The signature was `(turbine_library='local', print_out=True, filter_=True)`; exactly the packaged `windpowerlib/oedb/turbine_data.csv` was read; online-loader call count was **zero**. The WindTurbine constructor likewise resolves its default `"oedb"` path to packaged files.

`predecessor_finding_matrix`

| Finding ID | Applicability | Independent evidence | Result |
|---|---|---|---|
| H01-WIND-EMPTY | Original listing assertion could become a skip | Empty real listing input now raises `AssertionError`; historical replay fails the guard | **CLOSED** |
| H01-WIND-RATING | Wrong OEDB capacity could become a skip | Wrong nominal watts now raises `AssertionError`; valid controls pass | **CLOSED** |
| H01-WIND-PARSER | Initial reference fetch parsing failure could become a skip | Real CSV parser receives malformed columns and raises `ValueError`; historical guard replay fails | **CLOSED** |
| H01-WIND-LOCAL | Online/network explanation unsupported for the default listing | Installed-source inspection plus local-CSV execution with network failure sentinel | **CLOSED** |
| H01-WIND-IMPORT | Profile extension: internal/transitive import failures, including reference listing, must not be excused | Sixteen independent import probes; historical eight-case reproduction; internal listing probe | **CLOSED** |
| H01-WIND-GUARD | A regression guard must not count original-test skip as success | Compiled original-function broad-catch mutation produces guard failure | **CLOSED** |
| PREDECESSOR-JOBS | Installed-dependency skip in jobs tests | Different files and separately scoped follow-up | **NOT_APPLICABLE** to H01; no closure claimed |
| PREDECESSOR-REPORT | Installed-dependency skip in renderer tests | Different files and separately scoped follow-up | **NOT_APPLICABLE** to H01; no closure claimed |
| PREDECESSOR-PANDAS | Installed-dependency skip in MC export tests | Different files and separately scoped follow-up | **NOT_APPLICABLE** to H01; no closure claimed |

`findings_and_residual_limitations`

| ID | State | Finding or limitation |
|---|---|---|
| H01-DOMAIN-BLOCKERS | None | No `BLOCKS_CURRENT_CANDIDATE` finding |
| H01-RESIDUAL-UPSTREAM | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | The installed windpowerlib listing emits the pre-existing pandas downcasting `FutureWarning`. It does not affect the observed assertions, is disclosed in the implementation record, and requires no production or dependency change in this repair. |
| H01-RESIDUAL-SCOPE | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | Controlled package fixtures and reference-curve tests prove software behavior. They do not certify turbine data, Ct physics, commercial OEM suitability, or bankable resource assessment. |
| H01-RESIDUAL-DISCOVERY | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | The gate tests top-level import discoverability, not package health. Broken discoverable packages intentionally continue into the loader and fail. This is the requested behavior. |
| H01-RESIDUAL-DELIVERY | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | This is substantive exact-object acceptance. Receipt insertion, PR creation, final-head rebind and required hosted CI remain separate mandatory steps. |
| H01-NATIVE | `TRACKED_IN_NAMED_ISSUE` | Issue #1229 remains OPEN under the separately owned native-grid workstream. H01 offers no native-crash acceptance or HOLD effect. |
| H01-REVIEW-HARNESS | `SUPERSEDED_BY_SUCCESSOR_FINDING` | Initial duplicate-module historical replay and warning-producing injection were corrected and rerun as disclosed above. They do not support an adverse candidate finding. |

The implementation record’s substantive description is consistent with the reviewed code. Its pre-review and hosted-CI-pending statements are accurate for the frozen checkpoint. Its writer-side counts are explicitly writer receipts; the independently obtained counts are recorded separately above.

The following inventory binds the reviewed subject and additional governing/source objects for later continuity checks. All listed working-tree blobs matched their candidate Git blobs when verified. Files marked as execution dependencies or policy context are included conservatively; inclusion does not imply a complete semantic audit of those systems.

```text
# path<TAB>candidate git blob
changelog.d/hygiene-wind-failures.fixed.md	945ed3dad6913d0c835436a6fa9d78b38d84ab33
docs/H01_IMPLEMENTATION.md	85611d992b15740ef75fd0e81af56ef17f9e5460
tests/wind/test_power_curve_sourcing.py	80546f200428be27909d1487faa1784754086ee0
tests/wind/test_power_curve_sourcing_skip_integrity.py	c4f1df3423663f221f1d3b8b16c80fe592484d46

# Additional production/test objects read
wind_resource/power_curve_sourcing.py	2df6561d283baba22306823261e52800f57b1568
tests/wind/test_power_curve_sourcing_coverage.py	293137b29378683b142bf408e1179111338e9fb6

# Governing and ingress objects
AGENTS.md	766078ee1551044766bc39eca567f65d27936d90
go_with_the_flow_rules_v3_0_clean.csv	e4eb130a8cc292b1bb9b87706b40568b832afc57
docs/governance/recruit_01/01_capability_and_risk.md	4b5cdfbf7500d9b5abb32400b013bc2d291112df
docs/governance/recruit_01/02_writer_lease_and_recovery.md	9c088a835171388da2da71885e119e8dc48db787
docs/governance/recruit_01/03_independent_review_and_attestation.md	b6616416d25859d9e356c3ca25e85fe2d0d8aefc
docs/governance/recruit_01/04_staged_delegation_and_ingress.md	b2f1963bc8a81fa45809024d3bfa1b8a2013fd2f
docs/SESSION_HANDOVER_2026-09-07.md	b7b40063f3093cabbc4db32355e36f5c774fcd06
docs/SESSION_HANDOVER_2026-09-08_PR1237.md	6d630ffb013667eeabb194fa688697bab25d5438
docs/SESSION_HANDOVER_2026-09-08_PR1243.md	3211d976c987057995628fad20de731a1f8b9669
pyproject.toml	e71355e66aba5cc38dfd1b56151072268a8c751c
config/stochastic_test_policy.yaml	9c1f8c82230000794cc7b70fcb23d7e3e9e6c020
config/report_test_policy.yaml	ab247d06c341f3753d4866347668d609e30b0afb
config/grid_ci_policy.json	369d9c9c527e604951834768da1993e9749816b8

# Partial policy-context inspection and execution dependencies
tests/conftest.py	d4b2c52532f612453e23a2e76c3a05c668b9dee8
.github/workflows/test-suite.yml	e59739e69779f4399f1c79b1e58fa11aaed73b33
.pre-commit-config.yaml	c0946df1cc481b47a51571cab48f0f48960b5a6d
wind_resource/energy_calculator.py	0c01f74b4ad4effad9669f7968f44dcd78a75271
wind_resource/config/power_curves.yaml	97a9bd298196589e69ea33c0430c4a2d099f3e3b
```

Installed-source provenance for the local-data and real-reference controls, beneath `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/lib/python3.12/site-packages/`:

```text
# path<TAB>SHA-256
windpowerlib/data.py	99527d395b02430f86770390cb4bf65450dab1b5b19e7799fcfb59adf8e188b4
windpowerlib/wind_turbine.py	406950a501d7bb26384d9287ea91e5d26fb38ed3ab418639c888b65f7caf4aee
windpowerlib/oedb/turbine_data.csv	d379379ba20fe41ec151f74ad5ddf368f9e1cce596756ccea73888d0614c3840
windpowerlib/oedb/power_curves.csv	7d91ddde701ce6d0ac4cacb31fac04b38f0664921b75ca44c174ca26cd394add
turbine_models/__init__.py	41af212d13a7518c67cfcd44a2897e49ea36ef367ca2782da897f883e5963e92
turbine_models/data/Offshore/IEA_Reference_10MW_198.csv	cfbe42430368ce151e97e7f1283fa789060d7541c231d5d83da248bd54d3eef2
turbine_models/data/Offshore/2016CACost_NREL_Reference_10MW_205.csv	a3352c66905bfa3b93e17904efdcd4014d9923c6f3e98c2864e56da47e4f431a
turbine_models/data/Offshore/IEA_Reference_15MW_240.csv	5741b87187237994c45af18259704edbff331dfb1bb12a04d95da2bb3aeabd05
```

Observed package versions were windpowerlib **0.2.2**, turbine-models **0.2.2**, pytest **9.1.1**, and pandas **2.3.3**.

**This acceptance does not automatically transfer across a changed subject or moved base.** A receipt-only final-head rebind must verify the original disposition, unchanged subject blobs and named receipt delta. A base move additionally requires the recorded blob identities, bidirectional import/normative-reference isolation, and complete reviewed-to-updated diff prescribed by RECRUIT-01.

I created no source, documentation, review, index, ref or external-state mutation. The coordinator must persist this original body and the exact reproduction scripts. Final status remained clean at `acd64af762643dd3e85dd64566711f68f8f33faf`, tree `4630738c62859e5fd390dcb8a68847db72739641`.

<!-- H01_ORIGINAL_BODY_END -->
