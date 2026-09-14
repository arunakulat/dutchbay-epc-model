- Make `tests/lint/test_extra_pin_consistency.py` say why it cannot run, instead of dying with a
  bare `KeyError`. Its extras-driven control is parametrized from `[project.optional-dependencies]`
  at *collection* time, so a pyproject missing that section did not fail one control -- it raised
  `KeyError: 'optional-dependencies'` as a collection error that took all twenty-one controls with
  it, naming neither the file it read nor what it expected to find there. A missing `[project]`
  table behaved the same way. Both now raise an `AssertionError` naming the path, the absent key and
  the consequence.
- Close the quieter half of the same hole: a section that exists but declares nothing. That
  parametrizes zero cases, which pytest reports as "got empty parameter set" and scores as a SKIP,
  so the control went *green-adjacent* rather than red -- the exact silent-pass failure mode the
  rest of this file exists to catch. It is now refused explicitly.
- Give `test_every_dbpl_package_is_locked_and_within_its_declared_pin` the same treatment: a
  pyproject without a `[report]` extra raised `KeyError: 'report'` mid-body rather than saying that
  DBPL-01's stack is declared nowhere.
- Exercise all three refusals. The parsing was split from the file read (`_extras_from`) so the
  failure paths can be driven with synthetic TOML, because a guard whose failure path is never run
  is a guard nobody has seen work; a fourth control asserts the live `pyproject.toml` still passes
  the same gate, so the refusals cannot pass by rejecting everything. Twenty-one controls become
  twenty-five. No production code is touched and no existing control changed behaviour.
