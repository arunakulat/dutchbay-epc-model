# Issue #1229 screening adapter implementation record

Status: DELIVERY_IN_PROGRESS as draft PR #1449; both fresh reviews ACCEPT_WITH_NITS on the
rebased subject; N1, F1, N5 and F7 repaired in follow-up commits; five-run campaign, final-head rebinds,
hosted Grid Study and merge pending (see "Delivery as PR #1449").
Controlling authority and both verbatim owner instructions are in
`ISSUE1229_IMPLEMENTATION_PROFILE.md`, copied from the coordinator's profile.

## Identity and bounded ownership

Sole writer: task `01a08180-c2e0-71b1-b80d-54661c802b53`, GPT-6 Astra Extra High
(`gpt-6-astra`, `xhigh`), verified from actual session turn metadata. Coordinator:
`01a07ca9-86e2-79b2-a462-cab673d4ead5`. Project: DutchBay_EPC_Model.
Worktree: `/Users/aruna/.codex/worktrees/defd/dutchbay-epc-model`.
Branch: `codex/1229-pandapower-screening`.
Implementation starts at protected main `5ec33d32834c18e8c14dff06617ff92fec365828`,
tree `708171c4026e8f7386c53c323b90a01d9bc91867`, after F2/F3 PR1243 merged.
The detached ingress origin `61c5956d0ec23d03b1ac472abf735d6172ef4dbd` is historical.
Lease `ISSUE1229-WRITER-001` and its append-only base clarification bind initial exact
paths, original hashes, preflight and expiry. After the app pause, lease002 freshly
reconciled source/runtime ownership and safely fast-forwarded to H03 main
`71d3c138bd6043d7434b4cfacbfc3e39d3d16cec`, preserving all 12 candidate paths.
After H04 merged, another disjoint ff-only step reached protected main
`446d595fe526541c549ee90aca61c4698ac0876b`, again preserving all 12 paths.
Its append-only preflight clarification separates inherited historical fields
from the actual fresh resume/preflight and post-FF head. Risk is `R3_CONSEQUENTIAL`.

The full 74-rule canonical CSV, AGENTS, pinned unabridged CASPER/CESSPIT/CCCDIR
definitions, all four RECRUIT-01 modules, controlling September 7 bootstrap and
September 8 scoped PR1237/PR1243 successors were re-ingressed. The current
environment and rules gates pass. Persistent Python is 3.12.13 at
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`; this checkout leads PYTHONPATH.
No replacement environment or dependency change is part of this candidate.

## Evidence and design

The immutable diagnostic package remains under programme `issue1229/`; its 15
manifest entries reverified. Checkpoint SHA-256:
`07ba282d308eb930b94310a618721292f80e6be9d69222e7f99107e77259d5a9`.
Diagnostic manifest SHA-256:
`0130cc11c62e48c45328a4e27f8862ea83bb1170056cfdece870dc21d72d842d`.
New evidence is in the sibling `issue1229_implementation/`, under
`/Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/`.
Original source `reverent-chatterjee-e6191a` and shared programme ledgers are untouched.

One fresh interpreter executes each complete screening batch: both short-circuit
cases, the entire reactive operating-point sweep, or the full harmonic-order scan.
Each process owns its vendor compatibility state and exits after one request.
There is no worker pool, inherited Python heap, parent-module substitution, or
cross-request mutable worker lifetime. The existing public screen functions and
canonical contracts perform the mathematics and banding.

The worker uses the three vendor auxiliary Python originals, updates the two
known `get_values` aliases, and uses `gen_Ybus.py_func`. Existing
`runpp(numba=False)` remains. Compatibility is explicitly version-checked against
`config/pandapower_screening.json`; unsupported versions fail at call time. The
same policy specifies the whole-batch timeout. The private JSON channel has an
allowlisted operation set, finite numbers, exact result fields, canonical typed
decoding and method/bankability checks. The existing nonconverged power-flow NaN
is transported as a conditional null and restored only for a failed solve.

Parent-side optional-dependency guards and explicit closed-form opt-out remain.
A worker timeout, death, invalid result or failed solver cannot select a successful
fallback. Vendor diagnostics remain visible. Imports stay lazy with respect to
pandapower, Numba, llvmlite and OpenDSS. The in-process alternative was rejected
because a local lock cannot govern unrelated consumers or previously bound aliases.

## Verification and cost before campaign

All 10 baseline and candidate screen payloads match, including every IEEE float
hex value: six SC driver/rating cases, two reactive cases and two harmonic cases.
The untouched baseline was extracted from Git `5ec33d3`; all three public baseline
consumers hit the pre-import compilation sentinel at `_python_set_elements_oos`.
The guarded production adapter completed both SC cases, 15 reactive corners and
five harmonic orders without compilation. Removing auxiliary adaptation or Ybus
adaptation independently fails. The independent 60-digit radial Decimal oracle
and driver-responsiveness tests pass. Sparse/OOS buses, a transformer/get_values
alias and a late import match the unmodified vendor control.

Exact writer commands and original results live in the external evidence package.
The expanded native/lifecycle/app-emitter focused run passed **106 tests in
211.05 seconds**, exit 0. Subsequent grid-free transport/optional/import tests,
including an injected Python interruption, passed **171 tests in 19.61
seconds**, with three existing SWIG DeprecationWarnings. A fresh parent also executed an existing unrelated Numba specialization before
and after the real screen, then compiled and executed a new float specialization.
The dispatcher method, vendor helper and global JIT setting stayed unchanged.
Scoped five-source mypy and Ruff pass. The first pre-commit pass normalized the copied profile's terminal
newline and returned 1; both verbatim owner instructions are unchanged. An earlier
isort check reported the new native test's import order; its formatter corrected it.
The final scoped pre-commit rerun passed all applicable hooks.

Earlier failures remain in the receipt chain: two initial mypy errors were fixed;
two test collections failed on a reserved parameter name and its incomplete
rename. The initial focused run then passed 69 tests before the optional-Numba and
sparse/OOS extensions. These runs are dated focused evidence, never five-run or
independent acceptance.

The measured cost is material. Warm per-screen median seconds (three measurements
each, after parent imports and warmed font cache) were:

| Public screen | Unmodified vendor | Process adapter |
|---|---:|---:|
| SC min/max | 0.1201 | 2.5217 |
| Reactive 15-corner sweep | 1.0623 | 3.5426 |
| Harmonic 5-order sweep | 0.3360 | 2.7617 |

The actual unchanged report builder's pre-existing fixture rose from **1.2247 to
6.0310 seconds** median. With an explicit harmonic spectrum it rose from **1.6306
to 8.7791 seconds**. Each source completed one warm-up and three measured calls for
each fixture. The approximately 2.4-second interpreter/import cost is paid per
whole screen, never per solve. Results and the existing degradation categories
remain equal. These are measured workloads, not a performance improvement or SLA.

**Writer cost disposition, subject to both independent reviews:** accept the
approximately 5–7 added seconds for explicitly requested batch/async advisory
reports to isolate compatibility state and native death while preserving vendor
mathematics. The existing source and pre-change tests prohibit grid execution in
the synchronous HTTP route; no numeric opt-in batch budget was found in the
inspected policy/source/cited issue #645. The 120-second new lifecycle timeout is not
an existing performance budget. No default finance path cost is introduced.
Overhead accumulates in multi-scenario batches: 20 serial harmonic-enabled reports
would add roughly 143 seconds by extrapolation, not a measured 20-report benchmark.
A shared persistent worker would add lifetime/ownership hazards; broader report
orchestration is outside this bounded adapter. Both reviewers must explicitly
assess this tradeoff and the measured complete-suite walltimes.

Baseline caches were disposable containment for diagnostic writes, shared and
warmed for the measurement pair; they are not an avoidance mechanism and do not
define the native full-suite campaign. No JIT disabling was used. The original
cold 19.34-second SC call included font-cache construction and is excluded from
latency comparisons. `baseline_comparison_receipt.json` status PASS denotes
successful controls/measurement collection and numeric identity, not performance
acceptance. See `report_latency_receipt.json` and `latency_disposition.json`.

The first independent domain and assurance reviews both **REJECTED** commit
`dd9d7521ad58256027d35e11be9bb50900762032`. GDR-001 found that numeric mapping
spectra supported by the original harmonic parser could abort both harmonic and
mandatory reactive/report calls. A1229-001 reproduced three real SIGINT cases in
which Python 3.12 killed the worker but left it unreaped. The earlier injected
KeyboardInterrupt test bypassed the standard library's actual signal bookkeeping;
its passing result never proved real-signal cleanup. Original complete dispositions
and 44 selected execution events remain byte-preserved under programme
`issue1229_review_rejections_001/`; their manifest and exact rejected subject remain
unchanged. No acceptance was transferred from this rejected subject.

Fresh lease003 authorizes these bounded repairs. Numeric spectrum mappings at both
supported locations become ordered pairs, preserving key types, original parser
semantics, top-level/nested precedence and caller data. Process cleanup now uses
explicit Popen kill-and-wait after communication interruption. Twelve focused repair
tests passed in 79.15s: actual mapping/list/nested/empty precedence comparisons,
real report-core/harmonic calls and three actual caller SIGINT cases. The expanded focused regression passed **236 tests in 271.29s**, exit 0. The same
eight real-signal and supported-input regression tests failed 8/8 on the rejected
Git archive and passed 8/8 on the repaired source. Exact commands and concise
original-fails/repaired-passes evidence are recorded externally.
Both reviewers must review the freshly frozen substantive subject again.

The coordinator also rejected two external campaign controls before any suite ran:
legitimate module-level collection skips were absent from expected JUnit population,
and a rapid-exit parent could leave a detached descendant undetected. The corrected
controls separately track collection outcomes and inherited unique process ownership,
verify stable empty owned-process scans, and fail closed on unresolved ownership.
Their actual positive/hostile controls and exact hashes require independent review.
These external harness findings are separate from the production-source findings.

Required-not-run at this (September) checkpoint: five consecutive full suites, fresh
independent grid-domain and assurance acceptance, exact-head hosted CI/Grid Study, PR
merge and issue closure. Every remaining gate must bind the eventual exact frozen object.
The section below records what happened to each of them after delivery resumed.

## Delivery as PR #1449 (resumed 2026-10-27)

The September writer left this work as the unmerged local branch
`codex/1229-pandapower-screening`. On 2026-10-27, at the owner's request, a Claude Code
session (the new sole writer) cherry-picked its two commits unchanged and without
conflicts onto protected main `50d72d44ac54d11a7d0a2b44fa2531ce1b673d56` as
`claude/1229-pandapower-screening`. It opened draft PR #1449 and recorded the work item on
#1229 before pushing. The identity, worktree and base facts in "Identity and bounded
ownership" above describe the September writer and are historical. The governing CSV
at this base holds 77 rules, not the 74 recorded above.

**Reviewer model: waived by the owner, not silently substituted.** The profile's
acceptance step 5 requires reviewers recruited with explicit Astra/xhigh. The fresh
reviews ran on Claude Opus 5.5. The owner waived the Astra/xhigh clause for this PR on
2026-10-27 ("opus 5.5 is fine"), and that waiver covers the final-head rebinds too.

**Fresh reviews of the rebased subject** (head `25cb4e81e2ecef9dc01d0d282f099a5ff1891513`,
tree `070762c8db0b386604995cfeb134b2a87b3cf06b`, base `50d72d44`):

- Grid domain, ACCEPT_WITH_NITS. The reviewer checked compile avoidance by running it.
  A hook on llvmlite's `link_in` (the `link_modules` crash site) recorded 0 links and no
  compiled dispatchers on the strength, reactive and harmonic paths through the worker,
  against 34, 1 and 1 links on stock pandapower. The 190 recorded floats across 20
  result groups are bit-identical to base. Nits: the `[grid]` extra's declared range
  allows pandapower versions the policy refuses (N1); numpy integer scalars are now
  rejected (N2); errors raised inside the worker surface as `ScreeningProcessError`
  (N3); each screen costs about 2.4 s more, accepted for the advisory callers (N4); and
  spacing typos in this record (N5).
- Assurance, ACCEPT_WITH_NITS. Lifecycle cleanup, the JSON channel and the test oracles
  held under hostile probes. Findings: a worker whose caller is killed by SIGTERM or
  SIGKILL is orphaned with no time limit, because the timeout lived only in the parent
  (F1). Strict serialisation rejects unusual unused grid fields (F3). The crash-text
  pattern is broad (F4). Some negative tests are missing (F5). There is per-screen CI
  cost and no `.test_durations` entries for the new tests (F6). This record held stale
  claims (F7).

**Repairs in the follow-up commit:** N1, by pinning `pandapower==3.5.4` in
`constraints.txt`, which the documented `[grid]` install applies, so a fresh install
cannot resolve a version the policy refuses. F1, with an in-worker
`faulthandler.dump_traceback_later(timeout + 5 s, exit=True)` deadline that a real
subprocess test shows ending an orphaned worker without its parent. A mutant without
the deadline hangs. N5 and F7, in this record. N2, N3, F3, F4, F5 and F6 are recorded
as accepted limits or follow-ups, not fixed here. The repaired subject is a new object,
so both reviewers must rebind to its exact SHA.

**Hosted Grid Study finding, and the oracle change.** The first hosted Grid Study run
(Linux x86_64) failed a single assertion. The worker's charter SCR was
`0x1.e186c84e283bep-1` against the macOS-measured constant `0x1.e186c84e283bdp-1`, one
ulp apart. Everything else passed, including the same-platform stock-against-adapted
comparison in `test_sparse_oos_aliases_and_late_import_match_vendor`. The charter
constants are a macOS arm64 measurement, not a portable bit-identity oracle. The test
now runs the unmodified vendor path in its own child through the same process boundary,
and requires hex equality with it on whichever platform the suite runs on. It keeps the
charter values as an absolute 1e-14 check on SCR and 1e-11 on fault levels. The branch
was also brought up to date with main `becb634a`. None of the commits main gained
touches `analytics/grid/`, `tests/grid/` or `constraints.txt`.

The first local five-run attempt also stopped on run 1. Two `tests/lint/test_pip_audit_allowlist.py`
cases fail identically on an unmodified archive of base `50d72d44`, because macOS ships
GNU Make 3.81 and CI runs make 4.x. The streak therefore deselects exactly those two node
ids, and declares that it does so.

## Limits and authority

The candidate avoids identified compilation paths and contains worker failure.
It does not establish LLVM's underlying corruption cause or the application test
that triggered the newer F2/F3 incident. Existing harmonic-screen approximation
and advisory-only semantics remain. No financial algorithm, coverage threshold,
CI routing, release, professional, lender, Board or HOLD authority changes.
Issue #1110 remains OPEN and outside this implementation. Issue #1229 remains
OPEN until its actual acceptance and verified delivery are satisfied.
