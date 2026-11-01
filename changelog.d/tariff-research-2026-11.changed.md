- Apply the November 2026 tariff and BESS research to four scenarios (15.11.0). Source: the
  owner's research record "Sri Lanka small-plant tariffs, BESS methodology and curtailment
  (Nov 2026)" and, for the capacity charge, the repository's own NSO 250 MW record.
  - `scenarios/ceb_solar_bess_nightpeak_10mw.yaml` moves from CEB's 2025 night-peak scheme
    (45.80 LKR/kWh, 10 years) to the PUCSL feed-in tariff effective 25 Aug 2026 for ground
    solar + 4 h BESS: 50.10 LKR/kWh (47.08 + 3.02) in the prioritised window for 15 years
    (PUCSL Annex 2). Life, PPA term and timeline move to 15 years. The 2025 scheme is treated
    as superseded and kept only as a sensitivity. The window hours (18:30-22:30) and 365
    cycles remain assumptions: no official figure exists, internally or publicly.
  - The BESS capacity charge in `ceb_bess_10mw_capacity_charge.yaml` (was 2,500,000),
    `dutchbay_hybrid_bess_2025Q4.yaml` (was 5,000,000) and `blue_whale_hybrid_lot5b_2026.yaml`
    (input F06, was 5,000,000) becomes 1,752,500 LKR/MW/month: the capacity-weighted average
    of the 24 L1 bids at the NSO 250 MW tender's bid opening, already published in
    `scenarios/nso250_ltl_unit_base.yaml`. It is a bid-clearing level, not an award; no
    awarded rate is public.
  - Blue Whale (scenario v0.3): tariff 20.3 -> 24.76 LKR/kWh (input F03), the
    energy-weighted blend of the PUCSL 2026 wind (25.73) and ground-solar (20.72) tariffs;
    offtaker -> National System Operator (Private) Limited (input F02, Gazette 2479/36).
    Whether the < 10 MW limit counts per technology or per plant is unresolved; if per
    plant, the FiT does not apply to this 15 MW plant.
- KPI effect (project IRR): solar + BESS 6.61% -> 10.04%; standalone BESS -1.29% -> -6.27%;
  DutchBay hybrid + BESS 1.77% -> 0.16%; Blue Whale 4.59% -> 2.77%. At the new rate the
  DutchBay hybrid's battery lowers project IRR below the plain hybrid (0.307%); it raised
  it before, and `tests/analytics/test_tech_comparison_scenarios_821.py` now asserts the new
  direction. Covenant snapshots: CEB BESS (3 breaches, FAIL) -> (1, REVIEW); solar + BESS
  (2, REVIEW) -> (4, FAIL). The covenant-mechanics tests keep their former CEB FAIL fixture
  by pinning the former rate as fixture input; their expected values are unchanged. The
  canonical lender case is unchanged.
