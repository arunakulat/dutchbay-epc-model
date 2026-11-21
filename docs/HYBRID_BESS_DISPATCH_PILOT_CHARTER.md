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
   in the ledger.
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
| Revenue basis | A time-of-day energy tariff for energy delivered at the POC from the battery, with named periods | Not the existing CEB capacity-charge BESS arrangement, which is CEB-dispatched and grants no dispatch right (#1578, #1629 keep their residuals). Not merchant arbitrage. |
| Tariff values | Per-period energy prices declared in the screening YAML | The charter fixes no figure. Public-repository rules apply: no private figures. |
| Charging source | Co-located renewable only, unless the YAML assumes grid charging and a grid charging price | One switch, declared, never inferred. |
| Dispatch right | The project chooses its hourly instruction within the assumed tariff | This is the assumption that makes optimisation meaningful. No source says the project holds it. |
| LD and availability terms | None modelled | Stated in `ld_terms` text, as the ledger already requires. |
| Degradation and augmentation | Realised equivalent full cycles feed the existing SoH and augmentation treatment | Reuse the battery fade and augmentation conventions already on `main`; no new fade curve. |

Any later evidenced arrangement replaces this table through #1816's own done-when, not by editing
assumptions into facts.

## The two oracles

Both oracles are independent of the code they check, as `TEST-01` requires: neither may share
the implementation's objective function, aggregation code or constants module.

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
  wired into `finance/`, `analytics.evaluation_v14` or any committed KPI. IRR, XIRR and NPV, if a
  screening view shows them, come only from `finance.irr`.
- **Responsiveness.** Each pinned value is paired with a guard that moves it: a price, efficiency
  or SoH change must move revenue in the stated direction.

## Baselines and stresses (stage e)

Every screening result is shown beside two baselines on the same chronology: **no BESS** and
**BESS held idle** (capex and O&M only). Stresses: tariff spread, round-trip efficiency, SoH and
degradation, outages, and terminal SOC target. A result with no positive margin over the idle
baseline is reported as such, not tuned away.

## Delivery: separate slices after this charter

This charter is R1/R2 documentation. Implementation is separate, config-first, default-off, and
each slice is its own small PR under `RECRUIT-01` review:

| Slice | Content | Expected class |
|---|---|---|
| P1 | Pilot screening block schema (default off, every assumed term labelled) and the optimisation oracle's small cases | R2 |
| P2 | Deterministic dispatcher for the one assumed tariff, passing through the existing ledger | R2 |
| P3 | Realised cycles to the existing SoH and augmentation treatment | R2 |
| P4 | Screening aggregation to annual periods, with the finance oracle and both baselines | R2, or R3 with owner sign-off if any committed output changes |
| P5 | Stresses and a labelled screening report section | R2 |

A slice that would change a committed KPI, wire into the finance path, or let a scenario enable
the pilot by default needs an R3 review pair and the owner's sign-off first.

## Out of scope

- The capacity-charge BESS economics and the Blue Whale wind + BESS options study as they stand.
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
