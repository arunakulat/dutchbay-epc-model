- **Single source of truth for the canonical lender-case KPI vector (#955, Increment A)** — the eight
  canonical `dutchbay_lendercase_2025Q4` economics (`project_irr`, `equity_irr`, `project_npv`,
  `min_dscr`, `min_dscr_period`, `total_cfads_usd`, `project_npv_prudential`, `prudential_rate_used`)
  were echoed as bare literals across a dozen unit tests under five naming conventions, so a
  re-baseline had to hand-edit every copy or the echoes silently diverged from the oracle. The
  full-precision values now live once in `tests/_canon.py`; the oracle
  (`test_multitech_generation.py::test_canonical_lendercase_economics_unchanged`) and the
  full-precision consumers import the named constants (aliasing to their existing local names), so a
  re-baseline updates one file. Byte-identical and KPI-neutral: every migrated literal is replaced by
  a named constant equal to it — no asserted value changes, and the canonical oracle passes unchanged.
  Only exact full-precision literals were migrated; rounded pins (`0.014552`, `-79273039.21`, `1.30`)
  and canonical-shaped mock/stub payloads (e.g. `test_surface_contract.py`'s canned result, whose
  `project_npv` is deliberately not the canon) are deliberately left for the optional semantic
  Increment B. This is the unit-test byte-vector single source of truth; it is kept intentionally
  separate from the D3/D3b scenario-oracle JSON fixtures (`tests/fixtures/finance/*_expected_kpis.json`,
  #996), which pin whole-scenario `expected_results`. `finance/` and `analytics/` untouched. Ref #955.
