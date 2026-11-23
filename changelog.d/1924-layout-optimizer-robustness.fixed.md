- **Harden TopFarm layout optimizer (`wind_resource.layout_optimizer`)** —
  validate simple non-degenerate boundary/exclusion polygons and physical
  turbine curves, use boundary-aware smart-start candidate grids and
  spacing-respecting initial-position padding, route non-convex vs convex
  boundaries accurately, extract SLSQP driver iteration and convergence status,
  and verify post-optimization boundary, exclusion, and spacing constraints
  (#1924).
