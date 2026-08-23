- **`TEST-01` gains an independent-oracle clause** — a pin proves only that a number has not
  changed, never that it is still being *derived*, so a pinned-constant oracle must be paired
  with a responsiveness guard, and finance-material code must answer to an oracle that did
  not originate in the same change that introduced it (a pre-existing test, an external
  benchmark, a closed-form check, an independent implementation, or a property/invariant). A
  change whose only evidence is tests written alongside it is unverified, however green. The
  clause is echoed in `AGENTS.md` under "Financial-model changes" and both surfaces are
  pinned by `tests/lint/test_gwtf_canonical_source.py` so they cannot separate silently.
