# Gap review — Envision 10 MW/40 MWh design package vs NSO 250 MW BESS RFP

**For:** Envision Energy (via Hayleys) · **Re:** NSO Tender **TR/REP&PM/ICB/2026/001/C** (250 MW / 1000 MWh standalone BESS, 10 MW/40 MWh units, BOO, 15 yr)
**Reviewed document:** Envision *"Design Calculation Description for Sri Lanka 10 MW/40 MWh project"*, V1.0, 29 Jul 2026 (ENS-D10E-20100 + ENS-D06G-24120).
**Submission deadline:** **14 August 2026, 10:00** (RFP issue closes 13 Aug). **Purpose:** items to tighten so the offer is compliant, competitive and bankable.

---

## 1. What is already solid (keep)

- **Usable energy:** 40.2 MWh at POC BoL against 40 MWh required; **4.02 h at 10 MW** — meets the 4-hour rule (clause k).
- **Degradation:** 40.2 → 30.8 MWh, **76.7% SoH at yr 15** — comfortably above the RFP's Minimum Dispatchable Capacity floor (97.5% → **68.0%** at yr 15).
- **Reactive capability:** Q ±3.29 MVAR / PF ±0.95 at PCC — meets the ±3 Mvar / ±10 MW requirement.
- **Efficiency stack** is fully documented (usable-DC 98%, PCS 98.5%, transformers, cables), and — unlike the earlier DIMO design calc — an **explicit 15-year RTE curve** is provided.

## 2. Critical compliance gaps (must fix — risk of technical rejection)

1. **Grid-forming (V/F) is not addressed — the single biggest gap.** RFP §3(c) *mandates* that "the BESS is required to operate in **true grid-forming (V/F) mode** … full grid-forming-capable inverter (voltage-sourced, voltage-controlled) … **must not change to current-controlled (grid-following) during normal operation or under any network fault conditions**." The design calc is silent on control mode. **Action:** state explicitly that the ENS-D PCS is a full voltage-source grid-forming inverter meeting §3(c), and supply the documentary + modelling evidence the clause demands. (Note: Envision's previously circulated dynamic models were grid-*following* — those will not satisfy this round.)

2. **Dynamic models missing (clause p).** The tender requires **PSS®E *and* PSCAD/EMTDC** models — or fault test results — demonstrating V/P/Q response to deep and shallow faults and a **±50° phase-angle step at the POC, at SCR = 1, 3, 5, 10 (X/R 5)**. *"Failure to meet at least one of the above … may result in rejection."* These are not in the package. **Action:** deliver grid-forming EMT (PSCAD) + RMS (PSS®E) models validated across those SCR levels, with the tender.

3. **RTE dips below the 85% floor on an aux-inclusive basis.** The RFP requires a guaranteed **minimum AC-to-AC RtE of 85% monthly** (LD at 150% of the peak-time GP tariff on excess losses if below). The design calc shows RTE **including aux falling to 84.9% by yr 15** — below the floor — while **excluding aux it holds at 88.4%**. The calc also states aux "cannot be guaranteed separately." **Action:** (a) confirm the metered RtE basis with NSO and align the guarantee to it; (b) if metering is aux-inclusive, add design margin so RtE ≥ 85% is held to yr 15; (c) firm up the auxiliary-load figure so the RtE guarantee is defensible.

4. **Standards compliance not evidenced (clause b).** Documentary proof is required for **IEEE 1547-2018, IEEE 2800-2022, UL 1741-SB, IEC 62477-1, IEC 62109-1/2, IEC TS 62786-3** and the Sri Lanka Grid Connection Code (22 Jul 2024). **Action:** attach the certificates/type-test reports.

5. **Design point is 35 °C, but the site envelope is +45 °C.** Aux and performance are calculated at 35 °C, whereas RFP site conditions run to **+45 °C**, and clause k requires 4 h at rated power **under ambient site conditions at commissioning**. With only 0.5% headroom at BoL (40.2 vs 40 MWh), the 40 MWh may not hold at the hotter POCs. **Action:** provide the usable-capacity and RtE at the site maximum ambient, and add sizing headroom if needed.

## 3. Documentation the proposal still needs (OEM inputs)

6. **Capacity Maintenance Plan (clause m).** The degradation curve alone is not the Plan. NSO requires: BoL energy at the Termination Point vs contracted rating; an **augmentation schedule (MWh + timing)**; module/rack replacement intervals; augmentation/outage interface with NSO; and end-of-life decommissioning/recycling commitments. **Action:** supply the augmentation and replacement schedule underpinning the 15-year curve.
7. **Ride-through & control envelope (Annex A A.05, clause o).** Provide the frequency (47–52 Hz) and voltage ride-through envelope, droop settings, LVRT/HVRT and fault reactive-current behaviour, and confirm EMS logging of grid-support services for the mandatory monthly report.
8. **Single-line diagram + power-limiting method (clause e).** SLD to the Grid Point, with the stated method to limit output to **10 MW +10%** at the termination point.
9. **Service life (clause l).** Confirm **≥20-year** design life for non-battery equipment and **≥15-year** for cells/modules/racks under the ESA duty cycle.
10. **Fire safety & protection (clauses g, h).** Fire detection/suppression, thermal-runaway mitigation and compartmentalisation evidence; and confirm PCS fault-current contribution/withstand against the published site fault levels (e.g. Kiribathkumbura 16.2 kA; Monaragala the weakest at 4.5 kA). *(Installation is EPC scope; the equipment ratings and interface data are Envision's.)*

## 4. Commercial and margin flags

- **Thin energy margin:** 40.2 MWh vs 40 MWh required is 0.5% — see gap 5; a hotter site or metering-basis change could erode it.
- **FX:** the capacity charge is flat LKR with a **one-time 85% USD adjustment at ESA signing** (`Applicable rate = 0.15·Y + 0.85·Y·P2/P1`, P1 = rate at bid close, P2 = 7 days before signing). Ongoing 15-year LKR-depreciation risk on Envision's CNY/USD-priced supply and O&M still sits with the developer — Envision should hold pricing/FX terms that let the developer close on that basis.
- The offer is a **design calc only** — no capex, LTSA schedule, or grid-code control-mode statement. A complete, comparable bid needs all three.

## 5. Compliance checklist

| # | RFP requirement | Ref | In the design calc? | Action for Envision |
|---|---|---|---|---|
| 1 | True grid-forming (V/F) | §3(c) | **No** | Confirm GFM + evidence |
| 2 | PSS®E + PSCAD models @ SCR 1/3/5/10 | §3(p) | **No** | Supply GFM EMT+RMS models |
| 3 | RtE ≥ 85% monthly (guaranteed) | §2.8(iii) | Marginal (84.9% incl-aux yr15) | Fix aux basis / add margin |
| 4 | Inverter standards + proofs | §3(b) | **No** | Attach certificates |
| 5 | 4 h @ 10 MW at site ambient (≤45 °C) | §3(k) | 35 °C only | Re-state at ≤45 °C |
| 6 | Capacity Maintenance / augmentation plan | §3(m) | Curve only | Add augmentation schedule |
| 7 | Ride-through / droop / A.05 grid support | §3(o), Annex A | **No** | Provide envelope + logging |
| 8 | SLD + 10 MW+10% limiting method | §3(e) | **No** | Provide SLD |
| 9 | 20 yr non-battery / 15 yr battery life | §3(l) | Partial | Confirm |
| 10 | Fire safety + fault withstand | §3(g,h) | **No** | Provide ratings/evidence |
| — | Usable ≥40 MWh, 4 h, degradation ≥ floor | §2.8, §3(k) | **Yes** | Hold |
| — | Reactive ±3 Mvar / ±0.95 PF | §3, Annex A | **Yes** | Hold |

---

*Prepared 30 Jul 2026 for the 14 Aug 2026 submission. Sourced from NSO RFP Tender 2026/001/C (Vol I §2.8, §3.1 a–p; Annex A) and the Envision design calc V1.0 (29 Jul 2026). Items 8–10 and fire/protection installation are shared EPC scope; the design, ratings and interface data are the OEM's. No pricing was reviewed — this covers the technical and compliance package only.*
