- Require explicit YAML `power_mw` and `duration_h` for BESS at v14 preflight and
  finance resolution. One immutable nameplate contract derives omitted
  `energy_mwh` and reconciles authored energy within the existing 1% tolerance;
  revenue, LCOS and future dispatch share that basis. Missing, null, non-finite,
  boolean or inconsistent ratings fail loudly. The hybrid's 50 MW input is
  explicitly illustrative. Committed scenario ratings and KPIs are unchanged;
  legacy power-only or energy-only diagnostic configs must author duration.
