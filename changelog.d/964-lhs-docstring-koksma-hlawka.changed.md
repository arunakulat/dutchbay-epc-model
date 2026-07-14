- **`build_lhs_plan` docstring — LHS/QMC conflation corrected (methodology
  provenance, #964 §6).** The sampler note called `scipy.stats.qmc.LatinHypercube`
  "formal LHS with Koksma-Hlawka error bounds". The Koksma-Hlawka inequality bounds
  *quasi*-Monte-Carlo error via a point set's star discrepancy — a rate that
  low-discrepancy QMC sequences (Sobol'/Halton) attain but a scrambled Latin
  Hypercube design does not generically reach; attributing it to LHS conflated the
  two. Reworded to credit LHS's real benefit — stratified variance reduction of the
  sample mean for additive/near-additive integrands (Stein 1987, *Technometrics*
  29(2):143-151) — and to note that Owen's scrambled-net variance results are a
  separate QMC construction. Docstring-only: `build_lhs_plan` has no
  pipeline/report/committed-scenario caller (only the on-demand
  `run_pareto_search(plan_kind="lhs")` tool), no test pins the wording, and the
  `LatinHypercube` sampler itself is unchanged. KPI-neutral; canon pins pass.
