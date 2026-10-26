- **Dependabot stops proposing the unmergeable `mpmath` bump** — its `.github/dependabot.yml`
  ignore rule now blocks minor bumps as well as majors. `sympy 1.14.0` requires
  `mpmath<1.4,>=1.1.0`, and `1.3.0` to `1.4.1` reads as semver-minor. Nothing filtered the
  proposal, because before this change `mpmath` carried no ignore entry at all -- not a
  major-only one -- so Dependabot's unconstrained default proposed it: the numerics group
  carried it in #1325 next to the `numpy-typing-compat` bump, and the group died at the install
  step with 0 tests run. #1325's logs name only the `numpy-typing-compat` conflict, which is the
  one `pip` reported before it stopped; that the `mpmath` bump is unmergeable follows from
  `sympy`'s published cap, not from those logs.
  Patch bumps within `1.3.x` stay welcome. Lift in lockstep with a `sympy` release that
  raises the ceiling.
