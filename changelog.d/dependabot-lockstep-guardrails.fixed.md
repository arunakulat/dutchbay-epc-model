- Dependabot: fully freeze `pydantic-core`, `mypy`, and `pandapower` against standalone
  bot version bumps (#978 post-mortem). `pydantic-core` is exact-pinned by `pydantic`, so
  an independent `pydantic_core==2.47.0` bump against `pydantic==2.13.4` made the lock
  un-installable (`ResolutionImpossible`); a `mypy` patch bump desynced the lock from the
  hardcoded `test-suite.yml` workflow pin; and `pandapower` minors/patches cap `scipy<1.17`,
  which would break the canon-critical `scipy==1.17.1`. Each now moves only via a deliberate,
  gate-verified dolphin. Mirrors the antlr4 lockstep pin (#977).
