- **Lender report waterfall states its CFADS basis and reconciles to the DSCR covenant**. The
  "Cash-Flow Waterfall by Payment Priority" netted debt service against the project-basis
  (unlevered-tax) CFADS, and it said that figure was the DSCR numerator. So in the years after
  the tax losses run out, it showed coverage under 1x and negative cash to equity beside a DSCR
  profile that met the covenant.
  - The section now says its CFADS is the project basis, and that cash to equity is the
    project-basis residual, not the sponsors' distributions.
  - Its basis note states the run's own figures: the years where project-basis CFADS falls
    short of debt service, the covenant DSCR in those years, and any year below 1.00x. It
    never asserts the covenant is met.
  - When the run publishes the coverage CFADS, the section adds a "Reconciliation to the DSCR
    covenant" table, with these columns:
    - project-basis CFADS;
    - the senior fee as the project basis carries it, deducted inside EBITDA and so after the
      risk haircut;
    - the tax-basis difference, which is zero in a year with no tax;
    - coverage CFADS;
    - the senior fee;
    - covenant CFADS;
    - the covenant debt service, which includes the bridge period in year 1 under every
      bridge treatment;
    - the covenant DSCR, which equals the engine's annual `dscr_by_year`.
  - It also drops the claim that the model sweeps 100% of cash to equity with no reserve
    build-up.

  Report only: no KPI moves (#1897, #924 study O-2).
