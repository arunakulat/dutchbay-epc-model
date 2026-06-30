# `solar_resource` — pvlib solar AEP producer (optional `[solar]` extra)

The photovoltaic analogue of `wind_resource`: a standalone, config-driven producer that
turns a fixed-tilt PV-system spec + a measured site irradiance level into a **bankable
annual energy / capacity factor** for a hybrid's `generation.technologies.solar` block.

Two complementary surfaces consume that modelled CF, chosen per use:

- **VALIDATE** (`validate_declared_solar_cf`, in `pv_producer`) — cross-checks a
  config-declared P50 and flags drift; it **never mutates** the scenario. The declared P50
  stays the financed driver. This is the photovoltaic analogue of the ERA5 / ARCO wind
  VALIDATE guard.
- **OVERWRITE** (`solar_export_to_scenario_patch`, in `cashflow_adapter`) — makes the
  *modelled* CF the financed driver, patching the per-tech block and re-blending the
  project headline. This is the photovoltaic analogue of `wind_resource.cashflow_adapter`.

The two are deliberate opposites; the scenario's flow picks one. See the OVERWRITE bridge
section below.

## Why it's optional

The financed run bills solar revenue off the declared
`generation.technologies.solar.capacity_factor` (a P50 the engine consumes directly), so a
lender-grade run needs **no** solar toolchain. `pvlib` is therefore an opt-in extra —
imported lazily behind `_require_pvlib()` (CASPER fail-loud guard), exactly like `py-wake`
in `wind_resource` and WeasyPrint in `app.reports`. Install it only to produce/validate:

```bash
pip install -e '.[solar]'   # or: pip install pvlib
```

The solar tests are gated behind `pytest.importorskip('pvlib')`, so they skip when the
extra is absent (e.g. the default CI install).

## The model (reproducible; clear-sky by default, opt-in frozen TMY)

`compute_solar_aep(config)` runs a standard pvlib pipeline, all driven by config. By default
(no `tmy_path`) it is network-free and TMY-file-free — a clear-sky year scaled to the measured
annual GHI. When `resource.solar.tmy_path` points at a FROZEN hourly TMY (SOLAR-6/12, #529),
it instead uses the TMY's measured hourly GHI/DNI/DHI and its hourly ambient temp/wind for
Faiman cell temperature (steps 1-2 and the scalar-temp assumption are replaced); the frozen
TMY keeps the run reproducible and pvlib/network-free at finance time. Default pipeline:

1. **Clear-sky year** (pvlib Ineichen) for a fixed reference calendar.
2. **Scale to the measured annual GHI** (`annual_ghi_kwh_m2` — the single resource knob, a
   measurable site property; Puttalam ≈ 2000 kWh/m²/yr). The scale is the clear-sky index
   (~0.8 for a sunny tropical site).
3. **DISC decomposition** → DNI, closure → DHI.
4. **Hay-Davies transposition** → plane-of-array irradiance for the array geometry.
5. **Faiman cell temperature** → **PVWatts DC** → **PVWatts inverter** (clipped at the AC
   nameplate via `dc_ac_ratio`) → flat **system-loss** derate → annual AC energy.

Same config → same number (a fixed reference year; no `Date.now`).

**CF convention:** capacity factor is against the **DC nameplate** (MWp):
`annual_ac_energy / (dc_capacity_mw · 8760)` — the same basis the solar tech block uses.

## Usage

```python
from solar_resource import SolarResourceConfig, compute_solar_aep, validate_declared_solar_cf

cfg = SolarResourceConfig.from_scenario(scenario)   # reads resource.solar
result = compute_solar_aep(cfg)                      # AEP / CF / specific yield

# VALIDATE a declared P50 (warns on drift; never mutates the scenario)
v = validate_declared_solar_cf(cfg, declared_cf=0.20, tolerance_pct=15.0)
assert v.within_tolerance
```

`scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml` carries an example `resource.solar`
block with a frozen `tmy_path` (#529): on that PVGIS TMY the producer yields and the scenario
declares CF ≈ 0.1685, specific yield ≈ 1476 kWh/kWp — realistic for Kalpitiya utility-scale
fixed-tilt PV. (Without a TMY the clear-sky default on the same block yields ≈ 0.179 / 1568;
the #529 re-baseline lowered the financed P50 from 0.179 to 0.1685 on the real-GHI TMY.)

## The OVERWRITE bridge — `cashflow_adapter` (finance never imports pvlib)

When the *modelled* CF is chosen as the financed driver, `cashflow_adapter` patches it
into the scenario. It is a **pure function over plain dicts** and does **not** import
`pvlib`: the expensive physics run happens once, offline, and its result is frozen into a
small export dict (`build_solar_cashflow_export`) — exactly as `wind_resource.cashflow_adapter`
consumes a frozen `WindPipeline` export rather than re-running PyWake. The finance stack
therefore runs the hybrid case with no solar toolchain.

```python
from solar_resource import compute_solar_aep, SolarResourceConfig
from solar_resource.cashflow_adapter import (
    build_solar_cashflow_export, solar_export_to_scenario_patch,
)

# Offline (needs the [solar] extra): produce, then freeze.
cfg = SolarResourceConfig.from_scenario(scenario)
export = build_solar_cashflow_export(compute_solar_aep(cfg), dc_capacity_mw=cfg.dc_capacity_mw)

# In finance (pvlib-free): overwrite the per-tech CF + re-blend project.capacity_factor.
patched = solar_export_to_scenario_patch(export, scenario, adapter_mode="overwrite")
```

Modes mirror the wind adapter: `overwrite` (modelled CF wins), `fill_if_absent` (validate a
present value within tolerance, else write), `validate_only` (CI guard — never writes
economics). On overwrite/fill the project headline `project.capacity_factor` is re-blended
from the per-tech sum so the engine's ±1% reconciliation and `analytics.aep_reconciliation`
stay satisfied; storage techs are excluded exactly as the engine excludes them. The
independent bankable references (`expected_results`, `resource.aep_summary_path`) are **not**
touched — re-baselining those is a deliberate, audited scenario edit.
