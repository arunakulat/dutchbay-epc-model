# `solar_resource` — pvlib solar AEP producer (optional `[solar]` extra)

The photovoltaic analogue of `wind_resource`: a standalone, config-driven producer that
turns a fixed-tilt PV-system spec + a measured site irradiance level into a **bankable
annual energy / capacity factor**, which can **VALIDATE** (never silently overwrite) the
config-declared P50 a hybrid `generation.technologies.solar` block carries.

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

## The model (reproducible, no network / no TMY files)

`compute_solar_aep(config)` runs a standard pvlib pipeline, all driven by config:

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
block; the pvlib producer reproduces its declared 0.20 P50 within ~11% (modelled ≈ 0.18 CF,
specific yield ≈ 1565 kWh/kWp — realistic for Puttalam utility-scale fixed-tilt PV).
