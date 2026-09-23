**ACCEPTED — exact frozen H07 candidate, within the test-only R2 scope.** Independent execution confirms meaningful FX responsiveness, correct coefficient and population-variance oracles, and rejection of the relevant hostile mutations. This is the initial domain disposition; delivery-head rebind remains separate.

```yaml
reviewer_role: independent FX/statistical domain reviewer
reviewer_identity:
  agent: /root/domain_review
  nickname: Euler
  session_id: 01a08416-1582-7db1-917c-b1bc7a6d8359
  parent_session_id: 01a0840e-8e5f-7393-a425-34519b444044
  model: gpt-6-astra
  reasoning_effort: xhigh
  verification: actual session_meta and turn_context read independently
  independence: distinct from coordinator/writer; no other initial disposition received

candidate_commit: 26dfa0dd4fa54f73a1a82ab968691b2684a7233a
candidate_tree: 2eb450293a26046e3b9dd1795b335f6cc56705ba
base_sha: c17fc42b36ed93736d88e5cc229b048992c5882e
merge_base_sha: c17fc42b36ed93736d88e5cc229b048992c5882e
subject_manifest_sha256: b2c69a0ccb68b4d056e79d9221c5a0609c78cdd12dde1914980fc925f163eef3
subject_manifest_verification: sorted; all 18 HEAD and working-file blobs match; rechecked after probes

corpus_and_rule_identities:
  gateway:
    path: AGENTS.md
    sha256: 215dd99e206203b8b859cc0c2b97cf2e0150ea9863a91ccab80a72cabe0f4bcd
  gwtf:
    path: go_with_the_flow_rules_v3_0_clean.csv
    sha256: 0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1
    ingress: complete current CSV; bootstrap passed with 74 active v3.0 rules
  frameworks:
    path: /Users/aruna/.Codex/projects/-Users-aruna-Downloads/memory/dutchbay_gwtf_ruleset_and_framework_acronyms.md
    sha256: c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af
    ingress: full unabridged canonical definitions
  recruit_01: all four current modules read in full; identities verified against manifest and INGRESS_001.json
  handovers: 2026-09-07 startup pointer; applicable 2026-09-08 PR1243 and PR1237 successors; inherited HOLD boundaries
  preparation_profile_sha256: 4990baaa92c9046c887ea4fd37ddf3c0b66670c1a6d2381aa15944956a13c12c
  diagnosis_domain_sha256: 6a8116dbfdfd5085f6aa4b8d931f3f86fefc823d3b30b50cb2c623bafed9a787
  original_hygiene_report_sha256: 751b8b46ed3210c65ddd53fcdfcffff74a594dc75f8bc8254be09d64abd1d22c
  writer_evidence_read:
    - CHECKS_001.json
    - CHECKPOINT_001.json
    - VALIDATION_INITIAL.json
    - NEGATIVE_HARNESS_001_FAILURE.json
    - STRICT_TYPES_BASE_COMPARISON.json

review_scope:
  risk: R2_LOAD_BEARING
  changed_paths:
    - tests/analytics_layer/test_fx_sensitivity_real.py
    - changelog.d/hygiene-fx-integration.fixed.md
  inspected:
    - complete candidate diff and changed test body
    - real FX analyzer and canonical evaluation gateway
    - committed base-case scenario and FX forward/conversion implementation
    - pre-existing FX coverage and CLI oracle bodies
  production_and_scenario_change: none
  project_environment: DutchBay_EPC_Model origin verified; persistent Python 3.12.13; imports resolve into active worktree

checks_executed_and_exact_results:
  identity:
    commands:
      - git status --short --branch
      - git worktree list
      - git rev-parse HEAD HEAD^{tree} origin/main
      - git merge-base HEAD origin/main
      - git ls-remote origin refs/heads/main
    result: clean expected branch; candidate/tree/base match; live protected main equals base
  environment:
    command: DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv PYTHONDONTWRITEBYTECODE=1 ./check_venv.sh --no-bootstrap
    result: PASS; Python 3.12.13; no foreign checkout paths
  rules:
    command: DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py
    result: PASS; 74 active v3.0 rules
  main_probe:
    exact_command_artifact: DOMAIN_PROBE_001_MAIN.sh
    command_sha256: aaa027d49c1f14a70d6bca2d42243fc70895aa0846581b7dec1760202cb26ea0
    original_output_artifact: DOMAIN_PROBE_001_MAIN_OUTPUT.json
    output_sha256: c4e8753aef65b3811edf4a25c623c87e7d17daa0507b14c420ca8fbc38ce7d6b
    result: exit 0; 3+3 passing candidate controls; 8 analyzer mutations killed; 3 pre-existing live oracle bodies passed; 0 Python warnings
  supplemental_probe:
    exact_command_artifact: DOMAIN_PROBE_001_SUPPLEMENTAL.sh
    command_sha256: 7471ba2f7026ef57bf4206c2b0442e06ff602b3c709631b53f66631a14089bd0
    original_output_artifact: DOMAIN_PROBE_001_SUPPLEMENTAL_OUTPUT.json
    output_sha256: 987f503cbfdc3119eca6c7f3f15164ad8502bdab7f126e50fab427046f6c6d79
    result: exit 0; both stale mock-reader mutations killed; missing scenario explicit AssertionError; foreign cwd and restored integration passed
  final:
    command: git diff --check c17fc42b36ed93736d88e5cc229b048992c5882e HEAD
    result: exit 0; final Git status clean; all 18 subject blobs unchanged
  not_run:
    - pytest collection/full focused file rerun — direct candidate and pre-existing oracle execution used for this read-only domain review
    - full local suite/native campaign — excluded by profile and capacity boundary
    - independent mypy/lint/pre-commit rerun — writer receipts inspected; no domain claim of independently executing these checks
    - hosted CI/QSTS/merge — delivery coordinator responsibility; no QSTS acceptance claim

independent_oracles_or_counterexamples:
  - Exact-rational pairwise-difference OLS and population variance independently reconstructed live gateway sweeps, without NumPy fitting or statistics.linear_regression/pvariance.
  - Retired analyzer fx.fx_shock wiring killed all three repaired tests.
  - Spread sweep at zero hedge killed the live integration.
  - Equal one-third variance shares killed the unit and live integration oracles.
  - Sample variance substituted for population variance killed the live integration.
  - Fabricated R-squared of one killed the live integration.
  - Restoring retired mock-field reads killed both repaired mocked tests.
  - Real gateway returned identical baseline IRR for all three retired fx.fx_shock values.
  - A 50-bps spread at zero hedge left baseline IRR exactly unchanged.
  - Setting annual depreciation to zero reversed hedge benefit, confirming the direction is scenario-specific.

predecessor_finding_matrix:
  - finding_id: H07-P1-permanent-integration-skip
    applicability: applicable
    evidence: candidate integration executed repeatedly with real committed scenario
    result: CLOSED
  - finding_id: H07-P2-missing-file-and-cwd-skip
    applicability: applicable
    evidence: missing-scenario hostile probe raises explicit assertion; foreign-cwd execution passes
    result: CLOSED
  - finding_id: H07-P3-inert-regression-quality-mock
    applicability: applicable
    evidence: known nonzero slope passes; retired analyzer and mock-reader controls fail
    result: CLOSED
  - finding_id: H07-P4-inert-variance-mock-and-sum-only-oracle
    applicability: applicable
    evidence: analytic variance shares pass; equal-share and retired-driver controls fail
    result: CLOSED
  - finding_id: H07-P5-live-baseline-and-three-parameter-oracles
    applicability: applicable
    evidence: canonical baseline and independent pairwise statistics agree; exactly three parameters enforced
    result: CLOSED
  - finding_id: H07-P6-unlike-units-and-mixed-regime-interpretation
    applicability: applicable
    evidence: candidate removes raw-slope ranking and explicitly discloses full-hedge spread reference and mean-R-squared limitation
    result: CLOSED
  - finding_id: HYGIENE-other-skips-warnings-native-campaign
    applicability: outside H07
    evidence: changed-path and source-identity verification
    result: NOT_APPLICABLE

findings_and_residual_limitations:
  - id: DOMAIN-H07-L1
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    detail: Mixed-regime sweep shares and mean fit R-squared preserve existing analyzer conventions; neither is a joint stochastic risk decomposition.
  - id: DOMAIN-H07-L2
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    detail: Gateway agreement verifies analyzer wiring, not independent correctness of every underlying finance formula. The independent statistics and hostile controls supply separate evidence for the changed test oracles.
  - id: DOMAIN-H07-L3
    state: ACCEPTED_RESIDUAL_WITHIN_SCOPE
    detail: Writer strict focused mypy remains failing on disclosed legacy diagnostics. The inspected base comparison reports all candidate diagnostics pre-existing; no strict whole-file success or independent type execution is claimed here.
  - id: DOMAIN-H07-HARNESS-001
    state: SUPERSEDED_BY_SUCCESSOR_FINDING
    detail: Initial reviewer probe passed positional fixtures into patched test wrappers, causing FrozenInstanceError before candidate control execution. Classified HARNESS_ERROR_NOT_GUARD_EVIDENCE. Corrected keyword-fixture invocation passed and produced the retained main/supplemental evidence.
    original_call_id: call_fGNtlUpejjd7dAMdR4sWQLTK

hold_and_authority_effect: No HOLD, issue, grade, release, deployment, professional, lender, Board, publication or merge authority changes.
disposition: ACCEPTED
worker_outcome: EVIDENCE_RETURNED
mutation_attestation: No repository, index, refs, files, environment, PR or external-state mutation by reviewer. Probes used in-memory patches restored on exit and a filesystem-write-denying audit hook. Coordinator alone persisted the returned command/output artifacts.
```

The predecessor labels above are local identifiers for the previously unnumbered H07 diagnosis findings.

The independent real-scenario results were:

| Sweep | Coefficient | Population-variance share | R² |
|---|---:|---:|---:|
| Relative FX-rate shock | −0.12439002286827323 | 0.9216911797954858 | 0.9996734956146779 |
| Hedge fraction | +0.003572241819486205 | 0.0759918662485617 | 0.9999703072374333 |
| Spread, bps at full hedge | −0.000012475334473409649 | 0.0023169539559525346 | 0.9999988850727749 |

Baseline project IRR was `0.04201694802923463`; total population variance was `2.7988281651782565e-05`. With depreciation changed **only in memory** to zero, project IRR fell from `0.1039746879208123` at zero hedge to `0.05317030666629251` at full hedge. That counterexample supports retaining the candidate’s scenario-specific wording.

Exact commands and original outputs are preserved under [H07 delivery](/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H07/delivery), including [main probe](/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H07/delivery/DOMAIN_PROBE_001_MAIN.sh) and [supplemental probe](/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H07/delivery/DOMAIN_PROBE_001_SUPPLEMENTAL.sh). Their hashes were independently verified after persistence. These files preserve the exact heredoc commands actually executed; they were not separately rerun as shell scripts.

Memory was used to locate governance and historical FX caveats; the accepted conclusions above are grounded in current source inspection and fresh execution.
