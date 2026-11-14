# Blue Whale Equipment-Cost Parity & Logistics Review (`2026-11-14`)

- **Work item:** [#1677](https://github.com/arunakulat/dutchbay-epc-model/issues/1677)
- **Source package:** `Blue_Whale_Review_Package_2026-11-14.zip` (`BW-COST-AEP-REVIEW-2026-11-14`, v1.1, owner-authorized private review brief)
- **Code & Config:** [`analytics/wind/blue_whale_equipment_parity.py`](../../analytics/wind/blue_whale_equipment_parity.py), [`conf/blue_whale_equipment_parity.yaml`](../../conf/blue_whale_equipment_parity.yaml), [`scripts/run_blue_whale_equipment_parity_v14.py`](../../scripts/run_blue_whale_equipment_parity_v14.py)
- **Status:** Conditional benchmark and unpriced buildup guard only. **No scenario CAPEX is revised.**

## 1. Key Findings & Methodology Correction (Appendix E)

1. **No commercial price in the Kalpitiya 60/63 MW technical proposal:** The September 2026 Kalpitiya proposal (`6 × EN206/10.5 = 63 MW`, `283,644 MWh/yr`) contains no sale price, Incoterm, or priced BoQ. Accordingly, the existing screening baseline in `scenarios/blue_whale_wind_lot5b_2026.yaml` (`$8,899,980` wind CAPEX) is **not** revised.
2. **Parity threshold vs. price prediction:** Applying the recorded Mannar turbine-supply benchmark (`$19,490,000` over `50 MW` and `207,000 MWh/yr × 20 yr = 4,140,000 MWh`, i.e. `$389,800/MW` and `$4.707729/lifetime MWh`) to Blue Whale's preliminary net P50 AEP (`40.574749451543354 GWh/yr × 20 yr = 811,494.989031 MWh`) yields **`$3,820,298.87`** (`$402,136.72/MW`). Per Appendix E, this is a **conditional equipment-price parity threshold** (`+3.164885%` break-even `$/MW` premium over Mannar), **not** an inferred OEM quote. At unchanged `$/MW` (`$389,800/MW`), Blue Whale equipment is **`$3,703,100.00`** (`$4.563306/lifetime MWh`, `-3.067793%` vs. Mannar).
3. **Scaling counterexample:** Higher turbine rating does not guarantee lower equipment `$/MWh` (e.g., Ashuri et al. 2016 5 MW to 10 MW reference scaling rises `+28.718969%` on a common 20-year basis). Actual single-unit EN206 pricing requires a vendor quote.

## 2. Logistics & Unpriced Cost-Buildup Gates

- **Road vs. marine exclusivity:** `conf/blue_whale_equipment_parity.yaml` encodes the 17-item cost-buildup structure (`E01`–`E04`, `M01`–`M08`, `R01`–`R03`, `C01`–`C02`) with mutually exclusive `road` and `marine` routes.
- **`null`-safe accounting:** Unpriced packages are represented as `null` (`None`), never `0`. `evaluate_cost_buildup()` refuses to emit a `total_usd` (`None`, `status="UNPRICED_EVIDENCE_GAPS"`) whenever any required package is unpriced.
- **Road allowance comparator:** The existing `$40/kW × 9,500 kW = $380,000` inland transport allowance (`$399,000` with 5% EPC wrap) is a screening placeholder, not a contractor quote or marine-delivery budget.
- **Confidentiality:** Private supplier draft schedules and private RAG file contents remain outside this public repository.
