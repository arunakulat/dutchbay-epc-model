**ACCEPTED for the exact frozen H07 candidate**, with the disclosed legacy typing limitations retained. Independent execution demonstrated that the repaired guards reject incorrect coefficients, misleading normalized variance shares, a shared inert FX driver, and missing committed input. This is substantive assurance acceptance; final delivery-head rebind and required hosted CI remain separate gates.

```yaml
reviewer_role: "Independent test/evidence assurance reviewer; R2_LOAD_BEARING"

reviewer_identity:
  agent: "/root/assurance_review"
  session_id: "01a08416-5606-7b51-8293-caba395616e6"
  parent_session_id: "01a0840e-8e5f-7393-a425-34519b444044"
  model: "gpt-6-astra"
  reasoning_effort: "xhigh"
  execution_identity_evidence: >-
    Independently parsed this reviewer's session_meta and turn_context:
    actual model gpt-6-astra, effort xhigh, and the assigned 5f4a worktree.
    Project listing confirms DutchBay_EPC_Model and the durable repository;
    the H07 project-creation receipt and parent-session relationship were read.
  independence: >-
    Distinct from coordinator/writer. No access to the other reviewer's initial
    disposition. No implementation contribution.

candidate_commit: "26dfa0dd4fa54f73a1a82ab968691b2684a7233a"
candidate_tree: "2eb450293a26046e3b9dd1795b335f6cc56705ba"
base_sha: "c17fc42b36ed93736d88e5cc229b048992c5882e"
merge_base_sha: "c17fc42b36ed93736d88e5cc229b048992c5882e"
subject_manifest_sha256: "b2c69a0ccb68b4d056e79d9221c5a0609c78cdd12dde1914980fc925f163eef3"

corpus_and_rule_identities:
  governance:
    - "Complete current go_with_the_flow_rules_v3_0_clean.csv"
    - "AGENTS.md"
    - "All four canonical docs/governance/recruit_01 modules"
    - "Full pinned dutchbay_gwtf_ruleset_and_framework_acronyms.md"
    - "SESSION_HANDOVER_2026-09-07.md startup/bootstrap"
    - "SESSION_HANDOVER_2026-09-08_PR1237.md"
    - "SESSION_HANDOVER_2026-09-08_PR1243.md"
  csv_sha256: "0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1"
  csv_last_change_commit: "dbd924a00dd4b29e23139da768a8f2603396dc17"
  assurance_profile_sha256: "8295d12fcc1acff69b54d59bfdc40fdca9f7c41d734c168c02cc1272b0b23f30"
  preparation_profile_sha256: "4990baaa92c9046c887ea4fd37ddf3c0b66670c1a6d2381aa15944956a13c12c"
  diagnosis_domain_sha256: "6a8116dbfdfd5085f6aa4b8d931f3f86fefc823d3b30b50cb2c623bafed9a787"
  basecase_scenario_sha256: "bde22faf4f803a8309a6f40db68718f554c00ca5f69cad02d395daeb2f6c500e"
  checks_001_sha256: "63ac30ad14289ed2c8d38f1f4164ae35502a034e98c8b1310e4a859c4584fab8"
  primary_evidence_read:
    - "H07/PREPARATION_PROFILE.md and diagnosis_domain.md"
    - "Original f2f3/test_hygiene/TEST_HYGIENE_REPORT.md"
    - "H07 source leases, checkpoint, manifest and initial validation records"
    - "Both original and corrected writer negative-control scripts and results"
    - "STRICT_TYPES_BASE_COMPARISON.json"
    - "Complete candidate diff and repaired test bodies"
    - "analytics/fx_sensitivity_real.py implementation"
    - "Canonical evaluation gateway and configuration-merge implementation"
    - "Committed base-case scenario"
    - "Pre-existing real coverage tests and CLI tests/implementation"
  scope_exclusions: >-
    No fresh whole-finance, D0-D3, native-grid, stochastic qualification or
    production release review was undertaken. Historical handover constraints
    were not converted into current delivery claims.

review_scope:
  changed_paths:
    - "tests/analytics_layer/test_fx_sensitivity_real.py"
    - "changelog.d/hygiene-fx-integration.fixed.md"
  assessment: >-
    Restore the committed-base-case integration, repair both stale mocked
    oracles, verify independent statistics, meaningful failure sensitivity,
    missing-input and cwd behavior, source identity, evidence accuracy,
    typing limitations and authority boundaries.
  scope_identity: >-
    Exactly these two paths differ from the protected base. All 18 sorted
    subject-manifest entries matched both candidate Git blobs and on-disk bytes.
    Production analyzer, gateway, scenario and calculation sources are unchanged.

checks_executed_and_exact_results:
  - command: "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV"
    result: "PASS; Python 3.12.13."
  - command: >-
      DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
      ./check_venv.sh --no-bootstrap
    result: >-
      PASS; governed external environment, correct active-checkout analytics
      import, no foreign checkout paths, no editable project installation.
  - command: >-
      DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv"
      DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
      /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python
      dutchbay_bootstrap_rules.py
    result: "PASS; 74 active v3.0 rules."
  - command: "git ls-remote origin refs/heads/main"
    result: >-
      PASS at initial and final checks; protected remote main remained
      c17fc42b36ed93736d88e5cc229b048992c5882e.
  - command: "git status --short --branch; inspected independently with git worktree list"
    result: >-
      Clean codex/h07-fx-integration, ahead of origin/main by one candidate
      commit. Final status remained clean.
  - command: >-
      git diff --check c17fc42b36ed93736d88e5cc229b048992c5882e
      26dfa0dd4fa54f73a1a82ab968691b2684a7233a
    result: "PASS; exit 0."
  - command: >-
      PYTHONDONTWRITEBYTECODE=1
      /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff check
      --no-cache tests/analytics_layer/test_fx_sensitivity_real.py
    result: "PASS; all checks passed, exit 0."
  - command: >-
      PYTHONDONTWRITEBYTECODE=1
      /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/ruff format
      --no-cache --check tests/analytics_layer/test_fx_sensitivity_real.py
    result: "PASS; one file already formatted, exit 0."
  - command: >-
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
      /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/mypy
      --follow-imports=silent --cache-dir=/dev/null
      tests/analytics_layer/test_fx_sensitivity_real.py
    result: >-
      FAIL as disclosed; exit 1, 21 diagnostics: 20 missing annotations and
      one unused ignore. Strict whole-file typing success is not claimed.
  - command: >-
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
      /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/mypy
      --follow-imports=silent --cache-dir=/dev/null
      /Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H07/delivery/baseline_typecheck/test_fx_sensitivity_real.py
    result: >-
      FAIL; exit 1, 26 diagnostics. Independently verified that this baseline
      file and the preserved original exactly match the protected-base blob.
      Candidate diagnostics pre-exist; five baseline diagnostics are removed.
  - command: "Exact independently authored command retained in ASSURANCE_PROBE_001.sh"
    result: >-
      PASS; exit 0 in 4.64 seconds. Three repaired guards passed before and
      after mutation; seven hostile cases were killed by AssertionError;
      integration passed from cwd /; three pre-existing real lender oracles
      passed; closed-form slopes and pairwise variance checks passed.
      Zero Python warnings. Existing model limitation messages were counted
      separately and were not represented as absent.
  - command: "gh issue view 1110 --json number,state,title,updatedAt"
    result: "Issue 1110 remains OPEN."
  - command: "Full local pytest suite, native campaign, hosted CI and QSTS"
    result: >-
      not run - bounded read-only assurance scope and native campaign ownership.
      Hosted exact-final-head gates remain mandatory for delivery.
  - command: "Writer's complete 78-test focused suite and pre-commit command"
    result: >-
      not rerun by this reviewer - source bodies and receipts inspected;
      three repaired guards and three pre-existing real-engine oracles executed
      directly instead. Writer reports 78 passed, zero skips/warnings and passed
      applicable hooks; these counts remain writer evidence.

independent_oracles_or_counterexamples:
  probe_shell_sha256: "63e0403095d3856a316cf145272a41b28b57434526edec63765f48110b5198bc"
  probe_output_sha256: "83b8b4a829ca60643cdfbbb7170d2f4b998fe23b711a12c4bdb5878c5ea0f1a9"
  hostile_results:
    - "Halve FX coefficient while preserving sign, R2 and shares: all three repaired guards reject."
    - "Replace variance shares with equal thirds, still summing to one: variance and integration guards reject."
    - "Feed the retired FX key to BOTH analyzer and reference gateway: integration responsiveness rejects."
    - "Make only committed scenario is_file return false: explicit missing-scenario assertion rejects before engine execution."
  positive_results:
    - "Three unmodified controls pass before and after the hostile matrix."
    - "Actual integration body passes with process cwd /."
    - "Pre-existing test_fx_rate_sweep_is_live_against_the_real_engine passes."
    - "Pre-existing test_analyze_fx_sensitivity_is_live_against_the_real_engine passes."
    - "Pre-existing test_run_base_metric_identical_after_fx_shock_retirement passes."
  independent_statistics: >-
    Used the closed-form endpoint slope for equally spaced three-point grids,
    and Var(Y) = sum over i<j of (Yi-Yj)^2 / n^2. This calculation used neither
    the analyzer's NumPy fit nor the candidate's statistics.linear_regression
    and pvariance oracles.
  reproduced_values:
    baseline_project_irr: 0.04201694802923463
    fx_rate_slope: -0.12439002286827323
    hedge_ratio_slope: 0.003572241819486205
    spread_slope_per_bp_under_full_hedge: -0.000012475334473409649
    total_sweep_variance: 0.000027988281651782565

predecessor_finding_matrix:
  id_note: "Identifiers below are reviewer-local labels for the cited predecessor findings."
  findings:
    - finding_id: "H07-P01 permanent integration skip"
      applicability: "Direct"
      probe_evidence: "Decorator removed; real candidate integration executed successfully."
      result: "CLOSED"
    - finding_id: "H07-P02 retired-field regression mock"
      applicability: "Direct"
      probe_evidence: "Live-rate mock and nonzero slope assertion; halved-slope hostile case rejected."
      result: "CLOSED"
    - finding_id: "H07-P03 retired-field variance mock and sum-only oracle"
      applicability: "Direct"
      probe_evidence: "Live-rate mock and analytic per-driver variance; equal-thirds hostile case rejected."
      result: "CLOSED"
    - finding_id: "H07-P04 missing-input skip and cwd dependence"
      applicability: "Direct"
      probe_evidence: "Explicit missing-scenario assertion; real integration passed from /."
      result: "CLOSED"
    - finding_id: "H07-P05 misleading magnitude/risk-decomposition interpretation"
      applicability: "Direct"
      probe_evidence: "Removed mixed-unit ranking; test and changelog disclose full-hedge spread and mixed-regime variance."
      result: "CLOSED"
    - finding_id: "H07-V01 initial negative-control harness error"
      applicability: "Evidence accuracy"
      probe_evidence: >-
        Original copied-globals probe and failure preserved. Corrected probe
        binds the function to live module globals; independent assurance
        counterexamples now also fire.
      result: "CLOSED"
    - finding_id: "H07-V02 strict legacy typing"
      applicability: "Residual"
      probe_evidence: "Independent strict mypy: protected base 26, candidate 21 pre-existing diagnostics."
      result: "DEFERRED"
    - finding_id: "H07-V03 initial F841 failures"
      applicability: "Direct"
      probe_evidence: "Two unused locals removed under SOURCE_LEASE_002; independent Ruff passes."
      result: "CLOSED"

findings_and_residual_limitations:
  - id: "H07-V02"
    state: "ACCEPTED_RESIDUAL_WITHIN_SCOPE"
    detail: >-
      Existing whole-file annotation debt remains. This candidate adds no
      strict typing defect; its revised oracle functions are annotated.
      The relaxed writer check is accurately qualified and is not a replacement
      for the unchanged hosted type gate. Further whole-file typing belongs to
      the hygiene coordinator's separately scoped maintenance work, with strict
      file-level mypy as its acceptance gate. No HOLD effect.
  - id: "H07-R01"
    state: "ACCEPTED_RESIDUAL_WITHIN_SCOPE"
    detail: >-
      Real reference values share the production financial gateway. This review
      independently verifies wiring, responsiveness and scalar statistics,
      not the complete financial engine or external economic assumptions.
      The shared-inert-driver counterexample specifically challenges false
      agreement between those two paths.
  - id: "H07-R02"
    state: "ACCEPTED_RESIDUAL_WITHIN_SCOPE"
    detail: >-
      Mean R2 and normalized variance across different sweep regimes retain
      their existing interpretation. Neither is a stochastic variance
      decomposition. Hedge direction is scenario-specific, and spread is
      explicitly measured under full hedge for this unhedged scenario.
  - id: "H07-R03"
    state: "ACCEPTED_RESIDUAL_WITHIN_SCOPE"
    detail: >-
      Zero Python warnings does not mean no model caveats. The independent
      probe observed existing placeholder construction/draw timing, discount
      selection and unavailable equity-distribution IRR messages. No source,
      scenario or production change is required to close this test-only repair.
  - id: "H07-V01"
    state: "SUPERSEDED_BY_SUCCESSOR_FINDING"
    detail: >-
      The first writer negative-control execution remains HARNESS_ERROR_NOT_GUARD_EVIDENCE.
      The corrected execution and this independently authored hostile matrix
      supply replacement guard evidence without rewriting the original.

hold_and_authority_effect: >-
  None. Issue 1110 and all professional, lender, Board, evidence, release,
  deployment, publication and other HOLD boundaries remain unchanged.
  Native campaign ownership remains untouched. Acceptance does not establish
  final-head CI, merge readiness, grade or financial qualification.

disposition:
  semantic_decision: "ACCEPTED"
  evidence_yield: "EVIDENCE_RETURNED"
  blockers_current_candidate: []
  binding: "Only the exact candidate/tree/base/manifest identified above."
  delivery_boundary: >-
    Obtain the separate independent domain disposition, preserve originals,
    add only authorized receipts, and perform both final-head rebinds with
    unchanged subject blobs. Required hosted checks and protected-base
    currency must then be proved on the final delivery head.

mutation_attestation: >-
  No repository, file, index, ref, branch, worktree, PR, issue or environment
  mutation by this reviewer. The behavioral probe installed a process audit
  hook rejecting file/metadata writes; its temporary mocks and cwd change
  were restored. Ruff used --no-cache and mypy used /dev/null as cache
  destination. Coordinator, not reviewer, persisted the exact probe command
  and original tool output. Final subject hashes and clean Git state matched.
```

The exact independently executed probe and original result are retained at [ASSURANCE_PROBE_001.sh](/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H07/delivery/ASSURANCE_PROBE_001.sh) and [ASSURANCE_PROBE_001_OUTPUT.json](/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H07/delivery/ASSURANCE_PROBE_001_OUTPUT.json). I independently verified both retained hashes against the identities above.
