- **Hybrid BESS dispatch pilot charter, on assumed terms (#1816, roadmap P1.4).** New
  `docs/HYBRID_BESS_DISPATCH_PILOT_CHARTER.md` scopes the pilot the owner chose to scope on
  2026-11-21: it reuses the #1402 chronological input contract and SOC/POC ledger, states how the
  pilot relates to `chronological_dispatch`, `solar_resource/pv_bess_dispatch.py` and the
  `energy_tariff` model in `finance/bess_revenue.py`, adds six pilot invariants, labels every
  contract and revenue term (including currency, indexation, tenor and any grid-charging price)
  as an assumption with no source, and specifies an optimisation oracle and a finance oracle
  that both land before the code they check. Results stay screening-only and default off; every
  implementation slice is a separate R3 slice with the owner's sign-off. #1816's
  evidenced-arrangement done-when stays open. Documentation only; no KPI changes.
