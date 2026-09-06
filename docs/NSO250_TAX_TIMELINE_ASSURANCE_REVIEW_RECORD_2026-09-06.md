# NSO 250MW BESS tax layer and RFP timeline — contract / assurance review record

**Record status:** blocking review checkpoint under `RECRUIT-01` and `PERSIST-01`
**Review role:** contract and assurance specialist, independent of the domain reviewer
**Reviewer posture:** strictly read-only. No file, Git, GitHub, issue or release-state mutation.
**Important boundary:** this is a specialist AI review. It is not statutory assurance, an external
audit opinion, lender acceptance, a verified human professional engagement, or package release
authority.

## 1. Candidate bound

| | |
|---|---|
| candidate commit | `b4c2d25dc97b25b5e3d379238522a43c4ccaa16a` |
| candidate tree | `c3f923865f819cc0463f9f87c26f413295811a6e` |
| base | `ba4b51898f53afa6bb35f1e1464efb43c1c73951` |

Verified independently before review. `git status --porcelain` printed nothing, so what was run is
what was committed. The two reviewers reached their dispositions independently and converged on the
same blocking defect.

## 2. Disposition on `b4c2d25`: **VETO**

### Blocking defect

The enhanced capital allowance was switched on across all eight scenarios on a justification that
is **false on the files' own arithmetic**, from a source **held nowhere in this repository or its
corpus**, and it was **the single largest contributor to the headline positive KPI movement**.

Plant base (capex × `plant_capex_share` 0.90) against the USD 3,000,000 ceiling the header itself
records: `unit_bidimplied` 3,118,593 (over); `unit_upside` 5,309,842 and `unit_base` 5,346,024 and
`unit_stress` 5,679,110 (1.8×–1.9×); the four portfolio files 74.8m–136.3m (25×–45×). The
"each site is a separate undertaking" defence does not reach the portfolio files at all.

Attribution of the +2.70pp `bidimplied` project-IRR gain, by reversing each correction singly:

| held at HEAD except… | project IRR | equity IRR | attributable |
|---|---:|---:|---|
| HEAD as committed | 10.7226 | 8.1653 | — |
| allowance reverted | 8.9989 | 6.7231 | **+1.72pp / +1.44pp** |
| timeline reverted | 9.3150 | 6.5357 | +1.41pp / +1.63pp |
| SSCL fix reverted | 10.9574 | 8.5126 | −0.23pp / −0.35pp |

The least-evidenced change carried the most benefit. That is the shape `VERIFY-01` exists to catch.

### Provenance ledger

| citation | status |
|---|---|
| Gazette Extraordinary 2083/33 of 10-Aug-2018 | **verifiable in corpus** — ESA extract line 757, verbatim |
| Gazette Extraordinary 2458/38 of 15-Oct-2025 | **verifiable in corpus** — ESA extract line 761, verbatim |
| ESA Art. 6A(a)(i) "basis upon which the bid… was made and accepted" | **verified** — LKR 20,000,000 threshold and symmetric clawback at Art. 6A(b)(ii) both confirmed |
| ESA Art. 5(o) VAT added to payments | **verified** — the ESA's own TOC is off by one against its body; the commit cites the body numbering, correctly |
| RFP Volume I cl. 1.4 milestones | **verified** — lines 455–477 |
| ESA "bid closing (i.e. 14th October 2025)" vs Vol I "August 14, 2026" | **verified — the discrepancy is REAL and fairly stated** |
| 2458/38 adds storage facilities ≥ 1 MWh | **external only** — the ESA says only "energy storage facilities" |
| Scheme relieves CID, PAL, CESS and VAT | **external only** — this list appears nowhere in the corpus |
| SSCL not relieved; raw materials for re-export only | **external only** |
| RFP Clarifications 2026-08-21 cl. 47, 48 | **unverifiable** — no clarifications document is held |
| Second Schedule enhanced capital allowance | **unverifiable, and circular** — appears only in the eight files the commit edits |

The YAML presented the gazette numbers and the Second Schedule in the same register. For the
gazettes that is defensible; for the Second Schedule it is not.

### Withdrawn claim — correct, and the replacement is honest

Exhaustive search confirms no Addendum 01 is held: `find -iname "*addend*"` returns nothing, and
`grep -rn -i "addendum"` finds only RFP Vol I cl. 2.3 describing the *mechanism*, plus derived
registers. The replacement substitutes cl. 1.4, verified line by line. Good practice.

Flagged out of scope: `registers/build_ltl_case_dbpl_2026-09-06.py:293` in the private corpus
asserts "RFP Volumes I, II and III, Addendum 01 and the 21 August clarifications, held in the
public corpus" — two of those four are not held. That false provenance claim survives in the
corpus and this commit does not reach it.

### Config-contract integrity — clean

All eight parse and validate against `_ALLOWED_KEYS` / `_RELIEF_KEYS` and through
`resolve_indirect_taxes`: zero rejected keys, zero unknown relief keys. All eight complete
`run_pipeline` at `validation_mode="strict"`. `duty_rate` returns 0.025 on the six
obtained-variants and 0.075 on the two stress variants.
`pytest tests/finance/test_import_levies.py -q` → **33 passed**.

**No test pinned any value this change moved**; `grep -rln "nso250" tests/` returned nothing.

### KPI re-derivation — every stated number reproduces

`bidimplied` 8.0188 → 10.7226 and 5.5981 → 8.1653; `base` 1.7531 → 2.0907; `upside`
1.8239 → 2.1905; `stress` 0.6751 → 0.8132; `min_dscr_period` 1.300 → 1.300 on every variant.
**Nothing was unreproducible. The arithmetic is honest; the entitlement behind one input is not.**

Two observations offered, not held against the commit: `min_dscr` sits at 0.867–0.869 on every
variant before and after (pre-existing; a reader of "min_dscr unmoved at 1.300" may not register
that the other DSCR view is below 1.0); and the `unit` and `portfolio` files return byte-identical
KPIs, so the eight files are four distinct results.

### Scope discipline (`DELIVERY-01`)

Three independent corrections in one commit, demonstrated independent by reversing each singly.
Bundling would normally be a note; here it was load-bearing, because it welded two sound
corrections to one that had to come out, and `git revert` would have discarded all three.

### Amendments required

1. Split the commit; corrections (1) and (2) would be **ACCEPTED** on their own.
2. Withdraw the enhanced capital allowance until the Second Schedule is in the corpus as a primary
   extract with its retrieval provenance.
3. If re-proposed, reconcile with `project.boi_approved: false` and demonstrate band eligibility
   against each file's actual `capex.usd_total`.
4. Repair the orphaned sentence in all eight files.
5. Mark the external-only citations as external.
6. Consider a pinning test for these eight scenarios.

### Not verified

The substance of both gazettes; RFP Clarifications cl. 47, 48, 13; the Second Schedule in its
entirety; whether Kilinochchi and Chunnakam 1 & 2 are in the Northern Province (geographic, not
documentary); and whether an Addendum 01 exists outside this corpus — absence here is not proof of
non-existence, and the withdrawn SCOD extension may yet be real.

## 3. Coordinator response — remediation applied

| # | amendment | disposition |
|---|---|---|
| A1 | Withdraw the enhanced capital allowance | **applied** — `enhanced_allowance_applies: false`, multiple back to 1.5, on all eight; the header now records why, and re-enabling it requires the capex to change, not the flag |
| A2 | Restate every KPI figure | **applied** — commit message, changelog fragment and pull-request body all carry 9.00% / 6.72% |
| A3 | Reconcile `boi_approved` | **applied** — recorded in the header as one of three preconditions for re-proposal; moot while the allowance is off |
| A4 | Repair the orphaned sentence | **applied** — "Relief is real but conditional." restored, per-variant clause on its own line |
| A5 | Resolve the Addendum 01 contradiction | **applied** — the `statutory:` header no longer cites it as live authority; the pass-through rests on ESA Art. 5(o) |
| A6 | Reword `construction_years: 1` | **applied** — stated as a conservative rounding of 0.33 years, with the ~2pp sensitivity and the direction of both errors |
| A7 | Mark external-only citations | **applied** — a PROVENANCE paragraph separates corpus-verified citations from external content and unverifiable clarifications |
| A8 | `cod_year` disagrees with the annual grid | **applied** — recorded as documentary-only with no KPI effect |
| A9 | KPI-pinning test | **applied** — `tests/integration/test_nso250_ltl_scenarios.py` and `tests/fixtures/finance/nso250_ltl_expected_kpis.json`, 29 tests, with both negative controls observed to fire |
| A10 | Upstream generator is stale | **recorded, not applied** — the file is in a different repository and outside this pull request's tree |
| A11 | False provenance in `build_ltl_case_dbpl_2026-09-06.py:293` | **recorded, not applied** — same repository boundary |
| A12 | Split the commit | **not applied, reasoned** — the bundling objection was that a veto on one correction forced surgery on the other two. With the allowance withdrawn, the remaining two are same-family corrections to the same eight files, each bound to a tender document, and the repository squash-merges, so separate commits would confer no revertability. Recorded for the reviewers to accept or reject. |

## 4. Re-disposition

Recorded in the pull request against the final head, after the remediation and after this record
and its domain counterpart were themselves committed.
