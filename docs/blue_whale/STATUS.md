# Blue Whale hybrid: project status

Last updated: 2026-10-27. Stage: **concept screening (skeleton model, owner inputs outstanding)**.

## Configuration under study

| Component | Size | Notes |
|---|---|---|
| Wind | 1 x 10 MW turbine | A single large machine; whether it fits Lot 5B depends on setbacks |
| Solar PV | 5 MWp | Fixed tilt assumed |
| BESS | 10 MW x 4 h (40 MWh) base; 5 h (50 MWh) sensitivity | Revenue model not yet chosen |

Model file: `scenarios/blue_whale_hybrid_lot5b_2026.yaml` (version 0.1, placeholders only).
Inputs register: [INPUTS_REQUIRED.md](INPUTS_REQUIRED.md).

## Site

Lot 5B in Plan 3641 (24 Mar 2010), Mutuwal village, GN Dutch Bay 633, Kalpitiya DS,
Puttalam District. Extent 23 A 0 R 0 P = 9.3077 ha. Owner: Blue Whale Resort (Pvt) Ltd
(PV 71488), by Deed of Transfer 318 (3 May 2010). Sea to the north and west, Puttalam lagoon
to the south. Rights of way over Lot 5I (9 m road) and Lot 3 of Plan 3215, and a shared jetty
on Lot 5D.

These facts come from the owner's scanned title pack, reviewed outside this repository. The
pack has not been ingested into `docs/source_materials/`, so they are not yet evidence of
record under `DATA-01`.

## Open risks

1. **Fit of a 10 MW turbine.** A rotor of about 190 to 200 m on a 9.3 ha coastal lot, bounded by sea,
   lagoon and two streams, may not clear the coastal and residential setbacks. A setback
   check (inputs B05, B08) comes before any further wind work.
2. **Coastal permitting.** Most of the lot is likely inside the Coast Conservation Act zone
   (CC&CRMD permit, IEE or EIA), with lagoon ecology and bird collision in scope.
3. **Component transport.** Blade and tower delivery over a 9 m right of way, or by the
   shared jetty, is unsurveyed.
4. **Title.** The 2010 misregistration was cured only in 2023 (Deed of Declaration 11619).
   Lenders will want a fresh registry search; 9 of the 12 listed title documents are missing
   from the scan.
5. **Landowner and project company differ.** A lease or transfer from Blue Whale Resort (Pvt)
   Ltd to the project company has to be documented.
6. **Revenue.** No tariff, offtake route or BESS revenue model is fixed yet. Results from
   the skeleton reflect DutchBay assumptions, not Blue Whale ones.

## Next steps

1. Owner supplies the priority-1 inputs in INPUTS_REQUIRED.md (and the input workbook).
2. Setback and layout check for the turbine, PV and BESS on Lot 5B.
3. Replace placeholders in the scenario, then run the v14 pipeline for base, 5 h BESS and
   P90 cases.
4. Assemble the DBPL feasibility study once the model has owner-sourced inputs.
