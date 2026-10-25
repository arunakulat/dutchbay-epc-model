- **The reproducibility lock closes again after the `joblib 1.6.0` bump** — `requirements.txt`
  now pins `cloudpickle==3.1.2`. `joblib 1.5.3` vendored its own copy of cloudpickle; `1.6.0`,
  merged in #1359, declares `cloudpickle>=3.0` as an unconditional requirement instead, so the
  lock resolved to 313 distributions while declaring 311, and the extra one installed at
  whatever version the index served that day. With the pin, the resolver's install set is one
  larger than the declared set rather than two, the only unpinned entry being `pip` itself,
  which is the control `main` showed before #1359. cloudpickle declares no requirements of its
  own, so nothing further enters the graph. The `Security Scan` gate was not blind to it:
  `make security` runs `pip-audit -r requirements.txt` with no `--no-deps`, which resolves the
  file and audits the transitive set as well — measured on `e6194e90`, that set is 310 packages
  and includes cloudpickle 3.1.2. What the pin restores is reproducibility, not audit coverage.
  Raised as condition C-1 on #1359's review and discharged here rather than by holding that
  bump.
