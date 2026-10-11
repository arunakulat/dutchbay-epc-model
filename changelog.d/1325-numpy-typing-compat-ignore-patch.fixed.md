- **Dependabot stops regenerating the unmergeable `numpy-typing-compat` bump** — its
  `.github/dependabot.yml` ignore rule now blocks minor and patch bumps as well as majors.
  The package carries its target numpy range in the patch segment (`20260602.2.4` requires
  `numpy<2.5`, `20260602.2.5` requires `numpy>=2.5rc1`), so with the datestamp unchanged the
  bump read as semver-patch and the major-only rule let it through three times
  (PRs #1249, #1301 and #1325). numpy is held at 2.4.6 by pandapower, so no bump of this
  package is resolvable until that ceiling lifts (issue #1169).
