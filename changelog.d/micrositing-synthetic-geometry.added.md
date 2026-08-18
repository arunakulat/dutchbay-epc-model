- **Micro-siting runs again — on an explicitly SYNTHETIC derived geometry** —
  `feasibility_reproduce/run_all.sh` step 2 could only skip, because
  `optimize_layout()` needs a site boundary polygon and baseline turbine coordinates and
  neither was ever committed (the pinned `cache/expected/layout_optimized.json` came from
  geometry that never entered the repo). `cache/micrositing_synthetic_site.yaml` now
  declares a geometry DERIVED from committed scenario parameters — array centroid
  (`era5.latitude/longitude`), turbine count, `layout.turbine_spacing_avg_m` and
  `layout_orientation` — projected into the declared UTM zone (44N → EPSG:32644) by
  `lib/synthetic_site.py`. The turbine itself is built from the **committed** OEM power
  curve (`wind_resource/config/power_curves.yaml`), so real turbine physics drives a
  fabricated layout rather than invented numbers on both sides.
- **The boundary radius is a reasoned choice, not a default** — 15 turbines at 650 m span
  9,100 m, so a 2 km radius (4 km chord) fits only ~7 of them and 5 km leaves just 900 m of
  headroom. 6 km is committed; the builder REFUSES any radius that cannot contain the array
  and names the shortfall.
- **Provenance is enforced, not merely documented** — `build_synthetic_site()` rejects any
  config whose `provenance` is not `synthetic_derived`, so a real site block can never be
  laundered through the synthetic builder. The emitted artefact is
  `layout_optimized_synthetic.json` carrying `provenance`, `not_site_representative`, the
  site-config and scenario paths and the EPSG (MRM-02) — and it deliberately does NOT
  overwrite the committed `cache/expected/layout_optimized.json`. The uplift quantifies the
  OPTIMISER WIRING, never DutchBay's siting headroom.
- **Non-convergence is surfaced, not swallowed (FIN-01)** — SLSQP reports its exit status
  only on stdout and `LayoutOptimizationResult` carries no status field, so the runner
  captures it: at the committed 200-iteration cap the run hits the limit, and both the
  console line (`WARN` + an explicit note) and the artefact (`"converged": false`) say so.
  The reported uplift is the best point reached, never presented as an optimum.
- Derivation is covered by `tests/wind/test_synthetic_site_geometry.py` (22 tests): UTM
  projection, spacing/turbine-count fidelity, the 3.0 D → 594 m cross-check against the
  committed layout, boundary containment, determinism (MRM-01), and every CESSPIT guard
  including the too-small-boundary and malformed-UTM-zone cases.
