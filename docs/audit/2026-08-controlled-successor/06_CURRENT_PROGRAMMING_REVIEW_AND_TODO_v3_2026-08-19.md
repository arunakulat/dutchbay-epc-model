# DutchBay post-merge programming review and controlled to-do v3

**Control cutoff:** 2026-08-19T01:05:00+05:30
**Repository:** `/Users/aruna/Downloads/dutchbay-epc-model`
**Local and remote main:** `231b39d221c6a04b7fb2a34452b107054c3ee759`
**Main tree:** `9ea89e2360dd693a457a1333e84f617a2a128729`
**Version:** `15.4.0`
**Audit evidence basis:** `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Issue #923:** **OPEN**
**Board/lender status:** **HOLD**

This is an additive successor to
`05_CURRENT_PROGRAMMING_REVIEW_AND_TODO_v2_2026-08-18.md`. It records the final
verification and protected merge of #923-B1, the disposition of PRs #1049 and
#1050, the current Python 3.12 worktree state, and the next independently
reviewable dolphins. It does not rewrite the v2 capture, amend immutable audit
inputs, close an audit finding, authorize synthetic evidence as real evidence,
or lift the Board/lender hold.

## 1. Re-ingress and environment result

The canonical 66-rule GWTF v3.0 ruleset and the unmodified CASPER, CESSPIT and
CCCDIR definitions were re-ingressed before repository action.

The user-requested worktree and environment are now verified as follows:

- worktree:
  `/Users/aruna/Downloads/dutchbay-wt-923-synthetic-feeder`;
- HEAD:
  `231b39d221c6a04b7fb2a34452b107054c3ee759`, byte-aligned with merged
  `origin/main` at the control cutoff;
- Python: `3.12.13` from that worktree's own `.venv`;
- `pip check`: no broken requirements;
- repository-root `check_venv.sh`: PASS;
- post-merge focused #923-B1/R25 gate: 180 passed, one environmental Hypothesis
  collection warning;
- worktree files: clean.

The generator worktree
`/Users/aruna/Downloads/dutchbay-wt-923-synthetic-feeder-b` retains the exact
reviewed candidate commit
`d8e821024d911039a4313546867e78ac8b9f87fc` and its own ignored Python 3.12.13
environment. Because #1056 was squash-merged, that candidate commit is evidence
of the reviewed head rather than a fast-forwardable mainline commit. Its tree is
identical to merged main. It was not reset or destructively rewritten.

The canonical repository main branch is clean and synchronized to the same
merged commit and tree. It has no local `.venv`; post-merge Python checks were
therefore correctly run in the synchronized worktree-local environment, not by
borrowing a sibling environment for an unsynchronized tree.

## 2. PR #1049/#1050 assertion adjudication

The programmer assertion was historically correct against the main commit it
named, `d81f0e37`:

| PR | Asserted head | Relation to `d81f0e37` | Check result at asserted head |
|---|---|---|---|
| #1049 | `aebab99b` | 0 behind, 5 ahead | 15 success, one skip |
| #1050 | `495a10c7` | 0 behind, 3 ahead | 15 success, one skip |

It was not a durable current-state assertion. By the first live verification,
`main` had advanced to `3db2a4a` and both asserted heads trailed it by three
commits. They were subsequently refreshed, rechecked and merged:

| PR | Final reviewed head | Merge commit | Final protected result |
|---|---|---|---|
| #1049 handover close-out | `0bdb54aadf2b4081bf7dc8aec06668c4459d9ebe` | `4bbc6dec95c7c549b59da64b974805d55d5d758b` | 16 success, one skip |
| #1050 MODULE_REFERENCE path fix | `e802710b12b3eb5405bb41ec0aa76427dee2ab39` | `b10af65110179b47a3b9355bb03b452d0f07d593` | 16 success, one skip |

Their final changes are documentation/changelog-only and do not collide with
the #923-B1 source, configuration, runner or tests. The old head/check statement
is retained as valid historical evidence, not used as current merge authority.

## 3. Accepted v15.4.0 tag exception

The published, annotated but unsigned `v15.4.0` tag remains accepted as an
explicit user-authorized exception. It must not be moved, deleted, recreated or
silently replaced. The next release must return to the signed-tag procedure and
should make signature verification an executable release gate.

## 4. #923-B1 final disposition

Protected PR [#1056](https://github.com/arunakulat/dutchbay-epc-model/pull/1056)
was opened from exact base
`b10af65110179b47a3b9355bb03b452d0f07d593` and exact reviewed head
`d8e821024d911039a4313546867e78ac8b9f87fc`.

The final repository delta contains exactly five additions, 4,218 insertions and
no deletions:

| Repository path | SHA-256 |
|---|---|
| `analytics/grid/synthetic_feeder_placeholder.py` | `d69da0e1769d6962f214031785ab3e49cbef754dbc8edfd87ce0bfc5c57f36df` |
| `changelog.d/923-synthetic-feeder-placeholder.added.md` | `dfccbd166279d6917d2f46dcfafd9dc10f8de62031c9f8d726ee3d2b06c19c74` |
| `conf/synthetic_feeder_placeholder.yaml` | `0d15865ed884babcc5977654d553cbb115695f2b875e3bf63b82853f16f1f634` |
| `scripts/run_synthetic_feeder_placeholder_v14.py` | `a54f8f18fa605803668a5a8c652902f337c6e029ae8491fc5a0e1c5fed6b7021` |
| `tests/grid/test_synthetic_feeder_placeholder.py` | `b2059abaad127fc49434fa7b6b5a6e1e9080b7c268074048d8acc6876573f02f` |

The final generated package has exactly eight governed files. Its pinned
identity is:

- profile SHA-256:
  `cefa4b9e37f85e5f7774a14727bf35a43c9c3bd8b3219bd730a35aff4f36ab76`;
- manifest SHA-256:
  `7b303ab3e4be1f4aff8a0ca9d733921b53b15adb87d0f309d0ac73e821562685`;
- checksum-file SHA-256:
  `ccf9851b80e1249fe5ee2efcfaa77ab6cc142be1ec44dc89b88166d4be6583cc`.

The package is deterministic PCG64/AR(1)/Weibull output calibrated only to the
pinned scenario and hashed ERA5-derived summary. The 2021 dates supply an
8,760-hour UTC timestamp shape only. They are not observed or reconstructed
2021 ERA5, measured mast data, an authenticated CEB/NSO feeder, or an
independent resource assessment.

Its controlled classifications remain:

- `input_kind=synthetic_placeholder`;
- `source_kind=synthetic_era5_summary_calibrated`;
- `chronology_kind=synthetic_not_observed_2021`;
- generated input true;
- observed, site-representative, engineering-validated, utility-accepted,
  bankable, publishable, canonical, finance-executed and finding-closure flags
  false or zero;
- OpenDSS compile-only PASS;
- convergence `not_examined_deferred_issue_923_C`;
- finance `not_run_scope_923_B`.

## 5. R25 detection and correction

The first production-mode full run found exactly one failure after 5,408 tests
passed: the root runner violated the GWTF R25 root-entrypoint invariant. The
runner was relocated to `scripts/`, its repository-root and Hydra configuration
resolution were corrected, and only the relevant subprocess/invocation tests
and changelog were updated.

The additive controlling note is
`code_dolphins/ISSUE_923_B1_R25_ENTRYPOINT_RELOCATION_ADDENDUM_2026-08-19.md`,
SHA-256
`78bb7d86f4bdf2cb84ce08b4abeb8c87bba299447ab507d976961b38d1f5907b`.

The frozen design specification and seven dated refuter reports are preserved
unchanged. Their root-runner path is accurate for their predecessor snapshots
but is not the final-tree interface path.

## 6. Final harness and merge evidence

The exact final candidate passed:

- focused B1 plus R25 entrypoint controls: 180 passed;
- GWTF/CASPER/CESSPIT/CCCDIR/provenance/compatibility/canonical-identity
  matrix: 387 passed and one expected optional-dependency inverse-guard skip;
- scoped pre-commit, Ruff, Black, isort and strict mypy: PASS;
- Bandit: zero medium/high findings;
- dependency audit: no known vulnerabilities;
- two real Hydra runs: return code zero, byte-identical eight-file packages,
  one concise JSON receipt each, zero stderr and no retained runtime log;
- production-mode full regression after the R25 repair: 5,409 passed, 12
  expected skips, 22 warnings and 95.67% coverage.

The complete protected graph then produced 16 successes, zero failures or
pending checks, and one intentional non-blocking Grid Study skip. It included
CodeQL, security, code quality, fastlane, smoke, six Python 3.12 shards, the
95% coverage gate, combined test results and test summary.

The PR was marked ready only after that graph completed and was squash-merged at
`2026-08-19T01:00:42+05:30` as
`231b39d221c6a04b7fb2a34452b107054c3ee759`. Its tree is exactly the reviewed
candidate tree:

```text
candidate  9ea89e2360dd693a457a1333e84f617a2a128729
merged     9ea89e2360dd693a457a1333e84f617a2a128729
```

The remote topic branch was removed by the merge workflow. Canonical main and
the requested provenance worktree were safely fast-forwarded. The post-merge
focused gate passed 180 tests.

## 7. Issue #923 automatic closure and correction

GitHub's closing-reference linkage closed Issue #923 automatically at the merge
timestamp even though #1056's body and merge message explicitly state B1-only,
zero closure weight and that B2/C/D/E/R remain open. The post-merge control
detected the event immediately.

Issue #923 was reopened, and GitHub comment `5333054994` records that #1056 does
not satisfy the original user-gated canonical-finance acceptance criteria. The
issue is **OPEN** at this cutoff.

## 8. F5-02 and synthetic lender evidence remain separate

The controlling 55-item positive-evidence list remains
`code_dolphins/F5-02_TRANSACTION_EVIDENCE_REQUIREMENTS_2026-08-18.md`, SHA-256
`7f3199867ae6aaae2e7365b0cb15fe7ca81b3348060e9ac443622fbc231a9416`.

The detailed analyst-generated term sheet is
`deliverables/DUTCHBAY_ANALYST_GENERATED_SYNTHETIC_LENDER_TERM_SHEET_2026-08-18.md`,
SHA-256
`d42dc7e5c41824001a98923dc0b417203cfba58f7e3d11ff065fca07e63ea609`.
It is synthetic, non-binding and not lender evidence. Its ADB, IFC and probable
AIIB background material supports analyst assumptions only. “AIBB” remains an
unresolved acronym; it was not silently changed to AIIB.

The synthetic term sheet does not close #920 or F5-02. Transaction action still
requires lender-issued and legally reliable evidence for every applicable
identity, currency, drawdown, interest, repayment, fee, security, hedge,
reserve, tax, regulatory, PPA, payment-security, default and remedy field.
F5-01 and F5-02 remain completely separate.

## 9. Updated controlled to-do list

### Completed at this cutoff

1. Re-ingress all 66 GWTF rules and the canonical CASPER/CESSPIT/CCCDIR
   definitions.
2. Verify and reconcile both #923 Python 3.12 worktree environments.
3. Adjudicate the #1049/#1050 assertion against its named historical base and
   their final refreshed/merged states.
4. Complete #923-B1 generation, strict provenance, detached verification,
   adversarial refutation, R25 correction, protected CI, merge-tree proof,
   synchronization and post-merge focused regression.
5. Detect and reverse the unintended GitHub issue closure while preserving a
   durable explanation.

### Next autonomous code dolphins

1. **#923-B2 — runtime verifier/propagation seam.** Consume the exact package
   manifest and external digest at the runtime boundary; propagate truthful
   provenance without enabling finance or claiming QSTS convergence.
2. **#923-C — convergence and accounting.** Run and reconcile all 8,760 steps,
   cap exceedance, curtailment, injection, convergence/error telemetry and
   independent accounting identities. Compile-only PASS is insufficient.
3. **#923-D — synthetic finance counterfactual.** Use only the conspicuously
   synthetic package, remain noncanonical, compare the KPI oracle, and state
   that results are software-path sensitivities rather than project evidence.
4. **#923-E — presentation and release control.** Watermark every synthetic
   output, expose input kind/generated/site/limitations, prevent “real loss” or
   bankability language, and test every report/API consumer.
5. **#923-R — real evidence replacement.** Require authenticated CEB/NSO feeder
   and operating data, engineering verification, full QSTS reconciliation and
   explicit user sign-off before any canonical finance decision.

### Separately controlled evidence dolphins

6. **#961 synthetic mast/MCP placeholder.** Generate an ERA5-location-compatible
   synthetic modelling fixture only. It must be labelled generated, unmeasured,
   non-MEASNET, non-resource-assessment, non-bankable and zero-closure until a
   traceable on-site campaign, mast metadata, MCP analysis and independent
   assessment replace it.
7. **#920/F5-02 transaction evidence.** Retain the detailed synthetic lender
   term sheet as an analyst negotiation fixture, never lender evidence. Replace
   each applicable field with authenticated lender/legal/transaction documents
   before binding canon, re-baselining or lender presentation.
8. **ENV-PY312-01.** Make bootstrap prove a repository-owned `.venv`, executable
   identity and exact Python 3.12 version; test absent, valid, stale and
   parent-only cases.
9. **ENV-PY312-02.** Remove unpinned setup fallback, constrain editable extras,
   require the lock and `pip check`, and fail before a false ready state.
10. **ENV-PY312-03.** Remove `|| true` installation suppression from
    `scripts/venv_up.sh`; verify the environment before declaring it ready.
11. **ENV-PY312-04.** Reconcile web-session default extras with `LOCK_EXTRAS`
    and the lock; constrain installation and validate required imports before
    stamping success.

### Audit and circulation gates after the code/evidence dolphins

12. Ingress #1056 and its additive refuter/R25 evidence into the controlled
    findings, reproduction, architecture and source registers without granting
    synthetic evidence any closure weight.
13. Complete the remaining semantic reproductions and 72-pointer examination,
    including independent successor QA for the material P3/P5 claims.
14. Correct the feasibility/report package only from reconciled evidence and
    regenerate the Board/lender synthesis last.

## 10. Explicit non-actions and release state

- Do not enable the synthetic feeder package in canonical finance.
- Do not describe the chronology as ERA5 observations, measured site data or a
  resource assessment.
- Do not treat OpenDSS compilation as convergence, hosting capacity, utility
  acceptance or a bankability conclusion.
- Do not combine #923-B2/C/D/E/R in one rollback surface without a separately
  justified and independently reviewed scope decision.
- Do not treat the #961 placeholder as mast/MCP evidence.
- Do not treat the #920 term sheet as lender-issued evidence.
- Do not combine F5-01 and F5-02.
- Do not mutate the accepted v15.4.0 tag/release exception.
- Do not lift the Board/lender HOLD because code, a structural validator, a
  synthetic engineering package or a synthetic lender fixture passes.

The next immediate implementation action is #923-B2, after this v3 successor,
R25 addendum, index/worklog entries and a new immutable current-state manifest
have been finalized and checked.
