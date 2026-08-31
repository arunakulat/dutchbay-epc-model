# Session handover — 2026-08-31, successor 22

Durable `PERSIST-01` successor to
[`docs/SESSION_HANDOVER_2026-08-30_2.md`](SESSION_HANDOVER_2026-08-30_2.md) (successor 21).
That predecessor and its chain remain authoritative for Dolphin 0 through Dolphin 3A, the original
D3B-0 recovery, and the earlier protected merge receipts. This record supersedes successor 21's
open-candidate description of D3B-0: PR `#1204` is now independently accepted, squash-merged, and
retired.

This record closes a local governed Mac session that survived a power interruption by recovering
from pushed Git refs and repository review records. It records the completed Dolphin 3B-0
remediation/review chain, protected merge, post-merge synchronization and safe worktree retirement.
It changes no finance result, achieved grade, evidence disposition, professional conclusion,
lender or Board decision, package-release state, deployment authority, issue state, or `HOLD`.

## 1. Bootstrap — run this first

Start the next task from the Codex project `DutchBay_EPC_Model`. Treat the SHA below as a dated
receipt, not a substitute for live reconciliation.

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
cd "$expected_repo"
test "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)" = \
  "$(cd "$expected_repo" && pwd -P)"

export DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
test -x "$DUTCHBAY_VENV/bin/python"
"$DUTCHBAY_VENV/bin/python" -VV

git status --short --branch
git worktree list
gh pr list --state open --limit 100 \
  --json number,title,isDraft,headRefName,headRefOid,mergeStateStatus,url
gh issue view 1110 --json number,state,title,updatedAt,url
```

Stop and reconcile any dirty tree, unfamiliar worktree, unexpected branch owner, or ref movement.
Do not reset, stash, clean, delete, or guess. Only from a clean protected `main` run:

```bash
set -eu
expected_repo=/Users/aruna/Downloads/dutchbay-epc-model
cd "$expected_repo"
test "$(git branch --show-current)" = main
test -z "$(git status --porcelain)"

export DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
git fetch origin --prune
git merge-base --is-ancestor HEAD origin/main
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"

DUTCHBAY_VENV="$DUTCHBAY_VENV" ./check_venv.sh --no-bootstrap
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
git log --oneline -6
```

At this cutoff, the expected synchronized `main` is
`3f83e1448f2c595f899f49925e0d7602231a0ad5`; its tree is
`ac5bd5dccb14ba0f8f13d1ebc8615a7f2788077a`. The governed environment reports Python `3.12.13`,
and the canonical bootstrap reports `73/73` active v3.0 rules. Always prefer the newly fetched live
state if it has advanced coherently.

## 2. Power-interruption recovery

The Mac lost power after Hubble had completed the final domain review of candidate `6d4b788…` and
while Turing was still completing its assurance disposition. The restart lost the live reviewer
tasks but did not lose repository work:

- protected `main` remained clean and synchronized at `9e1c6fa…`;
- the D3B worktree, local branch, upstream branch, live topic ref and PR pull ref all remained clean
  and exact at pushed candidate `6d4b788…`;
- PR `#1204` remained open, draft, mergeable and exact-head CI green;
- the persistent governed Python `3.12.13` environment passed;
- the canonical ruleset reloaded `73/73` active rules; and
- issue `#1110` remained `OPEN`, with `0/23` controls checked and its explicit Board/lender `HOLD`
  unchanged.

The replacement assurance reviewer independently reproduced Turing's unfinished finding before any
writer was allowed to mutate the branch. This was the intended `PERSIST-01` recovery path: mutable
claims were re-queried, exact Git identities were proven, and work resumed from the durable head.

## 3. Why candidate `6d4b788…` did not merge

Hubble issued `DOMAIN ACCEPT` for candidate
`6d4b788f0c37249c75026c6449fde37a08f6dc7f`, tree
`e37d54300673e313ba7618bd162685c13fb29611`. The resumed assurance reviewer issued the controlling
`ASSURANCE VETO` on that same exact candidate.

A strict-Python child implementing `collections.abc.Mapping`, but not an exact built-in `dict`,
could reach the discriminated-union adapter. The adapter called the object's own `get("kind")` or
inherited `get()` to `__getitem__("kind")`. Raising mappings leaked raw `RuntimeError` twice at the
standalone policy root and twice at the containing request root. Stateful mappings produced
different validation receipts across repeated calls. Non-exact discriminator values could also
execute equality, hashing, string or representation behavior before refusal.

This was not a semantic false accept, a finance defect, or a repository security-scan finding. It
was a CASPER bounded-error defect at strict in-process ingress. Green CI did not override the
assurance veto.

Several writer/reviewer turns during the long remediation chain were separately interrupted by the
platform prompt classifier. Those interruptions were orchestration failures, not GitHub security
findings. The repository's exact-head Security Scan and CodeQL jobs were green on the delivered
heads.

The exact historical dispositions, counterexamples, fingerprints and prior veto chain are preserved
in [`DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md`](DOLPHIN_3B_POLICY_ROOT_INDEPENDENT_REVIEW_RECORD.md).
The corrections and local receipts are preserved in
[`DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md`](DOLPHIN_3B_POLICY_ROOT_REMEDIATION_RECORD.md).

## 4. Final bounded correction

One exclusive successor writer produced implementation candidate
`52974fcfa484fa30ac76037ef129a536bb7816be`, tree
`acb1d41ea389cca01de3eef3a9e954092a9a4022`.

The strict-Python child boundary now:

- admits only an exact built-in dictionary after exact-string-key copying, or an exact instance of
  one of the eight trusted compatibility models after declared-field sanitization;
- refuses every other Python child before adapter delegation with one constant-input bounded type
  error and the constant fallback diagnostic key;
- requires sanitized `kind` to be an exact built-in string equal to one of the eight closed tags;
- refuses missing, non-exact or unknown discriminators before adapter delegation with a bounded
  constant-input discriminator error; and
- preserves valid exact-dictionary, exact-model, JSON-wire and authored-order behavior.

Durable controls cover raising `Mapping.get`, inherited `get()` reaching raising `__getitem__`, a
stateful mapping, exact dictionary/model non-exact discriminator values, and missing/unknown tags.
Each controlling object is repeated at both public roots with identical structured/text/JSON
receipts, constant invalid input and zero caller-method ledgers.

## 5. Independent acceptance and exact-head rebind

Two fresh, read-only reviewers independently accepted implementation candidate `52974fc…`:

- `/root/d3b_52974_domain_review`: `DOMAIN ACCEPT`;
- `/root/d3b_52974_assurance_review`: `ASSURANCE ACCEPT`.

The domain review included the hardcoded `9 × 15` jurisdiction oracle at assertion, base, policy
and request roots: `28` admissible accepts and `107` inadmissible refusals per root, `540` decisions
with zero mismatch. It also covered external-route layering, `36` independent negative-root
refusals, six constructive wind/BESS/solar cases, four authored orders, the D3A shared-binding
distinction and the D2 boundary.

The assurance review independently exercised eight invalid object shapes twice at both public roots:
`32` deterministic refusals with stable complete receipts, constant input and zero `get`,
`__getitem__`, iteration, `items`, length, equality, hash, string or representation calls. Its
adapter spy covered `22` invalid ingress cases with zero adapter calls; sanitized exact-dictionary
and exact-model positives delegated exactly once each. Six valid variants preserved all ten
assertions and wire round trips.

Their exact dispositions were appended as Section 19 of the independent-review record in one
documentation-only successor `11ed41a03fb9f8ae88b1052ed88f97b1f9e4a1af`, tree
`ac5bd5dccb14ba0f8f13d1ebc8615a7f2788077a`. Both reviewers then issued
`DOMAIN REBIND ACCEPT` / `ASSURANCE REBIND ACCEPT` on `11ed41a…` after proving that only the review
record changed and every accepted production/test/remediation/changelog byte remained identical.
The rebind receipt is durably attached to PR `#1204` as its final review comment.

## 6. Verification receipts

Local governed receipts on the accepted implementation:

| Gate | Result |
|---|---|
| New mapping/discriminator controls | `2 passed, 301 deselected` |
| Complete D3B-0 contract | `303 passed` |
| Complete `tests/contracts` | `959 passed` |
| D3A predecessor regression | `330 passed` |
| D2 predecessor regression | `298 passed` |
| Import/changelog/cold/gateway-import controls | `35 passed` |
| In-memory contract branch coverage | `94.58%` package; `96.36%` modified module |
| Draft 2020-12, strict/frozen/export/import selection | `8 passed, 295 deselected` |
| Ruff check/format, Black, isort | passed |
| Mypy `--no-incremental` | passed |
| In-memory compile, forbidden-import AST, excluded surface | passed |
| `git diff --check` | passed |

The only local warnings were the inherited Hypothesis `norecursedirs` warning and the inherited
unused mypy configuration-section warning. A first coverage command loaded native dependencies in
the wrong order and stopped before test execution; the corrected in-memory command preloaded them,
passed all `959` tests and left no coverage data file. A first import-group selection omitted one
gateway-import test (`34` selected); the corrected complete selection passed `35`.

Exact-head GitHub CI on final PR head `11ed41a…` completed with every required and non-advisory job
successful: all six test shards, Coverage Gate, Test Summary, Code Quality, Security Scan, CodeQL,
smoke, fastlane, verification receipts, changed-path classification and the audit-review image.
Grid Study, Report Qualification and Stochastic Qualification were correctly skipped by the
fail-closed changed-path classifier because this contract-only delta did not touch their governed
surfaces.

## 7. Protected merge and post-merge proof

PR [`#1204`](https://github.com/arunakulat/dutchbay-epc-model/pull/1204) was promoted from draft only
after both exact-head rebinds and the complete exact-head CI rollup were green. Immediately before
merge:

- PR head was `11ed41a…`, base/live `main` was `9e1c6fa…`;
- the branch was `0` behind and `23` commits ahead;
- the PR was open, ready, `MERGEABLE` and `CLEAN`;
- unresolved GitHub review threads were `0`;
- every required check was successful and the complete rollup had no failed or pending job; and
- issue `#1110` remained `OPEN`, `0/23`, with `HOLD` present.

`MERGE-01` therefore applied. The exact-head guarded squash merge produced protected commit
`3f83e1448f2c595f899f49925e0d7602231a0ad5` at `2026-08-31T03:12:39Z`.

Post-merge proof:

| Control | Result |
|---|---|
| PR state | `MERGED` |
| Merge parent | exact former protected base `9e1c6fa…` |
| Merge tree | `ac5bd5dccb14ba0f8f13d1ebc8615a7f2788077a` |
| Final PR tree | same `ac5bd5dc…` |
| Durable `main` | fast-forwarded, clean and exactly `origin/main` at `3f83e14…` |
| Governed environment/bootstrap | Python `3.12.13`; PASS; `73/73` active |
| Issue `#1110` | `OPEN`; `0/23`; HOLD unchanged |

Merged file fingerprints:

| File | SHA-256 |
|---|---|
| `analytics/feasibility_report_contract/assessment_scope.py` | `707a1e5d22d9b831e65e42d87690e6b951d77cceab172c43c1f7909c3c4e36a6` |
| `tests/contracts/test_assessment_scope_contract.py` | `70220e8bf210da7dd23e383cbe3190073d3cb5936619a9d85ac71a1109cfd4a9` |
| independent-review record | `d93269554f3f0361272fd94372cf4300d66a2b94d04770ffebac013c69b1fc3f` |
| remediation record | `532e28b9810fc2446aa517ef81479ab1c02b4e7c8216110fc22f2aa7d72053f1` |
| changelog fragment | `4696181879e807015b68cc0be9dbbf21f2c6c7afc7b75b6f09c1c43b5b462772` |

The remote topic branch was deleted automatically. The local D3B worktree and local topic branch
were removed only after proving a clean worktree, exact topic/merge tree equality, empty branch-to-
merge diff, merge ancestry and absence of the remote topic branch.

## 8. Delivered scope and explicit deferrals

D3B-0 is now a protected declaration/validation contract for assessment scope, authored-base
compatibility and `EvaluationRequest` ownership. It does **not**:

- inspect a live `ProjectCase` or authored configuration;
- call `analytics.evaluation_v14.evaluate_with_overrides()`;
- rerun or change any finance, KPI, tax, tariff, FX, AEP, debt or lender calculation;
- assemble the D2/D3C twenty-section report package;
- resolve multi-asset allocation when physical assets share one technology binding;
- implement HTTP duplicate-key/body-size/content-type handling, authentication, persistence,
  OpenAPI or transport-error mapping;
- aggregate achieved grade, authorize package release, or move any `#1110` control; or
- lift evidence, professional, lender, Board, deployment or project `HOLD` state.

D3B-1 remains a separate dolphin. It owns live `ProjectCase`/configuration reconciliation,
evidence and valuation cutoff integration, one preflighted call to the canonical
`evaluate_with_overrides()` gateway, and the execution-spy/no-rerun proof. D3C consumes the governed
v14 result from that seam and must not rerun finance. D3C implementation should not begin from a
stale pre-training snapshot; re-ingress this successor, the merged D3B records and live `main`
before handing its writer the lease.

## 9. Worktree and ownership state

At this cutoff:

- protected `main` is clean at `3f83e14…`;
- the D3B implementation worktree/branch is retired;
- the temporary handover worktree/branch exists only to deliver this two-file PERSIST successor and
  should be retired after its own protected green merge; and
- detached worktree
  `/Users/aruna/Downloads/dutchbay-epc-model/.claude/worktrees/update-continue-9a1759` remains at
  `25ebf6804d142df43006f3b95c105fed7c8202b1` and belongs to the other local programmer. It was not
  modified, synchronized, reset or deleted. Reconcile its owner and work before touching it.

## 10. Open items carried forward

1. **D3B-1:** implement only the chartered one-gateway execution seam as a new dolphin after fresh
   current-main ingress and independent oracle planning.
2. **D3C implementation:** re-train the preselected writer on this merged D3B corpus and keep D3C a
   v14-result-to-D2-package consumer. Do not let it call or recompute finance.
3. **D3D:** the orphaned grade/release-policy charter merged in `#1203`; implementation remains a
   separate policy dolphin and may not infer release from calculation or CI success.
4. **Issue `#1110`:** remains `OPEN`, `0/23`, with Board/lender circulation `HOLD`. No D3 merge may
   silently advance it.
5. **Other programmer's detached worktree:** establish ownership/current intent before any action.
6. **Dependabot PRs `#1176` and `#1178`:** remain open and were not changed in this session. Their
   merge state is mutable; re-query and drive each independently under current-main/green rules.

## 11. Unchanged authority

- `VERSION` remains `15.4.0`; the D3B change alters strict contract validation, not committed
  finance behavior.
- D3B engineering acceptance and CI success do not establish evidence sufficiency, achieved grade,
  statutory/professional approval, lender acceptance, Board circulation authority, package release
  or deployment authority.
- Issue `#1110` remains the controlling audit/remediation/release queue. Its immutable historical
  evidence, separate F5-01/F5-02 boundaries and explicit HOLD continue unchanged.
