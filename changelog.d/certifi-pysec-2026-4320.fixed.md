- Raise the `certifi` pin in the reproducibility lock from `2026.7.22` to `2026.10.19`, which
  fixes PYSEC-2026-4320 (GHSA-6q48-6c7w-9gw2) and clears it from the `pip-audit` leg of the
  `Security Scan` gate. No abstract dependency changes: `pyproject.toml` does not constrain
  `certifi`, and nothing else in the lock caps it.
- The eight advisories against `pillow==12.3.0` are **not** cleared by this change and the gate
  stays red on them. Their only fix version is `pillow 13.0.0`, and every `streamlit` release up
  to `1.66.0` requires `pillow<13`, with no `pillow` release between `12.3.0` and `13.0.0` to
  take instead, so no installable pillow clears them while streamlit is in the lock.
