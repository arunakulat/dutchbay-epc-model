- Enforce the existing lender/IC run-mode prohibition on toy Monte Carlo trial
  fallback, including an explicit `monte_carlo.allow_toy_fallback: true` override.
  Malformed mode declarations fail before trials. Screening, developer and
  undeclared modes retain their fallback setting; healthy seeded financial
  metrics are unchanged. This closes only the mode-ceiling slice of #962;
  undeclared production configs still need explicit fail-closed configuration,
  and the direct engine does not certify the lender-report sample floor.
