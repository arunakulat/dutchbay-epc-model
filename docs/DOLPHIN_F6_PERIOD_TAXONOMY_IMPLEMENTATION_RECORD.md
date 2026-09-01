# Dolphin F-6 — implementation record: publish the debt period taxonomy

**Worker:** implementation worker recruited under GWTF `RECRUIT-01` · **Date:** 2026-09-01
**Charter:** `DUTCHBAY_DOLPHIN_F6_F2F3_CHARTER_2026-09-01.md` (§5)
**Base:** `origin/main` @ `3bdfb027bdea12035ea9edcf5fbf343bf68d75cc`
**Branch:** `dolphin/f6-debt-period-taxonomy` · **Worktree:** `.claude/worktrees/agent-a1c04696117f68f14`

This record is work product under `PERSIST-01`. Every command below is quoted with its actual
output; a check that was not run is declared as `not run — <reason>` rather than left silent
(`VERIFY-01`). The worker does **not** self-approve: two independent reviewers bind their
dispositions to the frozen SHAs recorded in §8.

---

## 1. What changed

`finance/debt_v14.py` only. `analytics/contracts_v14.py` was **not** touched — see §3.

### 1.1 New public keys on `plan_debt`

Three keys, appended **after every pre-existing key** so the published mapping's existing 40-key
order survives untouched as a prefix:

| Key | Type | Source |
|---|---|---|
| `construction_periods` | `int` | the count the engine already resolved via `_resolve_construction_periods` inside `apply_debt_layer` |
| `bridge_debt_period` | `int \| None` | the synthetic bridge index; explicit `None` when the timeline has no bridge |
| `first_operating_period` | `int` | earliest debt period mapping to an operating row |

All three are emitted **unconditionally**, on every config path (CASPER). Absent is an explicit
`None`, never a plausible substitute.

### 1.2 `_resolve_first_operating_period` (new private helper)

Takes the row→period map as the **definitional** source and falls back to the timeline layout
(`construction_periods + (1 if a bridge exists else 0)`) only where no operating row exists. The
map and the formula agree on every evaluable committed scenario; the sweep pins that.

### 1.3 CESSPIT single-resolver discipline

The count is **read from the value the engine already resolved**, not re-derived. F-6 exists because
one path defaulted to `2` and another to `0`; adding a third derivation would have reproduced the
defect. `core` is read **after** the balloon treatment, so an `amortize` resize is reflected — that
path rebinds `core` entirely and is pinned by its own test.

### 1.4 Docstring — index-space contract

`plan_debt`'s docstring now states the index space of every published series and carries an explicit
`.. warning::` that `dscr_series` (compacted by `_clean_public_dscr_series`) and `raw_dscr_series`
(positional) are in **incompatible** spaces while `annual_row_debt_period_map[*]["debt_period"]`
indexes the raw one — so `debt_result["dscr_series"][debt_period]` reads a different period than
intended. Documenting that collision is in scope; fixing it is not (that is F-2).

---

## 2. Coordinator receipts — independently reproduced

Every §1 claim in the charter was re-derived from scratch before being relied on.

```
$ $DUTCHBAY_VENV scratchpad/reproduce_receipts.py
=== F-6 ===
internal _resolve_construction_periods(cfg) = 2
published dr.get('construction_periods')    = None
'construction_periods' in dr                = False
published dr.get('construction_years')      = 2
published dr.get('bridge_debt_period')      = None
'bridge_debt_period' in dr                  = False
published dr['cfads_bridge_debt_period']    = 2
'first_operating_period' in dr              = False

=== F-2 ===
len(dscr_series)      = 15
len(raw_dscr_series)  = 23
map[0]                = {'annual_row_index': 0, 'year': 1.0, 'debt_period': 3, 'cfads_usd': 19472460.87312382}
raw[3]               = 2.604704706563112
public[3]            = 1.3

=== F-3 ===
leading Nones in raw  = 2
first mapped period   = 3
offset (first_mapped - leading_Nones) = 1
```

**Verdict: every charter receipt reproduces exactly.** F-2's `raw[3] = 2.6047` vs `public[3] = 1.3`
and F-3's 1-year offset are confirmed as stated.

### 2.1 One refinement to the charter's wording (not a refutation)

The charter says the published dict "returns `None`" for `construction_periods`. Precisely: the
**key is absent**, and the resolved value *is* published — under the different name
`construction_years`. So a consumer today can obtain the construction count, just not under the name
the engine itself uses. The genuinely unobtainable piece is `first_operating_period`, which cannot be
derived without knowing the engine's internal synthetic-bridge convention. The defect and its
remedy are unchanged; only the description is sharpened.

---

## 3. `analytics/contracts_v14.py` — left untouched, deliberately

The charter permits touching it *only if* a typed debt-result contract exists that must carry the
new keys. It does not:

```
$ grep -n "class Debt\|DebtPlan\|DebtResult\|debt_result" analytics/contracts_v14.py
226:class DebtCovenantSnapshot(ContractMixin):
260:    debt_result: dict[str, Any] = field(default_factory=dict)
4398:class DebtTrancheMix(ContractMixin):
```

`debt_result` is an untyped `dict[str, Any]` field on `ScenarioResult`; `DebtCovenantSnapshot` is a
covenant summary, not a debt-result contract. There is nothing to extend, so the file stays out of
the diff. No new import edge from `finance/` into `analytics/` was created (CCCDIR).

---

## 4. Byte-identity sweep

Harness: capture `plan_debt`'s full result for every `scenarios/*.yaml` at full `repr()` precision,
before and after the patch, then compare key set, key **order** and every value.

```
$ $DUTCHBAY_VENV scratchpad/diff_sweep.py
scenarios compared : 21
scenarios skipped  : 8

BYTE-IDENTICAL: every pre-existing key, value and order preserved.
ADDITIVE ONLY : exactly ['bridge_debt_period', 'construction_periods', 'first_operating_period'] added in all scenarios.
```

### 4.1 Charter deviation — 21 evaluable, not 29

The charter asks for a sweep "across all 29 committed scenarios". Only **21** of the 29
`scenarios/*.yaml` files are evaluable whole-scenario configs. The other 8 are not scenarios at all
and cannot produce a `debt_result`:

| File | Why it cannot be evaluated |
|---|---|
| `bad_missing_tax.yaml` | deliberately invalid fixture (missing `corporate_tax_rate`) |
| `contracts_edgecase_base_v14.yaml` | contract edge-case fragment |
| `dscr_sensitivity_example.yaml` | sensitivity parameter file |
| `dutchbay_mc_enhanced_2025Q4.yaml` | Monte-Carlo parameter file |
| `dutchbay_sprint17_enhanced.yaml` | partial enhancement overlay |
| `example_fx_structured_blocks.yaml` | multi-document YAML (`ComposerError`) |
| `kolonnawa_epc_100mw.yaml` | EPC cost fragment, no project life or generation |
| `sensitivity_parameters_examples.yaml` | sensitivity parameter file |

Each fails at `load_scenario_config` or `build_annual_rows` with a schema error, identically before
and after the patch (the harness compares the skip reasons too). The shipped test lists all eight
**explicitly** with a reason each, and a guard asserts the list has not drifted from what is
committed — a blanket `try/except`-skip would have silently absorbed a regression that made a
working scenario stop evaluating.

### 4.2 Taxonomy invariant across the sweep

Every evaluable scenario carries `construction_periods = 2`, a bridge at period 2 and a first mapped
period of 3. The hostile cases the charter requires are therefore **unreachable from committed
configuration** and are covered synthetically (§6).

---

## 5. KPI neutrality

### 5.1 Canon oracle

```
$ $DUTCHBAY_VENV -m pytest -p no:cacheprovider --no-cov -q \
    tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged
1 passed in 1.27s
```

### 5.2 Base-vs-patched, full precision — the decisive receipt

All 39 KPIs captured from `evaluate_with_overrides` on the lender case, at the base engine
(`3bdfb02`) and at the patched engine (`cfeba57`):

```
$ diff scratchpad/kpis_base.json scratchpad/kpis_after.json && echo "..."
ALL 39 KPIs BIT-IDENTICAL base(3bdfb02) vs patched(cfeba57)
```

**No KPI moved.** The change adds dict keys and touches no arithmetic.

### 5.3 Finding: two canon constants are already ~1 ULP off on this machine, at base

Comparing the live pipeline against `tests/_canon.py` by exact `repr` rather than by the oracle's
tolerance:

```
project_irr              expected=-0.001166233356501311   actual=-0.001166233356501311   IDENTICAL
equity_irr               expected=-0.07853839579881439    actual=-0.07853839579881605    *** DIFFERS ***
project_npv              expected=-91810995.06051566      actual=-91810995.06051566      IDENTICAL
min_dscr                 expected=1.3                     actual=1.3                     IDENTICAL
total_cfads_usd          expected=166083177.3168602       actual=166083177.31686017      *** DIFFERS ***
project_npv_prudential   expected=-96435848.53558263      actual=-96435848.53558263      IDENTICAL
```

**This is pre-existing on `origin/main` and is not caused by F-6.** The identical output was produced
with `finance/debt_v14.py` checked out at base `3bdfb02` and the patch entirely absent.

Magnitudes: `equity_irr` differs by 1.67e-15 absolute (2.12e-14 relative, 120 ULP); `total_cfads_usd`
by 2.98e-08 absolute (1.79e-16 relative, **1 ULP**). The oracle asserts with `abs=1e-9` / `rel=1e-9`,
so both are far inside the repo's own definition of "canon unchanged" and the oracle passes.

Consequence for the charter: its acceptance gate of "byte-identical canon … to full precision" is
**stricter than the repository's own oracle** and is not satisfied at the base commit either. The
gate that *is* satisfied, in its strictest possible form, is §5.2: patched output is bit-identical to
base output on every KPI. Re-baselining is out of scope here (`DOC-02`) and no canon constant was
touched. Flagged for the coordinator.

---

## 6. Hostile cases

`tests/finance/test_debt_period_taxonomy.py`. None is reachable from a committed scenario.

| Case | Covered by |
|---|---|
| `construction_periods = 0` | `test_zero_construction_periods_puts_the_bridge_at_period_zero` — bridge lands at 0, `first_operating_period` must be 1 |
| no bridge period | `test_no_bridge_period_yields_none_not_a_substitute_value` — explicit `None`, not 0 |
| first mapped period is 0 | `test_first_mapped_period_zero_is_reported_as_zero` |
| config omits the field | `test_taxonomy_is_published_for_a_config_that_omits_the_field` — resolved default reported, keys still emitted |
| out-of-order map | `test_resolver_takes_the_earliest_mapped_period_not_the_first_listed` |
| malformed map entries | `test_unusable_map_entries_fall_back_to_the_timeline_layout` |
| negative construction count | `test_layout_fallback_matches_the_timeline_construction` |
| `amortize` rebinds `core` | `test_taxonomy_survives_the_amortize_balloon_resize` |

### 6.1 `first_operating_period == 0` is unreachable through `apply_debt_layer`

`_build_cfads_timeline` creates the bridge whenever CFADS is non-empty, and CFADS is derived from
`annual_rows`. So a timeline with operating rows **always** has a bridge, and the earliest mapped
period is at least 1. The charter's "a scenario whose first mapped period is 0" therefore has no
scenario form; it is exercised against the resolver directly. Stated here rather than quietly
substituted.

---

## 7. Negative controls (`VERIFY-01` §5)

A guard never observed to fail is an unverified claim. Each was made to fail before acceptance.

| Control | Mutation | Result |
|---|---|---|
| A | drop the `first_operating_period` key from the return | **26 failed**, 13 passed |
| B | publish `construction_periods + 1` | **25 failed**, 14 passed |
| C | make `_resolve_first_operating_period` ignore the row→period map | see below |
| D | remove the malformed-map-entry guard | **3 failed**, 36 passed (`ValueError` at `debt_v14.py:598`) |

### 7.1 Control C initially did NOT fire — a real defect in the first draft of the test

Under a resolver that ignored the map entirely, the suite still reported **39 passed**. Both
map-driven hostile tests had been parameterised such that the layout fallback coincidentally returned
the same answer (`(row_map, 0, None)` → 0 either way; `(row_map, 4, 4)` → 5 either way). They proved
nothing.

Re-parameterised so the map and the formula **disagree** (`(row_map, 2, 2)` → map says 0, formula
says 3; `(row_map, 0, None)` with periods 7 and 5 → map says 5, formula says 0). Re-run under the
same mutation:

```
FAILED test_first_mapped_period_zero_is_reported_as_zero
FAILED test_resolver_takes_the_earliest_mapped_period_not_the_first_listed
2 failed, 37 passed
```

The engine was restored byte-identically after every control (`git status --porcelain` clean against
the commit each time).

---

## 8. Checks — commands and results

Environment: `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`
(`Python 3.12.13`, `THREAD-01`), worktree first on `PYTHONPATH` (`ENV-01`).

| Check | Command | Result |
|---|---|---|
| GWTF bootstrap | `$DUTCHBAY_VENV dutchbay_bootstrap_rules.py` | `73 rules; versions: v3.0; latest = v3.0`, `active=73` — see §9 |
| CSV digest | `shasum -a 256 go_with_the_flow_rules_v3_0_clean.csv` | `707ee9ba28a48536f3d145931afa87f2a053f234d6268c8cbebd5b385ead79d9` |
| black | `-m black --check finance/debt_v14.py tests/finance/test_debt_period_taxonomy.py` | `2 files would be left unchanged` |
| isort | `-m isort --check-only <both files>` | clean (no output) |
| ruff | `-m ruff check <both files>` | `All checks passed!` |
| mypy | `-m mypy <both files>` | `Success: no issues found` |
| new test | `-m pytest -p no:cacheprovider --no-cov -q tests/finance/test_debt_period_taxonomy.py` | `39 passed` |
| canon oracle | `-m pytest ... test_canonical_lendercase_economics_unchanged` | `1 passed` |
| KPI neutrality | `diff kpis_base.json kpis_after.json` | all 39 bit-identical |
| byte-identity sweep | `scratchpad/diff_sweep.py` | 21 compared, additive only |
| full suite | `-m pytest -p no:cacheprovider -q` | see §8.1 |

### 8.1 Full suite

Recorded in §10 against the final tree. An earlier background run was **discarded**: the engine file
was swapped between base and patched mid-run for the §5.2 capture, so modules imported at different
points could have seen different sources. Declared rather than reported as a pass.

### 8.2 Checks NOT run

- **Pre-commit hooks** — not run; the four tools they wrap (black, isort, ruff, mypy) were run
  directly on both touched files.
- **CI (`Verification receipts (VERIFY-01)`, TEST-05 coverage gate)** — not run; no PR was opened.
  The charter reserves PR creation and merge to the coordinator.
- **Coverage gate** — not run locally; targeted runs used `--no-cov` per the charter's `R8`
  allowance. The full-suite run in §10 carries the project's configured coverage settings.

---

## 9. `RECRUIT-01` and the ruleset count

The charter pins **74 rules**, CSV SHA `cbf2c6a7…`. This worktree's base predates that:

```
$ $DUTCHBAY_VENV dutchbay_bootstrap_rules.py
[rules] 73 rules; versions: v3.0; latest = v3.0
[rules] Status breakdown: active=73
$ gh pr view 1217 --json state,mergedAt,title
{"mergedAt":null,"state":"OPEN","title":"docs(gwtf): add RECRUIT-01 delegation and review policy"}
```

`RECRUIT-01` is still **open** as PR #1217 and is absent from the base CSV. This is expected, not
drift. The rule text was ingressed from the PR diff and followed in full: written capability profile,
sole-writer coordinator, no self-approval, reviewers read-only until the tree is frozen and bound to
exact SHAs, the writer-lease state machine, and the ingress order in which every prior statement is a
claim to verify.

---

## 10. Frozen candidate

| | |
|---|---|
| **Candidate commit** | *(recorded at freeze — see §11)* |
| **Base commit** | `3bdfb027bdea12035ea9edcf5fbf343bf68d75cc` |
| **Base tree** | `aab9ea298244c2ec8809bd1584feff36f3ddcc5f` |
| **Branch** | `dolphin/f6-debt-period-taxonomy` |
| **Worktree** | `/Users/aruna/Downloads/dutchbay-epc-model/.claude/worktrees/agent-a1c04696117f68f14` |

Commits:

1. `826cc5d` — `feat(debt): publish the debt period taxonomy on plan_debt`
2. `cfeba57` — `test(debt): pin the debt period taxonomy and its hostile cases`
3. *(this record + changelog fragment)*

No PR opened, nothing pushed, nothing merged — reserved to the coordinator.

---

## 11. Authority boundary

This dolphin proves only that the checks named above passed. It confers no achieved grade, no
report-grade, and no release, deployment, audit, lender or Board authority, and lifts no `HOLD`
including issue `#1110`. F-2, F-3 and F-1 remain unauthorized. The state after this record is
`WAIT_FOR_REVIEW`.
