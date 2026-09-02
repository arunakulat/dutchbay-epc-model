# Dolphin F-6 — independent ASSURANCE review record

**Reviewer:** assurance reviewer (contract/API + regression), recruited under GWTF `RECRUIT-01`
**Date:** 2026-09-01 · **Role:** strictly read-only · **Lane:** contract compatibility, index-space
correctness, test adequacy, evidence quality. Finance is the domain reviewer's lane and is not judged
here. Reached independently; no coordination with the domain reviewer.

---

# DISPOSITION: **REJECT**

One unresolved **test-adequacy defect**, on a requirement the charter names explicitly. The
implementation is correct on every path I could reach and every contract check passes; the defect is
that a charter-mandated hostile case is **claimed as covered but is not covered at the published
surface**, and two mutations that reintroduce the exact F-6 defect class survive the shipped tests.

Remedy is ~4 assertions in the already-allowlisted test file. **No implementation change is
required.** Details in §7 and §12.

---

## 1. SHA binding (mandatory)

| | |
|---|---|
| **Candidate commit** | `72e49a8318d86682bc9c77c30f90e8d9a424371e` |
| **Candidate tree** | `93d636505a0511d0bf97e83b2ddccbe5d8d56cee` |
| **Base commit** | `6fa3fb506bf4d426c25f4517f8f50a32390e9739` |
| **Branch** | `dolphin/f6-debt-period-taxonomy` |
| **Worktree** | `/Users/aruna/Downloads/dutchbay-epc-model/.claude/worktrees/agent-a1c04696117f68f14` |

Verified at ingress and again at finish. This disposition binds to this exact commit/tree/base and
**transfers to nothing else**. Any further delta requires a fresh review.

**Topology note (not drift).** `HEAD^` is `f781f8539893b00dbe343bd066f33866a5ec8251`, not the declared
base. The declared base is the **fork point**: `git merge-base HEAD origin/main` = `6fa3fb50…` =
`origin/main` head, and `git merge-base --is-ancestor 6fa3fb50… HEAD` returns true. Six commits sit on
the branch above it. Correct as declared.

---

## 2. Ingress (RECRUIT-01 order)

```
$ shasum -a 256 go_with_the_flow_rules_v3_0_clean.csv
cbf2c6a709a1be5e2d7aeab53e5f865984a4263104d884821f83da2dccfd01f3
$ DUTCHBAY_FLOW_RULESET_CSV=$PWD/... $DUTCHBAY_VENV dutchbay_bootstrap_rules.py
[rules] 74 rules; versions: v3.0; latest = v3.0
[rules] Status breakdown: active=74
$ $DUTCHBAY_VENV --version
Python 3.12.13
```

74 rules / `active=74` / digest matches the charter pin. `FRAMEWORK-01/02/03` and `RECRUIT-01` read in
full from the CSV. Charter §3/§5/§10 and the worker's implementation record read in full.

---

## 3. Allowlist compliance — **PASS**

```
$ git diff --stat 6fa3fb50… HEAD
 analytics/feasibility_report_contract/result_facade.py |   9 +
 changelog.d/f6-debt-period-taxonomy.added.md           |  22 +
 docs/DOLPHIN_F6_..._IMPLEMENTATION_RECORD.md           | 553 +
 finance/debt_v14.py                                    | 123 +
 tests/finance/test_debt_period_taxonomy.py             | 415 +
 5 files changed, 1122 insertions(+)
```

Exactly the five leased files. **1122 insertions, 0 deletions**, as claimed.

- `tests/contracts/test_d3c_result_projection_contract.py` — **NOT touched**. Confirmed absent from
  `git diff --name-status`.
- `analytics/contracts_v14.py` — untouched. The worker's §3 justification is sound: `debt_result` is
  an untyped `dict[str, Any]` field, and `DebtCovenantSnapshot` is a covenant summary, not a debt
  result contract. Nothing to extend.
- **Facade edit genuinely confined.** The 9 lines are 3 names + a 6-line comment, inserted inside the
  `*( (("full_result","debt_result",_name), ResultPathDisposition.OPAQUE_ARTIFACT) for _name in (…) )`
  generator, immediately after `"cfads_bridge_debt_period"`. I read lines 668–732 to confirm the
  enclosing disposition really is `OPAQUE_ARTIFACT` and not a neighbouring tuple. It is. No logic, no
  new route, no predicate.

Changelog fragment naming (`f6-…` with no issue-number prefix) matches established practice — 78 of
103 fragments have no numeric prefix, including `recruit-01-…` and `merge-01-…`. Not a defect.

---

## 4. CASPER — contract compatibility — **PASS**

### 4.1 Structural unconditionality

- `plan_debt` has **exactly one** `return` (line 1696). No early return, no alternative exit.
- `apply_debt_layer` has **exactly one** `return` (line 1050); the only other exits are `raise
  ValueError`. Its returned dict always carries `construction_periods` (1060),
  `cfads_bridge_debt_period` (1069), `annual_row_debt_period_map` (1070).
- `core` in `plan_debt` is `apply_debt_layer(...)`, optionally rebound by `_resize_for_amortization`.
  I read that function: **both** its return paths yield an `apply_debt_layer` result, so the three
  source keys survive the `amortize` rebind. The taxonomy is read *after* the rebind, as claimed.

The three keys are therefore emitted on every path that returns at all. **Verified structurally, not
inferred from a green count.**

### 4.2 Additive, no rename / reorder / retype / revalue

Independent base-vs-patched sweep, my own harness, `git archive` exports of both trees into scratchpad
(no repo mutation), full `repr()` precision, comparing **key set, key ORDER and every value**:

```
scenarios compared : 21
scenarios skipped  : 8  (identical skip reasons)
pre-existing keys per scenario: 40
published keys after         : 43

BYTE-IDENTICAL: every pre-existing key, VALUE and ORDER preserved as an exact prefix.
ADDITIVE ONLY : exactly ['construction_periods','bridge_debt_period','first_operating_period']
                appended last, in all 21.
```

The one flagged item — `example_fx_structured_blocks.yaml` "skip reason changed" — is the absolute
**file path** embedded in the `ComposerError` string (scratchpad export path vs worktree path), not a
behavioural difference. Discounted after inspection.

This is a **stronger** check than the shipped test performs (see §7.3) and it passes.

### 4.3 Excluded scenarios justified

All 8 exclusions verified against their actual raised errors: `bad_missing_tax` (missing
`corporate_tax_rate`), `contracts_edgecase_base_v14` (missing `capacity_factor`, null
`tariff_lkr_per_kwh`), `dscr_sensitivity_example`, `dutchbay_mc_enhanced_2025Q4`,
`dutchbay_sprint17_enhanced`, `kolonnawa_epc_100mw`, `sensitivity_parameters_examples` (all fail
config validation), `example_fx_structured_blocks` (`ComposerError`, multi-document YAML). 21 + 8 = 29,
reconciling the charter's "29 committed scenarios". **The 21-vs-29 charter deviation is correctly
explained and correctly documented.**

---

## 5. Index-space documentation — **PASS, every claim verified**

Measured live on `dutchbay_lendercase_2025Q4.yaml`:

| Docstring claim | Measured | Verdict |
|---|---|---|
| `raw_dscr_series` period-indexed, full `timeline_periods` | `len=23`, `timeline_periods=23` | ✅ |
| `debt_service_total` aligned 1:1 with raw | `len=23` | ✅ |
| `interest_total` aligned 1:1 | `len=23` | ✅ |
| `total_service` aligned 1:1 | `len=23` | ✅ |
| `debt_outstanding` aligned 1:1 | `len=23` | ✅ |
| `senior_fee_usd` aligned 1:1 | `len=23` | ✅ |
| `balloon_resolution` aligned 1:1 | `len=23` | ✅ |
| `annual_row_debt_period_map` ROW-indexed | `len=20` = `len(annual_rows)=20` | ✅ |
| `dscr_by_year` keyed by operating YEAR | keys `1.0…20.0`, n=20 | ✅ |
| `dscr_series` compacted, NOT period-indexed | `len=15` ≠ 23 | ✅ |

**No wrong index-space claim.** The `.. warning::` about the `dscr_series`/`raw_dscr_series` collision
is accurate, and the coordinator's F-2 receipt reproduces exactly: `raw[3] = 2.604704706563112`,
`public[3] = 1.3`, first mapped period 3, leading `None`s 2, offset 1.

The timeline layout in `_build_cfads_timeline` confirms the documented shape — `[0.0]*construction_periods`,
then a bridge at index `construction_periods` iff `cfads` is non-empty, then one period per row, then
padding — so `first_operating_period = construction_periods + (1 if bridge else 0)` is the correct
fallback formula.

---

## 6. Route count — **PASS, verified at both ends**

```
base (6fa3fb5 export) len(D3C_RESULT_FIELD_ROUTES) = 23
head (72e49a8 worktree) len(D3C_RESULT_FIELD_ROUTES) = 23
```

Unchanged. The contract test's `len(projection.route_observations) == len(D3C_RESULT_FIELD_ROUTES) == 23`
holds with the test untouched. `OPAQUE_ARTIFACT` was the correct low-blast-radius disposition on that
count alone.

### 6.1 Disposition verified at runtime, not just in source

```
construction_periods       -> ResultPathDisposition.OPAQUE_ARTIFACT
bridge_debt_period         -> ResultPathDisposition.OPAQUE_ARTIFACT
first_operating_period     -> ResultPathDisposition.OPAQUE_ARTIFACT
cfads_bridge_debt_period   -> ResultPathDisposition.OPAQUE_ARTIFACT   (the cited precedent)
construction_years         -> ResultPathDisposition.ROUTE_CANDIDATE
timeline_periods           -> ResultPathDisposition.ROUTE_CANDIDATE
```

The worker's §11.4 description of the disposition landscape is accurate. The asymmetry —
`construction_years` is routed while its restatement `construction_periods` is opaque — is a
deliberate contract judgement the coordinator made in §13.1, and it is defensible: routing the
restatement would carry the same integer twice under two names and would force an edit to the
out-of-allowlist contract test's `== 23` assertion. Consistent, and correctly scoped.

### 6.2 No hidden exhaustive-key contract

`analytics/pipeline_v14_enhanced._validate_debt_result_structure` checks a `required_keys` **subset**
(`min_dscr`, `dscr_series`, `balloon_remaining`), not a whitelist, so additive keys pass cleanly. Repo
grep finds no test pinning `len(debt_result)` or an exhaustive `set(debt_result) ==`. No other
consumer breaks on the three additions.

---

## 7. TEST ADEQUACY — **FAIL** (the rejection ground)

I read `tests/finance/test_debt_period_taxonomy.py` in full, line by line, and then mutated the
implementation independently.

### 7.1 What the tests do well

Assertions **constrain values**, not merely presence/type. The sweep ties each new key to an
independently-published fact and cross-checks two derivations:

```python
assert construction_periods == _resolve_construction_periods(cfg)   # the shared resolver
assert construction_periods == debt_result["construction_years"]    # the legacy key
assert bridge_debt_period   == debt_result["cfads_bridge_debt_period"]
assert first_operating_period == min(mapped)                        # from the map
assert first_operating_period == construction_periods + (0 if bridge_debt_period is None else 1)
```

plus real partition invariants (`bridge_debt_period not in set(mapped)`, `bridge < first_operating`).
`PRE_EXISTING_KEYS` is pinned exactly, so a rename or removal fails. The `NON_EVALUABLE` exclusions are
explicit with per-file reasons and drift-guarded, rather than a blanket `try/except` skip.

**The worker's Control-C disclosure is corroborated.** The record says its first draft had two hostile
tests passing by coincidence and that it re-parameterised until they discriminated. The shipped
parameters show exactly that: `_resolve_first_operating_period(row_map, 2, 2) == 0` (formula would say
3) and `(row_map, 0, None) == 5` (formula would say 0). Both are genuinely discriminating now. This is
honest, and the fix is real.

### 7.2 Independent mutation testing — 10 mutations, done outside the repo

Method: `git archive` both trees into scratchpad, mutate **the scratchpad copy only**, run the shipped
taxonomy suite. The repository was never written to.

| # | Mutation | Result |
|---|---|---|
| M1 | drop `first_operating_period` from the return | 26 failed ✅ |
| M2 | publish `construction_periods + 1` | 24 failed ✅ |
| M3 | resolver ignores the row→period map | 2 failed ✅ |
| M4 | remove the malformed-map guard | 3 failed ✅ |
| M5c | CESSPIT second default (hardcode `2`) | 1 failed ✅ |
| M5d | resolver `max()` instead of `min()` | 28 failed ✅ |
| M5f | drop the bridge term from the fallback formula | 6 failed ✅ |
| **M5a** | **`bridge_debt_period` `None` → plausible `0`** | **39 passed — SURVIVED ❌** |
| **M5b** | **emit the 3 keys only when a bridge exists** | **39 passed — SURVIVED ❌** |
| M5e | move the taxonomy keys to the front of the dict | 39 passed — SURVIVED ⚠️ |

M1–M4 reproduce the worker's declared controls A–D at comparable magnitudes (26/25→24/2/3), so its
negative-control claim checks out.

### 7.3 The defect — the "no bridge" hostile case is not covered at the published surface

**The surviving mutants are not equivalent mutants.** I proved the no-bridge path through `plan_debt`
is reachable and returns a well-formed result:

```
$ plan_debt(annual_rows=[], config=<construction_periods=3>)
plan_debt(annual_rows=[]) SUCCEEDED — no-bridge path IS reachable
  bridge_debt_period      = None
  cfads_bridge_debt_period= None
  construction_periods    = 3
  first_operating_period  = 3
  taxonomy keys present   = True
```

The **implementation is correct here**. The **tests do not constrain it**:

- `test_no_bridge_period_yields_none_not_a_substitute_value` — despite its name — never calls
  `plan_debt`. It calls `_build_cfads_timeline` and `_resolve_first_operating_period` directly and
  asserts about the *timeline builder's* return value, not the published key.
- In the sweep, line 177 is `assert bridge_debt_period is None or isinstance(bridge_debt_period, int)`
  — a disjunction satisfied by any int. Lines 196 and 202 are `if bridge is None` branches that are
  **never taken**, because every evaluable scenario has a bridge.
- Repo-wide grep: no test anywhere asserts `debt_result["bridge_debt_period"] is None`.
  `tests/finance/test_construction_period_resolver.py` does call `apply_debt_layer(config, annual_rows=[])`
  — the no-bridge path — but only against `apply_debt_layer`, and only checks `construction_periods`.

**Whole-suite confirmation.** An in-memory probe over all 4067 `plan_debt` calls the full suite makes
records `bridge_none: 0` (§10.1.1) — the no-bridge branch is exercised **zero** times anywhere in the
repository. This is not a sampling artefact of which test files I mutated.

Consequently the two charter §3.1 CASPER requirements are **unguarded**:

1. *"present unconditionally — never emitted only on some config paths, which is the failure mode
   that produced F-6"* → M5b gates emission on the bridge and all 39 tests pass.
2. *"Absent/undefined must be an explicit `None`, never a plausible substitute value"* → M5a
   substitutes `0` and all 39 tests pass.

This is the exact defect class F-6 exists to eliminate, left undefended on the one path where it can
still occur.

### 7.4 A worker claim that is wrong

Record §6 hostile-case table:

> | no bridge period | `test_no_bridge_period_yields_none_not_a_substitute_value` — explicit `None`, not 0 |

**This overstates the coverage.** The named test does not exercise `plan_debt`, so it cannot show the
published `bridge_debt_period` is `None` rather than a substitute. The record argues unreachability
carefully for `first_operating_period == 0` (§6.1 — and that argument is *correct*, see §8) but makes
no such argument for the no-bridge case; it asserts coverage instead. Under `VERIFY-01` a claimed check
that does not check the claimed thing is not a check.

### 7.5 Secondary observation — order is asserted but not guarded

The record §1.1 and the changelog both claim "the existing 40-key order survives untouched as a
prefix". The **shipped** test pins only the key *set*; M5e (reordering) passes 39/39. Key order and
pre-existing values before/after are proved only by the worker's unshipped `scratchpad/diff_sweep.py`.
I re-proved both independently (§4.2) so the *candidate* is fine — but the property is asserted in
delivered prose with no standing guard. Not a rejection ground on its own; worth a line in the test.

---

## 8. Charter and worker claims checked

| Claim | Source | Verdict |
|---|---|---|
| Full suite `7459 passed, 18 skipped` | worker §13.6 | ✅ reproduced (7428 + 31 split around the segfault) |
| Grid screening file passes standalone (`31 passed`) | worker §8.1 | ✅ reproduced |
| 5 files, 1122 insertions, 0 deletions | brief | ✅ exact |
| Contract test untouched | brief | ✅ |
| Facade edit confined to 3 names in `OPAQUE_ARTIFACT` | brief | ✅ |
| Route count 23 before and after | worker §13.5 | ✅ independently verified both ends |
| D3C `126 passed` | worker §13.6 | ✅ reproduced in the worktree |
| All 39 KPIs bit-identical base vs patched | worker §13.6 | ✅ reproduced exactly — `diff` clean over all 39 keys including the list-valued `dscr_series`. The count of 39 is correct. |
| 21 evaluable / 8 skipped, additive only | worker §4 | ✅ reproduced, and strengthened to order+values |
| `first_operating_period == 0` unreachable via `apply_debt_layer` | worker §6.1 | ✅ **correct** — `cfads` is built 1:1 from `annual_rows` (line 855), so any timeline with rows has a bridge and the earliest mapped period is ≥ 1 |
| Pre-existing canon ULP drift, not caused by F-6 | worker §5.3 / §13.7 | ✅ **correct and honest** — see §9 |
| "no bridge period" hostile case covered | worker §6 | ❌ **WRONG** — see §7.4 |
| Charter §5.3 "byte-identical canon to full precision" | charter | ⚠️ worker is right that this gate is stricter than the repo's own oracle and is unmet **at base**; the meetable form (patched ≡ base) is met |
| Record §13.9 "Five commits" | worker | ⚠️ trivially stale — there are six; the sixth is the record commit itself |

### 9. Canon ULP drift — independently confirmed as pre-existing

| KPI | canon | base `6fa3fb5` | head `72e49a8` |
|---|---|---|---|
| `project_irr` | −0.001166233356501311 | identical | identical |
| `equity_irr` | −0.07853839579881439 | **−0.07853839579881605** (Δ1.67e-15) | same as base |
| `project_npv` | −91810995.06051566 | identical | identical |
| `min_dscr` | 1.3 | identical | identical |
| `total_cfads_usd` | 166083177.3168602 | **166083177.31686017** (Δ2.98e-08) | same as base |
| `project_npv_prudential` | −96435848.53558263 | identical | identical |

`base == head` on all six. Both deviations exist **at the base commit with the patch entirely absent**
and are far inside the oracle's `1e-9` tolerance. **F-6 causes none of it.** The worker's disclosure is
accurate and was the right call to flag.

---

## 10. Evidence quality — flaky native crash is real and under-stated

The worker declared a flaky native fatal in `tests/app/test_grid_screening_emit.py` (212 extension
modules) that "did not recur" and aborted "once in four full runs".

**My first full-suite run hit the same crash**, at the same test, same signature:

```
Fatal Python error: Segmentation fault
Current thread …
  llvmlite/binding/ffi.py … link_modules  (numba JIT)
  analytics/grid/short_circuit.py:124 in _pandapower_fault_level_mva
  app/reports/grid_screening_emit.py:498 in build_grid_screening_model
  tests/app/test_grid_screening_emit.py:97 in test_build_model_runs_core_screens
Extension modules: … (total: 212)
```

Assessment: the crash is **real, environmental, and unrelated to F-6** (pandapower/numba grid
screening; F-6 adds no imports and touches no grid code). The worker's disclosure was correct and
appropriately declared rather than hidden. But **"did not recur" understates its frequency** — it
reproduced on my first attempt. That is an evidence-quality note for the coordinator (it will bite CI),
not a defect in this dolphin.

### 10.1 Full suite — **independently reproduced**

```
$ pytest -p no:cacheprovider --no-cov -q -rf --ignore=tests/app/test_grid_screening_emit.py
7428 passed, 18 skipped, 15 warnings in 461.54s (0:07:41)     exit 0, no failures

$ pytest -p no:cacheprovider --no-cov -q tests/app/test_grid_screening_emit.py
31 passed, 4 warnings in 24.56s                                exit 0
```

**7428 + 31 = 7459 passed, 18 skipped** — exactly the worker's claimed
`7459 passed, 18 skipped`. Reproduced. The split was forced by the segfault in §10, not by any
failure.

Targeted re-runs at HEAD in the real worktree:

```
canon oracle + taxonomy suite                                → 40 passed
tests/contracts/test_d3c_result_projection_contract.py       → 126 passed
```

Both match the worker's §13.6 receipts.

### 10.1.1 Instrumented probe — the conclusive test-adequacy evidence

I wrapped `plan_debt` **in memory** (pytest plugin outside the repo; no repo file written) and ran the
whole suite. Over **4067** `plan_debt` invocations:

```json
{ "calls": 4067, "bridge_none": 0, "keys_missing": 0, "order_violation": 0,
  "construction_zero": 1, "first_op_zero": 0 }
```

Read this carefully — it cuts both ways and settles both questions:

- `keys_missing: 0` and `order_violation: 0` over 4067 calls — the three keys were present, and were
  the **last three keys**, on every single invocation the suite makes. The CASPER unconditional-emission
  property and the order-prefix property **hold empirically and comprehensively**. The implementation
  is sound.
- `first_op_zero: 0` — corroborates the worker's §6.1 unreachability argument.
- `construction_zero: 1` — the `construction_periods == 0` hostile case is genuinely exercised.
- **`bridge_none: 0`** — **the no-bridge path through `plan_debt` is never exercised by any test in the
  entire 7459-test suite.** This is conclusive, whole-suite proof of the §7.3 gap: the branch that
  decides `None`-versus-substitute, on a path I demonstrated is reachable, has **zero** test coverage
  anywhere in the repository. M5a and M5b are unguarded by construction, not by accident of which
  files I sampled.

### 10.2 A methodological warning for the coordinator

My first broadened mutation run appeared to show M5a/M5b/M5e all being caught by
`test_d3c_result_projection_contract.py::test_real_public_gateway_is_an_independent_lossless_oracle`.
**A no-mutation control proved those were false positives** — that test fails *unmutated* inside a
`git archive` export (it depends on something the export does not carry), while passing `126 passed`
in the real worktree. Without the control I would have recorded the opposite conclusion. This is the
same trap the worker's Control C fell into. Any successor doing mutation work on this repo must run an
unmutated control in the same environment.

---

## 11. R10 / TYPE-01 hygiene — **PASS**

Run on all three touched code files (`finance/debt_v14.py`,
`tests/finance/test_debt_period_taxonomy.py`, `analytics/feasibility_report_contract/result_facade.py`):

```
black  → All done! 3 files would be left unchanged.
isort  → exit 0, no output
ruff   → All checks passed!
mypy   → Success: no issues found in 3 source files
```

### 11.1 Checks NOT run (VERIFY-01)

- **CI required checks** (`Verification receipts (VERIFY-01)`, TEST-05 coverage gate) — *not run — no
  PR exists; PR creation is reserved to the coordinator.* `MERGE-01` green cannot be asserted from a
  local review.
- **Coverage gate** — *not run — used `--no-cov` deliberately to avoid writing coverage artefacts into
  the repository while under a read-only mandate.*
- **Pre-commit hooks** — *not run — the four tools they wrap were run directly (§11).*
- **`tests/app/test_grid_screening_emit.py`** — *excluded from my clean full-suite run because it
  segfaults the interpreter (§10).*

---

## 12. What a fresh lease needs

Narrow. **No implementation change.** In `tests/finance/test_debt_period_taxonomy.py` (already on the
allowlist), add a test that goes through the **public** surface on the no-bridge path:

```python
def test_no_bridge_is_published_as_explicit_none_with_keys_still_emitted() -> None:
    debt_result = plan_debt(annual_rows=[], config=_synthetic_config(3))
    assert TAXONOMY_KEYS <= set(debt_result)          # kills M5b (conditional emission)
    assert debt_result["bridge_debt_period"] is None  # kills M5a (plausible substitute)
    assert debt_result["construction_periods"] == 3
    assert debt_result["first_operating_period"] == 3
```

Optionally (§7.5), one line pinning order:
`assert list(debt_result)[-3:] == ["construction_periods","bridge_debt_period","first_operating_period"]`.

Then correct record §6's hostile-case table so the "no bridge period" row names the test that actually
exercises the published surface.

I have verified by direct execution that the implementation **already satisfies** every assertion
above, so this is a test-only re-spin. A fresh candidate SHA will require a fresh disposition.

---

## 13. Mutation attestation (RECRUIT-01, read-only mandate)

I made **no** mutation of any kind to the repository:

- **No file** created, modified or deleted in the repo or any worktree.
- **No** `git add`, `commit`, `checkout`, `stash`, `reset`, `rebase`, `merge`, `push`, `branch`, `tag`.
- **No** index, ref, branch, worktree, remote, issue or PR mutation. No `gh` write commands. No PR
  opened, no comment posted.
- All mutation testing was performed on `git archive` exports inside the session scratchpad
  (`…/scratchpad/f6/{base,head}`); `git archive` is read-only. Instrumentation of `plan_debt` in the
  real worktree was **in-memory only**, via a pytest plugin living outside the repo on `PYTHONPATH`.
- Test runs used `-p no:cacheprovider`, `--no-cov`, `PYTHONDONTWRITEBYTECODE=1` and a scratchpad
  `MYPY_CACHE_DIR` to avoid writing artefacts into the tree.
- The single file I authored is this record, outside the repo, as permitted.

**Tree clean at finish:**

```
$ git status --porcelain
(empty)
$ git rev-parse HEAD        → 72e49a8318d86682bc9c77c30f90e8d9a424371e
$ git rev-parse HEAD^{tree} → 93d636505a0511d0bf97e83b2ddccbe5d8d56cee
```

---

## 14. Authority boundary

This review is an assurance disposition on contract compatibility, index-space correctness, test
adequacy and evidence quality at one exact SHA. It confers no achieved grade, no report-grade, and no
release, deployment, audit, lender or Board authority, and lifts no `HOLD` including issue `#1110`.
The finance judgement is the domain reviewer's and is not made here.
