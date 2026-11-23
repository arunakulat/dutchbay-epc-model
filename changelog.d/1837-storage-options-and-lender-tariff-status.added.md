- **Tariff legal status in committed storage-options summary and registry** — the wind battery
  options runner (`analytics.wind.wind_bess_options_runner`) now records the machine-readable
  `tariff_legal_status` block directly in `docs/site_analyses/blue_whale_wind_lot5b_2026/storage_options.json`,
  and `conf/tariff_legal_status.yaml` adds entries for the DutchBay lender case (`20.30 LKR/kWh`,
  `unconfirmed` unexecuted CEB SPPA assumption) and the Blue Whale hybrid scenario (`24.97345 LKR/kWh`,
  `analogy_unpublished` energy-weighted blend of PUCSL Annex 2 component rates). Labelling and
  metadata only: no tariff value and no KPI changes (#1837).
