# P50 haircut layering: builder-policy 5% vs kernel-identity 0% (ADR, #653 / #587 Fable follow-up)

Status: **Accepted** (2026-07). Decision: **the two config-consumption layers deliberately
disagree on the P50-haircut default, BY DESIGN.** The config/builder layer
(`analytics.wind.aep_summary_builder._uncertainty_from_config`) defaults a silent
`p50_haircut_pct` to the recommended `RECOMMENDED_P50_HAIRCUT_PCT` (5.0%); the exceedance
KERNEL (`wind_resource.bankable_aep.exceedance_levels`) keeps a `0.0` identity default and
NEVER embeds the policy in the math. This is option (b) of #653 — document the split as
intentional — NOT option (a) route both through one default. **No haircut value or default
changes anywhere; this ADR only records the ruling.**

## Context

#587 wired a recommended pre-construction P50 over-prediction haircut (5.0%) as a **policy
default at the config-consumption layer** so a no-EYA scenario is corrected for the
well-documented P50 optimism rather than assuming a naive 0%. The #587 Fable review then flagged
a divergence: the AEP-summary builder path applies the 5% default when a scenario is silent,
while the secondary `wind_resource` timeseries-diagnostic path
(`energy_calculator.calculate_net_aep`) calls the same `exceedance_levels` kernel with the
kernel's own `0.0` default. For a no-EYA scenario the two live consumers therefore report
different P50 bases. #653 asked for a ruling: (a) route the diagnostic call through the same
policy default so both layers agree, or (b) document that the kernel path is deliberately
un-haircut (raw modelled) and the builder path is the bankable one.

**User ruling: option (b) — the divergence is BY DESIGN.** The builder is a *policy* layer
(applies the bankability default at config consumption); the kernel is *identity/no-op in the
math* and must never become a policy layer. This ADR is the code-repo record of that ruling so
the split is a documented decision, not a silent inconsistency, and so the "pending #653"
in-code pins have an authoritative resolution to point at.

## Evidence (verified 2026-07 against branch point `03fdeda`, not asserted)

| fact | value |
|---|---|
| Builder policy default | `analytics/wind/aep_summary_builder.py::_uncertainty_from_config` — when `resource.uncertainty.p50_haircut_pct` is ABSENT, sets `haircut_pct = RECOMMENDED_P50_HAIRCUT_PCT` (5.0) and logs the silent-default (CESSPIT observability); an explicit config value overrides it |
| Recommended constant | `wind_resource/bankable_aep.py::RECOMMENDED_P50_HAIRCUT_PCT = 5.0` — a *policy* default applied only at config consumption, documented conservative (below the WES-2026 −6.6%/−7.4% central bias) for a project WITHOUT its own EYA (#587) |
| Kernel identity | `wind_resource/bankable_aep.py::exceedance_levels(..., p50_haircut_pct: float = 0.0, ...)` — `0.0` default = no-op (`p50_gwh * (1.0 - 0.0/100.0)`); the math applies whatever it is handed, never a policy |
| Diagnostic path pin | `wind_resource/energy_calculator.py::calculate_net_aep` calls `exceedance_levels(..., p50_haircut_pct=0.0, ...)` (kernel identity, hard-pinned); a scenario that DECLARES a haircut is surfaced via a log line but NOT applied on this path — it is consumed by the bankable builder path only |
| Shared, policy-free sigma parser | `wind_resource/bankable_aep.py::budget_from_mapping` resolves ONLY the seven IEC 61400-15-2 category sigmas; the policy knobs (`p50_haircut_pct`/`correlation`/`life_years`) are deliberately NOT resolved there, so both layers share ONE sigma parser that cannot drift (#618) while each keeps its own policy layer |
| Solar is intentionally 0.0 | `solar_resource/exceedance.py::solar_uncertainty_from_config` defaults the absent-knob haircut to `0.0`; `exceedance_levels_solar(..., p50_haircut_pct: float = 0.0, ...)` is likewise identity — the no-EYA `RECOMMENDED_P50_HAIRCUT_PCT` policy default is **wind-only by design** |
| Finance is unaffected | Finance consumes the pinned/frozen bankable AEP (the `aep_summary_builder` path), not the `energy_calculator` timeseries diagnostic; the split moves only a secondary reported P-value, never a committed KPI |
| Every committed scenario is explicit | All 8 committed configs set `resource.uncertainty.p50_haircut_pct` explicitly (DutchBay flagships `2.0`; Kalpitiya/Mullikulam `0.0`), so the 5.0% builder default is a fallback that NO committed scenario silently hits — nothing is quietly haircut |

## Decision

**Keep the two-layer split exactly as it stands.** Concretely:

1. **The builder/config layer owns POLICY.** `_uncertainty_from_config` is the correct place to
   apply a bankability default: it runs at config consumption, sees whether the scenario
   declared a haircut, and — only when silent — applies the recommended no-EYA 5.0% while
   logging that it did so (CESSPIT: a silent default is surfaced, never hidden). This is the
   "bankable" P50 basis that feeds the lender summary.

2. **The exceedance kernel stays 0.0-identity and NEVER embeds policy.** `exceedance_levels`
   (and its solar twin `exceedance_levels_solar`) are pure math: given a P50 and an uncertainty
   budget, produce P50/P75/P90. `p50_haircut_pct` is a *parameter* with a `0.0` identity default,
   not a place to bake in the recommended bias correction. Baking a 5% policy into the kernel
   would (a) make the math lie about what it computes, (b) double-apply the haircut whenever a
   caller already resolved policy at the config layer, and (c) silently move every raw-modelled
   diagnostic — a CESSPIT violation (policy masquerading as math). The kernel keeps the identity
   default so a caller that wants the raw modelled P50 gets exactly that.

3. **The `energy_calculator` timeseries path is deliberately un-haircut (raw modelled).** It is a
   secondary wind DIAGNOSTIC, not the bankable/financed surface; its P-levels disclose the raw
   modelled exceedance. It hard-pins `p50_haircut_pct=0.0` and, when a scenario declares a
   haircut, surfaces a log line stating the knob is consumed by the bankable builder path only —
   so the divergence is observable, not silent. The prior in-code "pending #653" pins on this
   path are resolved by this ADR (the kernel-identity pin is now the accepted design, not a
   placeholder awaiting a ruling).

4. **The no-EYA policy default is wind-only.** The solar exceedance layer intentionally defaults
   the absent-knob haircut to `0.0`; the WES-2026 pre-construction over-prediction evidence
   behind `RECOMMENDED_P50_HAIRCUT_PCT` is a wind-resource finding and is not transplanted onto
   the solar P50 without its own basis.

## Audit trail

- **#587** wired the builder-layer default (`RECOMMENDED_P50_HAIRCUT_PCT = 5.0`, applied in
  `_uncertainty_from_config` when a scenario is silent) and left the kernel at `0.0` identity.
  KPI-neutral at merge because every committed scenario already set its haircut explicitly.
- **#618** made `budget_from_mapping` the single, policy-free sigma parser shared by both
  consumers, so the two layers cannot drift on sigma key names/defaults — the *only* thing that
  differs between them is the policy layer this ADR governs.
- **#654** codified the flagship 2.0% calibration note (`docs/AEP_PROVENANCE.md`): the EN220 EYA
  corroboration bounds model-vs-EYA drift, not EYA-vs-operations bias, and any move of the
  flagship 2.0% toward the WES-2026 range is KPI-moving and separately user-authorized.
- **#653 (this ADR)** rules the builder-5% / kernel-0% split intentional (option b) and resolves
  the "pending #653" in-code pins.

## Consequences

- **No code change to any haircut value or default** — this ADR records the keep-the-split
  decision (docs-only, KPI-neutral by construction; every committed-scenario KPI is byte-identical
  because nothing in the math or the configs moves).
- The "pending #653" language in `wind_resource/energy_calculator.py` and the open-question notes
  in `wind_resource/bankable_aep.py::budget_from_mapping` / `aep_summary_builder` now have an
  authoritative resolution; those in-code comments may be tightened from "open question #653" to
  "resolved per `docs/P50_HAIRCUT_LAYERING_DECISION.md`" on the next natural touch of those files
  (not done here — a docs-only dolphin does not edit `.py` files).
- The split stays observable, not silent: the builder logs when it applies the 5% default, and
  the diagnostic path logs when it declines a declared haircut, so a lender reviewing either
  surface can see exactly which P50 basis it is looking at.

## Re-evaluation triggers

Revisit this ADR (open an issue, do not silently change a default) when **any** of:

1. A committed scenario is intentionally left SILENT on `p50_haircut_pct` and relies on the 5.0%
   builder default (today none do) — the fallback would then move a reported number and warrants
   re-confirming the 5.0% figure and its wind-only scope.
2. New operational-vs-predicted evidence materially shifts the recommended no-EYA haircut away
   from 5.0%, or establishes a solar analogue (which would end the wind-only carve-out).
3. Finance is ever re-wired to consume the `energy_calculator` timeseries diagnostic instead of
   the frozen bankable AEP — at which point the diagnostic path's kernel-identity choice would
   become KPI-bearing and must be reconsidered.

Related: [`AEP_PROVENANCE.md`](AEP_PROVENANCE.md) (the flagship 2.0% calibration note, #654) ·
[`WIND_AEP_CHAIN_OF_CUSTODY.md`](WIND_AEP_CHAIN_OF_CUSTODY.md) (the bankable-vs-diagnostic AEP
paths) · [`MONEY_PRECISION_DECISION.md`](MONEY_PRECISION_DECISION.md) /
[`OPENDSS_CURTAILMENT_DECISION.md`](OPENDSS_CURTAILMENT_DECISION.md) (the ADR pattern this
follows); `wind_resource/bankable_aep.py` (`RECOMMENDED_P50_HAIRCUT_PCT`, `exceedance_levels`,
`budget_from_mapping`), `analytics/wind/aep_summary_builder.py` (`_uncertainty_from_config`),
`wind_resource/energy_calculator.py` (`calculate_net_aep`), `solar_resource/exceedance.py`
(the wind-only carve-out); GWTF rows ARCH-01 (config-first policy), CESSPIT (no silent
defaults / no policy embedded in the math), CCCDIR (contracts centralised, one sigma parser).
