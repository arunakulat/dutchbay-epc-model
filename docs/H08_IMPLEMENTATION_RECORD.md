# H08 — windpowerlib listing compatibility

This R2_LOAD_BEARING change removes the listing downcast FutureWarning while
preserving windpowerlib 0.2.2's filtered-table contract. It changes no turbine
curve, physics, financial output or manufacturer-regex semantics. The public
unfiltered API supplies the four columns; the adapter retains both `.loc`
selections and the sorted outer merge, then replaces missing cells with False
and explicitly infers object dtypes. Malformed flags are not cast to booleans.

## Identity and authority

Writer task: `01a08432-8d23-7e11-a26d-86298cfad8f2`, branch
`codex/h08-windpowerlib-compatibility`, dedicated worktree
`/Users/aruna/.codex/worktrees/f779/dutchbay-epc-model`.
Protected base: `172af0398e8cd3c8c4622a54504d6d8562cb764b`.
The successful explicit project-target creation and actual session metadata
verify DutchBay_EPC_Model and `gpt-6-astra` / `xhigh`. Python is the persistent
governed 3.12.13 runtime; installed pandas is 2.3.3 and windpowerlib is 0.2.2.

External evidence root:
`/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H08/delivery/`.
`INGRESS_001.json` records source hashes and the successful 74-rule bootstrap and
environment check. Fresh full CSV, pinned unabridged framework definitions, all
four RECRUIT-01 modules, current AGENTS and applicable handover/bootstrap were
read. H08's preparation profile and both diagnoses were read against their
recorded hashes. The original `f2f3/test_hygiene/TEST_HYGIENE_REPORT.md` describes
the historical warning; its full-suite totals are not current H08 evidence.

`SOURCE_LEASE_001.json`, `SOURCE_LEASE_002.json` and the separate implementation
record lease bind exact paths and preimages. The extra H01 skip-integrity path
was explicitly reconciled with the queue coordinator: its fixture now exposes
the public unfiltered four-column schema. Every existing failure-to-skip guard
retains its assertions and exercised production loading path. The coverage test
file and original sourcing test file are unchanged.

> Do not wait for approval. work autonomously. Take your best, considered and safe decision. Use the Recruit-01 and verify-01 rules to reconsider and confirm your decisions. Start all new worktrees ingressing the rulesets - GWTF, CESSPIT, CASPER and CCCDIR. Follow these rules rigorously. Copy this instruction to all new tasks, worktrees, PR's

Owner setting instruction: "all new worktrees, PR's etc should also inherit the GPT-6 Astra Extra High setting from the coordinator"

The writer uses `gpt-6-astra` with `xhigh`, verified in actual execution metadata.
Both required separate read-only reviewers must use the same verified setting.
Frozen commit/tree/base and
the sorted subject blob manifest are recorded externally before recruitment.
This record does not claim independent acceptance, final-head CI or merge.

## Verification and negative controls

`verify_focused.sh` retains the exact commands once, with SHA-256
`f50e796d417cec6f4b99398ba62807b51b32b03801daa497e1661a80ac89d909`.
Its checkpoint execution receives a separate concise external result receipt.

| Check | Executed result before freeze |
|---|---|
| Original three sourcing modules | 46 passed, one upstream downcast FutureWarning, 2.07 seconds |
| All four sourcing modules, `-W error::FutureWarning` | 463 passed, no warnings or skips, 3.89 seconds; later mutation controls also passed all 463 |
| Packaged public oracle | Exact `assert_frame_equal(..., check_exact=True)` on 140 raw / 67 filtered rows; upstream emitted one warning, candidate zero |
| Synthetic reference outcomes | 407 fixtures: 350 successful tables and 57 matching malformed-flag KeyErrors; 392 baseline FutureWarnings; all candidate outcomes match |
| Independent constructed duplicate-key table | Four input rows produce five ordered output rows; plain row-filter shortcut rejected |
| Ruff lint / Ruff format / Black / isort | Passed on three changed Python files |
| `mypy --follow-imports=silent` on production and new compatibility module | Success: no issues found in two source files |
| `git diff --check` | Passed |
| Local full suite, coverage, qualification and QSTS | Not run: native-owner capacity; H08 makes no QSTS claim; exact-head hosted gates remain required |

The 407 synthetic fixtures cover all 256 four-row boolean combinations, 25
missing-label pairs, 121 boolean/missing/integer/string flag combinations, three
flag dtypes, an empty table and all-missing labels. Exact comparisons include
index, columns, ordering, values and dtypes. Packaged checks also exercise empty,
case-insensitive, alternation and no-match manufacturer expressions. A separate
duplicate fixture has a non-default named input index and an explicit output
table. Scope does not establish every extension dtype or future dependency.

Actual-source mutations were compiled into child-process memory and exercised
with the real four-module pytest selection; installed packages and source files
were unchanged. Passing 463-test controls bracket the mutations.

| Mutated behavior | Observed failure |
|---|---|
| Set all coefficient-curve flags False | 322 failed, 141 passed |
| Replace outer merge with left merge | 85 failed, 378 passed |
| Reverse output ordering | 286 failed, 177 passed |
| Restore implicit `fillna(False)` | 256 failed, 201 passed, six fixture errors under FutureWarning-as-error |

Original probe `source_mutation_probe.py` has SHA-256
`8645678105a72f9606d006a2b9d827c3ae41932f31d0e8d100d933d1c6fa956a`;
its results have SHA-256
`bf197982b106aadb3cba130ea8ddcb1db359e5410acfdf2cf24efb87a0a6de62`.
The initial ordering attempt failed in the harness before pytest and is
explicitly NO_EVIDENCE. `MUTATION_CORRECTION_001.json` preserves that failure.
The corrected ordering probe `source_mutation_probe_002.py` has SHA-256
`f7dc4599937911b5f139c789cb63dab8dc741d4bc00335eaec7194de478d58b0`;
its passing-control/failing-mutant/passing-control results have SHA-256
`8392eada7c0091c9b2ee42ea54a8deacb36f0179dff53c66dc796b1e946fdfaf`.
Four additional corrupted-output comparisons exercise the exact-equality guard;
those are not represented as source mutations.

The initial type check found an optional exception-variable annotation error in
the new test; the corrected two-file invocation passed. Ruff also exposed an
existing WTG inline-comment layout disagreement with Black. Moving that comment
above the same parse expression allows both formatters to pass without changing
parser behavior. These initial failures remain in `CHECKS_001.json`.

## Evidence limits and delivery gate

The unmodified installed public function is the existing independent oracle for
the packaged table. Synthetic cases use its original pandas expressions; the
separate explicitly constructed duplicate table and required reviewer challenges
provide additional assurance. Installed `windpowerlib/data.py` SHA-256 is
`99527d395b02430f86770390cb4bf65450dab1b5b19e7799fcfb59adf8e188b4`;
packaged `oedb/turbine_data.csv` SHA-256 is
`d379379ba20fe41ec151f74ad5ddf368f9e1cce596756ccea73888d0614c3840`.
The relevant upstream behavior and explicit inference approach are documented in
the [windpowerlib source](https://windpowerlib.readthedocs.io/en/stable/_modules/windpowerlib/data.html)
and [pandas release notes](https://pandas.pydata.org/docs/whatsnew/v2.2.0.html#deprecated-automatic-downcasting).

Independent domain and assurance reviewers must accept the frozen subject,
then rebind unchanged subject bytes through the receipt-only final head. Their
original bodies, including any memory footer, remain verbatim outside Git;
publication copies may omit only that footer with a recorded transformation.
Required hosted checks must pass on that exact head against current main.
An actually recorded native campaign reservation serializes protected merges;
recheck the programme capacity record before submission. No shared environment
or local full campaign is authorized here. After squash merge, prove tree
equality and ancestry, synchronize main only under the recorded safety predicates
and retire only H08-owned clean state. Issue #1110 and all professional, lender,
Board, release, evidence and HOLD boundaries remain unchanged.
