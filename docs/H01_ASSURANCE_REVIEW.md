# H01 assurance review — original transported disposition

Reviewer session: `01a08238-237a-75d1-a214-3bc6c31b0be4`. Original body SHA-256: `109d3298cb27d7f7115914d59cbb1cb4500546dc93ae74422917d074ef5eabf8`.
Original body length: 20711 UTF-8 bytes. The bytes between the following
markers preserve the delivered reviewer body, including its trailing newlines.

<!-- H01_ORIGINAL_BODY_BEGIN -->
**ACCEPTED for the frozen H01 substantive candidate.** The change restores failure visibility without removing existing assertions or changing production behavior. Independent execution confirmed the repaired tests reject empty listings, wrong capacity, malformed data, and broken imports. Replaying the immutable base test source against the new guard produced **12 failures and zero skips**, bracketed by **18 passing controls** before and after.

```yaml
reviewer_role: H01 independent PYTHON/ASSURANCE reviewer
reviewer_identity:
  agent: /root/h01_assurance_review
  nickname: Parfit
  session_id: 01a08238-237a-75d1-a214-3bc6c31b0be4
  model: gpt-6-astra
  reasoning_effort: xhigh
  independence: >
    Distinct from the sole writer, coordinator and wind-domain reviewer.
    No wind-domain disposition was read or used to anchor this conclusion.
  evidence_yield: EVIDENCE_RETURNED

candidate_commit: acd64af762643dd3e85dd64566711f68f8f33faf
candidate_tree: 4630738c62859e5fd390dcb8a68847db72739641
base_sha: 5ec33d32834c18e8c14dff06617ff92fec365828
merge_base_sha: 5ec33d32834c18e8c14dff06617ff92fec365828
subject_manifest_sha256: 8a40ecc0fe9bd348b22ffb827bcf44a86ab0485d02af1e7bf71cfd73e56af158

corpus_and_rule_identities:
  repository: /Users/aruna/.codex/worktrees/440e/dutchbay-epc-model
  branch: codex/h01-wind-test-integrity
  project: DutchBay_EPC_Model
  project_and_execution_configuration: >
    Project association supplied by actual coordinator dispatch.
    delivery/task_configuration.json records this reviewer session as
    gpt-6-astra/xhigh in the assigned worktree.
  governed_interpreter: /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python
  python_version: 3.12.13
  canonical_rules:
    path: go_with_the_flow_rules_v3_0_clean.csv
    sha256: 0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1
    bootstrap_result: 74 active rules, version v3.0
    ingress: Complete current CSV read; bootstrap executed successfully.
  framework_definitions:
    path: /Users/aruna/.Codex/projects/-Users-aruna-Downloads/memory/dutchbay_gwtf_ruleset_and_framework_acronyms.md
    sha256: c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af
    ingress: Full pinned definitions read; current CSV controls.
  recruit_01:
    ingress: All four canonical operational modules read in full.
    risk_class: R2_LOAD_BEARING
    boundary: Separate task-domain and assurance review; one veto blocks.
  startup_and_successors:
    - AGENTS.md
    - docs/SESSION_HANDOVER_2026-09-07.md
    - docs/SESSION_HANDOVER_2026-09-08_PR1237.md
    - docs/SESSION_HANDOVER_2026-09-08_PR1243.md
  delivery_profile:
    path: /Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H01/DELIVERY_PROFILE.md
    sha256: 3db3dbec513fccb31170c9f25f26e31d9399d7454b1e9374c79bf4b8062a60ae
  worktree_brief:
    sha256: fa968912b37d7b727ad303a871ff1b442b2312ad5c521c1a9fdc13c0248bcfec
  predecessor_diagnosis:
    path: /Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/test_hygiene/assurance_diagnosis.md
    sha256: 3f7f81f2dce0bf8b57410281736eeb9e47ea0a18868775c32ac5bf423e4cc53a
    treatment: Hypothesis independently replayed, not acceptance evidence by itself.
  delivery_records:
    ingress: WORKTREE_BRIEF, leases 001-004, baseline, freeze and task configuration read.
    baseline_sha256: ac84e130fcfd73d7b941ab7597901b25195325c99f1fadcfc738cef3bdd7a73d
    freeze_sha256: d3c58326c28b1c68b1d87a2e9dd1dd87f3d2e447b2d5b9ceee5dbcf7ff337b96
    task_configuration_sha256: b0a5e74a98811b5b76a85a028fdeecd6e31e7014d658ded70e4958162abf50bd
  policies:
    - pyproject.toml
    - config/stochastic_test_policy.yaml
    - config/report_test_policy.yaml
    - config/grid_ci_policy.json
    - Relevant import, fixture and collection sections of tests/conftest.py
  live_external_state:
    protected_main: 5ec33d32834c18e8c14dff06617ff92fec365828
    issue_1110: OPEN
    issue_1229: OPEN
    h01_pr: No H01 PR present in the open-PR listing at this substantive review.
    verification: Read-only gh queries and git ls-remote; protected head rechecked at completion.
  skill:
    path: /Users/aruna/.codex/plugins/cache/claude-cowork/engineering/1.2.0/skills/code-review/SKILL.md
    treatment: Read and applied.

review_scope:
  substantive_objects:
    - changelog.d/hygiene-wind-failures.fixed.md
    - docs/H01_IMPLEMENTATION.md
    - tests/wind/test_power_curve_sourcing.py
    - tests/wind/test_power_curve_sourcing_skip_integrity.py
  source_ingress: >
    Read the complete production power_curve_sourcing module, both existing sourcing
    test files, the new integrity test, the complete candidate diff and implementation
    record. Inspected installed windpowerlib get_turbine_types implementation.
  examined_properties:
    - Top-level package discovery and intentional absence gating.
    - Discoverable but broken package imports and retained exception causes.
    - Execution of original collected test functions and production loaders.
    - Preservation of all existing assertion ASTs.
    - Hostile fixtures, restoration and skip-to-failure guard behavior.
    - Truthful implementation-record scope and delivery boundaries.
    - Exact four-file scope with unchanged production and policy objects.
  exclusions: >
    No production repair, dependency change, environment change, native-grid investigation,
    full-suite campaign, financial qualification, publication or issue closure.

checks_executed_and_exact_results:
  receipt_location: >
    Exact shell/heredoc commands and outputs are in this reviewer's session record:
    /Users/aruna/.codex/sessions/2026/09/08/rollout-2026-09-08T23-41-52-01a08238-237a-75d1-a214-3bc6c31b0be4.jsonl.
    The in-memory probe source is retained there; no probe source file was written.
  identity_preflight: >
    pwd; git status --short --branch; git worktree list; git rev-parse HEAD HEAD^{tree};
    git merge-base HEAD 5ec33d32834c18e8c14dff06617ff92fec365828.
    PASS: assigned worktree/branch, exact candidate/tree/base, clean state.
  environment: >
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV;
    DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
    ./check_venv.sh --no-bootstrap.
    PASS: Python 3.12.13; governed prefix; active-checkout analytics import;
    no foreign checkout path or editable-project contamination.
  bootstrap: >
    PYTHONDONTWRITEBYTECODE=1
    DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv"
    PYTHONPATH="$PWD"
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py.
    Exit 0; 74 active v3.0 rules.
  focused_pytest: >
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest
    -o addopts='' -p no:cacheprovider --no-cov
    tests/wind/test_power_curve_sourcing.py
    tests/wind/test_power_curve_sourcing_coverage.py
    tests/wind/test_power_curve_sourcing_skip_integrity.py -q --tb=short.
    Exit 0; 46 passed, 1 warning in 1.77 seconds.
  independent_original_function_matrix:
    evidence_output: "Tool output chunk 46010c; complete heredoc in session record."
    result: >
      25 expected outcomes: eight real installed-package controls passed;
      two hostile results raised AssertionError; two parser probes raised ValueError;
      one internal listing probe raised ImportError; eight broken-import probes
      raised ImportError or its ModuleNotFoundError subtype with the expected cause;
      four independently simulated undiscoverable-package cases intentionally skipped.
      No hostile failure became a skip.
  executable_base_source_mutation:
    evidence_output: "Tool output chunk d38345; complete parent/child harness in session record."
    child_harness_sha256: c53fc967baf43d4263aecc5c2c373b0de758f7263f11fbc4eb7000309b3fad0a
    invocation: >
      Three independent Python subprocesses ran pytest.main with
      ['-o','addopts=','-p','no:cacheprovider','--no-cov',
      'tests/wind/test_power_curve_sourcing_skip_integrity.py','-q','--tb=no'].
      The middle subprocess's collection plugin substituted an in-memory module compiled
      from git show 5ec33d32834c18e8c14dff06617ff92fec365828:tests/wind/test_power_curve_sourcing.py.
    before_control: "Exit 0; 18 passed, 0 failed, 0 skipped."
    base_source_mutant: "Exit 1; 6 passed, 12 failed, 0 skipped."
    after_control: "Exit 0; 18 passed, 0 failed, 0 skipped."
  fixture_isolation:
    evidence_output: "Tool output chunk 4b5f9b."
    result: >
      Guard-only pytest run exited 0. All 18 preloaded windpowerlib/turbine_models
      module and submodule identities matched afterward; sys.meta_path object identity
      and pandas.read_csv function identity were restored.
  assertion_integrity:
    result: >
      AST comparison against the immutable base passed for all 48 existing assertions,
      including assertion messages. No original assertion was removed or changed.
  ruff_lint: >
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff check --no-cache
    tests/wind/test_power_curve_sourcing.py
    tests/wind/test_power_curve_sourcing_skip_integrity.py.
    Exit 0; all checks passed.
  ruff_format: >
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff format --check --no-cache
    tests/wind/test_power_curve_sourcing.py
    tests/wind/test_power_curve_sourcing_skip_integrity.py.
    Exit 0; 2 files already formatted.
  black: >
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/black --check --no-cache
    tests/wind/test_power_curve_sourcing.py
    tests/wind/test_power_curve_sourcing_skip_integrity.py.
    Exit 0; 2 files would be left unchanged.
  isort: >
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/isort --profile=black --check-only
    tests/wind/test_power_curve_sourcing.py
    tests/wind/test_power_curve_sourcing_skip_integrity.py.
    Exit 0.
  mypy: >
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
    /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/mypy
    --follow-imports=silent --cache-dir=/dev/null
    tests/wind/test_power_curve_sourcing.py
    tests/wind/test_power_curve_sourcing_skip_integrity.py.
    Exit 0; no issues found in 2 source files.
  diff_and_manifest: >
    git diff --check 5ec33d32834c18e8c14dff06617ff92fec365828 HEAD passed.
    Independently recomputed the manifest SHA-256, sorted path order, changed-path equality,
    candidate blob identities and on-disk git hash-object identities. All passed.
  final_identity: >
    git status --porcelain returned empty; HEAD and tree remained exactly frozen;
    final git ls-remote origin refs/heads/main still returned the reviewed protected base.
  not_run:
    - "Reviewer pre-commit: not run; separate scoped tools were independently executed."
    - "Full local suite and local coverage: not run; prohibited campaign and native-owner priority."
    - "Financial regression, QSTS and qualification: not run; no corresponding behavior change."
    - "Hosted exact-head CI and final-head rebind: not run; belong to subsequent PR delivery."

independent_oracles_or_counterexamples:
  real_data_controls: >
    Executed the four actual existing test paths against installed packages both before
    and after independent monkeypatch probes. No writer-authored positive fixture was
    required for this matrix.
  hostile_loader_results: >
    Patched windpowerlib's listing to an empty DataFrame and changed the actual constructed
    turbine's nominal power to 1000 W. The original listing and rating assertions fired.
    Patched pandas.read_csv to raise an independent parser marker; both reference-loading
    paths propagated it. A production listing ImportError also propagated.
  independent_import_seam: >
    Patched builtins.__import__ at the requested package boundary while find_spec still
    returned a real spec. Each of four original test paths propagated both a transitive
    and an internal ModuleNotFoundError; production wrappers retained the original cause.
  independent_absence_seam: >
    Removed the package from sys.modules temporarily and used a delegating meta-path
    finder that made only the requested package undiscoverable. All four original paths
    intentionally skipped. Restored actual package objects and repeated real controls.
  independent_negative_control: >
    Executed the complete immutable base test source in memory against the candidate guard.
    The 12 expected failure-masking cases failed rather than skipped; the candidate-source
    controls before and after passed. This is executable source replay, not a text predicate.
  local_data_claim: >
    Installed windpowerlib.get_turbine_types has signature
    (turbine_library='local', print_out=True, filter_=True).
    Its local branch reads packaged oedb/turbine_data.csv.
    Production list_oedb_turbines passes only print_out=False.
    Removing the online/network exemption is supported by the inspected implementation.

predecessor_finding_matrix:
  - finding_id: H01-PRE-EMPTY-LIST
    applicability: Applicable
    evidence: Independent real-loader empty-list probe raised AssertionError; base replay failed.
    result: CLOSED
  - finding_id: H01-PRE-WRONG-RATING
    applicability: Applicable
    evidence: Independent actual-turbine nominal-power probe raised AssertionError; base replay failed.
    result: CLOSED
  - finding_id: H01-PRE-PARSER-MASKING
    applicability: Applicable
    evidence: Independent ValueError propagated through thrust/reference paths; base thrust replay failed.
    result: CLOSED
  - finding_id: H01-PRE-INTERNAL-LISTING-IMPORT
    applicability: Applicable extension within the delivery profile
    evidence: Original reference test propagated a production listing ImportError; base replay failed.
    result: CLOSED
  - finding_id: H01-PRE-BROKEN-PACKAGE-IMPORT
    applicability: Applicable
    evidence: Eight independent import probes propagated failures; all eight base-source guard cases failed.
    result: CLOSED
  - finding_id: H01-PRE-ONLINE-EXPLANATION
    applicability: Applicable
    evidence: Installed source defaults to local packaged data; candidate explanation corrected.
    result: CLOSED
  - finding_id: PREDECESSOR-JOBS-REPORT-PANDAS-HYGIENE
    applicability: Separate follow-up outside H01
    evidence: None of those files changed; this review makes no closure claim.
    result: NOT_APPLICABLE

findings_and_residual_limitations:
  - finding_id: H01-ASR-001
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    finding: One existing windpowerlib pandas-downcasting FutureWarning remains.
    reason: >
      Observed in real installed-package controls and the focused run. It is not a swallowed
      failure and does not undermine the repaired assertions. No dependency change is warranted
      within this test-integrity slice.
  - finding_id: H01-ASR-002
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    finding: Controlled packages and discovery probes establish bounded test behavior.
    reason: >
      They do not qualify all third-party releases or genuine external data. Real installed
      controls were independently retained; undiscoverability was simulated without altering
      the persistent environment.
  - finding_id: H01-ASR-003
    state: NOT_APPLICABLE_WITH_REASON
    finding: Native-crash and finance acceptance remain outside this review.
    reason: >
      The four changed files contain no production, dependency, venv, qualification-policy,
      native-grid or finance change. A narrow green test run provides no crash-cure or
      financial-release evidence.
  - finding_id: H01-ASR-RECEIPT-CORRECTION
    state: SUPERSEDED_BY_SUCCESSOR_FINDING
    finding: Reviewer-generated static prose count in the first probe output was wrong.
    correction: >
      That output's literal label said 45 assertions across 18 functions; its actual
      computed assertion count already said 48. A subsequent computed receipt confirmed
      48 assertions across 17 pre-existing functions, including helpers. The successful
      AST equality check was unaffected. Use 48 assertions; discard the earlier prose label.
  - finding_id: H01-ASR-LEGACY-CONFIG-READ
    state: NOT_APPLICABLE_WITH_REASON
    finding: An exploratory cat of retired pytest.ini returned file-not-found.
    resolution: >
      pyproject.toml explicitly identifies itself as the canonical pytest configuration.
      It and current policy files were read; the dependent diff/record read was rerun
      successfully. No test or verification result is inferred from that failed read.

hold_and_authority_effect: >
  This is independent substantive engineering acceptance for the exact frozen subject
  manifest only. It does not merge, close an issue, publish, deploy, release, qualify
  data, cure issue 1229, satisfy the other reviewer's role, or lift issue 1110,
  professional, evidence, finance, lender, Board or other HOLD boundaries.
  PR creation, both final-head rebinds, exact-head required green CI, current-base
  verification and protected merge-tree/ancestry proof remain separate delivery steps.

disposition:
  decision: ACCEPTED
  blocking_findings: 0
  validity: Exact frozen subject blobs and stated base only.
  final_head_rebind: Required separately after the PR exists.
  candidate_subject_change: Requires fresh substantive review.
  base_movement: >
    No automatic transfer. Apply RECRUIT-01 module 3 with every reviewed blob's identity,
    bidirectional import/normative isolation and the complete reviewed-to-updated diff,
    followed by an explicit reviewer disposition.

mutation_attestation:
  source_index_refs_worktrees: No mutation.
  pull_requests_issues_external_state: No mutation.
  persistent_environment_dependencies: No mutation.
  durable_reviewer_files: None written.
  permitted_execution: >
    Read-only tools, narrowly scoped pytest, check-only static tools with caches disabled
    where supported, and process-local monkeypatch/compiled-source probes. Ordinary pytest
    temporary fixtures were used.
  final_git_state: Clean; exact frozen candidate and tree preserved.
```

The reviewed object inventory below includes all four substantive objects and additional source, governance, policy and executed startup objects used in the decision. The `tests/conftest.py` review was limited to the relevant sections identified above. Additional objects were independently verified identical to the protected base.

```text
AGENTS.md	766078ee1551044766bc39eca567f65d27936d90
changelog.d/hygiene-wind-failures.fixed.md	945ed3dad6913d0c835436a6fa9d78b38d84ab33
check_venv.sh	3655721f2c596e56a5c0bcee4f41357511091b74
config/grid_ci_policy.json	369d9c9c527e604951834768da1993e9749816b8
config/report_test_policy.yaml	ab247d06c341f3753d4866347668d609e30b0afb
config/stochastic_test_policy.yaml	9c1f8c82230000794cc7b70fcb23d7e3e9e6c020
docs/H01_IMPLEMENTATION.md	85611d992b15740ef75fd0e81af56ef17f9e5460
docs/SESSION_HANDOVER_2026-09-07.md	b7b40063f3093cabbc4db32355e36f5c774fcd06
docs/SESSION_HANDOVER_2026-09-08_PR1237.md	6d630ffb013667eeabb194fa688697bab25d5438
docs/SESSION_HANDOVER_2026-09-08_PR1243.md	3211d976c987057995628fad20de731a1f8b9669
docs/governance/recruit_01/01_capability_and_risk.md	4b5cdfbf7500d9b5abb32400b013bc2d291112df
docs/governance/recruit_01/02_writer_lease_and_recovery.md	9c088a835171388da2da71885e119e8dc48db787
docs/governance/recruit_01/03_independent_review_and_attestation.md	b6616416d25859d9e356c3ca25e85fe2d0d8aefc
docs/governance/recruit_01/04_staged_delegation_and_ingress.md	b2f1963bc8a81fa45809024d3bfa1b8a2013fd2f
dutchbay_bootstrap_rules.py	0a4bf8b08cd2c0b3361a82b127b35bc172db9fa6
go_with_the_flow_rules_v3_0_clean.csv	e4eb130a8cc292b1bb9b87706b40568b832afc57
pyproject.toml	e71355e66aba5cc38dfd1b56151072268a8c751c
tests/conftest.py	d4b2c52532f612453e23a2e76c3a05c668b9dee8
tests/wind/__init__.py	e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
tests/wind/test_power_curve_sourcing.py	80546f200428be27909d1487faa1784754086ee0
tests/wind/test_power_curve_sourcing_coverage.py	293137b29378683b142bf408e1179111338e9fb6
tests/wind/test_power_curve_sourcing_skip_integrity.py	c4f1df3423663f221f1d3b8b16c80fe592484d46
wind_resource/__init__.py	70daa3f99656b4d2dd507fc9cbc32b6a2049f27f
wind_resource/power_curve_sourcing.py	2df6561d283baba22306823261e52800f57b1568
```

The installed supplementary source inspected was `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/lib/python3.12/site-packages/windpowerlib/data.py`, SHA-256 `99527d395b02430f86770390cb4bf65450dab1b5b19e7799fcfb59adf8e188b4`. Its `get_turbine_types` function source SHA-256 was `801e41ff49e5ff3ec6e5334294c5832bd8a02a440fbdff88b4c9ccdc0f309f39`.

<!-- H01_ORIGINAL_BODY_END -->
