# Dolphin F-6 — INDEPENDENT DOMAIN REVIEW RECORD

**Reviewer:** independent domain reviewer (renewable project finance / lender covenants), recruited
under GWTF `RECRUIT-01` · **Date:** 2026-09-01 · **Role:** STRICTLY READ-ONLY
**Charter:** `/Users/aruna/Downloads/DUTCHBAY_DOLPHIN_F6_F2F3_CHARTER_2026-09-01.md`

---

## 0. DISPOSITION

# ACCEPT

Bound to the exact candidate below. This disposition transfers to **no other implementation, tree or
base**; any further delta requires a fresh review (`RECRUIT-01`).

| | |
|---|---|
| **Candidate commit** | `72e49a8318d86682bc9c77c30f90e8d9a424371e` |
| **Candidate tree** | `93d636505a0511d0bf97e83b2ddccbe5d8d56cee` |
| **Base commit** | `6fa3fb506bf4d426c25f4517f8f50a32390e9739` |
| **Branch** | `dolphin/f6-debt-period-taxonomy` |
| **Worktree** | `/Users/aruna/Downloads/dutchbay-epc-model/.claude/worktrees/agent-a1c04696117f68f14` |

`ACCEPT` is a **domain (financial-correctness) disposition only**. It confers no achieved grade, no
report-grade, and no release, deployment, audit, lender or Board authority; it lifts no `HOLD`,
including `#1110`. The separate assurance reviewer's disposition is required independently
(`RECRUIT-01`: two reviewers for load-bearing finance-contract code).

**Two non-blocking findings are recorded at §7. Neither is a financial defect; one is a demonstrably
false prose claim shipped in three artifacts, which the coordinator (sole writer) should correct.**

### 0.1 Candidate identity — verified before review

```
$ git rev-parse HEAD
72e49a8318d86682bc9c77c30f90e8d9a424371e
$ git rev-parse HEAD^{tree}
93d636505a0511d0bf97e83b2ddccbe5d8d56cee
$ git merge-base HEAD origin/main
6fa3fb506bf4d426c25f4517f8f50a32390e9739
$ git branch --show-current
dolphin/f6-debt-period-taxonomy
$ git status --porcelain
(empty)
```

No drift. The base `6fa3fb5` is `docs(gwtf): add RECRUIT-01 delegation and review policy (#1217)`,
one commit above the charter-time base `3bdfb02` — consistent with the §13 remediation lease.

### 0.2 Ingress performed (`RECRUIT-01` order)

```
$ DUTCHBAY_FLOW_RULESET_CSV=$PWD/go_with_the_flow_rules_v3_0_clean.csv \
  $DUTCHBAY_VENV dutchbay_bootstrap_rules.py
[rules] 74 rules; versions: v3.0; latest = v3.0
[rules] Status breakdown: active=74
$ shasum -a 256 go_with_the_flow_rules_v3_0_clean.csv
cbf2c6a709a1be5e2d7aeab53e5f865984a4263104d884821f83da2dccfd01f3
```

Matches the charter pin exactly. `FRAMEWORK-01/02/03` (CASPER / CESSPIT / CCCDIR) and `RECRUIT-01`
read in full from the CSV, not from summaries. Charter read in full (§3, §5, §10 in particular).
Worker record `docs/DOLPHIN_F6_PERIOD_TAXONOMY_IMPLEMENTATION_RECORD.md` read in full including §11
and §13. Full delta `git diff 6fa3fb5 HEAD` read. `finance/debt_v14.py` read at
`_resolve_construction_periods`, `_build_cfads_timeline`, `_resolve_first_operating_period`,
`apply_debt_layer`, `_resize_for_amortization`, `_build_funding` and the `plan_debt` return.

---

## 1. Question 1 — are the three keys financially correct?

**YES.** Verified live, not inferred from the record.

### 1.1 The lender case

```
=== TAXONOMY (published) ===
  construction_periods             = 2     present=True
  bridge_debt_period               = 2     present=True
  first_operating_period           = 3     present=True
  construction_years               = 2     present=True
  cfads_bridge_debt_period         = 2     present=True
  timeline_periods                 = 23    present=True

=== raw_dscr_series by period, annotated ===
  p= 0 dscr=None                service=0.00              CONSTRUCTION <FOP(non-op)
  p= 1 dscr=None                service=0.00              CONSTRUCTION <FOP(non-op)
  p= 2 dscr=1.3883208832620155  service=7,012,953.96      BRIDGE <FOP(non-op)
  p= 3 dscr=2.604704706563112   service=7,012,953.96      OP-ROW yr=1.0
  p= 4 dscr=1.3                 service=12,999,488.33     OP-ROW yr=2.0
  ...
  p=17..22 dscr=None            service=0.00              OP-ROW yr=15..20  (post-tenor)
```

`construction_periods = 2` is the count a project-finance practitioner expects: the pre-COD window
that bears no CFADS and no covenant test. `first_operating_period = 3` is the period carrying
operating year 1. `bridge_debt_period = 2` is the synthetic half-year lead-in that bears **real
scheduled service ($7.01M)** but maps to no operating row.

### 1.2 Generalisation beyond the committed configuration — the stronger test

Every committed scenario has `construction_periods == 2`, so the committed sweep alone cannot show
the taxonomy tracks the config. I therefore drove the engine across a construction/interest-only
grid:

```
 cp io | bridge  fop min(map)   tp | bridge==cp? fop==cp+1? fop==min(map)?
  0  0 |      0    1        1   11 |  True  True  True
  0  2 |      0    1        1   11 |  True  True  True
  1  0 |      1    2        2   12 |  True  True  True
  1  2 |      1    2        2   12 |  True  True  True
  2  0 |      2    3        3   13 |  True  True  True
  2  2 |      2    3        3   13 |  True  True  True
  3  0 |      3    4        4   14 |  True  True  True
  3  2 |      3    4        4   14 |  True  True  True
  5  0 |      5    6        6   16 |  True  True  True
  5  2 |      5    6        6   16 |  True  True  True
```

The taxonomy tracks the configured construction window exactly, and is unaffected by
`interest_only_years`. `first_operating_period` is the first period bearing operations in every case.

### 1.3 `bridge_debt_period is None` — correct, and structurally rare

`_build_cfads_timeline` sets the bridge only `if cfads:`, and `apply_debt_layer` line 855 builds
`cfads = [float(a.get("cfads_usd", 0.0)) for a in annual_rows]` — exactly 1:1 with the rows. So a
timeline with **any** operating row always has a bridge; `None` arises only on a row-less timeline.
Verified:

```
  rows=3 cp=0: bridge=0    mapped=[1, 2, 3] timeline=5 -> fop=1
  rows=3 cp=2: bridge=2    mapped=[3, 4, 5] timeline=7 -> fop=3
  rows=0 cp=0: bridge=None mapped=[]        timeline=5 -> fop=0
  rows=0 cp=3: bridge=None mapped=[]        timeline=8 -> fop=3
```

`None` is emitted, never a substitute `0` — CASPER satisfied. The `int | None` type is therefore a
defensive contract for the degenerate case, correct as written.

### 1.4 CASPER — unconditional emission is structural, not conventional

`plan_debt` has exactly **one** `return` statement (line 1749 region; `sed -n '1537,1765p' | grep -n
return` → a single hit). There is no early-exit path that can omit the keys. This is the strongest
form of the charter §3.1 requirement.

---

## 2. Question 2 — covenant semantics, and is the docstring *actually* true?

**YES on both.** I validated every index-space claim in the docstring against the running engine on
all 21 evaluable scenarios, rather than reading the prose:

```
$ $DUTCHBAY_VENV scratchpad/docstring_check.py
scenarios validated: 21
>>> EVERY docstring index-space claim HOLDS on all 21 evaluable scenarios <<<
```

Claims machine-checked per scenario:

| Docstring claim | Result |
|---|---|
| `raw_dscr_series` is period-indexed, full `timeline_periods` length | holds, 21/21 |
| `debt_service_total`, `interest_total`, `total_service`, `debt_outstanding`, `senior_fee_usd`, `balloon_resolution` aligned 1:1 with `raw_dscr_series` | holds, 21/21 |
| `dscr_series` is the compaction of `raw` with `None`/non-finite dropped | holds, 21/21 |
| `annual_row_debt_period_map[*].debt_period` indexes the RAW space | holds, 21/21 |
| `dscr_by_year` is keyed by operating YEAR | holds, 21/21 |
| **every period `< first_operating_period` maps to NO operating row** | holds, 21/21 |
| the compaction (hence the F-2 collision) is still real | holds, 21/21 |

### 2.1 Can a consumer now identify covenant-observable periods? Yes — and it matters

The taxonomy is what makes the bridge period excludable. On the lender case the bridge DSCR is
1.3883 — benign, above the 1.30 target — so the value of the fix is not visible there. It is visible
as soon as the construction/IO shape changes:

```
=== non-operating periods, cp=2 io=2 ===
  p=0 dscr=None               service=              0.00  NON-OP(<fop)
  p=1 dscr=None               service=              0.00  NON-OP(<fop)
  p=2 dscr=0.953907203907204  service=      6,289,920.00  NON-OP(<fop)
  p=3 dscr=1.907814407814408  service=      6,289,920.00   MAPPED
  p=4 dscr=1.3               service=      9,230,769.23   MAPPED
```

A **sub-1.0 DSCR at a period that carries no covenant observation.** Before this dolphin a consumer
holding `debt_result` had no published name for the boundary that excludes it; now
`first_operating_period` states it. That is a real lender-facing correctness gain, and it is the
substantive justification for the change.

### 2.2 Residual hazard — disclosed, not misstated (no finding)

`raw_dscr_series[first_operating_period] = 2.6047` on the lender case, whereas the covenant year-1
figure is `dscr_by_year[1.0] = 1.3024`: half of year 1's service sits at the bridge period. A
consumer who reads `first_operating_period` as "index me the year-1 covenant DSCR" would **overstate
year-1 coverage by roughly 2x**.

The docstring does disclose this — the `bridge_debt_period` bullet states its service "is folded into
operating year 1 by `dscr_by_year` and by the pipeline's row enrichment", and the `.. warning::`
directs per-year reads to `dscr_by_year`. Both statements are accurate. I record the hazard so it is
not lost, and recommend F-3 make the year-1 fold explicit at the point of use — but there is nothing
false here and it is **not** a defect in this dolphin.

---

## 3. Question 3 — CESSPIT: one resolver, one answer

**PASS.** The published count is the count the timeline was *built with*, not a re-derivation.

- `finance/debt_v14.py:763` — `construction_periods = _resolve_construction_periods(params)` inside
  `apply_debt_layer`.
- `:861` — that same variable is passed to `_build_cfads_timeline`, so it defines the actual layout.
- `:1060` — `"construction_periods": construction_periods` published on `core`.
- `:1665` — `plan_debt` reads `core.get("construction_periods", ...)`, i.e. the engine's own answer.

`core` in `plan_debt` has exactly two provenances, and both are `apply_debt_layer` output:
`core = apply_debt_layer(...)` (`:1598`) and `_resize_for_amortization(...)`, whose final statement is
`return resized_cfg, apply_debt_layer(params=resized_cfg, annual_rows=rows)`. **No second divergent
default survives on any live path.** The shipped sweep asserts this directly per scenario
(`assert construction_periods == _resolve_construction_periods(cfg)`), and my independent sweep
reproduced it with zero flags across 21 scenarios.

**Observation (not a defect).** The new read is written `int(core.get("construction_periods", 0) or 0)`
— a literal `0` default that can never fire, mirroring the pre-existing idiom at `:1625` and
`_build_funding` `:1449`. Strict CESSPIT would prefer `core["construction_periods"]` so a future path
that forgot to populate `core` fails loud rather than silently publishing a construction window of
zero. Latent only; no live path reaches it. Not blocking.

---

## 4. Question 4 — is the `OPAQUE_ARTIFACT` disposition financially right?

**The disposition is correct. The comment justifying it is imprecise for one of the three keys.**

Verified facade state:

```
len(D3C_RESULT_FIELD_ROUTES) = 23          # unchanged by the fix (worker §13.5 confirmed)

Routes touching debt_result (all 13):
   principal_by_tranche{lkr,usd,dfi} | FINITE
   total_idc                         | FINITE
   avg_debt_rate                     | POSITIVE_DEBT_FINITE
   balloon_remaining                 | FINITE
   balloon_pct                       | BALLOON_BASIS_PRESENT
   construction_years                | EXACT_INTEGER
   tenor_years                       | EXACT_INTEGER
   timeline_periods                  | EXACT_INTEGER
   fx_min / fx_max / fx_avg          | PROJECT_CONTEXT_REQUIRED
```

- `bridge_debt_period` restates `cfads_bridge_debt_period`, already `OPAQUE_ARTIFACT`. Verified equal
  on 21/21 scenarios. Matching its sibling's disposition is right.
- `construction_periods` restates `construction_years`, which **is** routed (`EXACT_INTEGER`).
  Verified equal on 21/21. Routing it again would carry the same integer twice under two names, so
  `OPAQUE_ARTIFACT` is the correct call and no fact is lost — the facade still routes the number.
- `first_operating_period` is the one the worker's stated reason does not cover: it restates no
  routed key. **The correct financial argument — which the comment does not make — is that the facade
  routes no period-indexed series at all** (no `dscr_series`, no `raw_dscr_series`, no
  `annual_row_debt_period_map`; all four are `OPAQUE_ARTIFACT`). A period index routed into a report
  that carries none of the series it indexes would be **inert**. `OPAQUE_ARTIFACT` is therefore right
  for the correct reason.

**Conclusion: nothing here needs routing today.** When F-2/F-3 unifies the DSCR surface and any
period-indexed series becomes routable, `first_operating_period` should be re-examined as a
`ROUTE_CANDIDATE` at that time, because it is then the key that tells the report which rows may carry
a covenant observation. I recommend the coordinator record that as a follow-on, not a blocker.

**Contract-safety of the additive change, checked repo-wide.** `_validate_debt_result_structure`
(`analytics/pipeline_v14_enhanced.py:188`) uses a *subset* test
(`required_keys - set(debt_result.keys())`), not an exhaustive one. A repo-wide grep for exhaustive
key-set consumers found only subset checks and diagnostics:

```
tests/api/test_v14_lender_suite.py:150            f"Available keys: {list(debt_result.keys())}. "
tests/api/test_run_full_pipeline_v14_lender_stack.py:161  missing_keys = required_keys - set(...)
analytics/pipeline_v14_enhanced.py:188            missing_keys = required_keys - set(...)
analytics/pipeline_v14_enhanced.py:205            len(debt_result),
```

The D3C facade was genuinely the **only** exhaustive gate in the repository — corroborating the §11
blocker narrative — and it has been cleared correctly.

---

## 5. Question 5 — KPI neutrality, verified independently

I did **not** take the worker's receipt or a pass count as proof. I materialised the base tree
read-only (`git archive 6fa3fb5 | tar -x` into scratchpad, repo untouched) and compared engines.

### 5.1 All 39 KPIs, base vs the CANDIDATE HEAD

```
$ diff kpis_base.json kpis_cand.json
>>> ALL 39 KPIs BIT-IDENTICAL base(6fa3fb5) vs candidate(72e49a8) <<<
```

This is stronger than the worker's own receipt, which bound to `f781f85`. I confirmed the final
commit `72e49a8` is documentation-only (`1 file changed, 102 insertions(+)`, the record), so the
worker's binding was sound — but mine is taken at the exact reviewed head.

### 5.2 Independent byte-identity sweep of the whole `plan_debt` surface

Full result captured at exact `repr()` precision, key **order** included, in both trees:

```
scenarios evaluated : 21
scenarios skipped   : 8 (identical skip reason before and after)
>>> BYTE-IDENTICAL: every pre-existing key, VALUE and ORDER preserved on every scenario <<<
>>> ADDITIVE ONLY : exactly ['construction_periods','bridge_debt_period','first_operating_period']
                    appended, in that order, everywhere <<<
```

### 5.3 The 40-key prefix claim, verified against the base engine

```
BASE published keys: 40      candidate: 43
candidate[:40] == base (exact ORDER)? True
added exactly: ['construction_periods', 'bridge_debt_period', 'first_operating_period']
```

The changelog's "existing 40-key mapping survives untouched as a prefix" is exactly true.

### 5.4 The canon oracle — I read the test, not the pass count

`tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged` asserts
**eight** constants imported from `tests/_canon.py` — `project_irr`, `equity_irr`, `project_npv`,
`min_dscr`, `min_dscr_period`, `total_cfads_usd`, `project_npv_prudential`, `prudential_rate_used` —
each via `pytest.approx` at `abs=1e-9` or `rel=1e-9`, plus the ordering assertion
`project_npv_prudential < project_npv`. It is a **tolerance** oracle, not a byte oracle. It genuinely
covers the KPI vector the charter names.

---

## 6. Question 6 — the three charter corrections, each verified independently

### 6.1 "21 evaluable scenarios, not 29" — **CORRECT**

29 files are committed under `scenarios/`; my own evaluation loop reproduces the split exactly, and
every one of the eight exclusions fails at config validation with a real error, not silently:

```
EVALUABLE: 21   NON-EVALUABLE: 8

  bad_missing_tax.yaml                  ValueError: corporate_tax_rate: missing (required)
  contracts_edgecase_base_v14.yaml      ValueError: capacity_factor: missing (required)
  dscr_sensitivity_example.yaml         ValueError: corporate_tax_rate: missing (required)
  dutchbay_mc_enhanced_2025Q4.yaml      ValueError: corporate_tax_rate: missing (required)
  dutchbay_sprint17_enhanced.yaml       ValueError: corporate_tax_rate: missing (required)
  example_fx_structured_blocks.yaml     ComposerError: expected a single document in the stream
  kolonnawa_epc_100mw.yaml              ValueError: corporate_tax_rate: missing (required)
  sensitivity_parameters_examples.yaml  ValueError: corporate_tax_rate: missing (required)
```

The eight names match the worker's list exactly. The charter's "29" counted files, not evaluable
scenarios; the correction is right and the shipped test guards the exclusion list against drift
rather than swallowing failures in a bare `except`.

Also confirmed: all 21 carry `construction_periods = 2`, bridge at 2, first mapped period 3 — so the
charter's hostile cases genuinely are unreachable from committed configuration, exactly as claimed.

### 6.2 "Pre-existing canon ULP drift at base" — **CORRECT, and it is a property of `main`**

Measured **at the base tree with the patch entirely absent**:

```
project_irr            canon=-0.001166233356501311  base=-0.001166233356501311  IDENTICAL
equity_irr             canon=-0.07853839579881439   base=-0.07853839579881605   *** DIFFERS ***
project_npv            canon=-91810995.06051566     base=-91810995.06051566     IDENTICAL
min_dscr               canon=1.3                    base=1.3                    IDENTICAL
total_cfads_usd        canon=166083177.3168602      base=166083177.31686017     *** DIFFERS ***
project_npv_prudential canon=-96435848.53558263     base=-96435848.53558263     IDENTICAL
prudential_rate_used   canon=0.11285835226329409    base=0.11285835226329409    IDENTICAL
min_dscr_period        canon=1.3                    base=1.3                    IDENTICAL

equity_irr       abs=1.6653e-15  ulp=1.3878e-17  ULPs=120.0  rel=2.120e-14  abs tol 1e-09 -> inside
total_cfads_usd  abs=2.9802e-08  ulp=2.9802e-08  ULPs=1.0    rel=1.794e-16  rel tol 1e-09 -> inside
```

The worker's "120 ULP" and "1 ULP" figures are exactly right. **This is NOT introduced by the patch** —
it is present on `origin/main` at `6fa3fb5`. Both deviations are ~5–6 orders of magnitude inside the
oracle's own `1e-9` tolerance, so the repository's definition of "canon unchanged" is satisfied.

The worker's consequential point is also correct and worth the coordinator's attention: the charter's
§5.3 gate — "every KPI in `tests/_canon.py` unchanged **to full precision**" — is stricter than the
repository's oracle and is **not satisfied at the base commit either**. The gate that *is* satisfied,
in its strictest possible form, is base-vs-patched bit-identity (§5.1–5.2 above). No canon constant
was touched, so `DOC-02` is not engaged.

### 6.3 "`first_operating_period == 0` is unreachable" — **CORRECT as stated**

The precise claim is that the first *mapped* period is never 0 through `apply_debt_layer`. Verified
structurally and empirically: `cfads` is 1:1 with `annual_rows` (`:855`), so any timeline with an
operating row has a bridge, and `min(mapped) = construction_periods + 1 >= 1`. My grid (§1.2) shows
`fop == 1` at `cp = 0`, never 0.

`first_operating_period == 0` arises **only** from the layout fallback on a timeline with zero
operating rows and `construction_periods == 0` (`rows=0 cp=0 -> fop=0`, §1.3). The worker states this
rather than quietly substituting a reachable case, and covers 0 against the resolver directly. The
shipped tests are genuinely discriminating on this point — `_resolve_first_operating_period(row_map,
2, 2) == 0` (map says 0, layout formula says 3) and `(row_map, 0, None) == 5` (map says 5, formula
says 0) would both fail a resolver that ignored the map. The worker's §7.1 "Control C did not fire"
narrative describes a real defect in its own first draft and a real fix; I confirmed the corrected
parameters do disagree.

---

## 7. FINDINGS — claims I found to be wrong

### 7.1 FINDING 1 (non-blocking, prose): "not derivable at all" is **FALSE**, and it ships

Three artifacts on this branch claim `first_operating_period` was previously underivable:

- `changelog.d/f6-debt-period-taxonomy.added.md:5` — "the first operating period was not derivable at
  all without knowing the engine's internal synthetic-bridge convention"
- `tests/finance/test_debt_period_taxonomy.py:8` — "``first_operating_period`` was not derivable at
  all"
- `docs/DOLPHIN_F6_PERIOD_TAXONOMY_IMPLEMENTATION_RECORD.md:93` — "The genuinely unobtainable piece is
  `first_operating_period`, which cannot be derived without knowing the engine's internal
  synthetic-bridge convention."

**Disproved on the base engine itself**, where the taxonomy does not exist:

```
engine has taxonomy keys?  {'construction_periods': False, 'bridge_debt_period': False,
                            'first_operating_period': False}
annual_row_debt_period_map is published on the BASE surface: True
min(map[*].debt_period) on the BASE engine = 3
  -> equals the value F-6 publishes as first_operating_period (3)? True
  -> required knowledge of the synthetic-bridge convention? NO — it is min() of a published column
```

`annual_row_debt_period_map` was already public, so `first_operating_period` was derivable in one
line, with no knowledge of the bridge. The implementation itself proves this: `_resolve_first_operating_period`
treats the row map as "the DEFINITIONAL source" and returns `min(mapped)`; the bridge convention is
needed only for the empty-map fallback.

The claim also **contradicts the branch's own facade comment** ("the taxonomy carries no fact this
facade does not already see"), which is the accurate one of the two.

**Why this does not change my disposition.** The defect being remediated is real and the remedy is
correct — the boundary was *unnamed*, not unobtainable, and a consumer had to know that "the minimum
of the `debt_period` column" is the operating boundary and that the periods below it include a bridge
carrying real service (§2.1 shows that bridge can sit below 1.0 DSCR). Naming it is a genuine CASPER
improvement. Only the *justification* is overstated. Nothing numeric, contractual or behavioural
depends on it.

**Recommendation to the coordinator (sole writer):** correct the changelog fragment and the test
module docstring to say the boundary was *unnamed* — derivable only as `min()` over the row map's
`debt_period` column, with the non-operating periods below it unmarked — rather than "not derivable
at all". The shipped changelog is the artifact that matters; it enters `CHANGELOG.md`. My disposition
is `ACCEPT` either way.

### 7.2 FINDING 2 (non-blocking, prose): the facade comment's reason does not cover all three keys

`analytics/feasibility_report_contract/result_facade.py` justifies the disposition by noting that
`bridge_debt_period` and `construction_periods` restate existing keys, then concludes "the taxonomy
carries no fact this facade does not already see." That reasoning covers two keys of three;
`first_operating_period` restates no routed key. As set out at §4, the disposition is nonetheless
correct, for the stronger reason that the facade routes no period-indexed series, so a period index
would be inert. Suggest the comment say so. No behavioural consequence.

---

## 8. Forward intelligence for the F-2/F-3 lease (offered, not part of this disposition)

Charter §6.2 requires proof, before F-2/F-3 is declared KPI-neutral, that restricting `min_dscr` to
operating periods does not move it. I generated that evidence as a by-product:

```
scenario                                    min_dscr   bridge op-only min  verdict
ceb_bess_10mw_capacity_charge.yaml            0.9069   1.4998      1.3000  period-min unchanged
ceb_solar_bess_nightpeak_10mw.yaml            0.8724   1.3262      1.3000  period-min unchanged
dutchbay_basecase_2025Q4.yaml                 0.6098   0.9446      0.6098  period-min unchanged
dutchbay_lendercase_2025Q4.yaml               1.3000   1.3883      1.3000  period-min unchanged
dutchbay_pessimistic_2025Q4.yaml              0.4101   0.7875      0.4101  period-min unchanged
edge_extreme_stress.yaml                      0.5571   0.6875      0.5571  period-min unchanged
... (21 scenarios)

scenarios where restricting the PERIOD series to operating periods moves the period-min: 0
```

**On all 21 evaluable scenarios the bridge DSCR is strictly above the operating-period minimum**, so
excluding non-operating periods from the *period* series moves the period-min nowhere. That
de-risks F-2/F-3 materially, and confirms the charter's lender-case reasoning generalises.

**But a warning, which is the more important half.** On several scenarios the headline `min_dscr`
(e.g. `ceb_bess` 0.9069) sits far **below** the operating-period minimum (1.3000). That gap is not
the bridge period in the raw series — it is the **year-1 fold** in `dscr_by_year`, where the bridge's
real service is folded into operating year 1 and `plan_debt` takes `min(raw_min, by_year_min)`. The
fold is economically correct: year 1's total debt service genuinely includes the bridge's cash. If
F-2/F-3 "restricts `min_dscr` to operating periods" in a way that discards the fold, it will **raise**
the reported coverage on those scenarios and overstate lender protection — a canon move in the
flattering direction, which is exactly the kind the owner's standing constraints guard against. F-2/F-3
must preserve the fold while fixing the index space. This is a caution, not a finding against F-6.

---

## 9. Checks run — commands and results (`VERIFY-01`)

Environment: `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python` (3.12.13,
`THREAD-01`), worktree first on `PYTHONPATH` (`ENV-01`),
`DUTCHBAY_FLOW_RULESET_CSV=$PWD/go_with_the_flow_rules_v3_0_clean.csv`.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Candidate identity | `git rev-parse HEAD` / `HEAD^{tree}` / `merge-base` / `status` | `72e49a8` / `93d6365` / `6fa3fb5` / clean — **no drift** |
| 2 | GWTF ruleset | `dutchbay_bootstrap_rules.py` | `74 rules; latest = v3.0`, `active=74` |
| 3 | CSV digest | `shasum -a 256 go_with_the_flow_rules_v3_0_clean.csv` | `cbf2c6a7…d01f3` — matches charter pin |
| 4 | Taxonomy on lender case | live `run_v14_pipeline` | `cp=2, bridge=2, fop=3`; series all 23 |
| 5 | Construction/IO grid | synthetic `plan_debt`, cp∈{0,1,2,3,5} × io∈{0,2} | `bridge==cp`, `fop==cp+1`, `fop==min(map)` — 10/10 |
| 6 | Docstring index-space claims | `docstring_check.py` | **21/21 scenarios, every claim holds** |
| 7 | Scenario evaluability | independent evaluation loop | 21 evaluable / 8 non-evaluable, names match |
| 8 | CESSPIT single resolver | source trace `:763 → :861 → :1060 → :1665` + `_resize_for_amortization` | one resolver; no live divergent default |
| 9 | Additive-only sweep | base-vs-candidate full `repr` capture, order included | **byte-identical 21/21, exactly 3 keys appended** |
| 10 | 40-key prefix | base vs candidate key list | `candidate[:40] == base` exact order — True |
| 11 | KPI bit-identity | `diff kpis_base.json kpis_cand.json` | **all 39 bit-identical, base `6fa3fb5` vs head `72e49a8`** |
| 12 | Canon vs live at BASE | exact `repr` comparison, patch absent | `equity_irr` 120 ULP, `total_cfads_usd` 1 ULP — **pre-existing on `main`** |
| 13 | Canon oracle | `pytest …::test_canonical_lendercase_economics_unchanged` | passed (within the 166 below); test body read, asserts 8 constants at 1e-9 |
| 14 | Taxonomy + oracle + D3C contract | `pytest -q --no-cov tests/finance/test_debt_period_taxonomy.py … tests/contracts/test_d3c_result_projection_contract.py` | **`166 passed`** |
| 15 | Facade routes | live `len(D3C_RESULT_FIELD_ROUTES)` | `23` — unchanged, worker §13.5 confirmed |
| 16 | Exhaustive key-set consumers | repo-wide grep | only subset checks; D3C facade was the sole gate |
| 17 | black | `-m black --check` on the 3 touched code files | `3 files would be left unchanged` |
| 18 | isort | `-m isort --check-only` on the same 3 | clean (no output) |
| 19 | ruff | `-m ruff check` on the same 3 | `All checks passed!` |
| 20 | mypy | `-m mypy` on the same 3 | `Success: no issues found in 3 source files` |
| 21 | Derivability disproof | base-engine `min(map[*].debt_period)` | `3` — equals `first_operating_period`; **claim in §7.1 disproved** |
| 22 | F-2/F-3 forward risk | operating-only period-min across 21 scenarios | 0 scenarios move; fold caveat at §8 |
| 23 | Full suite (attempt 1) | `pytest -p no:cacheprovider -q -rf` | **ABORTED — native segfault, see §9.1** |
| 24 | Full suite (attempt 2, minus flaky file) | `pytest -p no:cacheprovider -q -rf --ignore=tests/app/test_grid_screening_emit.py` | **`7428 passed, 18 skipped, 15 warnings in 473.30s`**, `0` FAILED lines |
| 25 | Flaky file standalone | `pytest -q --no-cov tests/app/test_grid_screening_emit.py` | **`31 passed, 4 warnings in 25.45s`** |

**7428 + 31 = 7459 passed, 18 skipped — reproducing the worker's §13.6 full-suite figure
(`7459 passed, 18 skipped`) exactly, on the candidate head, independently.** With coverage enabled
(no `--no-cov`), so the project's configured coverage settings applied.

### 9.1 The full-suite segfault — independently reproduced, and unrelated to this change

My first full-suite run aborted at 29% with a native fatal error, at exactly the site the worker
disclosed in §8.1:

```
Fatal Python error: Segmentation fault
Current thread (most recent call first):
  llvmlite/binding/ffi.py, line 212 in __call__
  llvmlite/binding/linker.py, line 7 in link_modules
  numba/core/codegen.py, line 746 in add_llvm_module
  numba/core/cpu.py, line 235 in create_cpython_wrapper
  ...
  analytics/grid/reactive_screen.py, line 300 in _poc_pf_and_voltage
  app/reports/grid_screening_emit.py, line 498 in build_grid_screening_model
  tests/app/test_grid_screening_emit.py, line 97 in test_build_model_runs_core_screens
Extension modules: … (total: 212)
```

The crash is inside **numba's LLVM JIT codegen**, reached through the pandapower grid-screening path.
It touches nothing in `finance/debt_v14.py`, and this dolphin adds no imports. `0` pytest `FAILED`
lines were emitted before the abort. This **independently corroborates** the worker's §8.1 / §13.8
disclosure of a flaky native-extension crash in this environment, and I record it as such rather than
reporting a clean pass I did not obtain.

I then obtained the honest receipt in two parts (checks 24–25): the suite with that one file excluded
(`7428 passed, 18 skipped`, zero failures) and that file on its own (`31 passed`) — **7459 passed, 18
skipped in total, which is exactly the figure the worker reported at §13.6.** Nothing in the suite
fails on this candidate; the only obstacle is an environment-level JIT crash that is order-dependent
and unrelated to the diff. The worker's characterisation ("aborted once in four full runs") matches
my own experience (once in two).

### 9.2 Checks NOT run — declared (`VERIFY-01`)

- **CI required checks** — `Verification receipts (VERIFY-01)`, TEST-05 coverage gate: **not run — no
  PR exists for this branch and PR creation is reserved to the coordinator.** `MERGE-01` green is
  therefore not yet established; that is a delivery gate, separate from this disposition.
- **Pre-commit hooks as a bundle** — **not run — the four tools they wrap (black, isort, ruff, mypy)
  were run directly on all three touched code files (checks 17–20).**
- **Coverage gate locally** — **not run in the targeted runs (`--no-cov`, permitted by charter §8 /
  `R8`); the full-suite runs at checks 23–24 carry the project's configured coverage settings.**
- **Negative-control mutation testing** — **not run by me: it requires mutating the engine, which my
  read-only lease forbids.** I verified the worker's controls indirectly by reading the test bodies
  and confirming the discriminating parameters genuinely make the row map and the layout formula
  disagree (§6.3), so a resolver ignoring the map cannot pass.
- **`analytics/contracts_v14.py`** — not examined for new typed contracts beyond confirming the
  worker's grep result; there is no typed debt-result contract to extend, so the file is correctly
  absent from the diff (CCCDIR: no new `finance/` → `analytics/` import edge was introduced).

---

## 10. MUTATION ATTESTATION

I made **no** mutation of any kind. Specifically:

- **No file** in the repository was created, modified or deleted.
- **No index, ref, branch, tag, worktree, stash or remote** was changed. No `git add`, `commit`,
  `checkout`, `stash`, `reset`, `rebase`, `merge`, `push`, `worktree add`.
- **No issue or PR** was created, edited, commented on, labelled, closed or merged. No `gh` write
  command was run.
- All scratch artifacts — including a read-only `git archive` extraction of the base tree used for
  the base-vs-candidate comparisons — were written **outside** the repository, under the session
  scratchpad. `git archive` reads the object database and does not touch the working tree or index.
- This review record is the single file I wrote, at `/Users/aruna/Downloads/`, outside the repo.

Final state, verified at the end of the review:

```
$ git rev-parse HEAD
72e49a8318d86682bc9c77c30f90e8d9a424371e
$ git rev-parse HEAD^{tree}
93d636505a0511d0bf97e83b2ddccbe5d8d56cee
$ git status --porcelain
(empty)
$ git status --porcelain --untracked-files=all
(empty)
$ git branch --show-current
dolphin/f6-debt-period-taxonomy
$ git stash list
(empty)
$ git worktree list
/Users/aruna/Downloads/dutchbay-epc-model                                            3bdfb02 [main]
…/worktrees/agent-a1c04696117f68f14                                                  72e49a8 [dolphin/f6-debt-period-taxonomy]
…/worktrees/dutchbay-epc-evaluation-18b468                                           6fa3fb5 [claude/dutchbay-epc-evaluation-18b468]
```

**The candidate tree was clean when I finished, at the same commit and tree I bound to.**

---

## 10.1 Handover point — this record must be transferred into `docs/` by the coordinator

`RECRUIT-01` states plainly: *"Review records and dispositions are WORK PRODUCT: write them to
`docs/` the moment they land (`PERSIST-01`) — a review chain that lives only in a session's context is
lost, and the pass must be redone."* The rule's memory entry records that a D3B review chain was in
fact lost this way and had to be redone.

As a strictly read-only reviewer I **cannot** write into the repository, and my lease confines me to
this one file outside it. **The coordinator (sole writer) must copy this record into `docs/` before
merge**, alongside the assurance reviewer's, so the two-reviewer chain `RECRUIT-01` requires for
load-bearing finance-contract code is durable rather than session-local. Flagging it rather than
acting on it is the correct behaviour under the lease, but it is a real outstanding step, not a
formality.

---

## 11. Authority boundary

This record is a domain review under `RECRUIT-01`. It is `ACCEPT` on financial correctness for the
exact commit `72e49a8318d86682bc9c77c30f90e8d9a424371e` / tree
`93d636505a0511d0bf97e83b2ddccbe5d8d56cee` / base `6fa3fb506bf4d426c25f4517f8f50a32390e9739` and
nothing else. It confers no achieved grade, no report-grade, and no release, deployment, audit,
lender or Board authority, and lifts no `HOLD` including `#1110`. It does not authorise a merge:
`MERGE-01` requires every REQUIRED check green on the exact head, and no PR has yet been opened. The
independent assurance reviewer's disposition is required separately before merge.
