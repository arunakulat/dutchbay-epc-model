# Blue Whale wind: battery options for the separate 9.5 MW wind project

**SCREENING ONLY, not lender-grade.** PUCSL's BESS feed-in tariff names ground-mounted and
floating solar PV only, so every wind + BESS revenue basis here is a working assumption. The
wind yield carries the met-mast HOLD (no measured Dutch Bay wind, no P90 for lenders). F-5 (no
quarterly CFADS or intra-year DSCR figure supports a lender representation), #1110 and v15.6.1
stand.

- Inputs: `conf/blue_whale_wind_bess_options.yaml` (strict: every key required, unknown keys refused).
- Method: `analytics/wind/wind_bess_options.py`.
- CLI: `scripts/run_blue_whale_wind_bess_options_v14.py` (Hydra, one JSON object on stdout).
- Committed output: `docs/blue_whale/wind_bess_options_summary.json`. It pins the config and
  scenario SHA-256; model 15.27.0; scenario `scenarios/blue_whale_wind_lot5b_2026.yaml` v0.6.
- Every KPI comes from `analytics.evaluation_v14.evaluate_with_overrides` (ARCH-04).

```bash
DUTCHBAY_NASA_POWER_DIR=/path/to/power \
  .venv/bin/python scripts/run_blue_whale_wind_bess_options_v14.py \
  output.summary_json=docs/blue_whale/wind_bess_options_summary.json
```

## What the owner asked (2026-11-14)

1. Solve for the 9.5 MW wind project with a battery and no solar.
2. A battery is needed only for a ramping and black-start function suited to the turbine. It is
   not mandatory.
3. The battery charges from the turbine off-peak and gives up the wind tariff on that energy. At
   peak it is paid on the solar + BESS terms, read as **a whole wind peak rate**.
4. Price the down-ramp unit from a battery supplier's quotation, named only as a generic battery
   supplier. The owner approved this on 2026-11-14 at 22:16Z.

The 40 MW AC black-start battery mentioned in PUCSL discussions is **UNCONFIRMED**. No document
supports it. It appears here only as the `cycled_10_40` comparison, never as a requirement.

## How the peak rate is built

The PUCSL Decision on Feed-in Tariffs of 25 August 2026, Table 7, sets these tariffs for
ground-mounted solar + BESS:

- 47.08 + 3.02 LKR/kWh in the Prioritized Feed-in Time, 17:30–21:30;
- 18.00 + 2.72 LKR/kWh at other times.

The Decision states a round-trip efficiency of 90% (s.2.2.3.5). From these, the BESS component is
priority − other / RTE = 47.08 − 18.00 / 0.90 = **27.08** LKR/kWh. The floating line gives the
same 27.08, and the parser checks that the two agree. The prosumer components in Table 6 do not
apply to a power plant.

| Basis | LKR/kWh discharged | How it is built |
|---|---:|---|
| **Whole wind peak rate (base)** | **55.67** (50.19 fixed + 5.48 escalable) | The solar + BESS formula with the wind tariff as R_charging: 20.80 / 0.90 + 27.08 + 4.93 / 0.90 |
| Stacked (sensitivity) | 52.81 | Wind tariff 25.73 + BESS component 27.08 |
| Whole rate on all window exports (sensitivity) | 55.67 on the turbine's own window exports too | An upside reading only: it pays the peak rate on about 7.3 GWh/yr the turbine exports anyway |

- Each charged kWh gives up the wind tariff of 25.73.
- The contract term is 15 years (Table 7 note [2]). After it, discharged energy earns the wind
  tariff.
- Table 7 note [1] allows one adjustment after 12 months, weighted 70% LKR/USD and 30% CCPI. On
  the scenario's own paths this raises the component to 27.95 and the whole rate to 56.54. It is
  run as a sensitivity.

## Results (project NPV change vs wind-only USD 1,398,803)

Wind-only KPIs:

| KPI | Value |
|---|---|
| Project IRR | 12.41% |
| Equity IRR | 10.55% |
| Equity NPV | USD −740,793 |
| Engine min DSCR | 0.867 (operating-year-1 covenant row) |

The min DSCR is unchanged, to three decimals, by every option.

Readings of the 10 MW standardised-PPA limit:

- **A:** turbine plus battery power must not exceed 10 MW, so the battery is at most 0.5 MW.
- **B:** export at the connection point is capped at 10 MW.
- **C:** the battery sits outside the limit.

| Option | Fits A | B: whole rate | C: whole rate | Stacked (B) | Equity IRR (B) |
|---|:-:|---:|---:|---:|---:|
| Held 0.5 MW / 0.5 MWh (black start only) | yes | −79k | −79k | −79k | 10.42% |
| **Cycled 0.5 MW / 2 MWh** | **yes** | **−65k** | **−65k** | −91k | **10.40%** |
| Held 1 MW / 1 MWh | no | −153k | −153k | −153k | 10.29% |
| Cycled 1 MW / 4 MWh | no | −151k | −128k | −206k | 10.22% |
| Cycled 2.5 MW / 10 MWh | no | −580k | −349k | −694k | 9.51% |
| Cycled 10 MW / 40 MWh (UNCONFIRMED 40 MW reading) | no | −4.26M | −1.92M | −4.48M | 5.53% |

- **No option beats wind-only.** The smallest battery that does the ramping and black-start job
  is **0.5 MW / 2 MWh, cycled daily**. It costs about USD 65k of project NPV and 0.15 points of
  equity IRR.
  - It fits every reading of the 10 MW limit.
  - It delivers 723 MWh/yr (362 equivalent full cycles).
  - On its own pre-tax cash flow it earns USD +47k NPV at a 13.8% IRR. Tax, debt sizing and the
    CFADS haircut turn that into −65k at project level.
  - After the one-time adjustment: −52k.
- **Break-evens for 0.5 / 2 MWh:**
  - all-in capex of USD 109.9/kWh, against the 140.74 mode;
  - or a peak rate of 61.75 LKR/kWh, against 55.67.
  - For 10 / 40 outside the 10 MW limit: USD 90.6/kWh or 67.41 LKR/kWh.
- **Reading B** clips anything above about 1 MW. The turbine reaches about 9.2 MW at the
  connection point and is windiest in the evening window. So 10 / 40 cycles 133 times a year
  under B, against 307 under C.
- **Monte Carlo:** 256 LHS trials of capex, battery RTE, residual fade and wind yield. No trial
  of any option beats wind-only. For 0.5 / 2 MWh the change is P50 −99k and P90 −154k.
- **Battery RTE:** from 0.80 to 0.90, 0.5 / 2 MWh ranges from −84k to −42k.
- **The all-window-exports reading** is the only basis that turns positive: about +2.96M for
  0.5 / 2 MWh. It pays the battery premium on energy the turbine exports anyway, so it is not a
  battery case. PUCSL would have to say so explicitly.

## The open input: the NSO's down-ramp allocation

The CEB embedded-wind grid guide (s.3.1) sets the ramp limit:

- ramp at most 10 MW/min per grid substation;
- shared among wind farms by installed capacity;
- delivered by turbine controls.

The guide does not say whether a wind lull counts. A full drop from 9.5 MW at Blue Whale's share
needs the following firming (the ramp triangle):

| Other wind on the substation | Blue Whale's share | Minutes | Firming energy |
|---|---:|---:|---:|
| none | 10 MW/min | 0.95 | 0.075 MWh |
| 90 MW (illustrative) | 0.955 MW/min | 9.95 | **0.79 MWh at 9.5 MW** |

If the share is small, the firming unit replaces the black-start battery, because it can also
black-start the turbine. It is priced from **a generic battery supplier's budgetary offer**:

- CIF, excluding duty and taxes, priced for many sites;
- flat at USD 90.00 per DC kWh, split into lines;
- lifted to all-in by the repository's mode (140.74 / 99.50).

| Firming unit | CIF | All-in | Project NPV change | Equity IRR |
|---|---:|---:|---:|---:|
| 9.5 MW / 0.79 MWh power-heavy, cells at the offer's DC rate | USD 357k | 505k | −547k | 9.66% |
| Same, power cells at 3× (assumption) | 492k | 696k | −755k | 9.35% |
| Supplier's smallest block with one 10.08 MW skid (18.3 MWh usable), held | 1.81M | 2.56M | −2.74M | 6.83% |
| Same block, cycled at the whole rate, reading C | 1.81M | 2.56M | **−0.70M** | 9.25% |
| Same block, cycled, reading B | 1.81M | 2.56M | −1.32M | 8.48% |

The power-heavy price is weak, for three reasons:

- the offer's AC line is an allocation of a flat rate, not a cost;
- 9.5 MW from under 1 MWh is about 11C, beyond the energy cells offered, and no supplier has
  quoted such a unit;
- the offer is priced for many sites, so a single unit would cost more.

The smallest block is a product the supplier actually offered. If the battery may sit outside
the 10 MW limit, cycling it recovers most of its cost.

## What would change the answer

1. The NSO's ramp allocation for the substation, and whether a lull counts.
2. A PUCSL tariff that covers wind + BESS, or confirmation of the whole-rate reading.
3. Whether a battery may sit outside the 10 MW standardised-PPA limit (reading C).
4. A quotation for a power-heavy (≥ 2C) unit.
