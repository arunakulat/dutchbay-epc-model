- **`layout.turbine_spacing_avg_D` corrected across all 10 scenarios — stale rotor** — every
  scenario declared `3.8` "In rotor diameters (650m / 171m)", but the committed machine has
  `rotor_diameter_m: 198`, so 650 m is **3.28 D**, not 3.8. The comment carried a 171 m rotor
  from an earlier turbine model. Mullikulam (150 m rotor) was wrong in the other direction —
  650 m there is **4.33 D**. Each file is now derived from its own `rotor_diameter_m`, and the
  comment records that the field is doc-only. KPI-neutral and verified so: no code reads
  `turbine_spacing_avg_D` or `turbine_spacing_avg_m` (grep-confirmed across the tree), and the
  canon oracles are untouched. The value matters because anyone sizing a layout from the
  declared figure would space turbines ~16 % too far apart.
