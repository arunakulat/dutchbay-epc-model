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
  scenario SHA-256; model 15.29.0; scenario `scenarios/blue_whale_wind_lot5b_2026.yaml` v0.7.
- Every KPI comes from `analytics.evaluation_v14.evaluate_with_overrides` (ARCH-04).

> **Addendum (`#1578` U2, 17 November 2026):** The options now run for any scenario that
> declares a `storage_options` block (contract `#1754`):
> `scripts/run_wind_bess_options_v14.py scenario=<path>`, with the method inputs (revenue
> bases, Monte Carlo settings, hold text) in `conf/wind_bess_options.yaml` and the evaluation in
> the site-neutral `analytics/wind/wind_bess_options_runner.py`. The turbine, battery, options,
> tariff basis, grid limits, hourly-profile reference, firming supplier and wind-yield
> uncertainty below now live in `scenarios/blue_whale_wind_lot5b_2026.yaml`'s block; the wind
> tariff comes from the scenario itself. A scenario without the block is reported as not
> applicable. The config and CLI named above remain as a single-site adapter: its output is
> byte-identical, and the block-driven run reproduces every figure in the committed summary.
> The summary was regenerated only because the scenario file gained the block; its
> `scenario_sha256` is the one value that changed. The same scenario also carries the
> `equipment_cost_parity` block (`#1755`), which reproduces the single-site parity result.
>
> **Addendum (`#1823`, 21 November 2026):** The recommended held 0.5 / 0.5 option is now part
> of the scenario's own project: `storage_options.headline_option: held_0_5_0_5` (scenario
> v0.7, model 15.29.0) carries it into the headline KPIs, debt sizing and reports, capex and
> O&M only, built by the same `scenario_with_battery` this analysis uses
> (`analytics/storage_headline.py`). The headline KPIs therefore equal this summary's figures
> for that option (project NPV USD 1,319,305, project IRR 12.31%). This analysis still compares
> every option with the wind-only case: it reads the scenario without the headline request.
> The summary was regenerated only because the scenario file and the model version changed.
> Tariff basis, a working assumption: the held battery earns no storage tariff.

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
- **For the short units, that cost is a floor.** Every option is priced at the all-in mode of
  USD 140.74 per kWh, the price of a 4-hour product. Power-related and per-site costs (the
  inverter skid, the EMS) do not shrink with the energy, so a 1-hour unit costs more per kWh. Priced bottom-up from the generic
  supplier's own lines (the skid pro rata by power, the EMS once per site, the DC energy at the
  offer's DC rate, the same all-in factor; `bottom_up_price` in the summary), the held
  0.5 MW / 0.5 MWh unit costs about USD 141k all-in instead of 70k, and its project NPV change is
  about −147k instead of −79k. Cycled 0.5 / 2 becomes −162k, held 1 / 1 −233k and cycled 1 / 4
  −221k (reading B). Held 1 / 1 and cycled 1 / 4 swap places at that price (−233k against
  −221k, where the flat price ranks held 1 / 1 ahead at −153k against −196k), but that swap
  depends on where the all-in factor is calibrated, so it is not a finding. The held
  0.5 / 0.5 unit stays the cheapest option and the recommendation, and no option beats
  wind-only. A small grid-forming inverter may carry a further premium.
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
- **Battery RTE:** from 0.80 to 0.90, cycled 0.5 / 2 ranges from −140k to −107k. The grid is
  not smooth: the scenario's WACC moves in small steps with gearing, so one step between 0.865
  and 0.88 moves the result by about 5.6k, against about 1.3k per 0.005 elsewhere. The
  break-evens are found by bisection and can land on such a step.
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
- **Tariff duration.** PUCSL's methodology (s.5.1.1, s.5.2.1) assumes 4 hours at nominal
  capacity (`battery.duration_h_for_tariff`, recorded but not read). Revenue here is paid per
  delivered kWh. An option that keeps the 0.5 MWh reserve delivers under 4 hours at its
  nameplate power: cycled 0.5 / 2 at most 1.5 MWh a window (3 hours at 0.5 MW), and the cycled
  smallest block under 2 hours at 9.5 MW. Declaring a lower nominal power for the tariff would
  leave these figures nearly unchanged, since the revenue follows the delivered energy.
- The round-trip loss is taken from the wind block's capacity factor, so it inherits the
  turbine's 0.5%/yr degradation and is slightly understated in later years (about 3k for
  cycled 0.5 / 2).

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

The triangle treats a lull as an instantaneous loss of rated output, the worst case. Real lulls
take minutes, so these energies are upper bounds.

Both rows need the full 9.5 MW: a full drop from rated must be firmed at rated power at any
allowed ramp rate, so the allocation sets only the energy, from 0.075 MWh at the whole
substation limit to 0.79 MWh at a 0.955 MW/min share. Only the second case is priced below. If
a lull counts, a firming unit is needed at any allocation and replaces the black-start battery,
because it can also black-start the turbine. It is priced from **a generic battery supplier's
budgetary offer**:

- CIF, excluding duty and taxes, priced for many sites;
- flat at USD 90.00 per DC kWh, split into lines;
- lifted to all-in by the repository's mode over the offer per usable kWh, 140.74 / (90.00 / 0.91),
  using the rounded usable fraction;
- equipment ratings rounded: one skid of about 10 MW, a smallest block of about 20 MWh DC, and
  91% of DC energy usable;
- long-term service and maintenance at 2% of CIF a year, a generic ASSUMPTION not taken from the
  offer.

A cycled block keeps 1.29 MWh in hand, the 0.79 MWh ramp energy plus the 0.5 MWh black-start
reserve, so it keeps both functions after the window. The held power-heavy unit keeps only the
0.79 MWh ramp energy. That covers a down-ramp or a black start, but not one straight after the
other before the unit recharges. Holding both would need about 0.5 MWh more cells, roughly USD
60k more all-in at the offer's DC rate (the assurance review's estimate; not run here).

| Firming unit | CIF | All-in | Project NPV change | Equity IRR |
|---|---:|---:|---:|---:|
| 9.5 MW / 0.79 MWh power-heavy, cells at the offer's DC rate | USD 357k | 508k | −550k | 9.65% |
| Same, power cells at 3× (assumption) | 492k | 700k | −758k | 9.34% |
| Supplier's smallest block with one skid (about 18 MWh usable), held | 1.80M | 2.56M | −2.74M | 6.83% |
| Same block, cycled at the whole rate with the 1.29 MWh reserve, reading C | 1.80M | 2.56M | **−0.84M** | 9.07% |
| Same block, cycled with the reserve, reading B | 1.80M | 2.56M | −1.39M | 8.40% |

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
6. Whether CEB lets the turbine be energised from its own battery before the network returns.
   An embedded generator normally has loss-of-mains protection and may not island or reconnect
   until the network is back. In that case the battery's role is auxiliary supply during an
   outage (yaw, pitch, heating), not a faster restart, and its sizing basis changes. No CEB text
   on islanding is in the repository. It cannot make any option beat wind-only.
7. A quotation for a small (about 0.5 MW, 1-hour) grid-forming unit, which replaces the
   bottom-up estimate.
