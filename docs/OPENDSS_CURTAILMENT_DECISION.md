# OpenDSS power-flow curtailment: adapt + defer (ADR, #621 / benchmarking §5 roadmap)

Status: **Accepted** (2026-07). Decision: **do NOT build the OpenDSSDirect power-flow
integration now.** Keep the existing energy-balance shared-POI curtailment seam
(`analytics/portfolio/poi_curtailment.py`) as the modelled surface, gate any future
power-flow refinement behind explicit config, and require **two** preconditions before the
integration is opened as a build: (a) real CEB feeder / network data, and (b) explicit user
authorization for the new `OpenDSSDirect.py` runtime dependency.

## Context

The 2026-07-01 SOTA benchmarking report (§5 roadmap) and the prior grid co-simulation proposal
evaluation both raised OpenDSS (OpenDSSDirect + QSTS) as a way to model **network-limited**
curtailment: instead of a single shared point-of-interconnection (POI) MW cap, run a
quasi-static time-series power flow over the actual feeder to find where thermal/voltage limits
bind and how much generation is spilled as a result.

The prior grid co-sim verdict (recorded in the analyst's memory,
`dutchbay-grid-cosim-proposal-eval`) already settled the shape of this: **reject** a
PySAM-primary + HELICS co-simulation stack, but **adapt + defer** the OpenDSS curtailment idea —
fold a network-derived curtailment percentage into the existing loss stack, gated on real feeder
data, default-off. This ADR is the code-repo record of that verdict against the current
codebase, so the deferral is a documented decision and not a silent omission.

## Evidence (verified 2026-07-02 against branch point `461a2b6`, not asserted)

| fact | value |
|---|---|
| POI curtailment seam exists | `analytics/portfolio/poi_curtailment.py` — `resolve_shared_poi_curtailment(config)` and `estimate_poi_curtailment(...)` |
| It is opt-in / default-off | `resolve_shared_poi_curtailment` returns `None` unless `generation.shared_poi.limit_mw` is set **and** ≥2 technologies supply `generation.technologies.<tech>.hourly_profile_mw`; otherwise the interaction is not modelled |
| Curtailment basis today | energy-balance against a single scalar POI export cap on summed per-tech hourly injection (`combined − poi_limit_mw`), NOT a network power flow |
| `opendss` / `OpenDSSDirect` dependency | **absent** — `grep -ri opendss` over `requirements.txt`, `pyproject.toml` and the source tree returns nothing |
| CEB feeder / network model in repo | **absent** — no `.dss` circuit files, no feeder topology, no per-node impedance/rating data |
| DutchBay's own POI | the 220 kV evacuation line is a **separate CEB-funded project sized for the plant**, so the POI is not a binding constraint for the committed DutchBay scenarios (memory: `dutchbay-eia-envision-sep2025`, `dutchbay-sppa-ceb-standardized`) |
| Contract for the result | `analytics.contracts_v14.SharedPoiCurtailmentResult` (frozen dataclass) already centralises the curtailment result shape (CCCDIR) |

Assessment: the honest, physically-correct **energy-balance** curtailment interaction is
already modelled and opt-in. A full OpenDSS power-flow model would add a heavy new runtime
dependency and a large calibration surface (feeder topology, conductor ratings, tap/regulator
settings, load allocation) for which **no input data exists in this project**. Building it now
would mean either fabricating a feeder — producing a precise-looking but unfounded curtailment
number (a CESSPIT violation: a silent, unvalidated assumption presented as a result) — or
shipping dead, un-exercisable code. Neither is acceptable.

## Decision

1. **Do not build the OpenDSS integration now.** No `OpenDSSDirect.py` dependency is added to
   `requirements.txt` / `pyproject.toml`; no `.dss` circuit or feeder model is introduced.
2. **Keep the energy-balance shared-POI seam as the modelled curtailment surface**, unchanged
   and default-off. `resolve_shared_poi_curtailment` continues to return `None` absent the
   opt-in `generation.shared_poi.limit_mw` + per-tech hourly profiles, so every committed
   scenario stays byte-identical.
3. **Any future power-flow refinement is a config-gated, default-off extension of that same
   seam** — a network-derived curtailment percentage folded into the existing loss stack, NOT a
   new mandatory pipeline stage. The scalar `poi_limit_mw` cap is the degenerate (single-node)
   case of a network limit, so the extension slots in behind the existing gate rather than
   forking a parallel curtailment path.

## Gate (both preconditions required before this is opened as a build)

Opening the OpenDSS integration as a build requires **all** of:

1. **Real CEB feeder / network data** — an actual `.dss` (or equivalent) circuit for the
   relevant evacuation network with conductor ratings, node voltages and load allocation.
   Absent this, any power-flow curtailment number is unfounded.
2. **Explicit user authorization for the new `OpenDSSDirect.py` runtime dependency** — it is a
   new hard dependency and a new licence/security surface; per repo discipline a dependency of
   that weight is not added inside a feature dolphin without sign-off.
3. **A default-off config gate** (e.g. `generation.shared_poi.network_model`) so the power-flow
   path is opt-in and every committed scenario remains byte-identical — the OpenDSS run must
   never become a mandatory dependency of the canonical pipeline.

Until all three hold, the deferral stands and the energy-balance seam is the curtailment model.

## Re-evaluation triggers

Revisit this ADR (open an issue, do not silently build) when **any** of:

1. Real CEB feeder data for a DutchBay-relevant network becomes available.
2. A committed scenario acquires a POI that is genuinely network-limited (as opposed to the
   scalar cap the current seam already handles) — e.g. a shared, congested evacuation corridor.
3. The user authorizes the `OpenDSSDirect.py` dependency for an explicit modelling need.

## Consequences

- No code change to the curtailment path; the energy-balance seam and every committed-scenario
  KPI are unchanged (KPI-neutral by construction — this half of #621 adds only this document).
- No new runtime dependency; `pip-audit` surface and wheel metadata are unchanged.
- The deferral is now a documented, gated decision with explicit re-open triggers, keeping a
  future power-flow build dolphin-sized rather than an undocumented gap that resurfaces as a
  whale.

Related: [`HYDRA_MAINTENANCE_DECISION.md`](HYDRA_MAINTENANCE_DECISION.md) /
[`CURRENCY_NUMERAIRE_DECISION.md`](CURRENCY_NUMERAIRE_DECISION.md) (the ADR pattern this
follows); `analytics/portfolio/poi_curtailment.py` and
`analytics.contracts_v14.SharedPoiCurtailmentResult` (the preserved seam); GWTF rows ARCH-01
(config-first), CESSPIT (no silent defaults / unvalidated assumptions).
