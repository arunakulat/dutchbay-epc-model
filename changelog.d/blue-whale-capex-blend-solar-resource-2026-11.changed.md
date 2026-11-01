- Blue Whale capex blend and solar resource (15.15.0). On the owner's request and decision of
  1 Nov 2026 (#1353 comment 6556975196, "Derived blend may publish"), the wind and BESS capex
  become blends of China FOB pricing and internal anchors, and the solar resource at the site is
  reported with cross-checks. The disclosure surface moves on the owner's authority: the
  published figures are blends that include private commercial inputs, and no raw private
  figure is published.
  - New `solar_resource/blue_whale_site_inputs.py`, `conf/blue_whale_capex_solar_resource.yaml`
    and the Hydra CLI `scripts/run_blue_whale_capex_solar_resource_v14.py`. The landed-cost
    build-up uses the repository's own levy postures (bonded, prudent, full stack paid) and
    reads the private anchors at run time from outside the repository.
  - Wind, single 9.5 MW turbine excluding the B26 line: 728.16 / 936.84 / 1,341.16 USD/kW
    (was the 1,300 placeholder). BESS, 4 h all-in: 129.13 / 140.74 / 202.51 USD per kWh
    contracted (was 78.75 / 135.00 / 143.41). PV prices unchanged.
  - Solar resource at the PV centroid (pvlib 0.16.1 on the frozen TMY, which is PVGIS-ERA5,
    not SARAH3): GHI 1,871 kWh/m2, POA 1,886, specific yield 1,536 kWh/kWp, PR 0.815, AC CF
    21.06%; PVGIS 1,473, Global Solar Atlas PVOUT 1,633, satellite GHI about 9% above ERA5.
    Outputs and methods in `docs/blue_whale/`.
  - The solar + BESS sizing, re-run unchanged, moves to 107 tables (4.01464 MWp), 3.5 MW AC
    and 1.0 MW / 4.0 MWh under both readings (was 160 tables, 5.0 MW AC, 4.5 MW / 18 MWh);
    every eligible size has a negative P50 unit NPV. PR 3's hybrid sizing does not move.
  - Wind v0.3, solar + BESS v0.2 and hybrid v0.8. Wind project IRR 7.80% -> 10.81%; hybrid
    6.90% -> 8.73%; solar + BESS project NPV USD -4.77M -> -4.03M (no project IRR).
  - The handling notes NSO250MW-OFFERS-HANDLING-2026-09-04 and
    KALPITIYA60MW-WIND-HANDLING-2026-09-21 record the decision; parent manifest pins refreshed.
