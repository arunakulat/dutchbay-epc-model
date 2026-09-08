**Disposition: ACCEPT frozen H03 source for the bounded compatibility change.** Independent collection, strict-warning, fixture-value and qualification-control checks found no blocking defect. This is substantive source acceptance; final-head rebind and required hosted CI remain pending.

```yaml
reviewer_role: independent_test_integrity_and_governance_assurance
reviewer_identity:
  task: /root/h03_assurance
  session: 01a08283-4bb1-7b60-8062-8aa041c058da
  parent_coordinator: 01a0827b-44d2-7660-b7fa-aadec78920c5
  model: gpt-6-astra
  reasoning_effort: xhigh
  actual_metadata: session_meta line 1 and turn_context line 8
risk: R2_LOAD_BEARING
candidate_commit: 1f2c3ca4573fe9f708166461bc389897cc86d1cf
candidate_tree: a2a233c0acb22aa3bb37e654c6937f14ec92cd34
base_sha: ac75dab100a4cd7509825d9be3f0a43efbbf2a3f
merge_base_sha: ac75dab100a4cd7509825d9be3f0a43efbbf2a3f
subject_manifest_sha256: 7fd2d391f99b752391d94e40030eb87793d12620d52019ff78c18bc73cffc4e0
review_scope: warning causes, collection preservation, qualification controls, fixture precision/scope, diagnostic preservation, receipt truth
disposition: ACCEPT_FROZEN_SOURCE
evidence_yield: EVIDENCE_RETURNED
mutation_attestation: No repository, index, ref, worktree, environment, durable-file or external-state mutation. Probe mutations existed only in process memory; ordinary pytest temporary artifacts were permitted.
hold_and_authority_effect: No HOLD uplift or merge, release, publication, issue-closure, professional, lender, Board, grade or qualification authority.
```

`corpus_and_rule_identities`: Primary ingress completed for the assurance and preparation profiles, creation/resolved identity records, applicable user instructions and AGENTS, complete current GWTF CSV, unabridged pinned framework definitions, all four RECRUIT-01 modules, September 7 bootstrap and PR1243 successor, original hygiene report, full candidate diff and FX test source, installed pytest/Hypothesis warning implementations, qualification policies and relevant control tests, checkpoint/manifest/leases, writer checks, formatting finding and structured probe receipts. The other reviewer’s conclusions were not inspected.

Key ingress SHA-256 identities:

- GWTF CSV: `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1`.
- Pinned framework definitions: `c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af`.
- Assurance profile: `2588d5aeefd61ce9ce2567fb492a2601a003d2468cdd7a9900ff833fb6cc8861`.
- Original hygiene report: `751b8b46ed3210c65ddd53fcdfcffff74a594dc75f8bc8254be09d64abd1d22c`.
- Writer checks: `a42a13e5439c19aa4894e94bd1bbf8095cde6bde5c767ea833f0e751f5c6ff96`; independently matches the checkpoint’s digest.
- Installed `_pytest/fixtures.py`: `f5d4d3f848d97411e456d50400d3aaecc19a9b0c90def9151e395ee8952042b7`.
- Installed `_pytest/main.py`: `8ee2725057ff1811e2ae9ebdf1befb7518195f8f333f9f8ca024d76a4b80780e`.
- Installed `_hypothesis_pytestplugin.py`: `5b8df643a5394e86bfe608b710ff2534ac74f7192f4f81faa091356ad426f182`.

The complete path/blob/SHA-256 identity receipt is in the command result associated with session line 155 below. Dependency source identities there were verified; unchanged production FX implementations were not subjected to a new finance audit.

All three manifest entries independently match both Git objects and working-file bytes:

| Subject | Git blob |
|---|---|
| `changelog.d/hygiene-pytest-compatibility.fixed.md` | `52a773169ed0cd1778a6c49c11a17663bc46bcb8` |
| `pyproject.toml` | `912f58077b4bb2202f282d236d0abe866f811534` |
| `tests/analytics/test_fx_calibration.py` | `6675e343db5e909f33a085d4282662b5465e0b72` |

`checks_executed_and_exact_results`:

- Persistent Python reports **3.12.13**. `PYTHONDONTWRITEBYTECODE=1 DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap` passed, resolving imports to the active worktree with no foreign checkout paths. Rules bootstrap passed with **74 active v3.0 rules**.
- Independent instrumented `pytest.main` run used `-o addopts= -p no:cacheprovider --no-cov -q -W error` on `tests/analytics/test_fx_calibration.py`, `tests/lint/test_stochastic_suite_policy.py` and `tests/lint/test_report_test_policy.py`: **48 passed in 12.74s**, exit 0, zero warnings. The fixture was class-bound, executed once and supplied one shared object to all five fixture consumers.
- Independent actual `--collect-only` run: **7,810 collected in 26.45s**, exit 0, zero warnings. Every node ID and marker-name list exactly matched both author inventories. All **seven qualification items retained their skip markers**. Inventory digest: `e67c47356478de13fb48bea82413b9c985b9642af2913679edaeb45b1a859763`.
- Independently executed original and candidate fixture bodies produced exactly equal complete dataclasses. Serialized value digest: `09db23e5b2b1e8270b2e137b4ebe02b86cc76114788bf8dfd3ead6987b23082d`.
- TOML comparison proves that removing the candidate’s one added `.hypothesis` entry makes the entire parsed configuration equal to base. No tracked path contains a `.hypothesis` component. Function inventory remains **32**, including all **29 tests**; only the fixture declaration and disclosed descriptor diagnostic binding differ. The fixture return AST is identical.
- Ruff lint and format checks passed using `--no-cache`; in-memory Black and isort formatting exactly reproduced candidate bytes; `git diff --check` passed. The baseline Black/Ruff disagreement was independently reproduced.
- Restored, unmutated fixture control using the ordinary pytest CLI and `-W error`: **7 passed in 0.84s**, exit 0.
- Final `git status --short --branch`, `git rev-parse HEAD HEAD^{tree} origin/main` and `git ls-remote origin refs/heads/main` confirmed clean source, unchanged candidate/tree and unchanged live protected base. `gh issue view 1110 --json number,state,title` confirmed **OPEN**. No H03 PR existed at initial external-state inspection.
- The writer’s **65 passed in 13.22s** receipt was read as writer evidence. My independently executed count is **48**, with the additional separate seven-test restoration control; I do not represent the writer’s 65-test run as my own.

`independent_oracles_or_counterexamples`:

1. **Hypothesis configuration mutation:** Removed `.hypothesis` only from an in-memory real pytest configuration and invoked the installed Hypothesis and pytest collection hooks. The original warning raised under `UserWarning`-as-error and native pytest ceased excluding the path. Candidate and restored controls emitted no warning and native pytest excluded it. Only the target directory’s existence was simulated; no scratch source was created.
2. **Fixture binding mutation:** Rebound the same fixture body to a class instance in memory. Actual strict pytest execution produced **2 passed, 5 setup errors in 1.17s**, exit 1, with the original `PytestRemovedIn10Warning`. Restored source passed.
3. **Qualification marker mutation:** Removed the real report test’s qualification decorator through an in-memory source-read seam. The pre-existing `test_complete_live_matrix_remains_one_explicit_qualification_test` assertion killed the mutation; unchanged controls passed before and after.
4. **Stochastic budget counterexamples:** The real guard rejected **201 LHS evaluations** and **129 Sobol requests expanding to 256**, with requested/effective counts in the diagnostics. Ordinary 200 and explicitly qualified 10,000 controls remained accepted. No model campaign was executed.
5. **Descriptor assertion counterexamples:** Corrupted each of the ten descriptor keys independently against both original and candidate tests. **All 20 mutations failed with the exact original diagnostic**, while controls passed before and after. The format repair preserves the guard’s useful behavior.

`predecessor_finding_matrix`:

| Finding | Applicability and evidence | Result |
|---|---|---|
| H03-W01 — Hypothesis collection warning | Applicable; installed hook mutation/control, configuration identity and full collection inventory | CLOSED |
| H03-W02 — instance-bound class fixture | Applicable; class-bound runtime observation, exact dataclass equality, strict mutation and restored control | CLOSED |
| H03-F01 — pre-existing Black/Ruff conflict | Applicable; baseline disagreement reproduced, candidate passes both, 20 descriptor mutations preserve assertion behavior | CLOSED |

`findings_and_residual_limitations`:

- **No `BLOCKS_CURRENT_CANDIDATE` finding.**
- **SUPERSEDED_BY_SUCCESSOR_FINDING — assurance harness correction:** The first fixture-mutant harness correctly obtained two passes and five errors but then failed its own assertion that every cached error would repeat the full warning text. Pytest supplied one detailed originating trace and abbreviated cached failures. The corrected harness requires that originating trace plus the exact failure counts and passed. Preserve the first failed harness event and corrected successor; neither is a candidate defect.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE — bounded environment evidence:** Collection and warning observations apply to pytest **9.1.1**, Hypothesis **6.165.10** and the verified governed environment. Historical baseline execution cannot be recreated retroactively; current independent inventory, source identity and executable mutations support the substantive claims.
- **NOT_APPLICABLE_WITH_REASON — unrelated hygiene/native issues:** Other warnings/skips in the original inventory and native issue #1229 are outside H03. No closure or cure is implied.
- **Not run — local full suite, coverage, QSTS execution or stochastic/report qualification campaigns:** Native owner priority and assignment scope. Hosted final-head checks, including the required Grid Study for `pyproject.toml`, remain delivery gates.
- **Not independently rerun — writer mypy and pre-commit:** This review independently checked changed-source lint/format, runtime behavior and controls; writer results remain attributed receipts.
- `git fetch` was intentionally not run because reviewer refs are read-only; live main was checked with `git ls-remote`. No receipt-only final-head acceptance is issued here.

The coordinator can preserve exact commands once from [this assurance session](/Users/aruna/.codex/sessions/2026/09/09/rollout-2026-09-09T01-03-57-01a08283-4bb1-7b60-8062-8aa041c058da.jsonl). Below, `line/command` identifies the event and command index; hashes cover the exact decoded shell command, including its complete inline probe body.

| Evidence | Session line/command | Shell-command SHA-256 |
|---|---:|---|
| Strict 48-test run and fixture observation | 101/1 | `b1e2c2a4e9b6868fe2744ae2dde837bc05dd98fbbfa22091e7c91faede192cbc` |
| Hypothesis hook mutation and controls | 108/1 | `67dadb66d6627398a3c0832e129c5743fe8bd474d139116a1802072b0ee40413` |
| Original failed fixture harness | 115/1 | `62fc8958e22873f21c588ebb7eebc8d3a35a5e779afc652ace7aa87a1ec33eb3` |
| Independent full collection | 124/1 | `6fa6b8e3ff56450c0217f3c107f7a8c4d5b4c5122ced36954aac1e052b338eab` |
| Qualification and budget challenges | 140/1 | `71cad42f8dbd852db8d3146a6011d964e178178d6d1a78a3ff18d27dd721bc0e` |
| Independent formatting checks | 140/2 | `9370bf5ebac3882fa08f1feded81c9769256f13d565befc116f058e1be93826b` |
| Corrected fixture-mutant harness | 148/1 | `b192c1329fef1c019dae61626e8837281631c6db1ad99a406132f400ffc23dd4` |
| Object identities, AST/TOML and baseline format proof | 155/1 | `2f95a3020c30df1a7917fe631ff1597fb72f9e6505de6e67be9de5a7979b885e` |
| Direct baseline/candidate fixture and 20 descriptor challenges | 172/1 | `2b69d29d30ac3b0205d49710b5fc90ced8c95fb455d52fbe91b9427540a2670b` |
| Restored seven-test fixture control | 181/1 | `763c881374ced15411b7c944f7f0e43108a2b34b9c0c09d59d7625f22984581b` |

I remain available for the separate receipt-only final-head rebind after the coordinator persists this complete body and establishes the PR evidence channel.

<oai-mem-citation>
<citation_entries>
MEMORY.md:45-48|note=[Located review and verification requirements then verified current canonical modules]
</citation_entries>
<rollout_ids>
01a07c84-d0ec-7821-8f88-797a9bbeab2f
</rollout_ids>
</oai-mem-citation>
