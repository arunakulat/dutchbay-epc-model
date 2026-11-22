- **Tariff legal status beside revenue** — a shared registry, `conf/tariff_legal_status.yaml`,
  records for each rate a scenario prices its status (`published`, `analogy_unpublished` or
  `unconfirmed`), the instrument and clause that set it, and its effective window, quoted from
  the pinned PUCSL decision, annex and methodology (DATA-01). The reader
  (`analytics.tariff_legal_status`) refuses a rate without a status, an unknown key or a
  dangling reference. The command-line lender report adds a "Tariff Basis and Legal Status"
  section after the key indicators, prints the headline rate's status above the income
  statement, flags an assumed SPPA signing date or COD outside a rate's window, and labels every
  wind battery options figure that rests on the solar + BESS formula applied to wind
  ("Analogy, unpublished"). A scenario the registry does not list is reported as "Legal status
  not recorded", never as published. Labelling only: no tariff value and no KPI changes. Not a
  legal opinion (#1837).
