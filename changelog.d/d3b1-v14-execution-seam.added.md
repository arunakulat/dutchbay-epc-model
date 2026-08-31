- **Dolphin 3B-1 governed v14 execution seam** — adds a held, preflighted transition from one exact
  `ProjectCase` and `EvaluationRequest` to exactly one call of the public
  `analytics.evaluation_v14.evaluate_with_overrides()` gateway. The seam binds authored source
  bytes, digests, jurisdiction and technology authority, cutoff and valuation facts, ProjectCase
  material values, exact numeric projections and result origins before handing D3C an owned,
  recursively immutable full-result snapshot. The production scenario-authority catalogue remains
  intentionally empty, so this change authorizes no committed production scenario.
- Adds the downstream D3C implementation acceptance ledger: D3C-0 assembly authority first, all
  twenty report sections in SSOT order, all six reconciliation families, every D2 register,
  explicit unperformed human roles, a partial-engine-manifest bridge, and static field/unit/precision
  mappings. D3C may consume one accepted result but may not rerun finance or recompute KPIs.
- This engineering seam changes no finance mathematics or canonical KPI baseline. `VERSION` remains
  `15.4.0`; achieved grade remains `ungraded`; package release and Board/lender circulation remain
  `HOLD`; issue `#1110` and all professional, lender, Board, release and deployment authorities are
  unchanged.
