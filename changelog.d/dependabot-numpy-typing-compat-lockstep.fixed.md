- **Dependabot: freeze `numpy-typing-compat` against major bumps (#986/#988 post-mortem)** —
  `optype[numpy] 0.17.1` requires `numpy-typing-compat<20251207,>=20250818.1.25`, so the weekly
  group's `numpy-typing-compat 20251206→20260602` bump produced an un-installable lock
  (`ResolutionImpossible`: `numpy-typing-compat==20260602.2.4` vs `optype[numpy]`'s `<20251207`)
  — #986 and #988 closed un-installable. `numpy-typing-compat` now ignores semver-major
  (YYYYMMDD-datestamp) bumps and lifts only in lockstep with an `optype[numpy]` release that
  raises the ceiling. The #987 `pyarrow` guardrail held (pyarrow stayed at 24); this extends the
  grouped-bump lockstep set (#977/#978/#980/#987).
