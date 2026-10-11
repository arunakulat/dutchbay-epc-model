- **Dependabot stops proposing the unmergeable `mpmath` bump** — its `.github/dependabot.yml`
  ignore rule now blocks minor bumps as well as majors. `sympy 1.14.0` requires
  `mpmath<1.4,>=1.1.0`, and `1.3.0` to `1.4.1` reads as semver-minor, so the major-only
  default let it through: the numerics group proposed it in #1325 next to the
  `numpy-typing-compat` bump and both died together at the install step with 0 tests run.
  Patch bumps within `1.3.x` stay welcome. Lift in lockstep with a `sympy` release that
  raises the ceiling.
