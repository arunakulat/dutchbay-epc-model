# Session handover — 2026-08-24, successor 4

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-24_3.md`](SESSION_HANDOVER_2026-08-24_3.md).
The predecessor remains authoritative for its historical receipts except where
this record updates live state.

## 1. Live repository and environment state

**Protected main at this cutoff:**
`5503ff0e49683ddb8d8439d2460e2ebd08451985`.

**Active worktree:**
`/Users/aruna/Downloads/dutchbay-wt-1110-architecture-ledger`.

**Active branch:** `codex/1110-architecture-examination-ledger`.

**Branch base:** exact `origin/main` at `5503ff0e49683ddb8d8439d2460e2ebd08451985`.

**At this authored cutoff:** the architecture-ledger candidate is coherent and
locally validated but uncommitted, unpushed and not represented as a pull
request or merged result. Check live Git/GitHub state rather than treating this
capture-time sentence as permanent.

The Codex task remains rooted at `/Users/aruna/Downloads`, not the repository.
The built-in post-PR monitor is therefore blind under ENV-01. Until a future
task is reopened from `/Users/aruna/Downloads/dutchbay-epc-model`, use explicit
repository context:

```bash
git -C /Users/aruna/Downloads/dutchbay-epc-model ...
gh --repo arunakulat/dutchbay-epc-model ...
```

The only permitted local Python is the persistent governed environment:

```bash
export DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
export PATH="$DUTCHBAY_VENV/bin:$PATH"
export PYTHONPATH=/Users/aruna/Downloads/dutchbay-wt-1110-architecture-ledger
export PYTHONDONTWRITEBYTECODE=1
"$DUTCHBAY_VENV/bin/python" -VV
DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  "$DUTCHBAY_VENV/bin/python" dutchbay_bootstrap_rules.py
```

Latest receipt: Python 3.12.13; environment selection and import-origin checks
PASS; imports resolve from the active worktree; 72 GWTF v3.0 rules load and all
72 are active. No checkout-local `.venv` was created.

## 2. F5-02 lender-input dolphin is merged but remains open

PR [#1150](https://github.com/arunakulat/dutchbay-epc-model/pull/1150)
squash-merged through branch protection at `2026-08-24T10:29:09Z` as
`5503ff0e49683ddb8d8439d2460e2ebd08451985`, from exact reviewed head
`92b829a394cdbd836012fb4cb37f2b796058bddb` and base
`f2b6bed8bf5121f650a957afcfe643beb2ce0515`.

The reviewed feature tree and merged tree were exactly equal at
`d714ba756dc4ad57d69dd678a116b161f690dea6`. Exact-head CI recorded 18
successes and three scope-based skips. Post-merge main was clean and synchronized;
the governed environment, 88 focused F5-02 tests, and repository-safe controlled
pack validator passed from merged main. The retired feature worktree and branch
were removed only after tree equivalence was proved.

PR #1150 makes genuine private lender evidence collectable and fail-closed. It
does not provide lender evidence, select F5-02 treatment, change canon, close
F5-02, or lift HOLD. Issue [#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110)
remains OPEN. Delivery/non-closure receipt:
<https://github.com/arunakulat/dutchbay-epc-model/issues/1110#issuecomment-5393973550>.

F5-01 and F5-02 remain separate dolphins and must not be netted, rebaselined or
reviewed in one rollback surface.

## 3. Private/full archive re-entry and exact recovery

The full external validator requires a clean audited worktree at
`7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`. A temporary detached worktree was
created only for validation and removed afterward.

The first private run failed closed because two registered P5 PDF aliases had
been removed even though exact sibling files and manifest entries survived. A
complete PSR artifact reconciliation found no unrecoverable PSR object. The two
already-manifested paths were restored by exact byte copy:

- `McKay_Beckman_Conover_1979_LHS.pdf`: 699,567 bytes, SHA-256
  `45baafb7013b3404258d6b72b797d770498902db6b0b9657497dec7521c4a344`;
- `Morris_1991_factorial_sampling_plans.pdf`: 1,559,800 bytes, SHA-256
  `4153f39f14384c3a126773f46f6fe6d5fb045f42f9a706349d216a5c793a4567`.

No network source, new edition, text substitute or register edit was used.
`sources/SOURCE_ARCHIVE_MANIFEST.v2.sha256` passes for all 74 retained objects.
The final full/private validator run at `2026-08-24T16:27:37+05:30` returned
structural PASS/release HOLD with 42 sources, 111 findings, 72 architecture
pointers and 34 reproductions (18 completed, 11 required-not-run, five
unavailable).

Durable external receipt:
[`qa/PRIVATE_ARCHIVE_RECOVERY_AND_VALIDATION_2026-08-24.md`](</Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/qa/PRIVATE_ARCHIVE_RECOVERY_AND_VALIDATION_2026-08-24.md>).

External current-state manifest:
`/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/CURRENT_STATE_MANIFEST_2026-08-24T163000+0530.sha256`, 441 files,
SHA-256 `2b0d04f7b91116b291bdfed289975106896b66aa90425cf21e186c01c9c702a1`,
immediate check PASS.

The older 2026-08-19 current-state manifest is a historical snapshot and now
reports three unrelated later-removed outputs. It was not rewritten and those
synthetic/temporary files were not recreated.

## 4. Active dolphin — immutable 56-row pre-execution architecture ledger

The issue #1110 architecture gate covers 51 historical `not_examined` pointers
and five `deferred` pointers. This dolphin creates the control surface required
before execution; it does not claim that any pointer has now been examined.

The v1 design has 15 dependency-aware batches and exactly 56 immutable plan
rows. Each generated row contains:

- historical audited commit, source anchor, area, code location, assigned phase,
  risk claim and source disposition;
- the historical risk claim frozen as the testable claim plus its SHA-256;
- pinned current-main cutoff and one or more file-level scout seams;
- owner, typed dependencies and a pointer-specific planned negative control;
- required independent reviewer role;
- null reviewer identity and null result artifact/hash;
- `pending_examination`, `not_assessed`, unresolved gaps and
  `blocks_board_lender_release`.

The immutable input cannot carry result or disposition fields. Completed work
must use an additive result overlay or a new version; v1 must never be
back-written.

The plan is bound to a byte-preserved historical 72-pointer source snapshot,
not the mutable active overlay:

`registers/history/architecture_pointer_dispositions.pre-architecture-examination-plan.20260824.0b9c6803.json`
at SHA-256
`0b9c68039c24a4f23b2c6299b4189db6b6cabaffddf0cec628de5afc70ea96d8`.

All 86 unique current-main seam files were independently checked to exist in
Git at cutoff commit `5503ff0e49683ddb8d8439d2460e2ebd08451985`.

Key candidate identities at this cutoff:

| Artifact | SHA-256 |
|---|---|
| `registers/architecture_examination_plan.v1.json` | `43d648f23ff4aad876f02d42ffa2ff724a6f693a761fc3bca2385ab7dd65c0ca` |
| `registers/architecture_examination_ledger.v1.json` | `e6f3529c1fd2f5a3b384b2c93bb8713fce90cfd7ec9e585fb487a8844e613162` |
| `registers/architecture_examination_ledger.v1.csv` | `b446ec294da9adc46c41fb6c58129f3080b48d79f22d2a20ae4e317fec514c71` |
| ledger builder | `de20f7fd556dddfe3d369db547ef235f714b0a45784a1099ae532cb936a3160b` |
| pack validator | `d00d58f0b2fe6003842cbb4894ffd9913d9fcbbaabfd49f49875f70e365c290e` |
| 62-entry publication manifest | `05609b08dc791652bfd7c1ea796e4de12fa183eddbf3ca5bd964377643bbc242` |

The generated plan semantic SHA-256 is
`11e64a5e8b5d1be191a533974725d874f824fe1ca44c7efe64bf4585612d2319`.

## 5. Candidate files

The intended repository slice currently contains:

- `AGENTS.md` — point startup to this successor;
- `changelog.d/1110-architecture-examination-ledger.added.md`;
- `docs/SESSION_HANDOVER_2026-08-24_4.md`;
- controlled-pack `README.md` and `registers/README.md` updates;
- immutable plan, frozen source snapshot, generated JSON/CSV ledger;
- pure deterministic ledger builder;
- fail-closed pack-validator extensions;
- focused adversarial audit-pack tests; and
- regenerated non-self-referential publication manifest.

No finance, scenario, canonical result, VERSION, report template, stochastic
method, grid/QSTS runtime, lender return or F5 file is changed.

## 6. Local verification receipts

All commands used the governed persistent Python 3.12 environment with this
worktree first on `PYTHONPATH` and bytecode disabled.

- ledger builder: PASS, 56 records, 56 pending, zero result hashes, HOLD;
- repository-safe pack validator: PASS/HOLD, 62 manifest entries, 111 findings,
  42 sources, 72 architecture pointers and 34 reproductions;
- exact plan QA: 56 unique IDs; 15 exact batch populations; 51 source
  `not_examined` plus five `deferred`; 86/86 cutoff seam paths exist; 56/56 null
  result hashes; 56/56 HOLD-blocking;
- focused audit-pack tests: 10 passed after adding source-drift and duplicate-key refusal;
- complete `tests/lint`: 331 passed;
- cross-layer GWTF/CASPER/CESSPIT/CCCDIR/provenance/API/report/finance/grid
  slice: 430 passed, one expected skip, two warnings;
- Ruff repository-wide: PASS;
- Black repository-wide: 704 files unchanged;
- isort repository-wide: PASS, four configured skips;
- strict CI library/engine mypy: 255 source files PASS;
- relaxed real-error scripts mypy gate: 63 source files PASS;
- focused strict mypy over the two pack scripts and test: PASS;
- `pip check`: PASS;
- Bandit over the new/changed pack scripts: PASS;
- pinned `pip-audit -r requirements.txt`: no known vulnerabilities;
- changed-file pre-commit: Black, Ruff, isort, large-file, AST, EOF,
  whitespace, conflict, debug and protected-branch controls PASS;
- `git diff --check`: PASS;
- private/full controlled-register validator: structural PASS/release HOLD.

One exploratory blanket `mypy .` invocation is not a valid repository gate: it
stops on the pre-existing duplicate module names `scripts/make_clean_zip.py`
and `legacy_scripts/archive/make_clean_zip.py`. Neither file is touched. The
actual CI commands above pass exactly and are the recorded typing evidence.

Full `make test` is not represented as run locally for this documentation and
control-only slice. `TEST-03` stochastic qualification, `TEST-04` rendered
report qualification and the independent Grid Study are also not represented
as run because no corresponding runtime surface changes. Protected exact-head
CI remains merge authority and may add broader evidence.

## 7. Release and evidence boundary

The correct current posture remains:

- repository-safe pack structural status: PASS;
- private/full pack structural status: PASS;
- architecture examination results: 0 of 56 independently reviewed and
  hash-bound;
- release status: HOLD;
- F5-01: separate current-main reconciliation remains required;
- F5-02: external transaction evidence remains absent;
- wind resource: synthetic/ERA5-derived placeholders are not mast/MCP evidence;
- Board/lender synthesis: do not regenerate until all preceding gates complete;
- issue #1110: OPEN.

## 8. Exact continuation sequence

1. Re-fetch `origin/main`; if it advances, inspect the delta and revalidate the
   pinned cutoff/seam interpretation before commit.
2. Rebuild the architecture descendants and publication manifest; rerun the
   repository-safe validator, focused tests, complete lint tests, formatting,
   typing, changed-file hooks and diff checks.
3. Stage only the intended architecture-ledger slice, inspect cached diff,
   commit, push one topic branch and open one narrow PR linked to #1110.
4. Wait for every required and aggregate check on the exact current head. Merge
   only when the branch is current, CLEAN/MERGEABLE and all required checks pass.
5. Post-merge, verify tree identity/current main, rerun the focused pack gate,
   comment on #1110 with explicit non-closure, then retire the task worktree and
   branch.
6. Continue in a separate dolphin with the 23-row #1110 gate ledger.
7. Then continue, separately, current-main F5-01 reconciliation, the
   #1111-to-current delta ledger, independent FX/Monte Carlo QA, P4 controls and
   versioned method reproductions.
8. Regenerate the Board/lender synthesis last. Only an independent explicit
   `RELEASED` disposition can lift HOLD.
