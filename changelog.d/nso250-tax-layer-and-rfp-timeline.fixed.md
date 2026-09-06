- **The NSO 250MW BESS scenarios were relieving a levy the bonded scheme does not reach, running
  a delivery timeline the RFP does not state, and leaving an allowance they are entitled to
  switched off.** Three corrections, all sourced.

  `relief.bonded_scheme: true` zeroes CID, PAL **and** SSCL as one line in
  `finance/import_levies.py`. The bonded warehousing scheme — Customs Ordinance, Gazette
  Extraordinary 2083/33 of 10-Aug-2018, amended with effect from 15-Oct-2025 by Gazette
  Extraordinary 2458/38 to add renewable energy storage facilities of at least 1 MWh — relieves
  Customs Import Duty, PAL, CESS and VAT on approved capital goods during construction. It does
  not relieve SSCL: only raw materials imported for processing and re-export are exempt, and
  capital goods pay. The flag is now `false` on every variant and the relief is expressed on the
  lines the scheme actually reaches, so the 2.5% import SSCL stands where it always should have.

  `cod_year` was 2028 and `Financing_Terms.construction_years` was absent, which
  `finance/debt_v14.py` silently defaults to **2** — and
  `finance/equity_distribution_v14_hydra.py` prepends that many zero years to the equity return
  vector. RFP Volume I clause 1.4 states the schedule: ESA signing 06-Nov-2026, Financial Closure
  06-Jan-2027, Commissioning, Testing and COD 06-May-2027. Financial close to COD is four months,
  not two years. The key is now set explicitly rather than defaulted, and the headers no longer
  cite an "Addendum 01" two-month SCOD extension that is not held in the corpus.

  The Second Schedule enhanced capital allowance — 100% of the investment in depreciable assets
  **in addition to** the normal capital allowance, for a total investment of USD 250,000 to
  USD 3,000,000 in a new undertaking from 01-Apr-2026 with BOI approval, and 150% in the Northern
  Province — was switched off. It is now on at a total write-off multiple of 2.0. The band is a
  ceiling, which the headers record: a price high enough to push a site's plant base past USD 3m
  forfeits the allowance that justified it.

  KPI effect on all eight scenarios, direction positive: `bidimplied` project IRR 8.02% to 10.72%
  and equity IRR 5.60% to 8.17%; `base` project IRR 1.75% to 2.09%; `upside` 1.82% to 2.19%;
  `stress` 0.68% to 0.81%. `min_dscr_period` is unmoved at 1.300 on every variant — the sculpt
  floor still binds. The three OEM-priced variants stay at a negative equity IRR, which is the
  finding, not a defect: the awarded capacity charges do not support those equipment prices.
