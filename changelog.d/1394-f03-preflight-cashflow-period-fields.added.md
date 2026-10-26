- **`F-03` — the v14 pre-flight gate refuses an unsupported `cashflow.resolution` or
  `cashflow.within_year_profile`.** Both A3 period fields are now registered in the v14 field
  specs, so the schema surface lists them, and `validate_config_for_v14` refuses a bad value
  before evaluation begins, naming the config path and the accepted values
  (`FRAMEWORK-02`). The rules are not restated anywhere: the gate delegates verbatim to the
  resolvers that own them — `finance.period_grid_v14.resolve_period_grid`,
  `require_engine_support` and `finance.subannual_rows_v14.resolve_within_year_profile` — the
  `_validate_run_mode` / `_validate_taxes_indirect` pattern, so pre-flight and call time
  cannot drift. The resolvers were already strict; what was missing was anything consulting
  them before a run, which is why a typo'd resolution reached evaluation before it was
  refused. The grid is resolved first so the profile can be measured against it, which
  catches the cross-field mistake most likely to reach a real config: a four-weight profile
  with no declared resolution is now refused rather than quietly ignored under the default
  annual grid -- recorded under Changed, since that is where an operator holding such a file
  will look. An unusable grid suppresses the profile error, so one mistake yields one
  message instead of a second, misleading one about length. The registered specs deliberately
  carry no validator — a flat predicate can express neither field, since the accepted
  resolution set lives in the resolver and a profile's required length depends on the sibling
  key, and a partial copy would be a second authority to drift from — and a control fails if
  one is added. Both fields stay opt-in: with neither declared the config resolves to the
  annual grid and an even split, which is what every committed scenario does, so no committed
  behaviour moves. Evidenced by a KPI oracle over 14 Dutch Bay scenarios and 393 float KPIs
  compared as `float.hex()`, identical before and after. The engine-support half is proved
  with a synthetic describable-but-unbuildable resolution, because
  `SUPPORTED_RESOLUTIONS` and `ENGINE_SUPPORTED_RESOLUTIONS` are the same set today and no
  real value can exercise it. No financial formula, scenario, model input or KPI change; the
  `F-5` bar and #1110's `HOLD` are untouched.
