# Hybrid BESS dispatch pilot: charter on assumed terms

Status: **charter, screening only** (#1816, roadmap milestone P1.4 in
[`CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md`](CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md)).
Written against `main` `4cfed491` (15.28.0). This document scopes work; it implements none. It
changes no code, no committed KPI, no finance path, no release and no `HOLD`. F-5, #1110 and
`v15.6.1` stand.

## Authority and what it covers

On 2026-11-21 at 04:55Z the owner chose **"Scope the pilot now"** for #1816 (recorded on #1816).
The decision's stated consequence: a writer drafts this charter on **assumed** terms, and any
revenue result stays screening-only and is not relied on.

So every contract or revenue term below is an **assumption with no source claimed**. #1816's
original done-when (an owner-recorded, evidenced dispatch or revenue arrangement, and specialists'
reliance limits) is **not** met by this charter and stays open. A pilot result built under this
charter cannot be cited as evidence that any such arrangement exists or is worth a given amount.

## What already exists, and is reused rather than rebuilt

Roadmap P1.4 names five stages, (a) to (e). Stages (a) and (b) landed under #1402:

- **(a) Chronological input contract.** `analytics.contracts_v14.ChronologicalDispatchInput`:
  hourly UTC timeline, wind and solar generation, signed dispatch instruction, shared POC limit,
  outage masks, charge source, one-way efficiencies, static SoH, SOC window, initial and final
  SOC, tariff, LD and provenance text. No implicit defaults.
- **(b) Deterministic feasibility ledger.** `analytics.storage_dispatch.simulate_dispatch` and
  the self-verifying `DispatchLedger`. It follows supplied instructions, chooses nothing, values
  nothing, and has no cashflow path. Its whole-ledger energy balance, custody, continuity and
  bound checks are documented in [`BESS_CHRONOLOGICAL_LEDGER.md`](BESS_CHRONOLOGICAL_LEDGER.md).

The pilot therefore adds stages (c) to (e) on top of that ledger. It does **not** introduce a
second SOC model, a second energy balance, or a second input contract.

Three more pieces on `main` overlap the pilot. Each slice must keep to the relationship stated
here, or bring a change to it for review first:

- **`analytics.storage_dispatch.evaluate_chronological_dispatch`**, the default-off
  `chronological_dispatch` scenario block that runs the #1402 ledger from configuration. P1
  extends that block (or states in its PR why it cannot) rather than adding a parallel block.
- **`solar_resource/pv_bess_dispatch.py`**, an hourly PV-charged BESS dispatcher with fixed
  clock-time discharge windows, its own SOC recursion, no optimisation and no grid charging, paid
  through `TariffConfig`'s `priority` and `other` window rates. The pilot does not add another
  tariff schema beside it: P1's named tariff periods reuse or generalise its `Window` and
  `DispatchConfig` form (local clock times, non-overlapping windows, one rate per window), or the
  P1 PR states why they cannot. Its fixed-window rule becomes the pilot's **rule-based baseline**
  in stage (e), run through the #1402 ledger so the comparison shares one energy balance. The
  pilot does not change that module or the solar + BESS results it feeds.
- **`finance/bess_revenue.py`**, whose `energy_tariff` revenue model (in
  `SUPPORTED_BESS_REVENUE_MODELS`) pays a solar-charged BESS a flat tariff at a fixed number of
  cycles a year, and which holds the state-of-health fade and `augmentation_schedule` treatment.
  The pilot's screening revenue does not replace, feed or wire into `energy_tariff` or any
  `revenue.model`. P3 may **call** the fade and augmentation helpers read-only, so there is one
  degradation convention; no slice edits `finance/`.

## The SOC/POC ledger the pilot must keep

Every pilot result is a `DispatchLedger`, so the #1402 identity holds for every run:

```text
wind input + solar input + grid import
  = POC delivery + change in stored energy
    + charge loss + discharge loss
    + wind/solar curtailment + wind/solar outage energy
```

The pilot adds these invariants, each tested with a hostile case that makes it bind:

1. **Instructions come from the dispatcher, then go through the ledger.** The pilot's dispatcher
   proposes `dispatch_instruction_mw`; the existing ledger decides what is physically feasible.
   The dispatcher never writes a ledger row itself.
2. **No simultaneous charge and discharge** in any hour, in the dispatcher's own plan as well as
   in the ledger. The ledger takes one signed instruction per hour, so it cannot express both at
   once; the hostile case and the oracle's negative control must therefore target the
   dispatcher's (or the reference programme's) separate charge and discharge variables before
   they are netted into one instruction.
3. **No double claim on the POC.** Generation export and battery discharge share one POC limit
   under the ledger's `gross_sum` basis; a plan that needs more is clipped and the clip recorded
   as unmet instruction.
4. **Terminal SOC is a constraint, never a balancing entry.** A plan that misses the final SOC
   target is infeasible, not silently topped up.
5. **Grid charging stays grid charging.** A charge from the grid is never relabelled renewable,
   and an assumed arrangement that forbids grid charging sets `charge_source` so.
6. **Default off is inert.** With the pilot block absent or disabled, every committed scenario's
   KPIs and result keys are byte-identical to `main`.

## Assumed terms (no source claimed)

The roadmap's decision gate asks for one contractual revenue basis. Under this charter it is
**assumed**, not evidenced. The pilot carries exactly one assumed arrangement, chosen in its
screening YAML, with every term labelled `assumption` and `source: none`:

| Term | Assumed form | Note |
|---|---|---|
| Revenue basis | A time-of-day energy tariff for energy delivered at the POC from the battery, with named periods | Not the existing CEB capacity-charge BESS arrangement, which is CEB-dispatched and grants no dispatch right, and not the flat `energy_tariff` model in `finance/bess_revenue.py`. Not merchant arbitrage. |
| Tariff periods | Named local clock-time windows, each with one rate | Reuses or generalises the `Window` form of `solar_resource/pv_bess_dispatch.py` (see above). |
| Tariff currency | One currency, declared in the screening YAML | Never inferred from the site or the scenario's other tariffs. |
| Tariff indexation | Declared: flat, or indexed to a named index the scenario already carries | No implicit escalation. A declared index that the scenario does not carry is refused. |
| Arrangement tenor | Declared first and last project year in which the assumed tariff applies | Outside the tenor the battery earns nothing under this arrangement; no default tenor. |
| Tariff values | Per-period energy prices declared in the screening YAML | The charter fixes no figure. Public-repository rules apply: no private figures. |
| Charging source | Co-located renewable only, unless the YAML assumes grid charging | One switch, declared, never inferred. |
| Grid charging price | Only when grid charging is assumed: per-period price, its currency and its indexation, declared like the tariff | Absent grid charging, no charging price exists and none is defaulted. |
| Dispatch right | The project chooses its hourly instruction within the assumed tariff | This is the assumption that makes optimisation meaningful. No source says the project holds it. |
| LD and availability terms | None modelled | Stated in `ld_terms` text, as the ledger already requires. |
| Degradation and augmentation | Realised equivalent full cycles feed the existing SoH and augmentation treatment | Reuse the battery fade and augmentation conventions already on `main`; no new fade curve. |

Every row's value enters the screening YAML labelled `assumption` with `source: none`; a term
with no declared value is refused, never defaulted. Any later evidenced arrangement replaces this
table through #1816's own done-when, not by editing assumptions into facts.

**Time-shift, not arbitrage.** With grid charging assumed and the project choosing its hourly
instruction under a time-of-day tariff, the dispatcher will charge in cheap periods and deliver
in dear ones. A grid-charging variant's margin is labelled **assumed contracted time-shift** and
is never presented as merchant or market arbitrage value.

## The two oracles

`TEST-01` requires finance-material code to answer to an oracle that did not originate in the
same change that introduced it. So each oracle merges in a slice **before** the code it checks
(see "Delivery"). In addition, as this charter's own condition, neither oracle may share the
implementation's objective function, aggregation code or constants module.

### Optimisation oracle (small-case reference)

- **Instances.** Small fixed chronologies (for example 4 to 8 hours) with rational inputs, chosen
  so the optimum is hand-derivable or exhaustively enumerable, plus seeded random small cases.
- **Reference.** A transparent linear programme for one assumed tariff, solved by a different
  route from the pilot's dispatcher. Exhaustive enumeration over a coarse instruction grid is
  acceptable as a second reference on the smallest cases. The lock already carries `scipy` and
  `ortools`; whichever the pilot uses, the oracle uses the other or enumeration.
- **Agreement.** Objective values agree within a stated tolerance, and both plans pass the
  ledger. Where the optimum is not unique, compare objective value and ledger validity, not the
  plan itself.
- **Negative controls.** A plan that charges and discharges in one hour, breaches the POC limit,
  or misses the terminal SOC must fail; a mutated objective sign must change the answer.

### Finance oracle

- **Instances.** The same small cases, with annual aggregation hand-computed: delivered energy
  times assumed period price, minus assumed charging cost, with any augmentation cost placed in
  its year.
- **Reference.** A closed-form or spreadsheet-style calculation written separately from the
  pilot's aggregation code, checked against the pilot's annual revenue, charging cost and
  augmentation lines.
- **Boundary.** The finance oracle checks the pilot's **screening** aggregation only. Nothing is
  wired into `finance/`, `analytics.evaluation_v14` or any committed KPI. Calling the
  `finance/bess_revenue.py` fade and augmentation helpers read-only (P3) is reuse, not wiring;
  editing them is out of scope. IRR, XIRR and NPV, if a screening view shows them, come only from
  `finance.irr`.
- **Responsiveness.** Each pinned value is paired with a guard that moves it: a price, efficiency
  or SoH change must move revenue in the stated direction.

## Baselines and stresses (stage e)

Every screening result is shown beside three baselines on the same chronology: **no BESS**,
**BESS held idle** (capex and O&M only) and the **rule-based fixed-window dispatch** of
`solar_resource/pv_bess_dispatch.py`, run through the #1402 ledger. Stresses: tariff spread, round-trip efficiency, SoH and
degradation, outages, and terminal SOC target. A result with no positive margin over the idle
baseline is reported as such, not tuned away.

## Delivery: separate slices after this charter

This charter is **R2** documentation (`RECRUIT-01` module 1 lists charters as
`R2_LOAD_BEARING`). The owner's ruling on #1816 makes every implementation slice after it a
separate, config-first **R3** slice, with a `RECRUIT-01` review pair and the owner's sign-off
before it merges. Each slice is default-off and its own small PR:

| Slice | Content | Class |
|---|---|---|
| P1 | Pilot screening block (extending `chronological_dispatch`, default off, every assumed term labelled), the optimisation oracle's small cases, and the finance oracle's hand-computed small cases | R3, owner sign-off |
| P2 | Deterministic dispatcher for the one assumed tariff, passing through the existing ledger, checked against P1's optimisation oracle | R3, owner sign-off |
| P3 | Realised cycles to the existing SoH and augmentation treatment (read-only calls into `finance/bess_revenue.py`) | R3, owner sign-off |
| P4 | Screening aggregation to annual periods, checked against P1's finance oracle, with the three baselines | R3, owner sign-off |
| P5 | Stresses and a labelled screening report section | R3, owner sign-off |

Both oracles land in P1, before the dispatcher (P2) and the aggregation (P4) they check, so
neither oracle originates in the change that introduces the code it judges (`TEST-01`). A slice
that would also change a committed KPI, wire into the finance path or let a scenario enable the
pilot by default must say so in its PR, with the KPI table, before its sign-off is sought.

## Out of scope

- The capacity-charge BESS economics and the Blue Whale wind + BESS options study as they stand.
- Any change to `finance/bess_revenue.py` (including its `energy_tariff` model) or to
  `solar_resource/pv_bess_dispatch.py` and the solar + BESS results it feeds.
- Merchant arbitrage, ancillary services and revenue stacking.
- The #1075, #1076, #1078 authenticated feeder evidence chain and any network study.
- The user-gated #924 feasibility study.
- Any lender, Board or reliance use. A screening result under this charter is not a lender
  representation (F-5) and is not cleared for circulation (#1110).

## Acceptance for the pilot as a whole

From roadmap P1.4, restated for assumed terms: every MWh entering the ledger exits as delivered
energy, stored-energy change or a named loss; no wind, solar, BESS or POC energy is double
counted; SOC and power constraints bind in hostile cases; the optimisation reference and the
finance oracle agree with the pilot on small instances; every revenue term is labelled assumed
with no source; default-off cases are unchanged; and no optimised value is presented as if a
contract granted the dispatch right.
