- Split the debt engine's code out of `finance/debt_v14.py` into the `finance.debt`
  package (14 modules) without changing it. `scripts/refactor/split_debt_v14.py` copies
  every top-level statement verbatim, with its docstring and the comments above it, and
  `--check` regenerates the package from the source commit to prove the committed files
  match. `finance.debt_v14` stays the public surface and re-exports every name it defined,
  so no import changes. The one exception is `_warned_decorative_tranches`, a flag that a
  function rebinds: it is read from `finance.debt.terms`, and the two tests that reset it
  now do so there. No computed value moves. Every committed scenario that runs gives the
  same output at every key before and after, and VERSION is unchanged.
