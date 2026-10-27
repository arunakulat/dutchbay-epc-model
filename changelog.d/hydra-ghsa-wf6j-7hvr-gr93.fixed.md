- **`hydra-core` 1.3.7 → 1.3.8, clearing GHSA-wf6j-7hvr-gr93 (#1460).** The new advisory
  (affected 1.3.6–1.3.7 and the 1.4.0.dev9, dev10, rc1 and rc2 prereleases) made the required
  Security Scan (`pip-audit` over `requirements.txt`) fail on every pull request. The lock line,
  the `pyproject.toml` security floor set by #1339 and its guard test now all reject every
  affected version. 1.3.8 keeps `omegaconf<2.4,>=2.2` and `antlr4-python3-runtime==4.9.*`, so
  no other lock line moves, and this repository does not call `hydra.utils.instantiate()`.
