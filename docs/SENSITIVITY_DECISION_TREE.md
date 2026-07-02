# Sensitivity Analysis — Method-Selection Decision Tree

**Version**: 1.0.0
**Date**: July 2, 2026
**Modules**: `analytics.sensitivity` (local tornado), `analytics.sensitivity.global_sa` (Morris / Sobol / PAWN)
**Framework Compliance**: GWTF, CASPER, CESSPIT, CCCDIR

---

## Purpose

DutchBay carries four complementary sensitivity methods. They are **not**
interchangeable — each answers a different question, at a different cost, with a
different blind spot. This page is the decision tree for *which* to reach for, and
in *what order*, so an analyst does not (for example) run an expensive Sobol
decomposition across a 12-driver box when a cheap Morris screen would have told them
that only three drivers matter.

The recommended workflow is a **funnel**:

```
                       ┌─────────────────────────────────────────────┐
                       │  All candidate drivers (D large, box wide)   │
                       └───────────────────────┬─────────────────────┘
                                               │
              (1) SCREEN — cheap, ranks         ▼
              ┌──────────────────────────────────────────────────────┐
              │  MORRIS elementary effects (mu_star / sigma)          │
              │  cost ~ N·(D+1)   →   optional optimal-trajectory     │
              │  subset: k·(D+1),  2 <= k < N   (#617)                │
              └───────────────────────┬──────────────────────────────┘
                                      │  keep the top-ranked drivers
              (2) DECOMPOSE            ▼
              ┌──────────────────────────────────────────────────────┐
              │  SOBOL first/total-order (S1 / ST)                    │
              │  cost ~ n·(D'+2), D' = screened subset                │
              │  ST >> S1  ⇒  interactions the tornado cannot see     │
              └───────────────────────┬──────────────────────────────┘
                                      │
              (3) CROSS-CHECK          ▼
              ┌──────────────────────────────────────────────────────┐
              │  PAWN moment-independent (KS-based)                   │
              │  given-data: reuse the existing sample                │
              │  robust on skewed / covenant-pinned KPIs where        │
              │  variance-based Sobol misbehaves                      │
              └───────────────────────┬──────────────────────────────┘
                                      │
              (4) PRESENT              ▼
              ┌──────────────────────────────────────────────────────┐
              │  LOCAL one-way TORNADO (analytics.sensitivity)        │
              │  per-driver low/base/high bars for the lender pack    │
              │  interpretable, but blind to interactions             │
              └──────────────────────────────────────────────────────┘
```

---

## The four methods

| Method | Question it answers | Cost (evals) | Sees interactions? | Blind spot |
| --- | --- | --- | --- | --- |
| **Morris** (screen) | Which drivers matter *at all*? Rank them. | `N·(D+1)` (or `k·(D+1)` with optimal-trajectories) | Flags them via high `sigma`, does not quantify | A coarse ranking, not a variance budget |
| **Sobol** (decompose) | How much of the output *variance* does each driver own, alone (`S1`) and with all interactions (`ST`)? | `n·(D+2)` | Yes — `ST − S1` is the interaction share | Needs a power-of-2 `n`; misbehaves on (near-)constant / covenant-pinned outputs |
| **PAWN** (cross-check) | Does a driver shift the whole output *distribution* (not just its variance)? | given-data (reuses any sample) | Implicitly (distributional) | Finite-sample KS noise floor at low `n`; rank-only |
| **Tornado** (present) | For the lender pack: what is the low/high swing of each driver, one at a time? | `2·D` (one sweep per driver) | **No** — one-at-a-time by construction | Cannot see any coupling between drivers |

All four are **opt-in, additive, read-only** analysis layers. None touches the
deterministic base case, and none moves a committed KPI (CESSPIT: config-first;
CCCDIR: everything flows through the canonical `evaluate_with_overrides` gateway).

---

## Step 1 — Morris screening (and the optimal-trajectories knob)

Morris is the cheap first pass. It draws `N` random "trajectories" (one-at-a-time
walks through the input box) and reports, per driver:

- **`mu_star`** — the mean absolute elementary effect. This is the importance rank.
- **`sigma`** — the spread of the elementary effects. A high `sigma` flags a driver
  whose effect is non-linear or interacts with others (the cheap analogue of Sobol's
  `ST >> S1`).

Run the top-ranked drivers on to Sobol; drop the inert tail.

### Optimal trajectories (#617)

By default `run_morris` samples `n_trajectories` trajectories directly. For a wide
box or many drivers, most randomly-drawn trajectories cluster, wasting evaluations.
SALib's **Campolongo/Ruano optimal-trajectory** selection draws a larger candidate
pool and keeps the subset that maximises the spread in the input space:

```python
from analytics.sensitivity.global_sa import run_morris

# Draw 100 candidate trajectories, keep the 10 with the widest coverage.
res = run_morris(
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    n_trajectories=100,
    optimal_trajectories=10,   # 2 <= k < n_trajectories; None = vanilla Morris
)
assert res["optimal_trajectories"] == 10
assert res["n_runs"] == 10 * (res["problem"]["num_vars"] + 1)
```

or from the CLI (Morris-only knob):

```bash
python scripts/run_global_sensitivity.py \
  --config scenarios/dutchbay_lendercase_2025Q4.yaml \
  --method morris --n 100 --optimal-trajectories 10
```

**OSeMOSYS guidance:** the energy-systems community (OSeMOSYS / SALib docs) suggests
**"10 optimal trajectories from a pool of 100"** as a workable default, and warns
that the brute-force selection cost grows fast — going **no higher than 4 levels
(`num_levels`) from a pool of 100** with the brute-force path. SALib's default
`local_optimization=True` (Ruano's iterative selection) relaxes that ceiling; DutchBay
leaves `local_optimization` at the SALib default and exposes only the
`optimal_trajectories` count.

**Contract (CESSPIT, fail-loud):** `optimal_trajectories` must satisfy
`2 <= optimal_trajectories < n_trajectories`. `run_morris` validates this itself and
raises a `ValueError` — it does **not** defer to SALib, whose own bound check is
inconsistent (it silently accepts `0` and only rejects `>= N` / `< 2`). `None` (the
default) is the vanilla path and is **byte-identical** to prior behaviour.

**Determinism (MRM-01):** the subset selection is seeded, so a fixed `seed` yields a
deterministic optimised sample.

---

## Step 2 — Sobol decomposition on the screened subset

Once Morris has ranked the drivers, run Sobol on the handful that matter. Sobol
splits the output variance into:

- **`S1`** — first-order: the variance a driver explains *acting alone*.
- **`ST`** — total-order: the driver's variance *including every interaction*.

`ST >> S1` is the diagnostic that interactions are material — the variance-based
analogue the one-way tornado structurally cannot produce. DutchBay flags a driver
`interactive` when `ST − S1 > INTERACTION_TOL` (0.05).

`n` **must be a positive power of 2** — SALib's base-2 Sobol' sequence loses its
balance properties otherwise, and `run_sobol` fails loud rather than silently
degrading (#586). A structurally-flat (covenant-pinned) metric yields undefined
Sobol indices, so it is flagged `flat_metric` with zeroed indices rather than
reported as noise (#575).

---

## Step 3 — PAWN cross-check on skewed / covenant-pinned KPIs

Variance-based Sobol assumes the output variance is a meaningful summary. For a
DSCR-floor-pinned or otherwise skewed / bimodal KPI it is not. **PAWN** (Pianosi &
Wagener) measures a driver's influence by the Kolmogorov–Smirnov distance between the
unconditional output CDF and the CDFs conditioned on that driver's slices — a
*distribution*-based index bounded in `[0, 1]` that stays well-behaved where Sobol
misbehaves.

PAWN is a **given-data** method: it can reuse the sample already drawn for Sobol
(or run its own LHS sample). Note a finite-sample noise floor — at the defaults
(`n=256`, `s=10`) even an inert driver measures a median KS of ~0.15, so low-end
ranking positions are not evidence of influence (the floor roughly halves as `n`
doubles). Use PAWN to *confirm* the Sobol/Morris ranking on the awkward KPIs, not to
discover marginal drivers.

---

## Step 4 — Local tornado for the lender presentation

The one-way tornado (`analytics.sensitivity`, surfaced in the lender pack) sweeps one
driver at a time between its low/base/high and plots the resulting swing. It is the
most *interpretable* view — a lender reads a tornado bar instantly — but it is blind
to interactions by construction. Use it to **present** the drivers the variance-based
methods have already established as material; do not use it to *decide* which drivers
matter when the structure is coupled (flat-LKR tariff erosion, FX ↔ LKR, capex ↔
gearing ↔ DSCR-sculpt), because it will silently miss the interaction terms.

---

## Quick reference

- **Just tell me what matters, cheaply** → Morris (`run_morris`), optionally with
  `optimal_trajectories` on a wide box.
- **Quantify the variance budget + interactions** → Sobol (`run_sobol`) on the
  screened subset, `n` a power of 2.
- **The KPI is skewed / covenant-pinned and I don't trust the variance** → PAWN
  (`run_pawn`), reusing the sample.
- **I need a bar chart for the lender pack** → local tornado (`analytics.sensitivity`).

---

## References

- Morris, M. D. (1991). *Factorial sampling plans for preliminary computational
  experiments.* Technometrics.
- Campolongo, F., Cariboni, J., & Saltelli, A. (2007). *An effective screening design
  for sensitivity analysis of large models.* Environmental Modelling & Software.
  (The optimal-trajectory enhancement `optimal_trajectories` exposes.)
- Ruano, M. V., Ribes, J., Seco, A., & Ferrer, J. (2012). *An improved sampling
  strategy based on trajectory design for application of the Morris method…*
  (SALib's `local_optimization=True`.)
- Sobol, I. M. (2001). *Global sensitivity indices for nonlinear mathematical models
  and their Monte Carlo estimates.*
- Pianosi, F., & Wagener, T. (2018). *Distribution-based sensitivity analysis from a
  generic input-output sample* (PAWN).
- SALib documentation — `SALib.sample.morris.sample` (`optimal_trajectories`,
  `local_optimization`, `num_levels`); OSeMOSYS "10-from-100 at step-size-4" guidance.
