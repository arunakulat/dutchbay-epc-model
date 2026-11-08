- **Five dependency bumps in one lock change** — `hybgensea` 0.1.1 → 0.2.0, `topfarm` 2.6.2 →
  2.7.1, `kiwisolver` 1.5.0 → 1.5.1, `tzdata` 2026.3 → 2026.6 and `rasterio` 1.5.1 → 1.5.2. They
  supersede Dependabot's #1543, #1544, #1545, #1546 and #1547, which all edit `requirements.txt`
  and so cannot ride one merge train as separate cars. None of the five is frozen or capped in
  `constraints.txt`, and the lock gains and loses no package. `make lock` from a clean venv
  reproduces exactly these five moves, so the `[solar]` pins for `pvlib` and `h5py` hold.
- **`topfarm` 2.7.1** widens its `openmdao` requirement from `==3.39.*` to `>=3.39,<3.45`. The lock
  keeps `openmdao` 3.39.0, so nothing else moves, but the `openmdao` ignore rule in
  `.github/dependabot.yml` now names a topfarm constraint that no longer holds. The rule still
  blocks the minor bumps, so it is left for a separate change.
- `hybgensea` reaches the lock only through `optiwindnet` (`>=0.1.1`), the cable-routing solver
  under `topfarm`; nothing here calls it directly. Its 0.2.0 changes are additive (warm-start
  solutions, an exposed feasible population) plus clearer error types.
- **`tzdata` 2026.6** leaves every zone this repository names byte-identical to 2026.3:
  `Asia/Colombo`, `Asia/Kathmandu`, `Australia/Lord_Howe`, `Etc/UTC`, `Europe/London` and
  `America/New_York`.
- `kiwisolver` arrives through matplotlib and `rasterio` 1.5.2 is a patch release of the
  `[gis]` extra; both stay within every dependent's range.
- **`rasterio` 1.5.2 raises its Apple-silicon wheel floor** from macOS 14 (`macosx_14_0_arm64`)
  to macOS 15 (`macosx_15_0_arm64`). On an arm64 Mac older than macOS 15, pip finds no wheel and
  falls back to building from source, which needs a local GDAL. Linux CI is unaffected.
