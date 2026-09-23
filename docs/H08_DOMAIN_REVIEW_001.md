**ACCEPT — the frozen H08 candidate preserves the reviewed windpowerlib listing behavior and removes the downcasting warning within the tested dependency and source envelope.** This is the domain disposition for the exact substantive object below. It is not final-delivery-head acceptance.

```text
reviewer_role: independent H08 domain reviewer
reviewer_identity: /root/h08_domain; Jason
reviewer_session: 01a0843d-46a3-71f0-82cf-b1f4ea89c86f
actual_model: gpt-6-astra
actual_reasoning_effort: xhigh
risk_class: R2_LOAD_BEARING
candidate_commit: 00123e4af2f7b8988fb2583fc9a7fc20955d972e
candidate_tree: e3b931d27385701ad90781aa1677201ca24e9875
base_sha: 172af0398e8cd3c8c4622a54504d6d8562cb764b
merge_base_sha: 172af0398e8cd3c8c4622a54504d6d8562cb764b
subject_manifest: SUBJECT_MANIFEST_003.tsv
subject_manifest_sha256: 14368d0c70dd725eb69621a274ee3d4943336f8869fb652bfef8b1c88aab9266
subject_manifest_objects: 31
review_scope: listing selection, merge contributions, ordering, index, columns,
  values, dtypes, malformed flags, manufacturer filtering, H01 integrity,
  substantive implementation record and evidence boundaries
disposition: ACCEPT
final_head_rebind: NOT_RUN; requires separate assignment against named receipt-only head
```

Actual execution settings were read from this reviewer’s own session metadata, not inferred from its recruitment prompt. Both the original `turn_context` at session line 8 and the recovery `turn_context` at line 184 record `gpt-6-astra`, `xhigh`, and the f779 worktree. The parent creation receipt identifies project `local-f59c59e1b0193682361ce364fadb27e0`; the live project listing resolves that ID to `DutchBay_EPC_Model`.

The earlier provider interruption remains **NO_EVIDENCE for a completed disposition**, as recorded in `REVIEW_INTERRUPTION_001.json`. The authorized single recovery resumed this same reviewer. Before using completed earlier checks, I independently reverified the clean candidate, all 31 manifest entries against both Git objects and working files, governing-source hashes, installed oracle hashes and actual recovery settings. No second reviewer’s substantive conclusion was read.

`corpus_and_rule_identities`: I read the complete canonical CSV, all four RECRUIT-01 modules, AGENTS, the pinned unabridged framework definitions, the applicable September 7 bootstrap and September 8 PR1243 handover, profiles 001/002 and amendment 003, both H08 diagnoses, original hygiene report, all four sourcing test modules, candidate implementation record, leases, checkpoint records and both mutation programs/results including their correction. Historical memory was used only to locate governance requirements; the relevant requirements were verified against the current tracked sources.

| Controlling or external source | Verified SHA-256 |
|---|---|
| Canonical GWTF CSV | `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1` |
| AGENTS.md | `215dd99e206203b8b859cc0c2b97cf2e0150ea9863a91ccab80a72cabe0f4bcd` |
| Pinned framework definitions | `c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af` |
| H08 preparation profile | `f5dd22f4cad6db04d00dd39fa1cc0d681334f82954577ef7f0bcc503a9a6e8a4` |
| DOMAIN_PROFILE_002.md | `1faec614fcba3f630b89743bb2ab8761daa31181d822921bebd4b6c298efe2e5` |
| Original TEST_HYGIENE_REPORT.md | `751b8b46ed3210c65ddd53fcdfcffff74a594dc75f8bc8254be09d64abd1d22c` |
| Installed windpowerlib/data.py | `99527d395b02430f86770390cb4bf65450dab1b5b19e7799fcfb59adf8e188b4` |
| Packaged oedb/turbine_data.csv | `d379379ba20fe41ec151f74ad5ddf368f9e1cce596756ccea73888d0614c3840` |

The governing modules, handovers and other tracked judged objects are bound by the verified 31-object manifest. Original five-object manifest 001 is superseded for completeness; manifest expansion changed no candidate source.

`checks_executed_and_exact_results`:

- `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV` — **Python 3.12.13**.
- `PYTHONDONTWRITEBYTECODE=1 DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv PYTHONPATH="$PWD" ./check_venv.sh --no-bootstrap` — **PASS**; persistent environment, f779 import path, no foreign checkout paths or editable-project contamination.
- `PYTHONDONTWRITEBYTECODE=1 DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` — **74 active v3.0 rules**, exit 0.
- The focused command below — **463 passed in 3.66 seconds; zero warnings and zero skips**, exit 0.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
  -o addopts='' -p no:cacheprovider --no-cov -q -W error::FutureWarning \
  tests/wind/test_power_curve_sourcing.py \
  tests/wind/test_power_curve_sourcing_coverage.py \
  tests/wind/test_power_curve_sourcing_skip_integrity.py \
  tests/wind/test_power_curve_sourcing_compatibility.py
```

- Governed `ruff check --no-cache` and `ruff format --check --no-cache` on production, compatibility and skip-integrity modules — **PASS; three files already formatted**.
- `git diff --check 172af0398e8cd3c8c4622a54504d6d8562cb764b..00123e4af2f7b8988fb2583fc9a7fc20955d972e` — **PASS**.
- AST comparison with the protected base — **all 12 other production function/class definitions unchanged**, including the WTG parser whose comment was reformatted.
- Read-only `git ls-remote origin refs/heads/main` confirmed the named base; live issue 1110 remained **OPEN**. No H08 PR appeared in the inspected open-PR list.

`independent_oracles_or_counterexamples`: The packaged-table comparison called the **unmodified installed public function**. Its result and the candidate were exactly equal: **67 × 4**, `RangeIndex(0, 67)`, label dtypes `object/object`, availability dtypes `bool/bool`. The public baseline emitted one downcasting `FutureWarning`; the candidate succeeded with `FutureWarning` treated as an error.

For synthetic cases I executed the installed public function’s unchanged code object with a private source-reader global and the actual adapter’s code object with a private import boundary. Neither installed functions nor package files were patched. This avoids deriving the reference from the writer’s `_legacy_filter` implementation.

The independent matrix contained **778 outcomes**:

| Challenge | Result |
|---|---|
| Exact successful tables | **186 matches**, including index, order, columns, values and dtypes |
| Malformed-source failures | **588 matching KeyErrors and four matching TypeErrors**, with matching messages |
| Baseline warnings | **342 FutureWarnings** |
| Candidate differences or FutureWarning failures | **0** |
| Input-frame changes | **0** |

The matrix included all **120 permutations** of an independently constructed five-row source with overlapping duplicate keys and a repeated, non-default named index; 36 missing/mixed-label combinations; 600 seeded malformed-flag combinations (`seed=88019`); nine flag dtypes and applicable missing-value variants; and an empty table. Flags included strings, bytes, decimals, complex values, integers, floating values and missing sentinels.

The separate manual relational oracle requires **six ordered rows** from that five-row source: four `A/a` merge contributions, one coefficient-only `M/m`, and one power-only `Z/z`. Every permutation matched it.

Four independently constructed mutations of the actual adapter were **killed between passing controls**:

| Actual-source mutant, executed only in memory | Observed rejection |
|---|---|
| Deduplicate merged rows | Three rows instead of six |
| Replace merge with a boolean row filter | Five rows instead of six |
| Coerce malformed coefficient flags to bool | Returned six rows where the public reference raises `KeyError: "['False'] not in index"` |
| Force availability columns to object dtype | Exact dtype comparison failed |

The initial printed mutation receipt accidentally reused one dictionary key, omitting mutant names from the output. All four comparisons had executed; I then repeated them with distinct `name` and status fields. The corrected named receipt is the cited evidence.

I also independently invoked the **actual original H01 listing test and its actual skip-integrity guard**. Empty data propagated `AssertionError`; malformed flags propagated `KeyError`. A deliberate broad `except Exception: pytest.skip(...)` wrapper was rejected by the real guard for both cases, with passing controls before and after.

The complete inline commands and results are preserved in this reviewer’s session file:

`/Users/aruna/.codex/sessions/2026/09/09/rollout-2026-09-09T09-06-43-01a0843d-46a3-71f0-82cf-b1f4ea89c86f.jsonl`

| Evidence | Command/result lines | Exact tool-input SHA-256 |
|---|---:|---|
| Independent 778-outcome matrix | 151 / 154 | `16621dbe96f1e4843820d39c9361e7296b515860ba7c67f0c9117a1f324b3365` |
| Independent H01 hostile-input guard | 167 / 170 | `96ef5b4ce09975b276d2dfda741408ce39a579d7ee055ad8f00cd489934ad1fd` |
| Corrected four-source-mutant receipt | 176 / 179 | `52ef101170a34d87b01c0c16b6ceb2ee3fc739cc9a40dd2a938ec4e3c3a4df96` |

`predecessor_finding_matrix`:

| Finding | Applicability and evidence | Result |
|---|---|---|
| H08 implicit downcasting | Real public baseline warns; actual candidate passes exact equality and warning-as-error execution | **CLOSED** |
| Boolean row-filter duplicate defect | Independent six-row oracle, 120 source permutations and killed row-filter/deduplication mutants | **CLOSED** |
| Malformed flags must retain upstream behavior | 592 matching error outcomes; malformed-bool-coercion mutant killed | **CLOSED** |
| H01 failures converted to skips | Original assertions preserved; 463-test run plus independent empty/malformed guard challenge | **CLOSED** |
| Initial writer ordering harness failed before pytest | Original remains **NO_EVIDENCE**; inspected and hash-verified corrected script/result records show passing controls and 286 failing/177 passing tests under reversal | **CLOSED by corrected evidence** |
| Initial manifest omitted unchanged judged objects | Preserved original, explicit expansions, all 31 final entries independently verified | **CLOSED** |

`findings_and_residual_limitations`:

- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** Evidence is bounded to Python 3.12.13, pandas 2.3.3, windpowerlib 0.2.2 and the stated source cases. It does not prove every future dependency version, pandas option regime or extension dtype. No broader compatibility claim is accepted.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** The interrupted original attempt supplied no disposition. Recovery reconciled unchanged identities before retaining its completed command receipts; this report supplies the completed substantive disposition.
- **NOT_APPLICABLE_WITH_REASON:** Local full suite, coverage, QSTS and qualification campaigns were not run by this reviewer because they exceed the bounded profile and native-owner capacity reservation. H08 makes no QSTS, convergence or qualification claim.
- **NOT_APPLICABLE_WITH_REASON:** I did not rerun mypy, Black, isort or pre-commit. Their writer receipts were inspected; my independent execution covered the domain oracle, all focused tests, Ruff and diff checks. Pre-commit was not invoked because it can mutate files.
- **DEFERRED_TO_NAMED_DOLPHIN:** Final-head rebind and required hosted checks remain with the H08 delivery owner. They do not block this frozen substantive disposition; they remain prerequisites to delivery. Any subject-byte change requires renewed substantive review.

`hold_and_authority_effect`: No HOLD is lifted. Issue 1110, professional, evidence, lender, Board, release, publication and other authority boundaries remain unchanged. This reviewer grants no merge or issue-closure authority. Receipt-only final-head acceptance must be separately requested and verified.

`mutation_attestation`: No repository source, index, ref, branch, installed package, shared runtime configuration, PR, issue or external evidence file was changed. Tests used transient fixtures; hostile substitutions and source mutants existed only in their Python processes. Source originals and prior failures were preserved. Final worktree status was clean at the exact candidate/tree/base above.
