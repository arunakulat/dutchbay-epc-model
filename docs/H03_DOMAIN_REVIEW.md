**H03 domain disposition: ACCEPTED for the frozen source object.** Independent behavioral checks found no blocking defect. Both warning causes are removed; fixture values and class lifetime are preserved; collection and qualification controls remain intact.

```yaml
reviewer_role: pytest compatibility and fixture lifecycle/domain
reviewer_identity: /root/h03_domain; Popper; task 01a08283-1778-7622-8957-8c33cfcd4e30
actual_execution_model: gpt-6-astra
actual_reasoning_effort: xhigh
risk_class: R2_LOAD_BEARING
candidate_commit: 1f2c3ca4573fe9f708166461bc389897cc86d1cf
candidate_tree: a2a233c0acb22aa3bb37e654c6937f14ec92cd34
base_sha: ac75dab100a4cd7509825d9be3f0a43efbbf2a3f
merge_base_sha: ac75dab100a4cd7509825d9be3f0a43efbbf2a3f
subject_manifest_sha256: 7fd2d391f99b752391d94e40030eb87793d12620d52019ff78c18bc73cffc4e0
review_scope: Three-file H03 source delta, warning causes, fixture binding/lifetime/value preservation, collection inventory, qualification controls, assertion rewrite, and writer-receipt consistency.
disposition: ACCEPTED
evidence_yield: NO_FINDING_WITH_EVIDENCE
mutation_attestation: No repository file, index, ref, branch, worktree, environment, PR, issue, or other durable/external state was mutated by this reviewer. Mutants and probe modules existed only in process memory. Ordinary pytest temporary artifacts were permitted. Final repository status was clean and HEAD/tree/base were unchanged.
```

`corpus_and_rule_identities`: I read the written domain profile before substantive work, the supplied user instructions, current `AGENTS.md`, complete canonical GWTF CSV, full pinned framework definitions, all four RECRUIT-01 modules, September 7 startup handover, applicable PR1243 successor, H03 preparation and creation/resolution identities, original hygiene report, frozen checkpoint and manifest, writer checks, formatting finding, structured probe receipts, actual changed test bodies, installed pytest/Hypothesis implementation, and relevant collection/qualification policy and tests. I also inspected the proposed PR body and handover as drafts. I did not inspect the assurance review or its conclusions.

Primary identity anchors:

| Object | Verified identity |
|---|---|
| Canonical GWTF CSV | SHA-256 `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1`; bootstrap counted 74 active v3.0 rules |
| Pinned framework definitions | SHA-256 `c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af` |
| Domain profile | SHA-256 `c190181b208a3790751bd7987055a47dc5da23fbe08a7d99a7ab8a229dd93dcd` |
| Original hygiene report | SHA-256 `751b8b46ed3210c65ddd53fcdfcffff74a594dc75f8bc8254be09d64abd1d22c` |
| Frozen checkpoint | SHA-256 `5c37d340f51de3bdfc1078c811cfc3e52041483b6aa6875f598903d16267f0aa` |
| Writer checks | SHA-256 `a42a13e5439c19aa4894e94bd1bbf8095cde6bde5c767ea833f0e751f5c6ff96` |

The frozen subject manifest was reconstructed from Git and matched the persisted bytes exactly:

| Subject | Git blob |
|---|---|
| [Changelog fragment](/Users/aruna/.codex/worktrees/2972/dutchbay-epc-model/changelog.d/hygiene-pytest-compatibility.fixed.md) | `52a773169ed0cd1778a6c49c11a17663bc46bcb8` |
| [pyproject.toml](/Users/aruna/.codex/worktrees/2972/dutchbay-epc-model/pyproject.toml:324) | `912f58077b4bb2202f282d236d0abe866f811534` |
| [FX calibration tests](/Users/aruna/.codex/worktrees/2972/dutchbay-epc-model/tests/analytics/test_fx_calibration.py:95) | `6675e343db5e909f33a085d4282662b5465e0b72` |

`checks_executed_and_exact_results`: All Python probes used the governed executable `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`, with `PYTHONDONTWRITEBYTECODE=1`, active worktree first on `PYTHONPATH`, and `DUTCHBAY_TEST_MODE=full`.

| Check | Exact command or preserved command reference | Result |
|---|---|---|
| Runtime and checkout binding | Governed `python -VV`; `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap` | Python 3.12.13; PASS; imports resolve to H03; no foreign checkout paths |
| Rules bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` with bytecode disabled | Exit 0; 74 active v3.0 rules |
| Independent fixture oracle and mutants | Exact probe events at reviewer rollout lines 95 and 100; script SHA-256 `54aac72bf92cd145dfe0a7102110c596f97d0a36951f5896b96166bbbcd8c5a2` | Controls before and after: 14 passed each, two setups total, one per class. Instance-method mutant: pytest exit 1, ten setup errors and four passes. Function-scope mutant: pytest exit 1, ten lifetime-guard failures and four passes. All probe drivers exited 0 because expected failures fired. |
| Independent real collection comparison | Exact probe events at rollout lines 127 and 161; script SHA-256 `bf61fc203d2a9f3970e15fbea95f3431eeadf4ebc962dcb18daafb2f074867e7` | Baseline and candidate each exit 0, 7,810 items; identical ordered node IDs and marker names/arguments. Seven qualification exclusions and three optional-module collection skips preserved. Baseline produced the Hypothesis warning; candidate produced no warnings. |
| Installed-hook and hostile descriptor probes | Exact probe event at rollout line 149; script SHA-256 `ab67904b0000d82b387180bcf57376946e457841271d6ab2311df926f4522c4b` | Nine directory cases passed. Ten deliberately incorrect descriptor values failed in each source version with identical error messages; both restored controls passed. Parsed TOML differs only by the `.hypothesis` exclusion. |
| Independent formatting replay | For each Git version, source supplied on stdin to governed `ruff format --check --no-cache --stdin-filename tests/analytics/test_fx_calibration.py -` and `black --check --stdin-filename tests/analytics/test_fx_calibration.py -`; exact event at rollout line 168 | Base: Ruff exit 1, Black exit 0. Candidate: both exit 0. |
| Final identity and diff | `git diff --check ac75dab100a4cd7509825d9be3f0a43efbbf2a3f HEAD`; `git status --porcelain=v1`; `git rev-parse HEAD HEAD^{tree}`; `git ls-remote origin refs/heads/main` | Diff check exit 0; clean; exact frozen commit/tree retained; live protected main equals the reviewed base |

The referenced reviewer rollout is [rollout-2026-09-09T01-03-44-01a08283-1778-7622-8957-8c33cfcd4e30.jsonl](/Users/aruna/.codex/sessions/2026/09/09/rollout-2026-09-09T01-03-44-01a08283-1778-7622-8957-8c33cfcd4e30.jsonl). It contains the complete executed commands and results. The coordinator preserves these externally once, with content hashes.

`independent_oracles_or_counterexamples`: The fixture probe loaded the original fixture implementation directly from the protected base and used its full dataclass as the comparison oracle. It ran the real seven test methods in both the original class and an independently introduced inherited class. It verified actual binding to each requested class, object reuse within that class, separate objects across classes, and full-precision equality. The normalized dataclass digest was `f91f95826bab25135b80302a7a864628eb13a426ed0d29caef6aa81868836018`. The function-scope mutant demonstrates that merely retaining numerical results would not pass this lifecycle check.

The collection digest was `110254f5fb13555b06ca366c07675ae3ee3d0c09e5afbb6f2f596b5d91d9294e` for both objects. Marker argument representations normalized process memory addresses only. The direct installed-hook matrix additionally verified root and nested `.hypothesis` directories, nearby names such as `.hypothesis_notes`, visible test directories, and existing build/venv exclusions. These hook cases used virtual directory existence in memory; the separate full collection passes exercised the real repository.

`predecessor_finding_matrix`:

| Finding | Applicability and evidence | Result |
|---|---|---|
| H03-W01 — Hypothesis collection warning | Actual baseline collection reproduced it; candidate collection emitted none. Installed hooks show explicit exclusion now handles both root and nested database directories without broadening nearby-name exclusions. | **CLOSED** |
| H03-W02 — class-scoped instance fixture | Actual class binding, one setup per class, inherited-class isolation, exact baseline values, firing instance-method negative control, and firing function-scope lifetime guard. | **CLOSED** |
| H03-F01 — pre-existing Black/Ruff disagreement | Independently reproduced the baseline disagreement; both accept the candidate. Every one of the ten descriptor mismatch cases retains the same failure message. | **CLOSED** |

`findings_and_residual_limitations`:

- **BLOCKS_CURRENT_CANDIDATE:** None.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** Behavioral compatibility was demonstrated on installed pytest 9.1.1 and Hypothesis 6.165.10. This is not execution evidence for an unreleased pytest version or every historical supported version.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** No local full-suite execution, coverage campaign, QSTS execution, or stochastic/report qualification campaign was run by this reviewer. Native-owner priority was respected; full collection is not full-suite execution.
- **NOT_APPLICABLE_WITH_REASON:** Other warning categories and optional-dependency skips in the original hygiene inventory are outside H03. Their disappearance is not claimed.
- Writer lint, isort, mypy, pre-commit and the 65-test strict run were inspected as writer receipts; I do not represent them as my independently executed checks. The independent checks above provide the domain evidence. No behavioral-probe harness failure was hidden; intentional mutants failed as required. One source lookup used an incorrect policy-test filename and was corrected before the actual file was read.

`hold_and_authority_effect`: Acceptance applies only to the exact frozen H03 subject. It grants no professional, release, lender, Board, grade, publication, issue-closure, deployment, or HOLD authority. Issues #1110 and #1229 were verified OPEN. Final delivery still requires both reviewers’ receipt-only final-head rebinds, current-base reconciliation, and exact-head required CI, including the applicable hosted Grid Study. I remain available for that bounded rebind.

<oai-mem-citation>
<citation_entries>
MEMORY.md:45-48|note=[Located exact-object review and verification receipt controls then verified current governing sources]
</citation_entries>
<rollout_ids>
01a07c84-d0ec-7821-8f88-797a9bbeab2f
</rollout_ids>
</oai-mem-citation>
