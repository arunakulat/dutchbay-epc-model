- Blue Whale stack audit cleanup: resolve cross-platform GeoJSON precision matching, provenance, CLI hygiene, and documentation drift.
  - `scripts/run_blue_whale_wind_siting_v14.py` and `tests/wind/test_blue_whale_wind_siting.py`: compare committed and generated site GeoJSON trees with `abs_tol=1e-9` via `_json_matches` so cross-platform BLAS/SVD float differences ($2.38 \times 10^{-12}$ in `west_edge_bearing_deg` on macOS Apple Silicon) do not break `site_geojson_matches_committed`, while rejecting any $\ge 10^{-9}$ coordinate or property drift.
  - `scripts/run_blue_whale_capex_solar_resource_v14.py`: set `@hydra.main(version_base="1.3")`,
    disable logging pollution on stdout, replace bare `assert isinstance` with explicit `TypeError`,
    and attach `model_version`, `schema`, `config`, and `scenario` metadata to output JSON summaries (`MRM-02`, `CLI-01`, `CLI-03`).
  - `docs/blue_whale/capex_blend_summary.json` and `docs/blue_whale/solar_resource_summary.json`:
    update with required `MRM-02` schema and model version metadata (`15.18.0`), verified in `tests/solar/test_blue_whale_site_inputs.py`.
  - `docs/blue_whale/met_mast_transfer_summary.json` and `docs/blue_whale/met_mast_wind_rose_130m.csv`:
    refresh stale `model_version` (`15.16.0` -> `15.18.0`) so `tests/wind/test_met_mast_transfer.py::test_rerun_reproduces_the_committed_summary` passes when re-run against the private mast, NASA POWER, and confidential curve inputs.
  - `analytics/gis/pv_array_layout.py` and `solar_resource/pv_bess_dispatch.py`: replace runtime `assert`
    statements with explicit exceptions (`ValueError`).
  - `docs/blue_whale/INPUTS_REQUIRED.md`: update stale hybrid tariff blend figure in item F03 to `24.97218`.
  - `tests/finance/test_blue_whale_scenario_kpis.py`: update docstring regression pin reference to `(v0.8, model 15.18.0)`.
  - `solar_resource/pv_bess_dispatch.py`: update docstring to reflect that `#1472` (`analytics.storage_dispatch`) is on `main`.
  - `docs/blue_whale/STATUS.md`: add historical reference banners to PR 3 and PR 4 sections clarifying they are intermediate design iterations superseded by PR 5–PR 7.
