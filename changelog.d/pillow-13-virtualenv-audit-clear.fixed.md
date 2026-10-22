- Raise `pillow` in the reproducibility lock from `12.3.0` to `13.0.0` and `streamlit` from
  `1.62.0` to `1.66.1`, and **remove all eight `--ignore-vuln` entries** from
  `PIP_AUDIT_IGNORES`. The eight advisories accepted in #1369 are now fixed rather than
  suppressed: `streamlit 1.66.1` (published 2026-10-21T17:02:55Z, twelve minutes after #1369
  merged) raises its cap from `pillow<13` to `pillow<14,>=9.2.0`, which was the only constraint
  holding `pillow` at `12.3.0`. PyPI reports no advisory against either target version. The two
  bumps move together because neither resolves without the other.
- Raise `virtualenv` from `21.7.13` to `21.14.12`, clearing five advisories published against
  the pinned version during 2026-10-21 (CVE-2026-113722, -113725, -113726, -113732 and -113776,
  shell-quoting defects in the generated `activate` scripts for bash, zsh and fish, fixed across
  `21.14.2` through `21.14.9`). Only `pre-commit` requires `virtualenv`, with no upper bound, so
  nothing caps it.
- The `pip-audit` leg of the `Security Scan` gate now reports `No known vulnerabilities found`
  with the allowlist **empty**, so the gate is clean on merit and not by exception. No abstract
  dependency changes: `pyproject.toml` constrains none of the three packages.
