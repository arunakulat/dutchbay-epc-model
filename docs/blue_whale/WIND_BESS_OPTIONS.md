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
| Stacked (sensitivity) | 52.81 | Wind tariff 25.73 + BESS component 27.08 (its escalable remainder of −0.002 kept, as in the whole rate) |
| Whole rate on all window exports (sensitivity) | 55.67 on the turbine's own window exports too | An upside reading only: it pays the peak rate on about 7.3 GWh/yr the turbine exports anyway |

- Each charged kWh gives up the wind tariff of 25.73.
- The contract term is 15 years (Table 7 note [2]). After it, discharged energy earns the wind
  tariff.
- Table 7 note [1] allows one adjustment after 12 months, weighted 70% LKR/USD and 30% CCPI. On
  the scenario's own paths this raises the component to 27.95 and the whole rate to 56.54. It is
  run as a sensitivity, and it is one reading of the note: it adjusts only the BESS component's
  non-escalable part. Adjusting the whole 50.19, or the wind tariff's own 20.80 (which would
  also raise the charging cost), are other readings and are not run.

## Results (project NPV change vs wind-only USD 1,398,803)

Wind-only KPIs:

| KPI | Value |
|---|---|
| Project IRR | 12.41% |
| Equity IRR | 10.55% |
| Equity NPV | USD −740,793 |
| Engine min DSCR | 0.867 (operating-year-1 covenant row) |

Every option moves the min DSCR by at most 0.001.

Readings of the 10 MW standardised-PPA limit:

- **A:** turbine plus battery power must not exceed 10 MW, so the battery is at most 0.5 MW.
- **B:** export at the connection point is capped at 10 MW.
- **C:** the battery sits outside the limit.

**Every cycled option keeps a black-start reserve.** It never discharges for revenue below
0.5 MWh (`battery.black_start_reserve_mwh`, an ASSUMPTION matching the held 0.5 MW / 0.5 MWh
option), so it can still black-start the turbine after the evening window. Without the reserve
a cycled battery is empty most evenings and has no black-start function. The no-reserve figure
is reported only to show what giving up the function would be worth.

| Option | Fits A | B: whole rate | C: whole rate | Stacked (B) | Equity IRR (B) | Pinned rate (B) |
|---|:-:|---:|---:|---:|---:|---:|
| **Held 0.5 MW / 0.5 MWh (black start only)** | **yes** | **−79k** | **−79k** | −79k | **10.42%** | −69k |
| Cycled 0.5 MW / 2 MWh, 0.5 MWh reserve | yes | −125k | −125k | −145k | 10.31% | −109k |
| Held 1 MW / 1 MWh | no | −153k | −153k | −153k | 10.29% | −137k |
| Cycled 1 MW / 4 MWh, reserve | no | −196k | −187k | −247k | 10.16% | −173k |
| Cycled 2.5 MW / 10 MWh, reserve | no | −611k | −406k | −721k | 9.46% | −547k |
| Cycled 10 MW / 40 MWh, reserve (UNCONFIRMED 40 MW reading) | no | −4.26M | −1.97M | −4.48M | 5.52% | −3.93M |

- **No option beats wind-only.** The cheapest black-start battery is **0.5 MW / 0.5 MWh,
  held**, with the soft (voltage-ramped) energisation the config assumes. It costs about USD 79k
  of project NPV and 0.13 points of equity IRR, and it fits every reading of the 10 MW limit.
- **It does not firm a grid down-ramp.** If a wind lull counts against the ramp limit, firming
  needs about the turbine's rated 9.5 MW whatever Blue Whale's allocation is; the allocation
  sets only the energy (see the down-ramp section). If a lull does not count, the turbine's own
  controls deliver the ramp limit (CEB s.3.1) and no battery has a grid-ramp role.
- **Cycling 0.5 MW / 2 MWh does not pay for its extra energy** once it keeps the reserve:
  - it delivers 544 MWh/yr (272 equivalent full cycles), against 723 without the reserve;
  - it costs −125k, against −65k if it gave up the black-start function;
  - on its own pre-tax cash flow it earns USD −50k NPV at a 6.9% IRR;
  - after the one-time adjustment: −119k;
  - break-evens: all-in capex of USD 78.5/kWh against the 140.74 mode, or a peak rate of
    72.01 LKR/kWh against 55.67.
- **Pinned rate.** The scenario's WACC moves with gearing, so adding a battery also
  re-discounts the whole wind project, at 10.632% instead of 10.619%. The last column holds the
  discount rate at the wind-only value; the difference (about 11k for held 0.5 / 0.5 and 17k for
  cycled 0.5 / 2) is that financing effect, not battery economics. It changes no sign and no ranking.
- **Reading B** clips anything above about 1 MW. The turbine reaches about 9.2 MW at the
  connection point and is windiest in the evening window. So 10 / 40 cycles 133 times a year
  under B, against 304 under C.
- **Monte Carlo:** 256 LHS trials of capex, battery RTE, residual fade and wind yield, each
  against wind-only at the same wind yield. No trial of any option beats wind-only. Held
  0.5 / 0.5: P50 −84k, P90 −98k. Cycled 0.5 / 2 with the reserve: P50 −158k, P90 −212k.
- **Battery RTE:** from 0.80 to 0.90, cycled 0.5 / 2 ranges from −140k to −107k.
- **The all-window-exports reading** is the only basis that turns positive: about +2.90M for
  cycled 0.5 / 2. It pays the battery premium on energy the turbine exports anyway, so it is not
  a battery case. PUCSL would have to say so explicitly.

Simplifications, each stated rather than modelled:

- The round-trip loss is booked on the wind energy for the whole 20-year term, so a cycled
  battery keeps cycling after the 15-year contract, where an operator would hold it. This is
  conservative: a few thousand USD of project NPV for cycled 0.5 / 2.
- Standby and auxiliary load (BMS, HVAC; a few kW) is excluded for every option. It would make
  each option slightly worse.
- The deterministic case has no battery fade; the Monte Carlo samples 0 to 2% a year. This
  favours the battery.
- The Monte Carlo wind-yield draw scales the engine's energy, not the hourly profile used for
  charging and headroom.

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

Both rows need the full 9.5 MW: a full drop from rated must be firmed at rated power at any
allowed ramp rate, so the allocation sets only the energy, from 0.075 MWh at the whole
substation limit to 0.79 MWh at a 0.955 MW/min share. Only the second case is priced below. If
a lull counts, a firming unit is needed at any allocation and replaces the black-start battery,
because it can also black-start the turbine. It is priced from **a generic battery supplier's
budgetary offer**:

- CIF, excluding duty and taxes, priced for many sites;
- flat at USD 90.00 per DC kWh, split into lines;
- lifted to all-in by the repository's mode (140.74 / 99.50);
- equipment ratings rounded: one skid of about 10 MW, a smallest block of about 20 MWh DC, and
  91% of DC energy usable.

A cycled block keeps 1.29 MWh in hand, the 0.79 MWh ramp energy plus the 0.5 MWh black-start
reserve, so it keeps both functions after the window.

| Firming unit | CIF | All-in | Project NPV change | Equity IRR |
|---|---:|---:|---:|---:|
| 9.5 MW / 0.79 MWh power-heavy, cells at the offer's DC rate | USD 357k | 505k | −547k | 9.66% |
| Same, power cells at 3× (assumption) | 492k | 696k | −754k | 9.35% |
| Supplier's smallest block with one skid (about 18 MWh usable), held | 1.80M | 2.55M | −2.73M | 6.84% |
| Same block, cycled at the whole rate with the 1.29 MWh reserve, reading C | 1.80M | 2.55M | **−0.83M** | 9.09% |
| Same block, cycled with the reserve, reading B | 1.80M | 2.55M | −1.37M | 8.42% |

The power-heavy price is weak, for three reasons:

- the offer's AC line is an allocation of a flat rate, not a cost;
- 9.5 MW from under 1 MWh is about 11C, beyond the energy cells offered, and no supplier has
  quoted such a unit;
- the offer is priced for many sites, so a single unit would cost more.

The smallest block is a product the supplier actually offered. If the battery may sit outside
the 10 MW limit, cycling it recovers most of its cost.

## What would change the answer

1. Whether a wind lull counts against the ramp limit (which decides whether a 9.5 MW firming
   unit is needed at all), and the NSO's allocation for the substation (which sets its energy).
2. A PUCSL tariff that covers wind + BESS, or confirmation of the whole-rate reading.
3. Whether a battery may sit outside the 10 MW standardised-PPA limit (reading C).
4. A quotation for a power-heavy (≥ 2C) unit.
5. The energy the turbine's black-start sequence actually needs, which sets the reserve (0.5 MWh
   assumed). A smaller reserve narrows the gap between the held and cycled options.
