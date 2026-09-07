- **The NSO 250MW BESS scenarios were relieving a levy the bonded scheme does not reach and
  running a delivery timeline the RFP does not state.** Two sourced corrections, plus the guard
  that should have existed before either was claimed.

  `relief.bonded_scheme: true` zeroes CID, PAL **and** SSCL as one line in
  `finance/import_levies.py`. The bonded warehousing scheme — Customs Ordinance, Gazette
  Extraordinary 2083/33 of 10-Aug-2018, amended from 15-Oct-2025 by Gazette Extraordinary
  2458/38 — relieves Customs Import Duty, PAL, CESS and VAT on approved capital goods during
  construction. It does not reach SSCL: only raw materials imported for processing and re-export
  are exempt, and capital goods pay. The flag is now `false` on every variant and relief is
  expressed on the lines the scheme actually covers, so the 2.5% import SSCL stands where it
  always should have — USD 59,773 on the unit case, previously nothing. The gazette *citations*
  are corpus-verified (the ESA names both verbatim); their *content*, and the SSCL rule itself,
  are external to this repository and are now marked as such in the headers rather than asserted
  in the same register as the held documents.

  `cod_year` was 2028 and `Financing_Terms.construction_years` was absent, which
  `finance/debt_v14.py` silently defaults to **2** — and
  `finance/equity_distribution_v14_hydra.py` turns into two zero years at the head of the equity
  return vector. RFP Volume I clause 1.4 states ESA signing 06-Nov-2026, Financial Closure
  06-Jan-2027 and COD 06-May-2027 — **superseded; see the correction fragment beside this one,
  which is part of the same release.** Addendum 01 item 01 revises that clause in full and gives
  ESA signing 14-Dec-2026, Financial Closure 15-Mar-2027 and COD 16-Aug-2027, five months rather
  than four. The key is now explicit, and the header states 1 as a **conservative rounding** of
  0.42 years rather than a figure read off the schedule — 0 would zero IDC, which is wrong for a four-month build on drawn debt, while 1
  overstates it by about eight months. The choice is worth roughly 2pp of project IRR. The
  headers also cited an "Addendum 01" two-month SCOD extension, and elsewhere "Addendum 01 item
  13" as live authority. **Both withdrawals were wrong and are themselves withdrawn in the
  correction fragment beside this one.** Addendum 01 is held, in this repository, ingressed by
  #1180 on 2026-08-27 and present in the base tree this change was reviewed against. Both original
  citations were correct.

  **An enhanced capital allowance was proposed with these corrections and withdrawn under
  review.** Switching it on at a multiple of 2.0 assumed each site's depreciable base sits inside
  the Second Schedule's USD 250,000–3,000,000 band. It does not. On the plant-only share of the
  levy-inclusive depreciable base — the narrowest reading the claim itself invoked — the cheapest
  variant is USD 3.17m against a USD 3.00m ceiling and the others run 1.80×–1.99× over, while per
  portfolio the same measure runs **25.4× to 47.8×** over. `project.boi_approved` is false in the same files, and nothing in `finance/`
  reads that key, so the contradiction failed silent. The Second Schedule is not held in this
  repository or its corpus, making the citation circular. Two independent `RECRUIT-01` reviewers
  vetoed it on the same ground and it is out — the allowance would have supplied about 64% of the
  headline improvement, on an entitlement not established.

  `tests/integration/test_nso250_ltl_scenarios.py` and
  `tests/fixtures/finance/nso250_ltl_expected_kpis.json` close the gap both reviewers named:
  these eight scenarios had **no test coverage at all**, so every KPI claim about them rested on
  author self-report. The oracle pins a seven-KPI vector per scenario, the unit/portfolio scaling
  identity, and two negative controls — that the allowance stays off and that bonded relief is
  never re-encoded through the flag that would zero SSCL with it. Both controls were observed to
  fire before being relied on.

  KPI effect against the previous head, direction positive: `bidimplied` project IRR 8.02% to
  9.00% and equity IRR 5.60% to 6.72%; `base` 1.75% to 1.80%; `upside` 1.82% to 1.88%; `stress`
  0.68% to 0.76%. `min_dscr_period` is unmoved at 1.300 — the sculpt floor still binds. Distinct
  from it, `min_dscr` (the #790/#806 fold-corrected annual covenant minimum) sits at 0.867–0.869
  throughout, before and after; that is pre-existing and is now pinned so the distinction cannot
  be lost. The three OEM-priced variants stay at a negative equity IRR, which is the finding
  rather than a defect: the awarded capacity charges do not support those equipment prices.

  **One thing "positive" does not mean.** The direction of every KPI move here is positive, and
  that is a statement about the delta and not about viability. Read against the Sri Lankan cost of
  equity of 18.00% that LTL's own IPO advisers apply to every Sri Lankan valuation in the group
  (NDB IB / CT CLSA, 31 July 2024, s.8.1.4 — a 12.00% risk-free rate plus a 6.00% power-sector
  risk premium), `bidimplied` returns 6.72% against an 18.00% hurdle, a shortfall of 11.3pp — and
  `bidimplied` is the best case in the family, explicitly a bid-implied ceiling rather than a cost
  estimate. The other three are negative. **No variant in this family clears.** Lifting
  `wacc.cost_of_equity` from 0.15 to the sourced 0.18 is a separate change and is deliberately not
  made here; it was verified to move none of the seven pinned KPIs, so it is orthogonal to this
  one rather than merely deferred.
