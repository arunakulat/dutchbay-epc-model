# Currency numéraire — decision record (LKR-primary by design)

**Status:** Decided / closed. Supersedes the long-standing "currency de-lock (item D)"
deferral. **Date:** 2026-06-21.

## Context

Several field names bake a currency into their identifier — most visibly
`tariff_lkr_per_kwh` and `exchange_rate_lkr_usd` in the secondary `wind_resource`
energy path (`energy_calculator.py`, `cashflow_adapter.py`, `wind_pipeline.py`), plus
LKR revenue defaults in `wind_resource/config/era5_config.yaml`. A recurring backlog
item ("de-lock D") asked whether to make the model currency-agnostic via a full
numéraire flip.

## Decision

**The model is LKR-primary by design, and the currency-suffixed field names are a
deliberate _soft_ lock — not a defect to be flipped.**

Rationale:

1. **The model is structurally LKR-primary.** Revenue is earned in LKR (LKR tariff →
   revenue → CFADS → tax). USD figures are a *post-hoc FX division* for reporting, not a
   parallel numéraire. `ppa.primary_currency` is informational only (no Python reads it
   to branch behaviour); it is pinned to `"LKR"` and guarded by
   `tests/finance/test_currency_lkr_primary.py`.

2. **Multi-currency projects are already supported without renaming.** A USD-bid project
   carries its native `tariff.usd_per_*`, which the resolver converts to LKR via
   `fx.start_lkr_per_usd`. The Mannar / Mullikulam scenario is the worked example: a
   3.96 USc/kWh WindForce bid is carried as `tariff.lkr_per_kwh: 13.22` at FX 333.79.
   Nothing about the LKR-suffixed names blocks a non-LKR project from being modelled.

3. **A full numéraire flip is high-cost / low-value.** Making the engine numéraire-agnostic
   would touch ~6 modules plus the debt and tax engines, for no change in any computed
   KPI — the FX mechanics already handle the cross-currency exposure (USD debt + USD
   capex/O&M against LKR revenue), which is the economically material part.

## Migration path (if ever required)

Do **not** rewrite call sites en masse. Follow the Dolphin SHIM pattern:

1. Add pydantic field **aliases** so the contracts accept a currency-agnostic name
   (e.g. `tariff_per_kwh`) alongside the existing `tariff_lkr_per_kwh`, with the old
   name `deprecated=True`.
2. Migrate producers/consumers one file per atomic commit (`Dolphin Strategy N/M`).
3. Drop the deprecated aliases after the standard 2–3 sprint sunset.

Until a concrete non-LKR-primary requirement appears, this is **not pursued**; the soft
lock stands as documented above.

## Enforcement

- `tests/finance/test_currency_lkr_primary.py` pins `primary_currency == "LKR"` and the
  LKR-primary revenue structure.
- The FX layer (`analytics/fx/fx_fetch.py`, config `fx_reference`) is the single source
  of the LKR/USD rate; `tests/lint/test_no_magic_fx.py` blocks hardcoded FX literals.
