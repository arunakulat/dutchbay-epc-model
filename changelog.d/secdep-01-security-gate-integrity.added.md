- **`SECDEP-01` gate integrity — the security gate cannot be neutered from inside the
  repository.** Closes the limit the declaration half stated: that the rule bound what is
  suppressed but not that the gate runs. The governed recipes are now exact — `audit` is
  canonical resolve-mode `pip-audit` and nothing else, `security` is exact Bandit followed by
  the resolve-mode and declared-pin passes — and the live `make -n` oracles compare each
  target's complete emitted command sequence, preambles and extra commands included, against
  that canonical sequence rather than filtering for lines that look like an audit. `.ONESHELL`,
  `SHELL` and `.SHELLFLAGS` overrides are rejected, as is any state that discards a governed
  exit status: `.IGNORE` with or without targets, a `MAKEFLAGS`/`MFLAGS` assignment, or a `-`
  recipe prefix. Those leave every command, argument and dry-run byte unchanged, so no other
  control can see them. Runtime sentinels prove the Bandit invocation and both `pip-audit`
  invocations reach the expected binaries with exact arguments, and — the core control here —
  the same sentinels forced to fail prove each of the three invocations failing in turn makes
  the target exit nonzero. A guard that can only succeed cannot tell a gate that passed from a
  gate whose failure was discarded, which is how the five earlier escapes went unseen. Each
  hostile form is executed before it is rejected, so the bypass is observed rather than
  assumed. Stated limit: this binds the committed file under a clean invocation, which is all a
  Makefile can promise about itself; a caller's `make -i` and a command-line
  `PIP_AUDIT_IGNORES` override both win over any in-file guard, and closing that class means
  pinning the invocation on the CI surface. No runtime, financial formula, scenario or KPI
  change.
