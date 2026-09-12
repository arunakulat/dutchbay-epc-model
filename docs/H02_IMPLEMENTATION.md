# H02 deterministic dependency guards — implementation record

Status: source checkpoint verified; independent acceptance and delivery pending.
This record covers H02 only. The live PR and external closeout receipts establish
subsequent delivery state. No production source, dependency, financial behavior,
environment, native-grid implementation, qualification policy or HOLD changes.

## Identity and ingress

Project: `DutchBay_EPC_Model`; sole writer/delivery owner:
`01a08255-9a4b-74b2-8618-b09b76be0775`. Coordinator:
`01a07e1b-a139-79e0-94fc-4a8d48c37b72`. Worktree:
`/Users/aruna/.codex/worktrees/61b5/dutchbay-epc-model`.
Branch: `codex/h02-dependency-guard-tests`.
Protected base: `f1fba1c0c3f5fdb3147acfee90b6581cfb8ee00f` (H01 PR #1244).
Source commit: `5ceb57f43768c5889ff965864bcca4e26e542ba8`;
tree: `bf6f98eca74a3824d2c93c42901596e42124efbb`.

Actual writer session metadata verifies `gpt-6-astra` / `xhigh`. Project association
is verified from successful project-task creation and the live app assignment;
the app-server database's unmigrated null project field is not used as authority.
Python 3.12.13 uses `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` with the active
checkout first on `PYTHONPATH` and `PYTHONDONTWRITEBYTECODE=1`.

Read the complete current GWTF CSV (74 active v3.0 rules), AGENTS, unabridged pinned
CASPER/CESSPIT/CCCDIR definitions, all four RECRUIT-01 modules, startup handover
`SESSION_HANDOVER_2026-09-07.md`, applicable F2/F3 and H01 successors, authoritative
H02 preparation/dispatch profile, original hygiene report and assurance diagnosis.
The bootstrap and governed environment check passed; current origin/main and
predecessor merge were independently fetched/verified. Source hashes and exact
lease preflights are retained under the external evidence root below.

## Scope and verification meaning

The original three test modules returned **43 passed, 3 skipped in 4.32s**. The
installed arq, WeasyPrint and pandas packages disabled their absence-path tests.
The changed tests now exercise real production calls through local dependency seams:

- Jobs: block arq and redis individually in `sys.modules`, provide the other import
  as a module, call the real guard and backend, and require installation guidance
  plus the missing module's chained `ModuleNotFoundError`. Memory storage remains
  available with both imports blocked; the both-available guard control passes.
- PDF: a narrowly targeted import hook raises a known package error or native
  loader `OSError`. The real public renderer and loader must wrap it as
  `ReportDependencyError`, retain that exact cause, and disclose package/system
  installation guidance and HTML availability. The real installed PDF test remains.
- Pandas: patch the production `analytics.mc.exports.pd` reference to `None` and call
  `build_lender_risk_table`. Existing real DataFrame tests remain. A separate probe
  proves exact DataFrame equality before and after the restored dependency seam.

Scoped lint initially found existing E402/B017 failures in the pandas test file.
The module docstring now precedes its future import and the immutability assertion
requires `FrozenInstanceError`. Scoped mypy initially reported the existing
deliberate `trials=None` compatibility input; a narrow, explained `arg-type` ignore
preserves that negative/legacy input. No production type or validation gate changes.
Touched Python files are Black/isort-normalized and Ruff-clean.

## Executed checks and retained evidence

Commands run from the named worktree with `DUTCHBAY_VENV` set to the persistent
path above, its `bin` tools, `PYTHONPATH="$PWD"`, and `PYTHONDONTWRITEBYTECODE=1`.
Exact tool inputs, including the complete pandas probe, are retained once as
`writer_executed_commands.txt`, SHA-256
`485b9f4a4c6cdc18d03b3716269727e5648c09a5d469e525be146a5fbe2b6779`.

| Check | Exact command or retained command reference | Result |
|---|---|---|
| Environment | `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap` | PASS; active-checkout import; no foreign-checkout paths |
| Rules | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` | PASS; 74 active v3.0 rules |
| Three edited modules | `$DUTCHBAY_VENV/bin/python -m pytest -o addopts='' -p no:cacheprovider --no-cov tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py -q -rs --tb=short` | Initial changed run: 50 passed, zero skips, 4.33s |
| Expanded final checks | `$DUTCHBAY_VENV/bin/python -m pytest -o addopts='' -p no:cacheprovider --no-cov tests/app/test_jobs_backend_gate.py tests/app/test_jobs_router.py tests/app/test_jobs_redis_store.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py -q -rs --tb=short` | 67 passed, zero skips, 4.17s |
| Ruff | `$DUTCHBAY_VENV/bin/ruff check tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py` | PASS after the disclosed existing lint fixes |
| Ruff format | `$DUTCHBAY_VENV/bin/ruff format --check tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py` | Three files already formatted |
| Black/isort | `$DUTCHBAY_VENV/bin/black tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py`; `$DUTCHBAY_VENV/bin/isort --profile black tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py` | Final run clean; three files unchanged |
| Scoped types | `$DUTCHBAY_VENV/bin/mypy --follow-imports=silent --allow-untyped-defs --allow-untyped-calls --cache-dir=/tmp/h02-mypy-cache tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py` | PASS, three files; annotation-completeness relaxation for existing test helpers only; imported library typing remains hosted-CI work |
| Pre-commit | `$DUTCHBAY_VENV/bin/pre-commit run --files tests/app/test_jobs_backend_gate.py tests/app/test_report_renderer.py tests/analytics_layer/test_mc_exports.py changelog.d/hygiene-dependency-guards.fixed.md` | All applicable hooks passed |
| Whitespace | `git diff --check` | PASS |

Mutation command: `$DUTCHBAY_VENV/bin/python
/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H02/delivery/guard_mutations.py`.
It compiles in-memory variants of the real production functions in isolated child
interpreters. Disk production source is never edited. Every mutant is bracketed
by a fresh passing unmutated run of its same test selection. The script verifies
source/test hashes before and after; routine pytest output is discarded.

| Mutation | Before | Mutant | After |
|---|---|---|---|
| Jobs guard becomes no-op | 4 pass | 4 fail | 4 pass |
| Backend omits guard call | 2 pass | 2 fail | 2 pass |
| Jobs original cause removed | 4 pass | 4 fail | 4 pass |
| PDF exception wrapper bypassed | 2 pass | 2 fail | 2 pass |
| PDF original cause removed | 2 pass | 2 fail | 2 pass |
| Pandas guard bypassed | 1 pass | 1 fail | 1 pass |

All six mutants were killed: 15 expected failing observations, no skips or setup
errors, 15-pass controls on each side in aggregate, and identical disk hashes.
Script SHA-256: `ede2bf09e020b028c7445353cb146a80dcbdc17646c554bd5af33364475ad0e8`.
Structured result SHA-256:
`4d7d8388ec6958351d5c68d65a031032aba3314e24c6bf49d378e5657d703ee9`.
The separate pandas probe returned a real 3-by-6 DataFrame before/after, with
`pandas.testing.assert_frame_equal(..., check_exact=True)` passing.

## Boundaries and next delivery gate

Risk is `R2_LOAD_BEARING`: tests define verification oracles. Freeze this record and
the four source objects, obtain separate domain and assurance dispositions with
independent challenge, preserve their exact original bodies, insert only leased
receipt files, open the PR, and obtain both external final-head rebinds. Required
hosted CI must pass on the exact current final head before standing-authorized merge.
No subject acceptance transfers to changed bytes or an unreviewed base movement.

Not run: local full suite or native five-run campaign (native owner retains
priority); local coverage (hosted unchanged 95% gate remains required); live Redis
round-trip (guard scope); package-wide pandas-free import qualification (the test
proves the call-time reference guard); stochastic/report qualifications, financial
regression and QSTS execution (no corresponding behavior or evidence claim).
Grid Study follows the unchanged fail-closed changed-path policy.

Issue #1110 and native #1229, release, evidence, professional, lender and Board
HOLDs remain. The controller owns shared programme ledgers. This task may retire
only its own clean state after accepted-tree/merge-ancestry verification and safe
primary-main synchronization. Original source evidence and other worktrees remain.

Evidence root: `/Users/aruna/Downloads/DutchBay_Test_Hygiene_2026-09-08/H02/delivery/`.
Leases L001/L002 cover the four source paths; separate L003 covers this record.
No raw runtime logs are retained.

## Owner standing instructions

> Do not wait for approval. work autonomously. Take your best, considered and safe decision. Use the Recruit-01 and verify-01 rules to reconsider and confirm your decisions. Start all new worktrees ingressing the rulesets - GWTF, CESSPIT, CASPER and CCCDIR. Follow these rules rigorously. Copy this instruction to all new tasks, worktrees, PR's

Owner addition, verbatim: "all new worktrees, PR's etc should also inherit the GPT-6 Astra Extra High setting from the coordinator"

Writer and both required reviewers use `gpt-6-astra` with `xhigh` reasoning;
actual session metadata must be verified before their work is accepted.
