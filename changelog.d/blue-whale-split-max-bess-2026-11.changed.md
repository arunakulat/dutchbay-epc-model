- Blue Whale split into two projects and the solar + BESS sized under the PUCSL 2026 rules
  (15.15.0). Owner decisions of 1 Nov 2026 (#1353 comment 6556854201): the 9.5 MW turbine is a
  separate project built first; maximise the BESS within the solar + BESS parameters for the
  PUCSL evening tariff band; "Max value, MC decides"; model both readings of the 10 MW limit
  and flag the turbine's cumulative risk.
  - New `scenarios/blue_whale_wind_lot5b_2026.yaml` (the turbine: #1530's CF 0.374256 and
    31.15 GWh, wind FiT 25.73, capex USD 14.35M with the USD 2.0M grid placeholder) and
    `scenarios/blue_whale_solar_bess_lot5b_2026.yaml`. The hybrid scenario is kept, unchanged
    apart from a header note, as the superseded combined view. Section 4 of handling note
    `KALPITIYA60MW-WIND-HANDLING-2026-09-21` now names the wind scenario beside the hybrid as
    carrying the derived AEP and CF, and its parent manifest pin is refreshed.
  - New `conf/blue_whale_pucsl_fit_2026.yaml`: the PUCSL methodology, consultation and Annex 2
    figures and the Electricity Act No. 36 of 2024 and Amendment Act No. 14 of 2025 clauses,
    each with its URL, section, PDF SHA-256 and verbatim text, checked by
    `solar_resource.pv_bess_sizing.RegulatoryBasis`.
  - BESS rules: 4 h at nominal capacity (energy = 4 x power, delivered energy, the loss booked
    on charge), PV-only charging, discharge only 17:30-21:30 at 50.10 for 15 years; every other
    kWh at 20.72. The 05:30-07:30 window is superseded. RTE stays 0.85 (0.90 is a sensitivity).
  - PR 3's seeded Monte Carlo (seed 20261101, 256 LHS trials, cited prices and ranges unchanged)
    re-run through `run_project_sizing` over 325 sizes of PV DC (to the lot's maximum, 191
    tables), PV AC and BESS power, under reading A (PV AC + BESS <= 10 MW) and reading B
    (export <= 10 MW): 84,175 evaluations; summary in
    `docs/blue_whale/solar_bess_project_sizing_summary.json`.
  - Result on the P50 unit NPV: reading A (committed) 160 tables (6.0032 MWp), 5.0 MW AC and
    4.5 MW / 18 MWh; reading B 191 tables, 6.0 MW AC and 5.5 MW / 22 MWh. The revenue maximum,
    9 MW / 36 MWh, needs reading B. Every size sits near zero unit NPV at P50 and below it at
    P90, and the engine finds no project IRR for the solar + BESS project.
  - KPIs: hybrid unchanged; wind project IRR 4.09%; solar + BESS project NPV USD -4.77M,
    equity IRR -3.28%, no project IRR. Pinned with responsiveness guards in
    `tests/solar/test_solar_bess_project_sizing.py`.
