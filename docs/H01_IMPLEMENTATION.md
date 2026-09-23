# H01 wind test integrity — implementation record

## Scope and provenance

Sole delivery writer: task `01a0822e-34fb-7a82-80b6-81a08be20cec`, dedicated
`440e/dutchbay-epc-model` worktree, branch `codex/h01-wind-test-integrity`.
Coordinator: `01a07e1b-a139-79e0-94fc-4a8d48c37b72`.
Base: `5ec33d32834c18e8c14dff06617ff92fec365828`; base tree
`708171c4026e8f7386c53c323b90a01d9bc91867`.
Risk: `R2_LOAD_BEARING` (test oracles). Delivery/review model: `gpt-6-astra`, `xhigh`.
The coordinator verified actual delivery dispatch configuration/project association.

Full current GWTF CSV, pinned unabridged CASPER/CESSPIT/CCCDIR definitions,
all four RECRUIT-01 modules, AGENTS, latest applicable handovers, test policies,
production sourcing module and both pre-existing sourcing test files were read.
The September 7 handover remains the applicable bootstrap pointer; the September 8
F2/F3 and coverage successors do not authorize unrelated changes. Historical D3
scope and HOLD boundaries remain outside H01.

Governed Python: `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`,
3.12.13. `check_venv.sh --no-bootstrap` passed with active-checkout import binding;
`dutchbay_bootstrap_rules.py` loaded 74 active v3.0 rules. CSV SHA-256:
`0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1`.
Exact ingress hashes, writer leases, WORKTREE_BRIEF and baseline receipt are held at
`/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H01/delivery/`.
No other writer has this worktree; the native-grid writer owns `defd` separately.

## Reproduction and change

The earlier assurance diagnosis was replayed against original source functions.
The OEDB exception wrapper hid empty-list and wrong-rating assertions, the thrust
wrapper hid a malformed-source ValueError, and the reference listing wrapper hid
an internal ImportError. All eight transitive/internal package import probes also
became skips. The unchanged two-file suite passed 28 tests with one upstream
FutureWarning. The new executable guard against that original source returned
**12 failed, 6 passed**, with no skip accepted as guard success.

The three wrappers are removed. A test-local `find_spec` gate skips only a missing
top-level optional package before production loading; broken discoverable packages
proceed to the original loader and fail. Every original assertion remains, including
capacity, validation, source provenance and thrust constraints. Function annotations
and scoped formatting make the touched test file type-checkable. Production code,
financial behavior, dependencies, environment and qualification policies are unchanged.

Installed windpowerlib source was inspected: `get_turbine_types` defaults to
`turbine_library="local"` and reads packaged `oedb/turbine_data.csv`. The misleading
online/network explanation is removed.

The new regression imports the actual sourcing test module and executes its functions.
Controlled discoverable packages feed the real source loaders, including temporary CSVs.
Valid original-function controls run before and after hostile patches. Explicit package
absence, broken installed imports, malformed columns, empty listing, wrong rating and
internal listing failure are exercised. A deliberate assertion-to-skip wrapper around
the original function triggers `pytest.fail`; the guard cannot pass by skipping.

## Verification receipts

All commands run from the assigned worktree. Python commands use
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"`; `VENV` below abbreviates the absolute
persistent environment `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`.

| Check | Command run | Result |
|---|---|---|
| Original controls | `VENV/bin/python -m pytest -o addopts='' -p no:cacheprovider --no-cov tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_coverage.py -q --tb=short` | 28 passed, 1 warning in 2.56s |
| Pre-fix firing guard | `VENV/bin/python -m pytest -o addopts='' -p no:cacheprovider --no-cov tests/wind/test_power_curve_sourcing_skip_integrity.py -q --tb=line` | 12 failed, 6 passed in 1.69s; expected failure masking reproduced |
| Fixed focused tests | `VENV/bin/python -m pytest -o addopts='' -p no:cacheprovider --no-cov tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_coverage.py tests/wind/test_power_curve_sourcing_skip_integrity.py -q --tb=short` | 46 passed, 1 warning in 2.09s |
| Lint | `VENV/bin/ruff check tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | All checks passed |
| Format | `VENV/bin/ruff format --check tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | 2 files already formatted |
| Black / isort | `VENV/bin/black --check <same two paths>` and `VENV/bin/isort --profile=black --check-only <same two paths>` | Passed, 2 files unchanged |
| Types | `VENV/bin/mypy --follow-imports=silent --cache-dir=/dev/null tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | Success: no issues found in 2 source files; initial unused-ignore error corrected |
| Scoped pre-commit | `VENV/bin/python -m pre_commit run --files <same two paths> changelog.d/hygiene-wind-failures.fixed.md` | All applicable hooks passed; TOML/YAML skipped because no matching files |
| Diff | `git diff --check` | Passed |
| Financial regression / full suite / local coverage / QSTS / qualifications | not run | No production change; H01 profile prohibits local full-suite campaign and environment mutation; native owner retains five-run priority |

The sole warning is windpowerlib's pandas downcasting FutureWarning; it predates H01.
The guard's package stubs are controlled fixtures, not qualification of third-party data.
The existing installed-package tests remain the real-data controls. Type checking is
scoped to two changed files with imports followed silently, not a complete repository gate.
Pre-commit is executed explicitly because no active Git pre-commit hook file was present.

## Acceptance and delivery boundary

At this substantive checkpoint, both independent exact-object reviews and hosted required
CI are pending. Freeze sorted subject blobs with commit/tree/base before recruiting
separate wind/test-domain and Python/assurance reviewers. Persist their original bodies,
then permit only named receipt files. Open the PR and obtain both final-head rebinds
outside Git while its exact-head CI runs. Recheck identity/content before merge.

No issue auto-closure is requested. Issue #1110 and native #1229 were OPEN at ingress;
H01 confers no native-crash cure, release, professional, evidence, lender, Board or HOLD
uplift. Required hosted CI and current base remain mandatory. After accepted green merge,
verify exact protected-tree equality and ancestry; preserve unrelated worktrees/state.

# Owner standing instruction — 2026-09-08

Copy the following verbatim into every new task prompt, worktree brief and PR description in this programme, including reviewer recruitment and successor tasks:

> Do not wait for approval. work autonomously. Take your best, considered and safe decision. Use the Recruit-01 and verify-01 rules to reconsider and confirm your decisions. Start all new worktrees ingressing the rulesets - GWTF, CESSPIT, CASPER and CCCDIR. Follow these rules rigorously. Copy this instruction to all new tasks, worktrees, PR's

Apply before substantive work in each new worktree: freshly read the full current canonical GWTF CSV and unabridged canonical CESSPIT, CASPER and CCCDIR definitions; execute applicable bootstrap and record provenance. RECRUIT-01 and VERIFY-01 are decision and verification requirements. Use explicit writer ownership, independent exact-object review, meaningful consequential evidence and negative controls. Proceed autonomously on existing authority and merge on independently accepted exact-head required green. Preserve source evidence and actual professional HOLD boundaries. Copying this instruction is not evidence that ingress or verification occurred.

## Inherited model and reasoning setting

Owner addition, verbatim: "all new worktrees, PR's etc should also inherit the GPT-6 Astra Extra High setting from the coordinator"

All new delivery and reviewer tasks must use model `gpt-6-astra` with Extra High reasoning (`xhigh`). Explicitly set `model=gpt-6-astra` and `thinking=xhigh` when creating or resuming Codex tasks. For collaboration agents explicitly set `model=gpt-6-astra`, `reasoning_effort=xhigh` with permitted context-fork arguments. Include this configuration and the verbatim owner instruction in new task prompts, worktree briefs and PR descriptions. The execution setting belongs to authoring/review tasks; record it in associated worktree and PR provenance. Never silently substitute a model or effort. Active F2F3 was sent this explicit configuration override on 2026-09-08; paused tasks receive it when resumed.
